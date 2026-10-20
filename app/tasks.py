from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path
from uuid import uuid4


class TaskStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("[]\n", encoding="utf-8")

    def create(self, *, filename: str, model: str, upload_path: Path) -> dict:
        now = datetime.now().isoformat(timespec="seconds")
        task = {
            "id": uuid4().hex,
            "filename": filename,
            "model": model,
            "status": "queued",
            "stage": "等待处理",
            "progress": 0,
            "created_at": now,
            "updated_at": now,
            "upload_path": str(upload_path),
            "output_path": "",
            "error": "",
            "current_segment": 0,
            "total_segments": 0,
        }
        with self._lock:
            tasks = self._read_unlocked()
            tasks.insert(0, task)
            self._write_unlocked(tasks[:50])
        return task

    def update(self, task_id: str, **changes) -> dict | None:
        with self._lock:
            tasks = self._read_unlocked()
            for task in tasks:
                if task["id"] == task_id:
                    task.update(changes)
                    task["updated_at"] = datetime.now().isoformat(timespec="seconds")
                    self._write_unlocked(tasks)
                    return task
        return None

    def get(self, task_id: str) -> dict | None:
        with self._lock:
            for task in self._read_unlocked():
                if task["id"] == task_id:
                    return task
        return None

    def list(self) -> list[dict]:
        with self._lock:
            return self._read_unlocked()

    def mark_unfinished_interrupted(self) -> None:
        with self._lock:
            tasks = self._read_unlocked()
            changed = False
            for task in tasks:
                if task.get("status") in {"queued", "running"}:
                    task["status"] = "failed"
                    task["stage"] = "已中断，可重试"
                    task["error"] = "服务已重启或退出，任务未完成。请点击重新转写。"
                    task["updated_at"] = datetime.now().isoformat(timespec="seconds")
                    changed = True
            if changed:
                self._write_unlocked(tasks)

    def remove_where(self, predicate) -> None:
        with self._lock:
            tasks = [task for task in self._read_unlocked() if not predicate(task)]
            self._write_unlocked(tasks)

    def _read_unlocked(self) -> list[dict]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, FileNotFoundError):
            return []
        return data if isinstance(data, list) else []

    def _write_unlocked(self, tasks: list[dict]) -> None:
        self.path.write_text(json.dumps(tasks, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
