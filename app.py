import secrets
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

import config
from converter import convert_835_to_mir

BASE_DIR = Path(__file__).resolve().parent
GENERATED_DIR = BASE_DIR / "generated"
GENERATED_DIR.mkdir(exist_ok=True)

app = FastAPI(title=config.APP_TITLE)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

_downloads: dict[str, Path] = {}


@app.get("/", response_class=HTMLResponse)
def home():
    return (BASE_DIR / "templates" / "index.html").read_text(encoding="utf-8")


@app.post("/api/convert")
async def convert(file: UploadFile = File(...)):
    data = await file.read()
    if len(data) > config.MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Uploaded file is too large.")

    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = data.decode("latin-1", errors="replace")

    try:
        mir_text, summary = convert_835_to_mir(text)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Conversion failed: {exc}") from exc

    token = secrets.token_urlsafe(config.DOWNLOAD_TOKEN_LENGTH)
    original_stem = Path(file.filename or "input_835").stem
    safe_stem = "".join(ch for ch in original_stem if ch.isalnum() or ch in "-_") or "input_835"
    output_path = GENERATED_DIR / f"{safe_stem}{config.OUTPUT_EXTENSION}"
    # Avoid overwriting another file with the same name in the same app session.
    if output_path.exists():
        output_path = GENERATED_DIR / f"{safe_stem}_{token[:8]}{config.OUTPUT_EXTENSION}"
    output_path.write_text(mir_text, encoding="ascii", errors="replace", newline="")
    _downloads[token] = output_path

    return {
        "ok": True,
        "summary": summary,
        "download_url": f"/download/{token}",
        "output_name": output_path.name,
        "note": "Fields not available from the 835 are preserved as fixed-width blanks/defaults for future API enrichment.",
    }


@app.get("/download/{token}")
def download(token: str):
    path = _downloads.get(token)
    if path is None or not path.exists():
        raise HTTPException(status_code=404, detail="Download not found. Please convert the file again.")
    return FileResponse(path, media_type="text/plain", filename=path.name)
