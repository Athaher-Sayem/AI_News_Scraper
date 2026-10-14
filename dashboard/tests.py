import tempfile
import threading
from pathlib import Path
from unittest.mock import patch

import pandas as pd
from django.test import TestCase, override_settings

from dashboard import api as dashboard_api
from dashboard import views
from news.api import jobs
from news.models import News
from pipeline import flow, progress


class TrackerTests(TestCase):
    def test_row_outcomes_update_stage_counters(self):
        tracker = progress.RunTracker()
        for status in ("APPROVED", "ARTICLE_REJECTED", "CONTENT_REJECTED", "FACT_EXTRACTION_FAILED"):
            tracker.row_start(1, 4, "t")
            tracker.row_done(status)
        stages = {s["key"]: s for s in tracker.snapshot()["stages"]}
        self.assertEqual(stages["content_check"]["passed"], 3)
        self.assertEqual(stages["content_check"]["rejected"], 1)
        self.assertEqual(stages["fact_extraction"]["failed"], 1)
        self.assertEqual(stages["verification"]["passed"], 1)
        self.assertEqual(stages["verification"]["rejected"], 1)

    def test_plan_marks_unused_stages_skipped(self):
        stages = {s["key"]: s["state"] for s in progress.RunTracker(progress.plan_for()).snapshot()["stages"]}
        self.assertEqual(stages["scrape"], "skipped")
        self.assertEqual(stages["deduplicate"], "skipped")
        self.assertEqual(stages["content_check"], "pending")
        full = {s["key"]: s["state"] for s in progress.RunTracker(progress.plan_for(scrape=True)).snapshot()["stages"]}
        self.assertEqual(full["deduplicate"], "pending")

    def test_log_is_incremental_and_bounded(self):
        tracker = progress.RunTracker()
        for index in range(progress.LOG_LIMIT + 25):
            tracker.log(f"line {index}")
        snapshot = tracker.snapshot()
        self.assertEqual(len(snapshot["log"]), progress.LOG_LIMIT)
        self.assertEqual(tracker.snapshot(after=snapshot["log_next"] - 1)["log"][0]["msg"], f"line {progress.LOG_LIMIT + 24}")

    def test_helpers_are_noops_without_a_tracker(self):
        progress.unbind()
        progress.log("ignored")
        progress.step("content_check")
        progress.checkpoint()
        with progress.stage("scrape"):
            pass

    def test_pipeline_reports_progress_and_saves_partial_results_on_cancel(self):
        from pipeline import pipeline as pipeline_module

        tracker = progress.RunTracker()
        progress.bind(tracker)
        self.addCleanup(progress.unbind)
        calls = []

        def process(news):
            calls.append(news["title"])
            if len(calls) == 2:
                tracker.request_cancel()
            news["status"] = "APPROVED"
            return news

        with tempfile.TemporaryDirectory() as folder:
            source, output = Path(folder, "in.csv"), Path(folder, "out.csv")
            pd.DataFrame({"title": list("abc"), "content": list("xyz"), "url": list("123"), "source": ["s"] * 3}).to_csv(source, index=False)
            with patch.object(pipeline_module, "process_row", side_effect=process):
                with self.assertRaises(progress.RunCancelled) as raised:
                    pipeline_module.run_pipeline(source, output)
            self.assertEqual(len(raised.exception.result), 2)
            self.assertEqual(len(pd.read_csv(output)), 2)
        self.assertEqual(calls, ["a", "b"])


class JobCancelTests(TestCase):
    def setUp(self):
        jobs.reset()
        self.addCleanup(jobs.reset)

    def test_cancel_stops_run_at_checkpoint_and_reports_cancelled(self):
        started = threading.Event()

        def runner(**kwargs):
            started.set()
            while True:
                progress.checkpoint()
                threading.Event().wait(0.01)

        job = jobs.submit({"limit": 1}, runner=runner)
        self.assertTrue(started.wait(2))
        jobs.cancel(job.id)
        self.assertTrue(job.done.wait(3))
        self.assertEqual(job.status, "cancelled")
        self.assertIsNone(job.error)
        with self.assertRaises(Exception) as raised:
            jobs.cancel(job.id)
        self.assertEqual(raised.exception.code, "not_cancellable")

    def test_cancel_unknown_run_is_not_found(self):
        with self.assertRaises(Exception) as raised:
            jobs.cancel("missing")
        self.assertEqual(raised.exception.status, 404)


