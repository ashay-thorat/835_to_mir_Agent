"""Conversational terminal interface for the agentic 835 assistant."""
import sys

from agent.supervisor import Supervisor


def _enable_unicode() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


def print_banner() -> None:
    print("╔══════════════════════════════════════════════════════╗")
    print("║        AGENTIC 835 PROCESSING ASSISTANT             ║")
    print("╚══════════════════════════════════════════════════════╝")
    print()
    print("Runtime : Ollama (local)")
    print("Model   : llama3.2")
    print("Mode    : Local — your 835 never leaves this machine")
    print()


def run_chat(supervisor: Supervisor) -> None:
    print()
    print("──────────────────────────────────────────────────────")
    while True:
        try:
            raw = input("\nYou: ")
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye! Your generated files have been preserved.")
            break
        events = supervisor.run_turn(raw)
        for event in events:
            kind = event.get("kind")
            text = event.get("text", "")
            if kind == "exit":
                print("\nGoodbye! Your generated files have been preserved.")
                return
            if not text:
                continue
            if kind in {"assistant", "report"}:
                print(f"\nAssistant:\n{text}")
            elif kind == "block":
                print(text)
            elif kind == "error":
                print(f"\n{text}")
            else:
                print(f"\n{text}")
