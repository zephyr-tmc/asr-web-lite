from __future__ import annotations

import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.tasks import TaskStore
from asr_workspace.provider import ChatCompletionsProvider, endpoint_url
from asr_workspace.routes import mount_workspace
from asr_workspace.service import Workspace


class SuccessfulProvider:
    def generate(self, connection, key, snapshot, purpose, length):
        return {"lead": "研究汇报应先明确问题。", "sections": [
            {"title": "明确问题", "body": "让听众理解目标。", "sources": ["S1"]}], "note": "请核对原文。"}


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        self.tasks = TaskStore(self.directory / "tasks.json")
        self.app = FastAPI()
        self.workspace = mount_workspace(self.app, self.directory, self.tasks)
        self.workspace.provider = SuccessfulProvider()
        self.client = TestClient(self.app, base_url="http://127.0.0.1")

    def tearDown(self):
        self.workspace.executor.shutdown(wait=True)
        self.client.close()
        self.temp.cleanup()

    def create(self, text="先明确问题。\n\n再用例子说明。"):
        response = self.client.post("/api/workspace/documents", json={"title": "演讲稿", "text": text})
        self.assertEqual(response.status_code, 201)
        return response.json()

    def configure(self):
        response = self.client.put("/api/workspace/connection", json={
            "name": "测试连接", "endpoint": "http://127.0.0.1:9999/v1", "model": "fixture-model", "key": "private-test-token"})
        self.assertEqual(response.status_code, 200)
        return response

    def submit(self, doc):
        response = self.client.post("/api/workspace/generations", json={"document_id": doc["id"], "version": doc["version"]})
        self.assertEqual(response.status_code, 202, response.text)
        return response.json()

    def wait(self, job):
        for _ in range(100):
            value = self.client.get("/api/workspace/generations/" + job["id"]).json()
            if value["status"] not in {"queued", "running"}:
                return value
            time.sleep(.01)
        self.fail("Generation did not settle")

    def test_document_versions_and_saved_results_survive_restart(self):
        doc = self.create()
        self.configure()
        job = self.wait(self.submit(doc))
        self.assertEqual(job["status"], "completed")
        self.assertIn("依据文稿 v1", job["markdown"])
        self.assertEqual(self.client.get("/api/workspace/generations/" + job["id"] + "/download").text, job["markdown"])
        saved = self.client.put("/api/workspace/generations/" + job["id"], json={"text": "我的修改", "revision": 0})
        self.assertEqual(saved.status_code, 200)
        updated = self.client.put("/api/workspace/documents/" + doc["id"], json={"title": "已校对", "text": "新的表达", "version": 1})
        self.assertEqual(updated.json()["version"], 2)
        self.assertEqual(self.client.put("/api/workspace/documents/" + doc["id"], json={"title": "旧页面", "text": "过时", "version": 1}).status_code, 400)
        restarted = Workspace(self.directory)
        try:
            stored = restarted.get("job", job["id"])
            self.assertEqual(stored["snapshot"]["segments"][0]["text"], "先明确问题。")
            self.assertEqual(stored["edited_text"], "我的修改")
            self.assertEqual(restarted.public_document(restarted.get("document", doc["id"]))["version"], 2)
            self.assertFalse(restarted.config()["has_key"])
        finally:
            restarted.executor.shutdown()
        export = self.client.get("/api/workspace/generations/" + job["id"] + "/download")
        self.assertEqual(export.text, "我的修改")

    def test_configuration_never_returns_or_persists_key(self):
        response = self.configure()
        self.assertNotIn("private-test-token", response.text)
        self.assertNotIn(b"private-test-token", self.workspace.path.read_bytes())
        self.assertTrue(response.json()["has_key"])
        response = self.client.put("/api/workspace/connection", json={"name": "另一服务", "model": "x", "endpoint": "http://127.0.0.1:9988/v1"})
        self.assertFalse(response.json()["has_key"])

    def test_rejects_cross_origin_and_rebinding_host(self):
        path = "/api/workspace/documents"
        self.assertEqual(self.client.get(path, headers={"Host": "untrusted.example"}).status_code, 403)
        self.assertEqual(self.client.post(path, json={"title": "x", "text": "x"}, headers={"Origin": "https://untrusted.example"}).status_code, 403)

    def test_validation_error_does_not_echo_credentials(self):
        response = self.client.put("/api/workspace/connection", json={"name": "x", "endpoint": "https://example.invalid/v1", "model": "x", "key": "private-marker" * 500})
        self.assertEqual(response.status_code, 422)
        self.assertNotIn("private-marker", response.text)

    def test_reordered_and_rewritten_text_does_not_invent_audio_positions(self):
        doc = self.workspace.create_document("时间稿", "第一段\n\n第二段", segments=[
            {"text": "第一段", "start": 0, "end": 10}, {"text": "第二段", "start": 60, "end": 70}])
        swapped = self.workspace.update_document(doc["id"], "时间稿", "第二段\n\n第一段", 1)
        self.assertEqual([s["start"] for s in swapped["segments"]], [60, 0])
        changed = self.workspace.update_document(doc["id"], "时间稿", "完全改写\n\n第一段", 2)
        self.assertIsNone(changed["segments"][0]["start"])
        self.assertEqual(changed["segments"][1]["start"], 0)

    def test_repeated_paragraphs_do_not_match_the_wrong_occurrence(self):
        doc = self.workspace.create_document("重复段落", "好的。\n\n主题。\n\n好的。", segments=[
            {"text": "好的。", "start": 0, "end": 5}, {"text": "主题。", "start": 30, "end": 35},
            {"text": "好的。", "start": 60, "end": 65}])
        updated = self.workspace.update_document(doc["id"], "重复段落", "主题。\n\n好的。", 1)
        self.assertEqual(updated["segments"][0]["start"], 30)
        self.assertIsNone(updated["segments"][1]["start"])

    def test_generation_requires_configuration_and_never_truncates(self):
        doc = self.create()
        self.assertEqual(self.client.post("/api/workspace/generations", json={"document_id": doc["id"], "version": 1}).status_code, 400)
        self.configure()
        large = self.create("长" * 32_001)
        response = self.client.post("/api/workspace/generations", json={"document_id": large["id"], "version": 1})
        self.assertEqual(response.status_code, 400)
        self.assertIn("32,000", response.text)

    def test_cancellation_does_not_late_overwrite_result(self):
        started, release = threading.Event(), threading.Event()
        class SlowProvider(SuccessfulProvider):
            def generate(self, *args):
                started.set()
                release.wait(3)
                return super().generate(*args)
        self.workspace.provider = SlowProvider()
        self.configure()
        doc = self.create()
        job = self.submit(doc)
        self.assertTrue(started.wait(2))
        self.client.post("/api/workspace/generations/" + job["id"] + "/cancel")
        release.set()
        self.workspace.executor.shutdown(wait=True)
        stored = self.client.get("/api/workspace/generations/" + job["id"]).json()
        self.assertEqual(stored["status"], "cancelled")
        self.assertIsNone(stored["result"])
        self.assertEqual(self.client.get("/api/workspace/documents/" + doc["id"]).status_code, 200)

    def test_existing_transcript_import_is_idempotent_and_keeps_timing(self):
        audio = self.directory / "source.wav"
        audio.write_bytes(b"fixture")
        output = self.directory / "source.txt"
        output.write_text("准确的文稿", encoding="utf-8")
        output.with_suffix(".json").write_text(json.dumps({"segments": [{"start": 2.5, "end": 6, "text": "准确的文稿"}]}))
        task = self.tasks.create(filename="录音.wav", model="base", upload_path=audio)
        self.tasks.update(task["id"], status="completed", output_path=str(output))
        path = "/api/workspace/from-task/" + task["id"]
        first, second = self.client.post(path).json(), self.client.post(path).json()
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(first["segments"][0]["start"], 2.5)
        self.assertEqual(self.client.get("/api/workspace/documents/" + first["id"] + "/audio").content, b"fixture")


