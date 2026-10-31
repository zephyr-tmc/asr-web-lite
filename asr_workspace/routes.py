from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel, Field

from asr_workspace.service import Workspace, markdown


class DocumentInput(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1, max_length=500_000)


class DocumentEdit(DocumentInput):
    version: int = Field(ge=1)


class ConnectionInput(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    endpoint: str = Field(min_length=1, max_length=2000)
    model: str = Field(min_length=1, max_length=200)
    key: str | None = Field(default=None, max_length=4096)


class GenerationInput(BaseModel):
    document_id: str
    version: int = Field(ge=1)
    purpose: Literal["summary", "analysis"] = "summary"
    length: Literal["brief", "standard"] = "standard"


class ResultEdit(BaseModel):
    text: str = Field(min_length=1, max_length=500_000)
    revision: int = Field(ge=0)


def mount_workspace(app: FastAPI, directory: Path, task_store) -> Workspace:
    workspace = Workspace(directory)
    app.state.workspace = workspace
    router = APIRouter(prefix="/api/workspace")

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        if request.url.path.startswith("/api/workspace"):
            return JSONResponse({"detail": "输入格式有误、内容过长或缺少必要字段。"}, status_code=422)
        return await request_validation_exception_handler(request, exc)

    @app.middleware("http")
    async def local_workspace(request: Request, call_next):
        if request.url.path.startswith("/api/workspace"):
            origin = request.headers.get("origin")
            if (request.url.hostname not in {"localhost", "127.0.0.1", "::1"}
                    or (origin and origin != str(request.base_url).rstrip("/"))):
                return JSONResponse({"detail": "文稿工作室仅接受本机同来源请求。"}, status_code=403)
        return await call_next(request)

    def invoke(function, *args, **kwargs):
        try:
            return function(*args, **kwargs)
        except KeyError:
            raise HTTPException(404, "文稿或结果不存在") from None
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from None

    @router.get("/connection")
    def connection():
        return workspace.config()

    @router.put("/connection")
    def configure(value: ConnectionInput):
        return invoke(workspace.configure, value.name, value.endpoint, value.model, value.key)

    @router.get("/documents")
    def list_documents():
        return {"items": [workspace.public_document(d) for d in workspace.list("document")]}

    @router.post("/documents", status_code=201)
    def create_document(value: DocumentInput):
        return invoke(workspace.create_document, value.title, value.text)

    @router.get("/documents/{identifier}")
    def document(identifier: str):
        return workspace.public_document(invoke(workspace.get, "document", identifier))

    @router.put("/documents/{identifier}")
    def update_document(identifier: str, value: DocumentEdit):
        return invoke(workspace.update_document, identifier, value.title, value.text, value.version)

    @router.get("/documents/{identifier}/audio")
    def audio(identifier: str):
        doc = invoke(workspace.get, "document", identifier)
        path = Path(doc.get("audio") or "")
        if not path.is_file():
            raise HTTPException(404, "原始音频不存在")
        return FileResponse(path)

    @router.post("/from-task/{identifier}")
    def import_task(identifier: str):
        task = task_store.get(identifier)
        if not task:
            raise HTTPException(404, "转写任务不存在")
        output = Path(task.get("output_path") or "")
        if task.get("status") != "completed" or not output.is_file():
            raise HTTPException(400, "请先完成转写")
        sidecar = output.with_suffix(".json")
        segments = None
        if sidecar.is_file():
            try:
                segments = json.loads(sidecar.read_text(encoding="utf-8")).get("segments")
            except (ValueError, OSError):
                pass
        return invoke(workspace.create_document, task["filename"], output.read_text(encoding="utf-8"),
                      segments=segments, audio=task.get("upload_path"), task_id=identifier)

    @router.get("/generations")
    def list_generations(document_id: str):
        invoke(workspace.get, "document", document_id)
        return {"items": [workspace.public_job(j) for j in workspace.list("job") if j["document_id"] == document_id]}

    @router.post("/generations", status_code=202)
    def generate(value: GenerationInput):
        return invoke(workspace.submit, value.document_id, value.version, value.purpose, value.length)

    @router.get("/generations/{identifier}")
    def generation(identifier: str):
        return workspace.public_job(invoke(workspace.get, "job", identifier))

    @router.post("/generations/{identifier}/cancel")
    def cancel(identifier: str):
        return workspace.public_job(invoke(workspace.cancel, identifier))

    @router.put("/generations/{identifier}")
    def save(identifier: str, value: ResultEdit):
        if not value.text.strip():
            raise HTTPException(400, "结果不能为空")
        return workspace.public_job(invoke(workspace.edit_result, identifier, value.text, value.revision))

    @router.get("/generations/{identifier}/download")
    def download(identifier: str):
        job = invoke(workspace.get, "job", identifier)
        if job["status"] != "completed":
            raise HTTPException(400, "结果尚未生成")
        return Response(markdown(job), media_type="text/markdown; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="summary-{identifier[:8]}.md"'})

    app.include_router(router)
    return workspace
