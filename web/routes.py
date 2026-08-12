"""HTTP routes for the agentic 835 assistant.

Frontend calls these from http://localhost:5173 (Vite dev server proxies
/api to this backend at http://127.0.0.1:8000).
"""
from pathlib import Path
from typing import List

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

import config
from agent.ollama import OllamaClient
from edi835_parser import parse_835
from web.session import SessionStore


class ChatRequest(BaseModel):
    session_id: str
    message: str


class ZipRequest(BaseModel):
    session_id: str
    file_ids: List[str]


class ConvertRequest(BaseModel):
    session_id: str


def build_router(store: SessionStore) -> APIRouter:
    router = APIRouter()

    @router.get("/health")
    def health():
        client = OllamaClient()
        problem = client.check_connection()
        return {
            "backend": "online",
            "ollama": "online" if problem is None else "offline",
            "model": config.OLLAMA_MODEL,
            "model_ready": problem is None,
            "message": "" if problem is None else problem,
        }

    @router.post("/files/upload")
    async def upload_file(file: UploadFile = File(...)):
        data = await file.read()
        if not data or not data.strip():
            raise HTTPException(status_code=400, detail="The uploaded file is empty.")
        if len(data) > config.MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="Uploaded file is too large.")
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            text = data.decode("latin-1", errors="replace")
        if not parse_835(text):
            raise HTTPException(
                status_code=400,
                detail="No 835 structure detected (no CLP claim segments found).",
            )

        session = store.create_session(file.filename or "uploaded_835", text)
        greeting = session.make_greeting()
        return {
            "session_id": session.session_id,
            "file_name": session.display_name,
            "claim_count": len(session.claims),
            "analysis": session.analysis,
            "greeting": greeting,
        }

    @router.post("/chat")
    def chat(payload: ChatRequest):
        message = (payload.message or "").strip()
        if not message:
            raise HTTPException(status_code=400, detail="Message is empty.")
        if len(message) > config.WEB_MAX_CHAT_MESSAGE_LENGTH:
            raise HTTPException(status_code=400, detail="Message is too long.")
        session = store.get(payload.session_id)
        if session is None:
            raise HTTPException(
                status_code=404,
                detail="Session not found. Please upload the 835 file again.",
            )
        return {"events": session.chat(message)}

    @router.post("/convert/835-to-mir")
    def convert_835_to_mir_endpoint(payload: ConvertRequest):
        import secrets
        from tools.conversion import convert_835_to_mir_file
        
        session = store.get(payload.session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found. Please upload the 835 file again.")
            
        file_stem = Path(session.upload_path).stem
        safe_stem = "".join(ch for ch in file_stem if ch.isalnum() or ch in "._-") or "converted"
        output_name = f"{safe_stem}{config.DEFAULT_MIR_EXTENSION}"
        output_path = session.generated_dir / output_name
        
        result = convert_835_to_mir_file(session.upload_path, output_path)
        
        if not result["success"]:
            raise HTTPException(status_code=500, detail=result["message"])
            
        token = secrets.token_urlsafe(config.WEB_DOWNLOAD_TOKEN_LENGTH)
        session.file_registry[token] = output_path
        
        return {
            "success": True,
            "message": result["message"],
            "file_id": token,
            "file_name": result.get("file_name", output_name),
            "download_url": f"/api/mir/download/{token}",
            "total_claims": result.get("total_claims", 0),
            "converted_claims": result.get("converted_claims", 0),
            "failed_claims": result.get("failed_claims", 0)
        }

    @router.get("/mir/download/{file_id}")
    def download(file_id: str):
        session = _session_for_file(store, file_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Download not found.")
        path = session.resolve_download(file_id)
        if path is None:
            raise HTTPException(status_code=404, detail="Download not found.")
        media_type = "application/zip" if path.suffix.lower() == ".zip" else "text/plain"
        return FileResponse(path, media_type=media_type, filename=path.name)

    @router.post("/mir/zip")
    def zip_files(payload: ZipRequest):
        session = store.get(payload.session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found.")
        token, name = session.create_zip(payload.file_ids)
        if token is None:
            raise HTTPException(status_code=400, detail="No valid generated files to zip.")
        return {
            "download_id": token,
            "file_name": name,
            "download_url": f"/api/mir/download/{token}",
        }

    @router.post("/mir/combine")
    def combine_files(payload: ZipRequest):
        session = store.get(payload.session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found.")
        token, name = session.combine_files(payload.file_ids)
        if token is None:
            raise HTTPException(status_code=400, detail="No valid generated files to combine.")
        return {
            "download_id": token,
            "file_name": name,
            "download_url": f"/api/mir/download/{token}",
        }

    return router


def _session_for_file(store: SessionStore, file_id: str):
    for session in store.sessions.values():
        if file_id in session.file_registry:
            return session
    return None