class FlowSourceTests(TestCase):
    def test_validate_sources(self):
        self.assertIsNone(flow.validate_sources(None))
        self.assertEqual(flow.validate_sources(["Daily Sun", "Daily Sun"]), ["Daily Sun"])
        for bad in ([], ["Nope"], "Daily Sun", [1]):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                flow.validate_sources(bad)


class DashboardApiTests(TestCase):
    def setUp(self):
        jobs.reset()
        self.addCleanup(jobs.reset)
        News.objects.create(source="Daily Star", category="sports", title="One", url="https://example.com/1", content="x")
        News.objects.create(source="Daily Star", category="business", title="Two", url="https://example.com/2", content="y")

    def test_overview_shape(self):
        data = self.client.get("/dashboard/api/overview/").json()["data"]
        self.assertEqual(data["totals"]["articles"], 2)
        self.assertEqual([s["name"] for s in data["sources"][:4]], list(flow.SOURCE_NAMES))
        self.assertEqual(data["sources"][0]["articles"], 2)
        self.assertEqual(data["sources"][0]["categories"], 2)
        self.assertEqual(len(data["timeline"]), dashboard_api.TIMELINE_DAYS)
        self.assertEqual(sum(day["count"] for day in data["timeline"]), 2)
        self.assertEqual([f["key"] for f in data["funnel"]][0], "processed")
        self.assertNotIn("secret", str(data["config"]).lower())
        self.assertIsNone(data["active_run"])

    def test_funnel_counts_survivors(self):
        funnel = dashboard_api._funnel({"APPROVED": 2, "CONTENT_REJECTED": 1, "ARTICLE_REJECTED": 1, "FACT_EXTRACTION_FAILED": 1}, 5)
        self.assertEqual([row["count"] for row in funnel], [5, 4, 3, 3, 3, 2])

    @override_settings(NEWS_API_KEY="k")
    def test_endpoints_require_api_key(self):
        for path in ("/dashboard/api/overview/", "/dashboard/api/runs/", "/dashboard/api/files/", "/dashboard/api/files/news_data.csv/download/"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 401)
                self.assertNotEqual(self.client.get(path, headers={"X-API-Key": "k"}).status_code, 401)
        self.assertEqual(self.client.post("/dashboard/api/runs/", data="{}", content_type="application/json").status_code, 401)

    def test_start_run_with_sources_and_cancel(self):
        release = threading.Event()
        captured = {}

        def runner(**kwargs):
            captured.update(kwargs)
            while not release.is_set():
                progress.checkpoint()
                release.wait(0.01)

        with patch.object(flow, "run_flow", runner):
            response = self.client.post(
                "/dashboard/api/runs/",
                data={"scrape": True, "limit": 2, "sources": ["Daily Sun"]},
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 202, response.content)
            run = response.json()["data"]
            self.assertEqual(run["sources"], ["Daily Sun"])
            self.assertEqual(run["progress"]["stages"][0]["state"], "pending")
            self.assertEqual(self.client.post("/dashboard/api/runs/", data={"limit": 1}, content_type="application/json").status_code, 409)

            cancel = self.client.post(f"/dashboard/api/runs/{run['id']}/cancel/", data="{}", content_type="application/json")
            self.assertEqual(cancel.status_code, 202)
            self.assertTrue(cancel.json()["data"]["progress"]["cancel_requested"])
            jobs.get(run["id"]).done.wait(3)

        detail = self.client.get(f"/dashboard/api/runs/{run['id']}/").json()["data"]
        self.assertEqual(detail["status"], "cancelled")
        self.assertTrue(any("Cancel requested" in line["msg"] for line in detail["progress"]["log"]))
        self.assertEqual(captured["sources"], ["Daily Sun"])
        self.assertEqual(self.client.post(f"/dashboard/api/runs/{run['id']}/cancel/", data="{}", content_type="application/json").status_code, 409)

    def test_source_validation(self):
        cases = (
            {"scrape": True, "sources": ["Nope"]},
            {"scrape": True, "sources": []},
            {"scrape": False, "sources": ["Daily Sun"]},
            {"scrape": True, "sources": "Daily Sun"},
        )
        for body in cases:
            with self.subTest(body=body):
                response = self.client.post("/dashboard/api/runs/", data=body, content_type="application/json")
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json()["error"]["code"], "invalid_field")

    def test_selecting_every_source_means_no_filter(self):
        with patch.object(flow, "run_flow", lambda **kw: pd.DataFrame({"status": ["APPROVED"]})) as runner:
            response = self.client.post(
                "/dashboard/api/runs/", data={"scrape": True, "sources": list(flow.SOURCE_NAMES)}, content_type="application/json")
            self.assertEqual(response.status_code, 202)
            self.assertIsNone(response.json()["data"]["sources"])
            jobs.get(response.json()["data"]["id"]).done.wait(3)

    def test_unknown_run_and_bad_after(self):
        self.assertEqual(self.client.get("/dashboard/api/runs/nope/").status_code, 404)
        self.assertEqual(self.client.post("/dashboard/api/runs/nope/cancel/", data="{}", content_type="application/json").status_code, 404)
        job = jobs.submit({"limit": 1}, runner=lambda **kw: pd.DataFrame({"status": ["APPROVED"]}))
        job.done.wait(3)
        self.assertEqual(self.client.get(f"/dashboard/api/runs/{job.id}/?after=x").status_code, 400)

    def test_file_download_is_confined_to_data_csvs(self):
        for name in ("../manage.py", "..%2Fmanage.py", "news_data.txt", "missing.csv"):
            with self.subTest(name=name):
                self.assertEqual(self.client.get(f"/dashboard/api/files/{name}/download/").status_code, 404)
        listing = self.client.get("/dashboard/api/files/").json()["data"]["items"]
        if listing:
            response = self.client.get(f"/dashboard/api/files/{listing[0]['name']}/download/")
            self.assertEqual(response.status_code, 200)
            self.assertIn("attachment", response["Content-Disposition"])
            response.close()


