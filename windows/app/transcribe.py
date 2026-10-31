from __future__ import annotations

import importlib
import json
from contextlib import contextmanager
from pathlib import Path
from typing import Callable

from app.audio import standardize_audio
from app.paths import resource_candidates, user_model_cache


ProgressCallback = Callable[..., None]
_MODELS: dict[str, object] = {}


def transcribe_file(
    *,
    input_path: Path,
    work_dir: Path,
    output_path: Path,
    model_name: str,
    language: str | None,
    progress: ProgressCallback,
) -> Path:
    progress(status="running", stage="正在标准化音频", progress=5)
    normalized = standardize_audio(input_path, work_dir / "normalized.wav")

    progress(status="running", stage="正在加载模型，首次运行可能需要几分钟", progress=10, total_segments=0, current_segment=0)

    model = _load_model(model_name)
    options = {
        "fp16": False,
        "verbose": False,
        "task": "transcribe",
    }
    if language:
        options["language"] = language

    progress(status="running", stage="正在转写", progress=12)
    with whisper_progress(progress):
        result = model.transcribe(str(normalized), **options)
    text = (result.get("text") or "").strip()

    progress(status="running", stage="正在合并文本", progress=95)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not text:
        raise RuntimeError("转写结果为空，请检查音频是否有人声或尝试更大的模型。")
    output_path.with_suffix(".json").write_text(
        json.dumps({"segments": result.get("segments", []), "language": result.get("language")},
                   ensure_ascii=False), encoding="utf-8")
    output_path.write_text(text + "\n", encoding="utf-8")
    progress(status="completed", stage="已完成", progress=100, output_path=str(output_path), preview_text=text[-1200:])
    return output_path


def _load_model(model_name: str):
    selected = model_name if model_name in {"tiny", "base", "small", "medium"} else "medium"
    if selected not in _MODELS:
        import whisper

        _MODELS[selected] = whisper.load_model(selected, device="cpu", download_root=str(_model_root()))
    return _MODELS[selected]


def _model_root() -> Path:
    for candidate in resource_candidates("models"):
        if candidate.exists():
            return candidate

    user_cache = user_model_cache()
    user_cache.mkdir(parents=True, exist_ok=True)
    return user_cache


@contextmanager
def whisper_progress(progress: ProgressCallback):
    module = importlib.import_module("whisper.transcribe")
    original = module.tqdm.tqdm
    module.tqdm.tqdm = lambda *args, **kwargs: WhisperProgress(progress, *args, **kwargs)
    try:
        yield
    finally:
        module.tqdm.tqdm = original


class WhisperProgress:
    def __init__(self, progress: ProgressCallback, *args, total: int | None = None, disable: bool = False, **kwargs) -> None:
        self.progress = progress
        self.total = total or 0
        self.disable = disable
        self.n = 0

    def __enter__(self) -> "WhisperProgress":
        if not self.disable:
            self.progress(status="running", stage="正在转写", progress=12)
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    def update(self, amount: int = 1) -> None:
        self.n += amount
        if self.disable:
            return
        if self.total <= 0:
            self.progress(status="running", stage="正在转写", progress=50)
            return
        self.progress(status="running", stage="正在转写", progress=12 + int(min(1.0, self.n / self.total) * 80))

    def refresh(self) -> None:
        return

    def close(self) -> None:
        return
