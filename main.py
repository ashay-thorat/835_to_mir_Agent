"""Entry point for the agentic 835 processing assistant.

Startup:
  python main.py

Loads a local 835 file, parses and analyzes it, then starts a conversational
chat backed by a local Ollama Llama 3.2 model.
"""
from pathlib import Path

import config
from agent.ollama import OllamaClient
from agent.prompts import greet_prompt
from agent.state import SessionState
from agent.supervisor import Supervisor
from chat import print_banner, run_chat
from edi835_parser import parse_835
from tools.analysis import analyze_835, format_analysis_report


def _enable_unicode() -> None:
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


def _find_input_path() -> Path:
    print("Enter the path of your 835 file:")
    while True:
        raw = input("> ").strip().strip('"')
        if not raw:
            print("Please provide a path.")
            continue
        path = Path(raw)
        if not path.is_file():
            print(f"File not found: {path}")
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            print(f"File is not readable: {exc}")
            continue
        if not text.strip():
            print("The file is empty.")
            continue
        claims = parse_835(text)
        if not claims:
            print("No 835 structure detected (no CLP claim segments found).")
            continue
        return path


def main() -> None:
    _enable_unicode()
    print_banner()

    print("AI Runtime : Ollama")
    print(f"Model      : {config.OLLAMA_MODEL}")
    print("Mode       : Local")
    print()

    print("Checking local Ollama runtime...")
    client = OllamaClient()
    problem = client.check_connection()
    if problem:
        print(problem)
        return

    path = _find_input_path()
    print("\nLoading 835 file...")
    text = path.read_text(encoding="utf-8", errors="replace")
    claims = parse_835(text)
    analysis = analyze_835(text)

    print("✓ File found")
    print("✓ File readable")
    print("✓ 835 structure detected")
    print("✓ File parsed")
    print(f"✓ {len(claims)} claims identified")
    print()
    print(format_analysis_report(analysis))
    print()

    state = SessionState(
        file_path=str(path),
        file_name=path.name,
        claims=claims,
        analysis=analysis,
    )
    supervisor = Supervisor(state=state, client=client)

    try:
        greeting = client.respond(greet_prompt(_greet_context(analysis)), [])
        greeting = _clean_greeting(greeting)
    except RuntimeError:
        greeting = (
            "Hello! I'm your 835 processing assistant.\n"
            "I've analyzed your uploaded 835 file and I'm ready to help.\n"
            "How can I help you?"
        )
    state.record("assistant", greeting)

    print("AI Assistant")
    print("--------------------------------------------------------")
    print()
    print(f"Assistant:\n{greeting}")
    run_chat(supervisor)


def _greet_context(analysis) -> str:
    return (
        f"File type: {analysis.get('file_type')}\n"
        f"Claims: {analysis.get('claim_count')}\n"
        f"Total paid: {analysis.get('total_paid')}\n"
        f"Payer: {analysis.get('payer')}"
    )


def _clean_greeting(text: str) -> str:
    lines = (text or "").strip().splitlines()
    while lines and lines[0].strip().lower() in {"assistant", "agent", "assistant:"}:
        lines.pop(0)
    return "\n".join(lines).strip()


if __name__ == "__main__":
    main()
