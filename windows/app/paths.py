from __future__ import annotations

import os
import sys
from pathlib import Path


APP_NAME = "ASR Web Lite"
ROOT = Path(__file__).resolve().parents[1]


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def executable_dir() -> Path:
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return ROOT


def bundle_root() -> Path | None:
    value = getattr(sys, "_MEIPASS", None)
    return Path(value).resolve() if value else None


def resource_candidates(*parts: str) -> list[Path]:
    candidates: list[Path] = []
    root = bundle_root()
    if root:
        candidates.append(root.joinpath(*parts))
    if is_frozen():
        candidates.append(executable_dir().joinpath(*parts))
    candidates.append(ROOT.joinpath(*parts))
    return candidates


def first_existing_resource(*parts: str) -> Path:
    candidates = resource_candidates(*parts)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[-1]


def data_dir() -> Path:
    if not is_frozen():
        return ROOT / "data"
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))
        return base / APP_NAME

    base = Path(os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share"))
    return base / "asr-web-lite"


def user_model_cache() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))
        return base / APP_NAME / "models"
    return Path.home() / ".cache" / "whisper"
