"""FastAPI entry point for the local agentic 835 assistant web app.

Run:  python -m uvicorn webapp:app --host 127.0.0.1 --port 8000
"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import config
from web.routes import build_router
from web.session import SessionStore

store = SessionStore()

app = FastAPI(title="Agentic 835 Assistant")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(build_router(store), prefix="/api", tags=["agentic-835"])

dist = Path(config.FRONTEND_DIST_DIR)
if dist.is_dir():
    app.mount("/", StaticFiles(directory=str(dist), html=True), name="frontend")
