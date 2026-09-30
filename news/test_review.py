"""Regression and integration checks added during the roadmap review."""

import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
from unittest.mock import patch

import pandas as pd
from django.test import SimpleTestCase, override_settings

from pipeline import flow


class PathBoundaryTests(SimpleTestCase):
    def test_api_rejects_unsafe_paths_before_submitting_work(self):
        for field in ("input", "output"):
            for path in ("Main.py", ".env", "db.sqlite3", ".git/config", "data",
                         "data/not_csv.py", "data/../config/settings.py", "", "data/x\x00.csv",
                         "data/file.csv:stream.csv", "../escape.csv"):
                with self.subTest(field=field, path=path), patch("news.api.jobs.submit") as submit:
                    response = self.client.post("/api/v1/pipeline/runs/",
                                                json.dumps({field: path}), content_type="application/json")
                    self.assertEqual(response.status_code, 400)
                    self.assertEqual(response.json()["error"]["code"], "invalid_path")
                    submit.assert_not_called()

    def test_flow_accepts_csv_and_rejects_raw_hardlink_before_work(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = root / "data"
            data.mkdir()
            source = data / "input.csv"
            output = data / "output.csv"
            raw = data / "news_data.csv"
            raw.write_text("title\noriginal\n", encoding="utf-8")
            pd.DataFrame([{"title": "Example", "content": "short", "source": "Fixture",
                           "url": "https://example.com/story"}]).to_csv(source, index=False)
            with patch.object(flow, "BASE_DIR", root), patch.object(flow, "RAW_CSV_PATH", raw):
                with contextlib.redirect_stdout(io.StringIO()):
                    result = flow.run_flow(source, output)
                self.assertEqual(result.iloc[0]["status"], "CONTENT_REJECTED")
                self.assertEqual(pd.read_csv(output).iloc[0]["title"], "Example")
                os.link(raw, data / "alias.csv")
                with patch.object(flow, "collect_news") as scrape, self.assertRaises(ValueError):
                    flow.run_flow(source, data / "alias.csv", scrape=True)
                scrape.assert_not_called()
                self.assertEqual(raw.read_text(encoding="utf-8"), "title\noriginal\n")


class RequestBoundaryTests(SimpleTestCase):
    def test_malformed_requests_never_submit_work(self):
        cases = [(b'{"limit": "\xff"}', "application/json", 400, "invalid_json"),
                 (b"[]", "application/json", 400, "invalid_json"),
                 (b"{}", "application/jsonp", 415, "unsupported_media_type")]
        with patch("news.api.jobs.submit") as submit:
            for body, content_type, status, code in cases:
                with self.subTest(body=body, content_type=content_type):
                    response = self.client.post("/api/v1/pipeline/runs/", body, content_type=content_type)
                    self.assertEqual(response.status_code, status)
                    self.assertEqual(response.json()["error"]["code"], code)
            submit.assert_not_called()

    @override_settings(NEWS_API_KEY="test-key")
    def test_unicode_invalid_api_key_returns_401(self):
        response = self.client.get("/api/v1/pipeline/runs/", headers={"X-API-Key": "clé"})
        self.assertEqual(response.status_code, 401)

    def test_internal_type_errors_are_not_misreported_as_client_errors(self):
        with patch("news.api.services.list_articles", side_effect=TypeError("private internal detail")):
            with self.assertLogs("news.api.http", level="ERROR"):
                response = self.client.get("/api/v1/articles/")
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()["error"]["code"], "internal_error")
        self.assertNotIn("private", response.content.decode())

    def test_valid_json_charset_and_key_reach_the_handler(self):
        from news.api.jobs import PipelineJob

        with override_settings(NEWS_API_KEY="test-key"), patch("news.api.jobs.submit") as submit:
            submit.return_value = PipelineJob({"limit": 1})
            response = self.client.post("/api/v1/pipeline/runs/", b'{"limit": 1}',
                                        content_type="application/json; charset=utf-8",
                                        headers={"X-API-Key": "test-key"})
            self.assertEqual(response.status_code, 202)
            self.assertEqual(submit.call_args.args[0]["limit"], 1)
