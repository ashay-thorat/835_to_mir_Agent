from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent.state import SessionState
from agent.supervisor import Supervisor
from edi835_parser import parse_835
from tools.analysis import analyze_835
from tools.claim_details import format_claim_detail, format_claim_list
from tools.conversion import generate_mir_texts
from tools.file_manager import resolve_save_paths
from tools.search_claims import filter_claims, search_claims
from tools.validation import validate_output_path

SAMPLE = (ROOT / "input" / "sample_payment.835").read_text(encoding="utf-8")
CLAIMS = parse_835(SAMPLE)


def _state() -> SessionState:
    return SessionState(
        file_path="input/sample_payment.835",
        file_name="sample_payment.835",
        claims=CLAIMS,
        analysis=analyze_835(SAMPLE),
    )


class FakeClient:
    def __init__(self, decisions):
        self.decisions = list(decisions)
        self.index = 0

    def check_connection(self):
        return None

    def decide(self, system, history):
        decision = self.decisions[self.index]
        self.index += 1
        return decision

    def respond(self, system, history):
        return "ok"


def _run(state, decisions, user_input, input_answer=None):
    inputs = [input_answer] if input_answer is not None else []
    printed = []

    def fake_input(prompt):
        if inputs:
            return inputs.pop(0)
        return ""

    supervisor = Supervisor(
        state=state, client=FakeClient(decisions), input_func=fake_input, print_func=printed.append
    )
    events = supervisor.run_turn(user_input)
    return events, supervisor, printed


def test_search_claims_tool():
    state = _state()
    events, supervisor, _ = _run(
        state,
        [
            {"type": "tool", "tool": "search_claims", "args": {"query": "Ashay"}},
            {"type": "chat", "reply": "I found 2 claims for Ashay."},
        ],
        "Find Ashay's claim.",
    )
    blocks = [e for e in events if e["kind"] == "block"]
    assert state.selected_claims == ["86520262053343501", "86520262053343502"]
    assert "86520262053343501" in blocks[0]["text"]
    assert "86520262053343502" in blocks[0]["text"]
    assert any(e["kind"] == "assistant" for e in events)
    assert events.index(next(e for e in events if e["kind"] == "assistant")) < events.index(blocks[0])


def test_convert_flow_asks_path_and_saves():
    state = _state()
    state.selected_claims = ["86520262053343501", "86520262053343502"]
    with tempfile.TemporaryDirectory() as tmp:
        out_dir = Path(tmp) / "mir_out"
        events, supervisor, _ = _run(
            state,
            [
                {"type": "tool", "tool": "convert_claims", "args": {"all_selected": True}},
            ],
            "Generate MIR for them.",
            input_answer=str(out_dir),
        )
        reports = [e for e in events if e["kind"] == "report"]
        assert len(reports) == 1
        assert "MIR generated successfully" in reports[0]["text"]
        files = sorted(out_dir.glob("*.mir"))
        assert len(files) == 1
        assert state.output_path == str(out_dir)
        for f in files:
            assert f.stat().st_size > 0


def test_convert_single_claim_single_file_path():
    state = _state()
    state.selected_claims = ["86520262053343500"]
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "single_claim.mir"
        events, supervisor, _ = _run(
            state,
            [{"type": "tool", "tool": "convert_claims", "args": {"positions": [1]}}],
            "Generate MIR for the first one.",
            input_answer=str(target),
        )
        assert target.is_file()
        assert any("Saved to:" in e["text"] for e in events if e["kind"] == "report")


def test_convert_with_no_selection():
    state = _state()
    events, supervisor, _ = _run(
        state,
        [{"type": "tool", "tool": "convert_claims", "args": {"positions": [1]}}],
        "Generate MIR for the first claim.",
    )
    assert any("have not selected any claims" in e["text"] for e in events)


def test_convert_whole_file_converts_all_claims():
    state = _state()
    with tempfile.TemporaryDirectory() as tmp:
        out_dir = Path(tmp) / "out"
        out_dir.mkdir()
        events, supervisor, _ = _run(
            state,
            [{"type": "tool", "tool": "convert_claims", "args": {"all_claims": True}}],
            "Convert the whole file into MIR.",
            input_answer=str(out_dir),
        )
        assert any(e["kind"] == "report" for e in events)
        files = sorted(out_dir.glob("*.mir"))
        assert len(files) == 1


def test_convert_whole_file_when_selection_empty_falls_back_to_all():
    state = _state()
    state.selected_claims = []
    with tempfile.TemporaryDirectory() as tmp:
        out_dir = Path(tmp) / "out"
        out_dir.mkdir()
        events, supervisor, _ = _run(
            state,
            [{"type": "tool", "tool": "convert_claims", "args": {"all_selected": True}}],
            "Convert the whole file into MIR.",
            input_answer=str(out_dir),
        )
        assert any(e["kind"] == "report" for e in events)


