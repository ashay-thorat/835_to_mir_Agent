"""Stateful web session for the local agentic 835 assistant.

A session owns one uploaded 835 file, its parsed claims/analysis, the agent
Supervisor (which reuses the existing 835 -> MIR converter), and a registry of
generated files so downloads stay controlled and path-safe.
"""
import secrets
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import config
from agent.ollama import OllamaClient
from agent.prompts import greet_prompt
from agent.state import SessionState
from agent.supervisor import Supervisor
from edi835_parser import parse_835
from tools.analysis import analyze_835


def _clean_greeting(text: str) -> str:
    lines = (text or "").strip().splitlines()
    while lines and lines[0].strip().lower() in {"assistant", "agent", "assistant:"}:
        lines.pop(0)
    return "\n".join(lines).strip()


class WebSession:
    """One upload = one chat session = one parsed 835."""

    def __init__(
        self,
        session_id: str,
        upload_path: Path,
        display_name: str,
        file_registry: Dict[str, Path],
        client: Optional[OllamaClient] = None,
    ):
        self.session_id = session_id
        self.upload_path = upload_path
        self.display_name = display_name
        self.file_registry = file_registry  # shared token -> Path store
        self.generated_dir = Path(config.WEB_GENERATED_DIR) / session_id
        self.generated_dir.mkdir(parents=True, exist_ok=True)

        text = upload_path.read_text(encoding="utf-8", errors="replace")
        self.claims = parse_835(text)
        self.analysis = analyze_835(text)
        self.state = SessionState(
            file_path=str(upload_path),
            file_name=display_name,
            claims=self.claims,
            analysis=self.analysis,
        )
        self.client = client or OllamaClient()
        self.supervisor = Supervisor(
            state=self.state,
            client=self.client,
            default_output_dir=self.generated_dir,
            on_files_generated=self._register_file,
        )
        self.greeting = ""

    def _register_file(self, claim_number: str, save_path: Path) -> None:
        token = secrets.token_urlsafe(config.WEB_DOWNLOAD_TOKEN_LENGTH)
        self.file_registry[token] = Path(save_path)

    def make_greeting(self) -> str:
        context = (
            f"File type: {self.analysis.get('file_type')}\n"
            f"Claims: {self.analysis.get('claim_count')}\n"
            f"Total paid: {self.analysis.get('total_paid')}\n"
            f"Payer: {self.analysis.get('payer')}"
        )
        try:
            greeting = _clean_greeting(self.client.respond(greet_prompt(context), []))
        except RuntimeError:
            greeting = (
                "Hello! I'm your 835 processing assistant.\n"
                "I've analyzed your uploaded 835 file and I'm ready to help.\n"
                "How can I help you?"
            )
        self.greeting = greeting or "Hello! How can I help you with your 835 file?"
        self.state.record("assistant", self.greeting)
        return self.greeting

    def chat(self, message: str) -> List[Dict[str, Any]]:
        events = self.supervisor.run_turn(message)
        return [self._map_event(event) for event in events]

    def _map_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        mapped: Dict[str, Any] = dict(event)
        if event.get("kind") == "files":
            files = []
            for item in event.get("files", []):
                path_text = item.get("path", "")
                token = next(
                    (t for t, p in self.file_registry.items() if str(p) == path_text),
                    None,
                )
                if token is None:
                    continue
                files.append(
                    {
                        "claim_number": item.get("claim_number", ""),
                        "file_name": Path(path_text).name,
                        "file_id": token,
                        "download_url": f"/api/mir/download/{token}",
                    }
                )
            mapped["files"] = files
        return mapped

    def resolve_download(self, file_id: str) -> Optional[Path]:
        path = self.file_registry.get(file_id)
        if path is not None and path.is_file():
            return path
        return None

    def create_zip(self, file_ids: List[str]) -> tuple[Optional[str], Optional[str]]:
        from datetime import datetime

        paths = [
            self.file_registry[fid]
            for fid in file_ids
            if self.file_registry.get(fid) is not None and self.file_registry[fid].is_file()
        ]
        if not paths:
            return None, None
        stem = _safe_name(self.display_name) + "_MIR_Files_" + datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_path = self.generated_dir / f"{stem}.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in paths:
                archive.write(path, arcname=path.name)
        token = secrets.token_urlsafe(config.WEB_DOWNLOAD_TOKEN_LENGTH)
        self.file_registry[token] = zip_path
        return token, zip_path.name

    def combine_files(self, file_ids: List[str]) -> tuple[Optional[str], Optional[str]]:
        """Stitch the given generated claim files into a single combined MIR file."""
        paths = [
            self.file_registry[fid]
            for fid in file_ids
            if self.file_registry.get(fid) is not None and self.file_registry[fid].is_file()
        ]
        if not paths:
            return None, None
        records = []
        for path in paths:
            text = path.read_text(encoding="ascii", errors="replace").rstrip("\r\n")
            if text:
                records.append(text)
        if not records:
            return None, None
        stem = _safe_name(self.display_name) + "_MIR_All"
        combined_path = self.generated_dir / f"{stem}.mir"
        combined_path.write_text(
            "\r\n".join(records) + "\r\n",
            encoding="ascii",
            errors="replace",
            newline="",
        )
        token = secrets.token_urlsafe(config.WEB_DOWNLOAD_TOKEN_LENGTH)
        self.file_registry[token] = combined_path
        return token, combined_path.name


class SessionStore:
    """In-memory session registry plus the shared, path-safe file registry."""

    def __init__(self):
        self.sessions: Dict[str, WebSession] = {}
        self.files: Dict[str, Path] = {}

    def create_session(
        self,
        file_name: str,
        text: str,
        client: Optional[OllamaClient] = None,
    ) -> WebSession:
        session_id = secrets.token_hex(config.WEB_SESSION_ID_LENGTH)
        upload_dir = Path(config.WEB_UPLOAD_DIR) / session_id
        upload_dir.mkdir(parents=True, exist_ok=True)
        upload_path = upload_dir / (_safe_name(file_name) + ".835")
        upload_path.write_text(text, encoding="utf-8", errors="replace")
        session = WebSession(
            session_id=session_id,
            upload_path=upload_path,
            display_name=file_name,
            file_registry=self.files,
            client=client,
        )
        self.sessions[session_id] = session
        return session

    def get(self, session_id: str) -> Optional[WebSession]:
        return self.sessions.get(session_id)


def _safe_name(name: str) -> str:
    stem = Path(name).stem
    safe = "".join(ch for ch in stem if ch.isalnum() or ch in "._-")
    return safe or "uploaded_835"
