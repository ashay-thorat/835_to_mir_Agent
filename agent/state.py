"""Session state for the agentic 835 assistant.

Structured state is kept here (not in the LLM) so references such as "the
second claim" or "it" resolve deterministically against the last selection.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from models import Claim


@dataclass
class SessionState:
    file_path: str = ""
    file_name: str = ""
    claims: List[Claim] = field(default_factory=list)
    analysis: Dict[str, Any] = field(default_factory=dict)
    selected_claims: List[str] = field(default_factory=list)
    last_operation: str = ""
    output_path: Optional[str] = None
    history: List[Dict[str, str]] = field(default_factory=list)

    def selected_as_claims(self) -> List[Claim]:
        by_number = {c.claim_number: c for c in self.claims}
        return [by_number[n] for n in self.selected_claims if n in by_number]

    def record(self, role: str, content: str) -> None:
        self.history.append({"role": role, "content": content})

    def clear_conversation(self) -> None:
        self.history = []
