from __future__ import annotations

import re
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from asr_workspace.routes import mount_workspace

from app.audio import ffmpeg_status, validate_audio_file
from app.paths import data_dir, first_existing_resource
from app.tasks import TaskStore
from app.transcribe import transcribe_file


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = data_dir()
UPLOADS_DIR = DATA_DIR / "uploads"
WORK_DIR = DATA_DIR / "work"
OUTPUTS_DIR = DATA_DIR / "outputs"
STATIC_DIR = (first_existing_resource("app", "static") if getattr(sys, "frozen", False)
              else Path(__file__).resolve().parents[2] / "app" / "static")
MAX_UPLOAD_BYTES = 500 * 1024 * 1024
MODELS = {"tiny", "base", "small", "medium"}
LANGUAGES = {"auto": None, "ja": "ja", "zh": "zh", "en": "en"}

for directory in [UPLOADS_DIR, WORK_DIR, OUTPUTS_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

store = TaskStore(DATA_DIR / "tasks.json")
executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="asr-task")
app = FastAPI(title="ASR Web Lite")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
store.mark_unfinished_interrupted()
workspace = mount_workspace(app, DATA_DIR, store)


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/workspace")
def workspace_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "workspace.html")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/ffmpeg")
def get_ffmpeg_status() -> dict:
    return ffmpeg_status()


@app.get("/api/tasks")
def list_tasks() -> dict:
    return {"items": store.list()}


@app.get("/api/tasks/{task_id}")
def get_task(task_id: str) -> dict:
    task = store.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task


@app.post("/api/transcribe")
async def create_task(file: UploadFile, model: str = Form("medium"), language: str = Form("auto")) -> JSONResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="请选择音频文件")
    if model not in MODELS:
        raise HTTPException(status_code=400, detail="模型只能选择 tiny、base、small 或 medium")
    if language not in LANGUAGES:
        raise HTTPException(status_code=400, detail="语言只能选择自动、日语、中文或英语")
    try:
        suffix = validate_audio_file(file.filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    safe_name = _safe_filename(Path(file.filename).stem) + suffix
    upload_path = UPLOADS_DIR / f"{Path(safe_name).stem}-{_short_id()}{suffix}"
    size = 0
    with upload_path.open("wb") as output:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_UPLOAD_BYTES:
                output.close()
                upload_path.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail="文件过大，第一版限制单文件最大 500MB")
            output.write(chunk)

    task = store.create(filename=file.filename, model=model, upload_path=upload_path)
    task = store.update(task["id"], language=language) or task
    executor.submit(_run_task, task["id"], upload_path, model)
    return JSONResponse(task)


@app.post("/api/tasks/{task_id}/retry")
def retry_task(task_id: str) -> JSONResponse:
    task = store.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    upload_path = Path(task.get("upload_path") or "")
    if not upload_path.exists():
        raise HTTPException(status_code=404, detail="原始上传文件不存在，无法重新转写")
    model = task.get("model") if task.get("model") in MODELS else "medium"
    store.update(
        task_id,
        status="queued",
        stage="等待处理",
        progress=0,
        output_path="",
        error="",
        current_segment=0,
        total_segments=0,
        preview_text="",
    )
    executor.submit(_run_task, task_id, upload_path, model)
    updated = store.get(task_id)
    return JSONResponse(updated or {"id": task_id})


@app.get("/api/tasks/{task_id}/download")
def download_result(task_id: str) -> FileResponse:
    task = store.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.get("status") != "completed" or not task.get("output_path"):
        raise HTTPException(status_code=400, detail="任务尚未完成")
    output_path = Path(task["output_path"])
    if not output_path.exists():
        raise HTTPException(status_code=404, detail="结果文件不存在")
    return FileResponse(output_path, filename=output_path.name, media_type="text/plain; charset=utf-8")


def _run_task(task_id: str, upload_path: Path, model: str) -> None:
    task_work_dir = WORK_DIR / task_id
    output_path = OUTPUTS_DIR / f"{upload_path.stem}.txt"
    task = store.get(task_id) or {}
    language_value = LANGUAGES.get(task.get("language") or "auto")

    def progress(**changes) -> None:
        if changes.get("status") in {"queued", "running", "completed"}:
            changes.setdefault("error", "")
        store.update(task_id, **changes)

    try:
        progress(status="running", stage="正在准备任务", progress=1)
        transcribe_file(
            input_path=upload_path,
            work_dir=task_work_dir,
            output_path=output_path,
            model_name=model,
            language=language_value,
            progress=progress,
        )
    except Exception as exc:
        store.update(task_id, status="failed", stage="失败", error=str(exc), progress=0)
    finally:
        if task_work_dir.exists():
            shutil.rmtree(task_work_dir, ignore_errors=True)


def _safe_filename(value: str) -> str:
    cleaned = re.sub(r"[^\w.-]+", "-", value, flags=re.UNICODE).strip("-._")
    return cleaned or "audio"


def _short_id() -> str:
    from uuid import uuid4

    return uuid4().hex[:8]


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8765, reload=False)
