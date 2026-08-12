"""Output path validation for generated MIR files (Windows-aware)."""
import os
import re
from pathlib import Path
from typing import Any, Dict, Optional

import config

_WINDOWS_ILLEGAL = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_WINDOWS_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def _is_windows() -> bool:
    return os.name == "nt"


def validate_output_path(path_text: str) -> Dict[str, Any]:
    path_text = (path_text or "").strip().strip('"').strip()
    result: Dict[str, Any] = {
        "ok": False,
        "path_text": path_text,
        "path": None,
        "is_directory": False,
        "errors": [],
        "warnings": [],
    }
    if not path_text:
        result["errors"].append("No path was provided.")
        return result

    path = Path(path_text)
    result["path"] = path

    if _is_windows():
        if re.match(r"^[a-zA-Z]:$", path_text):
            result["errors"].append("The path is only a drive letter.")
            return result
        if not (re.match(r"^[a-zA-Z]:[\\/]", path_text) or path_text.startswith("\\\\") or path_text.startswith("/")):
            result["errors"].append(
                "Please provide an absolute path, e.g. C:\\Users\\name\\file.mir"
            )
            return result
        bad = _WINDOWS_ILLEGAL.findall(path.name if path.name else path_text)
        if bad:
            result["errors"].append(
                f"The file name contains invalid character(s): {''.join(set(bad))}"
            )
            return result
        if path.name.upper().split(".")[0] in _WINDOWS_RESERVED:
            result["errors"].append("The file name is a reserved Windows name.")
            return result

    parent = path.parent
    if path_text.endswith(("/", "\\")):
        result["is_directory"] = True
        target_dir = path
    elif path.suffix:
        result["is_directory"] = False
        target_dir = parent
    else:
        result["is_directory"] = True
        target_dir = path

    if not target_dir.exists():
        result["warnings"].append(
            f"The directory does not exist: {target_dir}"
        )
    elif not os.access(str(target_dir), os.W_OK):
        result["errors"].append(f"No write permission for: {target_dir}")
        return result

    if not result["is_directory"] and path.suffix.lower() != config.DEFAULT_MIR_EXTENSION:
        result["warnings"].append(
            f"File extension is {path.suffix or '(none)'}; MIR files usually end "
            f"with {config.DEFAULT_MIR_EXTENSION}."
        )

    if path.exists() and not result["is_directory"]:
        result["warnings"].append(f"The file already exists: {path}")
    elif result["is_directory"] and path.exists():
        result["warnings"].append(f"The directory already exists: {path}")

    result["ok"] = not result["errors"]
    return result
