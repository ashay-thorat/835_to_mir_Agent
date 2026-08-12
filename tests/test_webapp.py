from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi import FastAPI
from fastapi.testclient import TestClient

from web.routes import build_router
from web.session import SessionStore

SAMPLE = (ROOT / "input" / "sample_payment.835").read_text(encoding="utf-8")


class FakeClient:
    def __init__(self, decisions=None):
        self.decisions = list(decisions or [])
        self.index = 0

    def check_connection(self):
        return None

    def decide(self, system, history):
        decision = self.decisions[self.index]
        self.index += 1
        return decision

    def respond(self, system, history):
        return "ok"


def _app(store):
    app = FastAPI()
    app.include_router(build_router(store), prefix="/api")
    return TestClient(app)


def test_upload_endpoint_parses_and_greets():
    store = SessionStore()
    client = _app(store)
    response = client.post(
        "/api/files/upload",
        files={"file": ("payment.835", SAMPLE.encode("utf-8"), "text/plain")},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["session_id"]
    assert payload["file_name"] == "payment.835"
    assert payload["claim_count"] == 4
    assert payload["greeting"]
    assert payload["analysis"]["total_paid"] == "513.44"


def test_upload_rejects_empty_and_invalid():
    store = SessionStore()
    client = _app(store)
    empty = client.post("/api/files/upload", files={"file": ("x.835", b"", "text/plain")})
    assert empty.status_code == 400
    bad = client.post(
        "/api/files/upload",
        files={"file": ("x.835", b"hello this is not edi", "text/plain")},
    )
    assert bad.status_code == 400


def test_chat_generates_mir_files_and_download():
    store = SessionStore()
    client = FakeClient(
        [{"type": "tool", "tool": "convert_claims", "args": {"all_selected": True}}]
    )
    session = store.create_session("payment.835", SAMPLE, client=client)
    session.state.selected_claims = ["86520262053343501", "86520262053343502"]

    events = session.chat("Generate MIR for them.")
    files_event = next(e for e in events if e["kind"] == "files")
    assert len(files_event["files"]) == 1
    assert "download_url" in files_event["files"][0]
    file_ids = [f["file_id"] for f in files_event["files"]]
    assert all(f["download_url"].startswith("/api/mir/download/") for f in files_event["files"])

    http = _app(store)
    for file_id, f in zip(file_ids, files_event["files"]):
        path = session.resolve_download(file_id)
        assert path is not None and path.stat().st_size > 0
        response = http.get(f"/api/mir/download/{file_id}")
        assert response.status_code == 200
        assert f['file_name'] in response.headers["content-disposition"]
        assert len(response.content) > 0


def _files_event_ids(session):
    client = FakeClient(
        [{"type": "tool", "tool": "convert_claims", "args": {"all_selected": True}}]
    )
    session.client = client
    session.state.selected_claims = ["86520262053343501", "86520262053343502"]
    events = session.chat("Generate MIR for them.")
    files_event = next(e for e in events if e["kind"] == "files")
    return [f["file_id"] for f in files_event["files"]]


def test_zip_download():
    store = SessionStore()
    session = store.create_session("payment.835", SAMPLE)
    file_ids = _files_event_ids(session)
    http = _app(store)
    response = http.post("/api/mir/zip", json={"session_id": session.session_id, "file_ids": file_ids})
    assert response.status_code == 200
    payload = response.json()
    assert payload["file_name"].endswith(".zip")
    zip_response = http.get(payload["download_url"])
    assert zip_response.status_code == 200
    assert zip_response.content[:2] == b"PK"


def test_combined_single_mir_download():
    store = SessionStore()
    session = store.create_session("payment.835", SAMPLE)
    file_ids = _files_event_ids(session)
    http = _app(store)
    response = http.post("/api/mir/combine", json={"session_id": session.session_id, "file_ids": file_ids})
    assert response.status_code == 200
    payload = response.json()
    assert payload["file_name"].endswith(".mir")
    combined = http.get(payload["download_url"])
    assert combined.status_code == 200
    body = combined.content.decode("ascii", errors="replace")
    assert "86520262053343501" in body
    assert "86520262053343502" in body


def test_chat_unknown_session_returns_404():
    store = SessionStore()
    http = _app(store)
    response = http.post("/api/chat", json={"session_id": "nope", "message": "hi"})
    assert response.status_code == 404


def test_health_endpoint():
    store = SessionStore()
    http = _app(store)
    response = http.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["backend"] == "online"
    assert body["model"] == "llama3.2"
