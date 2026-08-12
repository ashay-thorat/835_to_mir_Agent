"""Agent supervisor: intent handling, tool selection and task orchestration.

The LLM only decides *what* to do.  Every data operation, path dialog and file
write is executed deterministically here, so the agent can never invent claim
data or fabricate a saved file.
"""
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import config
from agent.ollama import OllamaClient
from agent.prompts import PATH_QUESTION, system_prompt
from agent.state import SessionState
from tools.claim_details import format_claim_detail, format_claim_list
import re
from tools.conversion import generate_mir_texts, convert_835_to_mir_file
from tools.file_manager import ensure_directory, resolve_save_paths, write_text_verified
from tools.search_claims import filter_claims, search_claims
from tools.validation import validate_output_path

EXIT_WORDS = {"exit", "quit", "bye", "goodbye", "/exit"}

_TOOL_COERCERS = {
    "positions": lambda v: _as_int_list(v),
    "claim_numbers": lambda v: [str(x) for x in (v if isinstance(v, list) else [v])],
    "min_amount": lambda v: _as_decimal(v),
    "max_amount": lambda v: _as_decimal(v),
    "status": lambda v: str(v),
    "query": lambda v: str(v),
    "all_selected": lambda v: bool(v),
    "all_claims": lambda v: bool(v),
    "separate": lambda v: bool(v),
    "claim_number": lambda v: str(v),
    "position": lambda v: int(v),
}


