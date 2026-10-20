from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


SUPPORTED_SUFFIXES = {".mp3", ".wav", ".m4a"}


def require_ffmpeg() -> tuple[str, str]:
    ffmpeg = _find_tool("ffmpeg")
    ffprobe = _find_tool("ffprobe")
    if not ffmpeg or not ffprobe:
        raise RuntimeError("未检测到 ffmpeg/ffprobe。请先安装 ffmpeg，或使用后续内置 ffmpeg 的打包版。")
    _prepend_to_path(Path(ffmpeg).resolve().parent)
    return ffmpeg, ffprobe


def ffmpeg_status() -> dict[str, object]:
    ffmpeg = _find_tool("ffmpeg")
    ffprobe = _find_tool("ffprobe")
    if ffmpeg:
        _prepend_to_path(Path(ffmpeg).resolve().parent)
    return {
        "ffmpeg": ffmpeg,
        "ffprobe": ffprobe,
        "path_head": os.environ.get("PATH", "").split(os.pathsep)[:6],
    }


def _find_tool(name: str) -> str | None:
    candidates = []
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        bundle_path = Path(bundle_root)
        candidates.append(bundle_path / "bin" / name)
        candidates.append(bundle_path.parent / "Frameworks" / "bin" / name)
    if getattr(sys, "frozen", False):
        contents_dir = Path(sys.executable).resolve().parents[1]
        candidates.append(contents_dir / "Frameworks" / "bin" / name)
    candidates.append(Path(__file__).resolve().parents[1] / "bin" / name)
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return shutil.which(name)


def _prepend_to_path(directory: Path) -> None:
    path = os.environ.get("PATH", "")
    entries = [entry for entry in path.split(os.pathsep) if entry]
    directory_text = str(directory)
    if directory_text not in entries:
        os.environ["PATH"] = directory_text + os.pathsep + path if path else directory_text


def validate_audio_file(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ValueError("仅支持 mp3、wav、m4a 三种音频格式。")
    return suffix


def standardize_audio(input_path: Path, output_path: Path) -> Path:
    ffmpeg, _ = require_ffmpeg()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        ffmpeg,
        "-y",
        "-i",
        str(input_path),
        "-vn",
        "-acodec",
        "pcm_s16le",
        "-ar",
        "16000",
        "-ac",
        "1",
        str(output_path),
    ]
    _run(command, "音频标准化失败")
    return output_path


def split_audio(input_path: Path, chunks_dir: Path, *, segment_seconds: int = 600) -> list[Path]:
    ffmpeg, _ = require_ffmpeg()
    chunks_dir.mkdir(parents=True, exist_ok=True)
    pattern = chunks_dir / "chunk-%03d.wav"
    command = [
        ffmpeg,
        "-y",
        "-i",
        str(input_path),
        "-f",
        "segment",
        "-segment_time",
        str(segment_seconds),
        "-c",
        "copy",
        str(pattern),
    ]
    _run(command, "音频切片失败")
    chunks = sorted(chunks_dir.glob("chunk-*.wav"))
    if not chunks:
        raise RuntimeError("音频切片失败：没有生成任何片段。")
    return chunks


def _run(command: list[str], message: str) -> None:
    result = subprocess.run(command, capture_output=True, encoding="utf-8", check=False)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(f"{message}：{detail or '未知错误'}")