class DashboardPageTests(TestCase):
    def test_page_assets_and_headers(self):
        page = self.client.get("/dashboard/")
        self.assertEqual(page.status_code, 200)
        self.assertIn("default-src 'none'", page["Content-Security-Policy"])
        self.assertEqual(page["X-Frame-Options"], "DENY")
        page.close()
        for path, kind in (("app.css", "text/css"), ("js/app.js", "text/javascript"), ("js/views/data.js", "text/javascript"), ("favicon.svg", "image/svg+xml")):
            with self.subTest(path=path):
                response = self.client.get(f"/dashboard/assets/{path}")
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response["Content-Type"].startswith(kind))
                response.close()

    def test_conditional_requests_and_traversal(self):
        first = self.client.get("/dashboard/assets/app.css")
        etag = first["ETag"]
        first.close()
        self.assertEqual(self.client.get("/dashboard/assets/app.css", headers={"If-None-Match": etag}).status_code, 304)
        for path in ("../views.py", "fonts/LICENSE-fira-OFL.txt", "nope.js"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(f"/dashboard/assets/{path}").status_code, 404)

    def test_redirect_and_unknown_subpath_do_not_fall_into_the_spa(self):
        self.assertEqual(self.client.get("/dashboard").status_code, 302)
        self.assertEqual(self.client.get("/dashboard/other/").status_code, 404)

    def test_page_has_no_inline_script_or_style_that_the_csp_would_block(self):
        html = (views.WEB_DIR / "index.html").read_text(encoding="utf-8")
        self.assertNotIn(" style=", html)
        self.assertNotRegex(html, r"<script(?![^>]*\bsrc=)[^>]*>")
        self.assertNotRegex(html, r"\son[a-z]+=")
