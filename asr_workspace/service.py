from __future__ import annotations

import json
import re
import sqlite3
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from asr_workspace.provider import ChatCompletionsProvider, ProviderError, endpoint_url


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def text_segments(text: str) -> list[dict]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]
    pieces = [p[i:i + 1500] for p in paragraphs for i in range(0, len(p), 1500)]
    return [{"id": f"S{i + 1}", "text": p, "start": None, "end": None} for i, p in enumerate(pieces)]


def markdown(job: dict) -> str:
    if job.get("edited_text") is not None:
        return job["edited_text"]
    data = job["result"]
    parts = ["# " + ("要点总结" if job["purpose"] == "summary" else "结构分析"), data["lead"]]
    for section in data["sections"]:
        parts += ["## " + section["title"], section["body"], "原文：" + "、".join(section["sources"])]
    parts += [data["note"], f"依据文稿 v{job['version']} · 模型 {job['model']}"]
    return "\n\n".join(p for p in parts if p) + "\n"


class Workspace:
    """Durable document snapshots and independent, cancellable generation jobs."""

    def __init__(self, directory: Path, provider=None):
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / "workspace.sqlite3"
        self.lock = threading.RLock()
        self.key = ""
        self.provider = provider or ChatCompletionsProvider()
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="text-generation")
        self.slots = threading.BoundedSemaphore(8)
        with self.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS records (kind TEXT, id TEXT, payload TEXT NOT NULL, PRIMARY KEY(kind,id))")
        for job in self.list("job"):
            if job["status"] in {"queued", "running"}:
                job.update(status="failed", error="服务已重启，请重新生成。")
                self.put("job", job)

    def connect(self):
        return sqlite3.connect(self.path, timeout=15)

    def put(self, kind: str, value: dict) -> dict:
        with self.lock, self.connect() as db:
            db.execute("INSERT OR REPLACE INTO records VALUES (?,?,?)", (kind, value["id"], json.dumps(value, ensure_ascii=False)))
        return value

    def get(self, kind: str, identifier: str) -> dict:
        with self.lock, self.connect() as db:
            row = db.execute("SELECT payload FROM records WHERE kind=? AND id=?", (kind, identifier)).fetchone()
        if row is None:
            raise KeyError(identifier)
        return json.loads(row[0])

    def list(self, kind: str) -> list[dict]:
        with self.lock, self.connect() as db:
            rows = db.execute("SELECT payload FROM records WHERE kind=? ORDER BY rowid DESC", (kind,)).fetchall()
        values = [json.loads(row[0]) for row in rows]
        return sorted(values, key=lambda v: v.get("created_at", v.get("updated_at", "")), reverse=True)

    def config(self) -> dict:
        with self.lock:
            try:
                value = self.get("config", "default")
            except KeyError:
                value = {"id": "default", "name": "", "endpoint": "", "model": ""}
            return {**value, "has_key": bool(self.key), "configured": bool(value["endpoint"] and value["model"])}

    def configure(self, name: str, endpoint: str, model: str, key: str | None) -> dict:
        endpoint = endpoint_url(endpoint)
        if not name.strip() or not model.strip():
            raise ValueError("请填写连接名称和模型名。")
        if key is not None and (not key.isascii() or any(ord(c) < 32 for c in key)):
            raise ValueError("密钥格式无效。")
        with self.lock:
            previous = self.config()
            if endpoint != previous["endpoint"]:
                self.key = ""
            if key is not None:
                self.key = key.strip()
            self.put("config", {"id": "default", "name": name.strip(), "endpoint": endpoint, "model": model.strip()})
            return self.config()

    def create_document(self, title: str, text: str, *, segments: list | None = None,
                        audio: str | None = None, task_id: str | None = None) -> dict:
        if not title.strip() or not text.strip():
            raise ValueError("文稿不能为空。")
        with self.lock:
            if task_id:
                for doc in self.list("document"):
                    if doc.get("task_id") == task_id:
                        return self.public_document(doc)
            parts = text_segments(text)
            if segments:
                parts = [{"id": f"S{i + 1}", "text": str(s.get("text", "")).strip(),
                          "start": s.get("start"), "end": s.get("end")} for i, s in enumerate(segments) if str(s.get("text", "")).strip()]
            snapshot = {"version": 1, "segments": parts, "created_at": now()}
            doc = {"id": uuid4().hex, "title": title.strip(), "versions": [snapshot], "audio": audio,
                   "task_id": task_id, "updated_at": now()}
            self.put("document", doc)
            return self.public_document(doc)

    @staticmethod
    def public_document(doc: dict) -> dict:
        current = doc["versions"][-1]
        return {"id": doc["id"], "title": doc["title"], "updated_at": doc["updated_at"],
                "has_audio": bool(doc.get("audio")), **current}

    @staticmethod
    def public_job(job: dict) -> dict:
        return {**job, "markdown": markdown(job) if job["status"] == "completed" else None}

    def update_document(self, identifier: str, title: str, text: str, version: int) -> dict:
        if not title.strip() or not text.strip():
            raise ValueError("文稿不能为空。")
        with self.lock:
            doc = self.get("document", identifier)
            old = doc["versions"][-1]
            if old["version"] != version:
                raise ValueError("文稿已在其它窗口更新，请刷新后再修改。")
            parts = text_segments(text)
            # Text identity is evidence of timing; paragraph position alone is not.
            unchanged = {}
            for original in old["segments"]:
                unchanged.setdefault(original["text"], []).append(original)
            if [p["text"] for p in parts] == [p["text"] for p in old["segments"]]:
                for part, original in zip(parts, old["segments"]):
                    part.update(start=original["start"], end=original["end"])
            else:
                counts = Counter(part["text"] for part in parts)
                for part in parts:
                    matches = unchanged.get(part["text"], [])
                    if len(matches) == 1 and counts[part["text"]] == 1:
                        original = matches[0]
                        part.update(start=original["start"], end=original["end"])
            doc["versions"].append({"version": version + 1, "segments": parts, "created_at": now()})
            doc.update(title=title.strip(), updated_at=now())
            self.put("document", doc)
            return self.public_document(doc)

    def submit(self, identifier: str, version: int, purpose: str, length: str) -> dict:
        with self.lock:
            config = self.config()
            if not config["configured"]:
                raise ValueError("请先配置模型连接。")
            snapshot = self.get("document", identifier)["versions"][-1]
            if snapshot["version"] != version:
                raise ValueError("文稿已更新，请刷新后生成。")
            if sum(len(s["text"]) for s in snapshot["segments"]) > 32_000:
                raise ValueError("首版单次生成最多 32,000 字符，请将长文分段导入后处理。")
            if not self.slots.acquire(blocking=False):
                raise ValueError("生成任务较多，请等待当前任务完成后重试。")
            job = {"id": uuid4().hex, "document_id": identifier, "version": version, "snapshot": snapshot,
                   "purpose": purpose, "length": length, "model": config["model"], "connection_name": config["name"],
                   "status": "queued", "error": "", "result": None, "edited_text": None,
                   "edit_revision": 0, "created_at": now(), "updated_at": now()}
            try:
                self.put("job", job)
                self.executor.submit(self.run, job["id"], config, self.key)
            except Exception:
                self.slots.release()
                raise
            return job

    def run(self, identifier: str, config: dict, key: str) -> None:
        try:
            with self.lock:
                job = self.get("job", identifier)
                if job["status"] == "cancelled":
                    return
                job["status"] = "running"
                self.put("job", job)
            try:
                result = self.provider.generate(config, key, job["snapshot"], job["purpose"], job["length"])
                status, error = "completed", ""
            except ProviderError as exc:
                result, status, error = None, "failed", str(exc)
            except Exception:
                result, status, error = None, "failed", "生成失败，文稿已保留，请检查模型配置后重试。"
            with self.lock:
                current = self.get("job", identifier)
                if current["status"] == "cancelled":
                    return
                current.update(status=status, result=result, error=error, updated_at=now())
                self.put("job", current)
        finally:
            self.slots.release()

    def cancel(self, identifier: str) -> dict:
        with self.lock:
            job = self.get("job", identifier)
            if job["status"] in {"queued", "running"}:
                job.update(status="cancelled", updated_at=now())
                self.put("job", job)
            return job

    def edit_result(self, identifier: str, text: str, revision: int) -> dict:
        with self.lock:
            job = self.get("job", identifier)
            if job["status"] != "completed":
                raise ValueError("任务尚未完成。")
            if revision != job["edit_revision"]:
                raise ValueError("结果已被更新，请刷新后编辑。")
            job.update(edited_text=text.strip(), edit_revision=revision + 1, updated_at=now())
            self.put("job", job)
            return job