class ProviderTests(unittest.TestCase):
    def test_provider_sends_snapshot_and_filters_nonexistent_sources(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, limit):
                content = {"lead": "核心", "sections": [{"title": "标题", "body": "内容", "sources": ["S1", "S999"]}], "note": ""}
                return json.dumps({"choices": [{"message": {"content": json.dumps(content)}}]}).encode()
        class Opener:
            def open(self, req, timeout):
                self.req = req
                return Response()
        opener = Opener()
        with patch("asr_workspace.provider.build_opener", return_value=opener):
            result = ChatCompletionsProvider().generate({"endpoint": "https://model.example/v1/chat/completions", "model": "chosen-model"}, "secret", {"segments": [{"id": "S1", "text": "真实资料"}]}, "analysis", "brief")
        request = json.loads(opener.req.data)
        self.assertEqual(request["model"], "chosen-model")
        self.assertIn("真实资料", request["messages"][1]["content"])
        self.assertEqual(opener.req.headers["Authorization"], "Bearer secret")
        self.assertEqual(result["sections"][0]["sources"], ["S1"])
        self.assertIn("已移除", result["note"])

    def test_endpoint_rejects_credential_query_and_insecure_remote(self):
        for value in ["https://model.example/v1?key=secret", "http://model.example/v1", "file:///etc/passwd", "https://user:secret@model.example/v1"]:
            with self.assertRaises(ValueError): endpoint_url(value)
        self.assertEqual(endpoint_url("http://127.0.0.1:11434/v1"), "http://127.0.0.1:11434/v1/chat/completions")


if __name__ == "__main__":
    unittest.main()