class Supervisor:
    def __init__(
        self,
        state: SessionState,
        client: OllamaClient,
        input_func: Callable[[str], str] = input,
        print_func: Callable[[str], None] = print,
        default_output_dir: Optional[Path] = None,
        on_files_generated: Optional[Callable[[str, Path], None]] = None,
    ):
        self.state = state
        self.client = client
        self._input = input_func
        self._print = print_func
        self._default_output_dir = Path(default_output_dir) if default_output_dir else None
        self._on_files_generated = on_files_generated
        self._tools = self._build_tools()

    # ------------------------------------------------------------------ entry
    def run_turn(self, user_input: str) -> List[Dict[str, str]]:
        text = (user_input or "").strip()
        if not text:
            return [{"kind": "note", "text": "Type a message or /help for options."}]
        if text.lower() in EXIT_WORDS:
            return [
                {"kind": "assistant", "text": "Goodbye! Your generated files have been preserved."},
                {"kind": "exit", "text": ""},
            ]
        command_events = self._handle_command(text)
        if command_events is not None:
            return command_events

        if _is_full_conversion_intent(text):
            return self._handle_full_conversion()

        self.state.record("user", text)
        try:
            decision = self.client.decide(self._system_prompt(), self.state.history)
        except RuntimeError as exc:
            return [{"kind": "error", "text": f"Lost connection to Ollama: {exc}"}]
        if decision is None:
            return [{"kind": "error", "text": "I couldn't understand that. Please rephrase."}]

        if decision.get("type") == "chat":
            reply = (decision.get("reply") or "").strip() or "Done."
            self.state.record("assistant", reply)
            return [{"kind": "assistant", "text": reply}]

        steps = self._normalize_steps(decision)
        if not steps:
            return [{"kind": "error", "text": "I couldn't understand that. Please rephrase."}]
        steps = steps[: config.MAX_AGENT_ITERATIONS]

        events: List[Dict[str, str]] = []
        pending_blocks: List[Dict[str, str]] = []
        data_results: List[Dict[str, Any]] = []
        for tool, args in steps:
            if tool not in self._tools:
                events.append({
                    "kind": "error",
                    "text": "I'm not sure how to do that yet. I can count, search, "
                            "filter, show and convert claims, or generate MIR files.",
                })
                break
            coerced = self._coerce_args(tool, args)
            if coerced is None:
                events.append({
                    "kind": "error",
                    "text": "I had trouble understanding that request. Please rephrase it, "
                            "for example 'Find claims above 100' or 'Generate MIR for the "
                            "selected claims'.",
                })
                break
            result = self._execute(tool, coerced)
            if result["kind"] == "terminal":
                events.extend(pending_blocks)
                for event in result["events"]:
                    if event["kind"] == "report":
                        self.state.record("assistant", event["text"])
                events.extend(result["events"])
                return events
            data_results.append(result)
            if result.get("block"):
                pending_blocks.append({"kind": "block", "text": result["block"]})

        if data_results:
            parts = []
            for result in data_results:
                leadin = result.get("leadin", "")
                if leadin:
                    events.append({"kind": "assistant", "text": leadin})
                    parts.append(leadin)
                if result.get("block"):
                    events.append({"kind": "block", "text": result["block"]})
                    parts.append(result["block"])
            if parts:
                self.state.record("assistant", "\n\n".join(parts))
        return events

    def _normalize_steps(self, decision: Dict[str, Any]) -> Optional[List[tuple]]:
        raw_steps = decision.get("steps")
        if isinstance(raw_steps, list):
            steps = []
            for step in raw_steps:
                if isinstance(step, dict) and step.get("tool"):
                    args = step.get("args") if isinstance(step.get("args"), dict) else {}
                    steps.append((step["tool"], args))
            return steps or None
        tool = decision.get("tool")
        if tool:
            args = decision.get("args") if isinstance(decision.get("args"), dict) else {}
            return [(tool, args)]
        return None

    # ------------------------------------------------------------- commands
    def _handle_command(self, text: str) -> Optional[List[Dict[str, str]]]:
        command = text.lower()
        if command == "/status":
            return [{"kind": "block", "text": self._status_text()}]
        if command == "/file":
            return [{"kind": "block", "text": self._file_text()}]
        if command == "/clear":
            self.state.clear_conversation()
            return [{"kind": "note", "text": "Conversation context cleared. The 835 file remains loaded."}]
        if command == "/help":
            return [{"kind": "block", "text": self._help_text()}]
        return None

    def _handle_full_conversion(self) -> List[Dict[str, str]]:
        if not self.state.file_path:
            return [{"kind": "error", "text": "Please upload an 835 file first. Once it is uploaded, I can convert the complete file into one MIR file."}]

        output_dir = self._require_output_path()
        if output_dir is None:
            return [{"kind": "note", "text": "Cancelled. No files were written."}]

        # Construct output path
        file_stem = Path(self.state.file_path).stem
        safe_stem = "".join(ch for ch in file_stem if ch.isalnum() or ch in "._-") or "converted"
        output_name = f"{safe_stem}_All{config.DEFAULT_MIR_EXTENSION}"
        output_path = output_dir / output_name

        result = convert_835_to_mir_file(self.state.file_path, output_path)

        if not result["success"]:
            return [{"kind": "error", "text": result["message"]}]

        if self._on_files_generated is not None:
            self._on_files_generated("_combined", output_path)

        report = (
            "Your complete 835 has been converted successfully.\n\n"
            f"Total Claims: {result['total_claims']}\n"
            f"Converted: {result['converted_claims']}\n"
            f"Failed: {result['failed_claims']}\n\n"
            f"{result['file_name']}"
        )
        
        files = [{"claim_number": "_combined", "path": str(output_path)}]
        
        return [
            {"kind": "report", "text": report},
            {"kind": "files", "text": "", "files": files}
        ]

    def _status_text(self) -> str:
        return (
            "File:  " + (self.state.file_name or "none") + "\n"
            "Status: ready\n"
            f"Claims: {len(self.state.claims)}\n"
            "Model:  " + config.OLLAMA_MODEL + "\n"
            "Ollama: connected"
        )

    def _file_text(self) -> str:
        analysis = self.state.analysis
        return (
            "File path:  " + self.state.file_path + "\n"
            "File type:  835\n"
            f"Claims:     {len(self.state.claims)}\n"
            f"Payer:      {analysis.get('payer', 'Unknown')}\n"
            f"Total paid: {analysis.get('total_paid', 'n/a')}"
        )

    def _help_text(self) -> str:
        return (
            "I'm your 835 processing assistant. Try asking me things like:\n"
            "- How many claims are there?\n"
            "- Find Ashay's claim.\n"
            "- Show claims above 5000.\n"
            "- Show me claim CLM12345.\n"
            "- Generate MIR for the second claim.\n"
            "- Convert all claims to MIR.\n\n"
            "System commands:\n"
            "/status  /file  /clear  /help  /exit"
        )

    # ------------------------------------------------------------------ tools
    def _build_tools(self) -> Dict[str, Callable]:
        return {
            "get_file_summary": self._tool_file_summary,
            "search_claims": self._tool_search,
            "get_claim": self._tool_get_claim,
            "filter_claims": self._tool_filter,
            "list_selected": self._tool_list_selected,
            "select_by_position": self._tool_select_by_position,
            "convert_claims": self._tool_convert,
        }

    def _execute(self, tool: str, args: Dict[str, Any]) -> Dict[str, Any]:
        return self._tools[tool](args)

    def _tool_file_summary(self, args: Dict[str, Any]) -> Dict[str, Any]:
        a = self.state.analysis
        text = (
            f"Claims:          {a.get('claim_count', 0)}\n"
            f"Transactions:    {a.get('transactions', 0)}\n"
            f"Total charge:    ${a.get('total_charge', '0.00')}\n"
            f"Total paid:      ${a.get('total_paid', '0.00')}\n"
            f"Payer:           {a.get('payer', 'Unknown')}\n"
            f"Unique members:  {a.get('member_count', 0)}\n"
            f"Unique patients: {a.get('patient_count', 0)}"
        )
        return {
            "kind": "data",
            "data": text,
            "block": text,
            "leadin": "Here is the summary of your 835 file:",
        }

    def _tool_search(self, args: Dict[str, Any]) -> Dict[str, Any]:
        matches = search_claims(self.state.claims, args.get("query", ""))
        self.state.selected_claims = [c.claim_number for c in matches]
        self.state.last_operation = "claim_search"
        return self._claims_result("search_claims", matches)

    def _tool_filter(self, args: Dict[str, Any]) -> Dict[str, Any]:
        matches = filter_claims(
            self.state.claims,
            min_amount=args.get("min_amount"),
            max_amount=args.get("max_amount"),
            status=args.get("status", ""),
        )
        self.state.selected_claims = [c.claim_number for c in matches]
        self.state.last_operation = "claim_filter"
        return self._claims_result("filter_claims", matches)

    def _tool_list_selected(self, args: Dict[str, Any]) -> Dict[str, Any]:
        claims = self.state.selected_as_claims()
        self.state.last_operation = "claim_list"
        return self._claims_result("list_selected", claims)

    def _tool_select_by_position(self, args: Dict[str, Any]) -> Dict[str, Any]:
        positions = args.get("positions", [])
        selected = self.state.selected_claims
        picked = [selected[p - 1] for p in positions if 1 <= p <= len(selected)]
        if not picked:
            return self._empty_selection_result("select_by_position")
        self.state.selected_claims = picked
        self.state.last_operation = "claim_select"
        claims = self.state.selected_as_claims()
        return self._claims_result("select_by_position", claims)

    def _tool_get_claim(self, args: Dict[str, Any]) -> Dict[str, Any]:
        number = args.get("claim_number") or ""
        position = args.get("position")
        if position:
            selected = self.state.selected_claims
            if isinstance(position, int) and 1 <= position <= len(selected):
                number = selected[position - 1]
        claim = next((c for c in self.state.claims if c.claim_number == number), None)
        if claim is None:
            text = f"Claim {number or '(unknown)'} was not found in the file."
            return {"kind": "data", "data": text, "block": text, "leadin": "I couldn't find that claim."}
        detail = format_claim_detail(claim)
        return {
            "kind": "data",
            "data": detail,
            "block": detail,
            "leadin": f"Here are the details for claim {claim.claim_number}:",
        }

    def _tool_convert(self, args: Dict[str, Any]) -> Dict[str, Any]:
        claims = self._resolve_target_claims(args)
        if not claims:
            return {
                "kind": "terminal",
                "events": [{"kind": "error", "text": self._empty_convert_message(args)}],
            }
        path = self._require_output_path()
        if path is None:
            return {
                "kind": "terminal",
                "events": [{"kind": "note", "text": "Cancelled. No files were written."}],
            }
        separate = bool(args.get("separate"))
        events: List[Dict[str, str]] = [
            {"kind": "note", "text": f"Generating MIR for {len(claims)} claim(s)...\n"}
        ]

        # Build each claim's MIR text first so any failure is isolated.
        generated: List[tuple] = []
        skipped: List[str] = []
        for claim in claims:
            try:
                result = generate_mir_texts(self.state.claims, [claim.claim_number])
                _, mir_text, _ = result[0]
            except Exception as exc:
                skipped.append(f"{claim.claim_number}: {exc}")
                continue
            generated.append((claim, mir_text))

        if not generated:
            events.append({
                "kind": "error",
                "text": "No MIR could be generated.\n"
                        + "\n".join(f"- {item}" for item in skipped),
            })
            return {"kind": "terminal", "events": events}

        lines: List[str] = []
        generated_files: List[Dict[str, str]] = []
        footer = ""
        if separate or len(generated) == 1:
            # One file per claim (a single claim is always a single file).
            numbers = [claim.claim_number for claim, _ in generated]
            save_paths = resolve_save_paths(path, numbers)
            for (claim, mir_text), save_path in zip(generated, save_paths):
                try:
                    ensure_directory(save_path)
                    write_text_verified(save_path, mir_text)
                except Exception as exc:
                    skipped.append(f"{claim.claim_number}: couldn't save ({exc})")
                    continue
                lines.append(f"✓ {claim.claim_number} → {save_path}")
                generated_files.append({"claim_number": claim.claim_number, "path": str(save_path)})
                if self._on_files_generated is not None:
                    self._on_files_generated(claim.claim_number, save_path)
            if len(lines) > 1:
                footer = f"{len(lines)} MIR file(s) generated."
            else:
                footer = "Saved to:\n" + str(save_paths[0])
        else:
            # Default: combine all targeted claims into a single MIR file.
            combined_text = "\r\n".join(
                text.rstrip("\r\n") for _, text in generated
            ) + "\r\n"
            save_path = self._combined_output_path(path, [c for c, _ in generated])
            try:
                ensure_directory(save_path)
                write_text_verified(save_path, combined_text)
            except Exception as exc:
                events.append({
                    "kind": "error",
                    "text": f"I generated the MIR but couldn't save it.\nReason: {exc}",
                })
                return {"kind": "terminal", "events": events}
            lines.append(f"✓ {len(generated)} claim(s) → {save_path}")
            generated_files.append({"claim_number": "_combined", "path": str(save_path)})
            if self._on_files_generated is not None:
                self._on_files_generated("_combined", save_path)
            footer = "Saved to:\n" + str(save_path)

        if not lines:
            events.append({
                "kind": "error",
                "text": "No MIR files could be saved.\n"
                        + "\n".join(f"- {item}" for item in skipped),
            })
            return {"kind": "terminal", "events": events}

        report = (
            "MIR generated successfully.\n"
            "✓ Claim extracted\n"
            "✓ MIR generated\n"
            "✓ File saved\n\n"
            + "\n".join(lines)
        )
        if skipped:
            report += "\n\nSkipped:\n" + "\n".join(f"- {item}" for item in skipped)
        report += "\n\n" + footer
        events.append({"kind": "report", "text": report})
        if generated_files:
            events.append({"kind": "files", "text": "", "files": generated_files})
        return {"kind": "terminal", "events": events}

    # ------------------------------------------------------------- helpers
    def _claims_result(self, tool_name: str, claims: List[Any]) -> Dict[str, Any]:
        from models import Claim as _Claim
        claim_list = [c for c in claims if isinstance(c, _Claim)]
        if not claim_list:
            return self._empty_selection_result(tool_name)
        block = format_claim_list(claim_list)
        label = "claim" if len(claim_list) == 1 else "claims"
        leadin = {
            "search_claims": f"I found {len(claim_list)} matching {label}:",
            "filter_claims": f"I found {len(claim_list)} matching {label}:",
            "list_selected": f"Your current selection ({len(claim_list)} {label}):",
            "select_by_position": f"Selected {len(claim_list)} {label}:",
        }.get(tool_name, "Here are the matching claims:")
        return {"kind": "data", "data": block, "block": block, "leadin": leadin}

    def _empty_selection_result(self, tool_name: str) -> Dict[str, Any]:
        text = "No claims matched. Try a different name, number or amount range."
        return {"kind": "data", "data": text, "block": text, "leadin": "I couldn't find any matching claims."}

    def _empty_convert_message(self, args: Dict[str, Any]) -> str:
        if args.get("claim_numbers"):
            missing = [str(n) for n in args["claim_numbers"]]
            return (
                "I couldn't find claim number(s): "
                + ", ".join(missing)
                + " in the 835 file."
            )
        if args.get("positions"):
            if not self.state.selected_claims:
                return config.SELECTION_EMPTY_MESSAGE
            return "Those positions are outside the current selection."
        return config.SELECTION_EMPTY_MESSAGE

    def _combined_output_path(self, output_path: Path, claims: List[Any]) -> Path:
        if output_path.suffix:
            return output_path
        first = claims[0].claim_number if claims else "claims"
        safe = "".join(ch for ch in first if ch.isalnum() or ch in "._-") or "claims"
        return Path(output_path) / f"{safe}_All{config.DEFAULT_MIR_EXTENSION}"

    def _resolve_target_claims(self, args: Dict[str, Any]) -> List[Any]:
        numbers: List[str] = []
        if args.get("all_claims"):
            return list(self.state.claims)
        if args.get("all_selected"):
            numbers = list(self.state.selected_claims)
            if not numbers:
                return list(self.state.claims)
        elif args.get("claim_numbers"):
            numbers = [str(n) for n in args["claim_numbers"]]
        elif args.get("positions"):
            selected = self.state.selected_claims
            for p in args["positions"]:
                if 1 <= p <= len(selected):
                    numbers.append(selected[p - 1])
        by_number = {c.claim_number: c for c in self.state.claims}
        return [by_number[n] for n in numbers if n in by_number]

    def _coerce_args(self, tool: str, args: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        specs = {
            "get_file_summary": {},
            "search_claims": {"query": "query"},
            "get_claim": {"claim_number": "claim_number", "position": "position"},
            "filter_claims": {"min_amount": "min_amount", "max_amount": "max_amount", "status": "status"},
            "list_selected": {},
            "select_by_position": {"positions": "positions"},
            "convert_claims": {"positions": "positions", "claim_numbers": "claim_numbers", "all_selected": "all_selected", "all_claims": "all_claims", "separate": "separate"},
        }.get(tool)
        if specs is None:
            return None
        aliases = {
            "min_value": "min_amount", "min": "min_amount", "above": "min_amount", "from": "min_amount",
            "max_value": "max_amount", "max": "max_amount", "below": "max_amount",
            "amount": "min_amount", "payment": "min_amount",
            "selected": "all_selected", "all": "all_selected",
            "whole": "all_claims", "whole_file": "all_claims", "entire": "all_claims",
            "everything": "all_claims", "file": "all_claims",
            "separate": "separate", "separately": "separate", "split": "separate",
            "each": "separate", "multiple": "separate", "per_claim": "separate",
            "numbers": "claim_numbers", "ids": "claim_numbers",
        }
        coerced: Dict[str, Any] = {}
        for key, value in args.items():
            key = aliases.get(key, key)
            if key not in specs:
                continue
            if value is None:
                continue
            coerce = _TOOL_COERCERS[key]
            try:
                coerced[key] = coerce(value)
            except (TypeError, ValueError):
                return None
        return coerced

    def _require_output_path(self) -> Optional[Path]:
        if self.state.output_path:
            return Path(self.state.output_path)
        if self._default_output_dir is not None:
            try:
                ensure_directory(self._default_output_dir)
            except Exception as exc:
                self._print(f"\nI couldn't create the output directory:\n{exc}")
                return None
            self.state.output_path = str(self._default_output_dir)
            return self._default_output_dir
        while True:
            self._print("\n" + PATH_QUESTION)
            raw = (self._input("> ") or "").strip().strip('"')
            if raw.lower() in EXIT_WORDS or raw.lower() in {"cancel", "none"}:
                return None
            validated = validate_output_path(raw)
            if validated["errors"]:
                self._print("\n" + "\n".join(validated["errors"]))
                continue
            path: Path = validated["path"]
            target = path if validated["is_directory"] else path.parent
            file_exists = (not validated["is_directory"]) and path.exists()
            if not target.exists():
                self._print(f"\nThe directory does not exist:\n{target}")
                choice = self._ask_yes_no("Would you like me to create it?", default=True)
                if choice is None:
                    return None
                if not choice:
                    self._print("No files were written. Please choose another location.")
                    continue
                try:
                    ensure_directory(path)
                except Exception as exc:
                    self._print(f"\nI couldn't create the directory:\n{exc}")
                    continue
            if file_exists:
                self._print(f"\nThe file already exists:\n{path}")
                self._print("Options: [1] Overwrite  [2] Use a different name  [3] Cancel")
                option = (self._input("> ") or "").strip()
                if option == "1":
                    pass
                elif option == "2":
                    continue
                else:
                    return None
            self.state.output_path = str(path)
            return path

    def _ask_yes_no(self, question: str, default: bool = True) -> Optional[bool]:
        suffix = " [Y/n]: " if default else " [y/N]: "
        while True:
            answer = (self._input("> " + question + suffix) or "").strip().lower()
            if answer in {"y", "yes"}:
                return True
            if answer in {"n", "no"}:
                return False
            if answer == "":
                return default
            self._print("Please answer yes or no.")

    # ----------------------------------------------------------------- prompt
    def _system_prompt(self) -> str:
        analysis = self.state.analysis
        session_note = (
            f"File: {self.state.file_name}\n"
            f"Claims: {len(self.state.claims)}\n"
            f"Total paid: {analysis.get('total_paid', 'n/a')}\n"
            f"Payer: {analysis.get('payer', 'Unknown')}"
        )
        return system_prompt(session_note, self._selection_note())

    def _selection_note(self) -> str:
        if not self.state.selected_claims:
            return "(none)"
        by_number = {c.claim_number: c for c in self.state.claims}
        lines = []
        for index, number in enumerate(self.state.selected_claims, start=1):
            if index > config.MAX_SELECTION_CONTEXT:
                remaining = len(self.state.selected_claims) - (index - 1)
                lines.append(f"... and {remaining} more")
                break
            claim = by_number.get(number)
            name = f"{claim.patient_last_name} {claim.patient_first_name}".strip() if claim else "?"
            paid = f"{claim.total_paid:,.2f}" if claim else "?"
            lines.append(f"{index}: {number} ({name}, paid {paid})")
        return "\n".join(lines)


def _as_int_list(value: Any) -> List[int]:
    if isinstance(value, str):
        cleaned = value.strip().strip("[]()").replace(" ", "")
        if cleaned == "":
            return []
        parts = cleaned.split(",") if "," in cleaned else cleaned.split()
        return [int(p) for p in parts if p != ""]
    if isinstance(value, list):
        return [int(v) for v in value]
    if isinstance(value, int):
        return [value]
    raise ValueError(f"not an integer list: {value!r}")


def _as_decimal(value: Any):
    from decimal import Decimal, InvalidOperation
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        raise ValueError(f"not a number: {value!r}")


def _is_full_conversion_intent(text: str) -> bool:
    text = text.lower()
    patterns = [
        r"convert.*whole.*835.*mir",
        r"convert.*entire.*835.*mir",
        r"convert.*this.*835.*mir",
        r"create.*mir.*from.*this.*835",
        r"convert.*all.*claims.*mir",
        r"generate.*mir.*from.*uploaded.*835",
        r"export.*835.*mir",
        r"convert.*uploaded.*835",
        r"convert.*complete.*file.*mir",
        r"create.*one.*mir.*file",
        r"convert.*this.*file.*mir",
        r"generate.*mir.*for.*entire.*file",
        r"convert.*835.*into.*mir"
    ]
    for p in patterns:
        if re.search(p, text):
            return True
            
    # More general fallback
    if re.search(r'\b(convert|create|generate|export)\b', text) and \
       re.search(r'\b(whole|entire|complete|all|this|uploaded)\b', text) and \
       re.search(r'\b(835|file|mir)\b', text) and \
       not re.search(r'\b(selected|those|these|specific|it)\b', text):
        return True
        
    return False
