"""Thin wrapper around the local Ollama runtime (Llama 3.2)."""
import json
import re
from typing import Dict, List, Optional

import ollama

import config


class OllamaClient:
    def __init__(self, host: Optional[str] = None, model: Optional[str] = None,
                 timeout: Optional[int] = None):
        self.host = host or config.OLLAMA_HOST
        self.model = model or config.OLLAMA_MODEL
        self.timeout = timeout or config.OLLAMA_TIMEOUT
        self._client = ollama.Client(host=self.host, timeout=self.timeout)

    def check_connection(self) -> Optional[str]:
        try:
            models = self._client.list()
        except Exception as exc:
            return f"Cannot reach Ollama at {self.host}: {exc}"
        names = [m.get("model", "") for m in models.get("models", [])]
        if not any(n == self.model or n.startswith(self.model + ":") for n in names):
            available = ", ".join(names) or "none"
            return (
                f"Model {self.model!r} is not installed locally. "
                f"Available models: {available}. Run: ollama pull {self.model}"
            )
        return None

    def decide(self, system: str, history: List[Dict[str, str]]) -> Optional[Dict]:
        """Return the parsed JSON decision from the model, or None on failure."""
        messages = [{"role": "system", "content": system}] + history
        content = self._chat(messages, force_json=True)
        if not content:
            return None
        parsed = _extract_json(content)
        if isinstance(parsed, dict):
            return parsed
        return None

    def respond(self, system: str, history: List[Dict[str, str]]) -> str:
        messages = [{"role": "system", "content": system}] + history
        return (self._chat(messages, force_json=False) or "").strip()

    def _chat(self, messages: List[Dict[str, str]], force_json: bool) -> str:
        try:
            response = self._client.chat(
                model=self.model,
                messages=messages,
                format="json" if force_json else None,
                options={"temperature": 0.2, "num_predict": config.OLLAMA_NUM_PREDICT},
            )
        except Exception as exc:
            raise RuntimeError(f"Ollama request failed: {exc}") from exc
        return (response.get("message", {}).get("content") or "").strip()


def _extract_json(text: str) -> Optional[Dict]:
    try:
        value = json.loads(text)
        return value if isinstance(value, dict) else None
    except (json.JSONDecodeError, ValueError):
        pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            value = json.loads(match.group(0))
            return value if isinstance(value, dict) else None
        except (json.JSONDecodeError, ValueError):
            return None
    return None