def test_convert_skips_claims_without_service_lines():
    import copy
    state = _state()
    state.claims = copy.deepcopy(state.claims)
    state.claims[0].services = []
    with tempfile.TemporaryDirectory() as tmp:
        out_dir = Path(tmp) / "out"
        out_dir.mkdir()
        events, supervisor, _ = _run(
            state,
            [{"type": "tool", "tool": "convert_claims", "args": {"all_claims": True}}],
            "Convert the whole file into MIR.",
            input_answer=str(out_dir),
        )
        report = next((e["text"] for e in events if e["kind"] == "report"), "")
        assert any(e["kind"] == "report" for e in events)
        assert "Failed:" in report
        assert len(list(out_dir.glob("*.mir"))) == 1


def test_convert_unknown_claim_number_shows_not_found():
    state = _state()
    events, supervisor, _ = _run(
        state,
        [{"type": "tool", "tool": "convert_claims", "args": {"claim_numbers": ["DOESNOTEXIST"]}}],
        "Convert claim DOESNOTEXIST.",
    )
    errors = [e["text"] for e in events if e["kind"] == "error"]
    assert any("DOESNOTEXIST" in t and "couldn't find" in t for t in errors)


def test_strict_search_matches():
    import config
    matches = search_claims(CLAIMS, "ashay")
    assert [c.claim_number for c in matches] == ["86520262053343501", "86520262053343502"]
    assert search_claims(CLAIMS, "jones maya") and search_claims(CLAIMS, "jones maya")[0].claim_number == "86520262053343503"
    assert search_claims(CLAIMS, "zzzzyyy") == []


def test_selection_note_is_capped():
    import config
    state = _state()
    sup = Supervisor(state=state, client=None)
    state.selected_claims = [c.claim_number for c in CLAIMS] * 20
    lines = sup._selection_note().splitlines()
    assert len(lines) == config.MAX_SELECTION_CONTEXT + 1
    assert lines[-1].startswith("... and ")
    assert "more" in lines[-1]


def test_convert_requires_overwrite_confirmation():
    state = _state()
    state.selected_claims = ["86520262053343500"]
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "existing.mir"
        target.write_text("OLD", encoding="ascii")
        inputs = iter([str(target), "1"])
        printed = []
        supervisor = Supervisor(
            state=state,
            client=FakeClient([{"type": "tool", "tool": "convert_claims", "args": {"positions": [1]}}]),
            input_func=lambda prompt: next(inputs),
            print_func=printed.append,
        )
        events = supervisor.run_turn("Generate MIR.")
        assert target.read_text(encoding="ascii").strip() != "OLD"
        assert any("already exists" in line for line in printed)
        assert any(e["kind"] == "report" for e in events)


def test_convert_cancel_on_overwrite_choice():
    state = _state()
    state.selected_claims = ["86520262053343500"]
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "existing.mir"
        target.write_text("OLD", encoding="ascii")
        inputs = iter([str(target), "3"])
        supervisor = Supervisor(
            state=state,
            client=FakeClient([{"type": "tool", "tool": "convert_claims", "args": {"all_selected": True}}]),
            input_func=lambda prompt: next(inputs),
            print_func=lambda x: None,
        )
        events = supervisor.run_turn("Generate MIR.")
        assert target.read_text(encoding="ascii").strip() == "OLD"
        assert any("No files were written" in e["text"] for e in events)


def test_exit_word():
    state = _state()
    events, _, _ = _run(state, [], "bye")
    assert any(e["kind"] == "exit" for e in events)


def test_validate_output_path_windows():
    good = validate_output_path("C:\\MIR\\out\\x.mir")
    assert good["ok"] is True
    relative = validate_output_path("out/x.mir")
    assert relative["ok"] is False
    illegal = validate_output_path("C:\\a<b.mir")
    assert illegal["ok"] is False


def test_resolve_save_paths_multiple():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp) / "outdir"
        paths = resolve_save_paths(base, ["CLM1", "CLM2"])
        assert len(paths) == 2
        assert paths[0].name == "CLM1.mir"


def test_format_claim_list_and_detail():
    assert "1." in format_claim_list(CLAIMS[:2])
    assert "Claim number:" in format_claim_detail(CLAIMS[0])


def test_generate_mir_texts_missing_claim():
    try:
        generate_mir_texts(CLAIMS, ["DOESNOTEXIST"])
        assert False
    except ValueError:
        pass


def test_filter_claims_by_amount():
    matched = filter_claims(CLAIMS, min_amount=100)
    assert [c.claim_number for c in matched] == ["86520262053343502"]
