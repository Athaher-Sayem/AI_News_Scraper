"""End-to-end application flow with deterministic external-service fixtures.

The HTML/browser boundary, embedding encoder, and generation HTTP responses are
substituted. Parsers, all four source configurations, ORM, CSV IO, clustering,
CLI, pipeline stages, real background jobs, API serialization and templates run.
"""

import contextlib
import io
from itertools import cycle
import json
import sys
from pathlib import Path
import tempfile
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

from django.test import TestCase
import numpy as np
import pandas as pd

import Main
from news.api import jobs
from news.models import News
from news.test_scraper import CATEGORY_HTML, fixture_page
from pipeline import flow


class CompleteWorkflowTests(TestCase):
    def test_collection_cli_and_background_api_success_and_failure(self):
        jobs.reset()
        self.addCleanup(jobs.reset)
        collect_news, deduplicate_news = flow.collect_news, flow.deduplicate_news
        encoder = ModuleType("sentence_transformers")
        encoder.SentenceTransformer = lambda name: SimpleNamespace(
            encode=lambda titles, **kwargs: np.tile([1.0, 0.0], (len(titles), 1))
        )
        category = fixture_page(CATEGORY_HTML.replace(
            "</main>", '<h2><a href="/second-story">Another link to the same news event</a></h2></main>'
        ))
        article = fixture_page()

        def generated(text):
            result = Mock()
            result.json.return_value = {"response": text, "done": True}
            return result

        replies = [generated('{"what":"A training programme was announced"}'),
                   generated("HEADLINE: Training announcement\nARTICLE: Students will receive training."),
                   generated('{"approved":true,"errors":[],"invented_facts":[]}')]
        bad = Mock()
        bad.json.return_value = {"error": "Generation service unavailable"}

        with tempfile.TemporaryDirectory(prefix="workflow-test-", dir=flow.BASE_DIR / "data") as directory:
            raw, unique, output = (Path(directory) / name for name in ("raw.csv", "unique.csv", "processed.csv"))
            with contextlib.ExitStack() as stack:
                stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
                previous_encoder = sys.modules.get("sentence_transformers")
                sys.modules["sentence_transformers"] = encoder
                def restore_encoder():
                    if previous_encoder is None:
                        sys.modules.pop("sentence_transformers", None)
                    else:
                        sys.modules["sentence_transformers"] = previous_encoder
                stack.callback(restore_encoder)
                playwright = stack.enter_context(patch("scraper.scraper.sync_playwright"))
                browser = playwright.return_value.__enter__.return_value.chromium.launch.return_value
                browser.new_page.side_effect = cycle([category, article])
                stack.enter_context(patch.object(flow, "collect_news", side_effect=lambda: collect_news(raw)))
                stack.enter_context(patch.object(flow, "deduplicate_news", side_effect=lambda destination: deduplicate_news(destination, raw)))
                stack.enter_context(patch.object(flow, "PROCESSED_CSV_PATH", output))
                post = stack.enter_context(patch("ai.llm.requests.post", side_effect=replies + replies + [bad]))

                exit_code = Main.main(["--scrape", "--all", "--input", str(unique), "--output", str(output)])
                self.assertEqual(exit_code, 0)
                self.assertEqual(News.objects.count(), 8)
                self.assertEqual(News.objects.values("source").distinct().count(), 4)
                self.assertEqual(len(pd.read_csv(raw)), 8)
                self.assertEqual(len(pd.read_csv(unique)), 1)
                self.assertEqual(pd.read_csv(output).iloc[0]["status"], "APPROVED")
                raw_before, unique_before = raw.read_bytes(), unique.read_bytes()

                for expected_job, expected_row in (("succeeded", "APPROVED"), ("failed", "FACT_EXTRACTION_FAILED")):
                    with self.subTest(expected_job=expected_job):
                        queued = self.client.post("/api/v1/pipeline/runs/", json.dumps({
                            "input": str(unique), "output": str(output), "limit": "all",
                        }), content_type="application/json")
                        self.assertEqual(queued.status_code, 202)
                        job = jobs.get(queued.json()["data"]["id"])
                        self.assertTrue(job.done.wait(10), "Background pipeline did not finish")
                        polled = self.client.get(queued["Location"]).json()["data"]
                        self.assertEqual(polled["status"], expected_job)
                        self.assertEqual(polled["summary"]["processed"], 1)
                        listed = self.client.get("/api/v1/processed/").json()["data"]
                        row = listed["items"][0]
                        self.assertEqual(row["status"], expected_row)
                        detail = self.client.get(f"/api/v1/processed/{row['row']}/").json()["data"]
                        self.assertEqual(detail, row)
                        self.assertEqual(pd.read_csv(output).iloc[0]["status"], expected_row)

                self.assertEqual(raw.read_bytes(), raw_before)
                self.assertEqual(unique.read_bytes(), unique_before)
                self.assertEqual(post.call_count, 7)
                self.assertEqual(browser.close.call_count, 4)
                self.assertEqual(self.client.get("/api/v1/articles/").json()["data"]["meta"]["total"], 8)
                self.assertContains(self.client.get("/collected/"), "Fixture newspaper headline")
                saved = News.objects.first()
                self.assertContains(self.client.get(f"/collected/articles/{saved.pk}/"), saved.source)
                stats = self.client.get("/api/v1/stats/").json()["data"]
                self.assertEqual(stats["articles"]["total"], 8)
                self.assertEqual(stats["processed"]["by_status"], {"FACT_EXTRACTION_FAILED": 1})
