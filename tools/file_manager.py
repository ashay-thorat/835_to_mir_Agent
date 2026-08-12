"""Output path handling, directory creation and verified file writing."""
from pathlib import Path
from typing import List

import config


def resolve_save_paths(output_path: Path, claim_numbers: List[str]) -> List[Path]:
    """Map the user's requested output location to one concrete file per claim.

    Single claim + file path  -> that exact file.
    Multiple claims + directory -> <dir>/<claim_number>.mir per claim.
    Multiple claims + file base -> <base_dir>/<base_stem>_<claim_number>.mir.
    """
    if not claim_numbers:
        return []
    if len(claim_numbers) == 1 and output_path.suffix:
        return [output_path]
    directory = output_path if output_path.suffix == "" else output_path.parent
    base = output_path.stem if output_path.suffix else ""
    paths = []
    for number in claim_numbers:
        safe = _safe_name(number)
        if base:
            paths.append(directory / f"{base}_{safe}{config.DEFAULT_MIR_EXTENSION}")
        else:
            paths.append(directory / f"{safe}{config.DEFAULT_MIR_EXTENSION}")
    return paths


def ensure_directory(path: Path) -> None:
    directory = path if path.suffix == "" else path.parent
    if not directory.exists():
        directory.mkdir(parents=True, exist_ok=True)


def write_text_verified(path: Path, text: str) -> Path:
    path.write_text(text, encoding="ascii", errors="replace", newline="")
    if not path.is_file() or path.stat().st_size == 0:
        raise OSError(f"Output file was not written correctly: {path}")
    return path


def _safe_name(number: str) -> str:
    safe = "".join(ch for ch in number if ch.isalnum() or ch in "._-")
    return safe or "claim"
