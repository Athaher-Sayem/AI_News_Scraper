"""Regression and integration checks added during the roadmap review."""

import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
from unittest.mock import patch

import pandas as pd
from django.test import SimpleTestCase

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
