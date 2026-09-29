import json
import tempfile
import threading
from pathlib import Path
from unittest.mock import patch

import pandas as pd
from django.test import Client, TestCase, override_settings

from news.api import jobs, services
from news.api.http import ApiError
from news.models import News
from pipeline import flow


def make_article(**overrides):
    defaults = {
        "source": "Daily Star",
        "category": "business",
        "title": "Markets rally as imports fall",
        "url": "https://example.com/markets-rally",
        "content": "Original source content about markets. " * 20,
        "author": "Reporter",
        "published_date": "Monday",
        "image_url": "",
        "language": "English",
    }
    defaults.update(overrides)
    counter = make_article.counter = getattr(make_article, "counter", 0) + 1
    defaults["url"] = overrides.get("url", f"https://example.com/article-{counter}")
    return News.objects.create(**defaults)


class ApiTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        jobs.reset()

    def tearDown(self):
        jobs.reset()

    def data(self, response):
        payload = response.json()
        self.assertIn("data", payload, payload)
        return payload["data"]

    def error(self, response):
        payload = response.json()
        self.assertIn("error", payload, payload)
        return payload["error"]


class HealthAndAuthTests(ApiTestCase):
    def test_health_is_public_and_reports_dependencies(self):
        with patch("news.api.services._generation_status", return_value={"available": False, "model": "qwen3:0.6b", "model_installed": False}):
            response = self.client.get("/api/v1/health/")
        self.assertEqual(response.status_code, 200)
        data = self.data(response)
        self.assertEqual(data["status"], "ok")
        self.assertTrue(data["database"]["available"])
        self.assertFalse(data["generation"]["available"])

    @override_settings(NEWS_API_KEY="secret-key")
    def test_endpoints_require_api_key_when_configured(self):
        response = self.client.get("/api/v1/articles/")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(self.error(response)["code"], "unauthorized")

        response = self.client.get("/api/v1/articles/", headers={"X-API-Key": "wrong"})
        self.assertEqual(response.status_code, 401)

        response = self.client.get("/api/v1/articles/", headers={"X-API-Key": "secret-key"})
        self.assertEqual(response.status_code, 200)

        # Health stays open for probes.
        with patch("news.api.services._generation_status", return_value={"available": False, "model": "m", "model_installed": False}):
            response = self.client.get("/api/v1/health/")
        self.assertEqual(response.status_code, 200)


class ArticleEndpointTests(ApiTestCase):
    def test_list_filters_and_paginates(self):
        make_article(source="Daily Star", title="First headline")
        make_article(source="Daily Star", title="Second headline")
        make_article(source="Dhaka Tribune", title="Third headline", url="https://example.com/third")

        response = self.client.get("/api/v1/articles/?source=Daily+Star&page_size=2")
        data = self.data(response)
        self.assertEqual(data["meta"]["total"], 2)
        self.assertEqual(len(data["items"]), 2)
        self.assertEqual(data["items"][0]["id"], 2)

        response = self.client.get("/api/v1/articles/?q=Third")
        data = self.data(response)
        self.assertEqual(data["meta"]["total"], 1)
        self.assertEqual(data["items"][0]["title"], "Third headline")

        response = self.client.get("/api/v1/articles/?page_size=1&page=2")
        data = self.data(response)
        self.assertEqual(len(data["items"]), 1)
        self.assertEqual(data["meta"]["page"], 2)
        self.assertEqual(data["meta"]["total_pages"], 3)

    def test_list_rejects_bad_query_parameters(self):
        make_article()
        for query in ("?unknown=1", "?page=abc", "?page=0", "?page_size=1000", "?q=" + "x" * 201):
            with self.subTest(query=query):
                response = self.client.get("/api/v1/articles/" + query)
                self.assertEqual(response.status_code, 400)
                self.assertIn(
                    self.error(response)["code"],
                    {"unknown_query_parameter", "invalid_query_parameter"},
                )

    def test_detail_and_not_found_envelope(self):
        article = make_article()
        response = self.client.get(f"/api/v1/articles/{article.pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.data(response)["url"], article.url)

        response = self.client.get("/api/v1/articles/999999/")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.error(response)["code"], "not_found")

    def test_method_not_allowed_sets_allow_header(self):
        response = self.client.post("/api/v1/articles/", data="{}", content_type="application/json")
        self.assertEqual(response.status_code, 405)
        self.assertEqual(response["Allow"], "GET")
        self.assertEqual(self.error(response)["code"], "method_not_allowed")

    def test_malformed_bodies_are_rejected(self):
        response = self.client.post("/api/v1/pipeline/runs/", data="{broken", content_type="application/json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.error(response)["code"], "invalid_json")

        response = self.client.post(
            "/api/v1/pipeline/runs/", data="limit=1", content_type="application/x-www-form-urlencoded"
        )
        self.assertEqual(response.status_code, 415)
        self.assertEqual(self.error(response)["code"], "unsupported_media_type")

        # A GET-only endpoint rejects the method before inspecting the body.
        response = self.client.post("/api/v1/articles/", data="{broken", content_type="application/json")
        self.assertEqual(response.status_code, 405)


class ProcessedEndpointTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.processed_csv = Path(self.temp_dir.name) / "processed.csv"
        rows = [
            {
                "source": "Daily Star",
                "category": "business",
                "title": "EV import ban row",
                "url": "https://example.com/ev",
                "content": "Source content " * 30,
                "author": "Reporter",
                "published_date": "Monday",
                "image_url": "",
                "language": "English",
                "scraped_date": "2026-09-14 15:01:00",
                "status": "APPROVED",
                "reason": "",
                "facts": json.dumps({"what": "An event"}),
                "generated_article": "A rewritten article.",
                "verification": json.dumps({"approved": True, "score": 9}),
            },
            {
                "source": "Dhaka Tribune",
                "category": "latest-news",
                "title": "Short row",
                "url": "https://example.com/short",
                "content": "Source content " * 30,
                "author": "Reporter",
                "published_date": "Tuesday",
                "image_url": "",
                "language": "English",
                "scraped_date": "2026-09-14 15:02:00",
                "status": "CONTENT_REJECTED",
                "reason": "Content too short",
                "facts": "",
                "generated_article": "",
                "verification": "",
            },
        ]
        pd.DataFrame(rows).to_csv(self.processed_csv, index=False, encoding="utf-8-sig")
        patcher = patch.object(flow, "PROCESSED_CSV_PATH", self.processed_csv)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_list_parses_json_fields_and_filters_status(self):
        response = self.client.get("/api/v1/processed/")
        data = self.data(response)
        self.assertEqual(data["meta"]["total"], 2)
        self.assertEqual(data["items"][0]["facts"], {"what": "An event"})
        self.assertTrue(data["items"][0]["verification"]["approved"])
        self.assertIsNone(data["items"][1]["facts"])

        response = self.client.get("/api/v1/processed/?status=CONTENT_REJECTED")
        data = self.data(response)
        self.assertEqual(data["meta"]["total"], 1)
        self.assertEqual(data["items"][0]["title"], "Short row")

    def test_detail_and_missing_file_behaviour(self):
        response = self.client.get("/api/v1/processed/0/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.data(response)["row"], 0)

        response = self.client.get("/api/v1/processed/50/")
        self.assertEqual(response.status_code, 404)

        with patch.object(flow, "PROCESSED_CSV_PATH", Path(self.temp_dir.name) / "missing.csv"):
            response = self.client.get("/api/v1/processed/")
            data = self.data(response)
            self.assertEqual(data["meta"]["total"], 0)
            self.assertEqual(data["items"], [])

    def test_rejects_unknown_status_filter(self):
        response = self.client.get("/api/v1/processed/?status=NOT_A_STATUS")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.error(response)["code"], "invalid_query_parameter")


class StatsEndpointTests(ApiTestCase):
    def test_stats_aggregate_database_and_csv(self):
        make_article(source="Daily Star")
        make_article(source="Dhaka Tribune")
        with tempfile.TemporaryDirectory() as directory:
            processed = Path(directory) / "processed.csv"
            pd.DataFrame(
                [
                    {"status": "APPROVED", "source": "Daily Star"},
                    {"status": "APPROVED", "source": "Daily Star"},
                    {"status": "CONTENT_REJECTED", "source": "Dhaka Tribune"},
                ]
            ).to_csv(processed, index=False)
            with patch.object(flow, "PROCESSED_CSV_PATH", processed):
                response = self.client.get("/api/v1/stats/")
        data = self.data(response)
        self.assertEqual(data["articles"]["total"], 2)
        self.assertEqual(data["articles"]["by_source"], {"Daily Star": 1, "Dhaka Tribune": 1})
        self.assertEqual(data["processed"]["total"], 3)
        self.assertEqual(data["processed"]["by_status"], {"APPROVED": 2, "CONTENT_REJECTED": 1})
        self.assertIsNotNone(data["articles"]["latest_scraped_date"])


class RunValidationTests(ApiTestCase):
    def test_valid_run_returns_accepted_with_location(self):
        with patch("news.api.jobs.submit") as submit:
            job = jobs.PipelineJob({"limit": 1, "scrape": False, "deduplicate": False})
            submit.return_value = job
            response = self.client.post(
                "/api/v1/pipeline/runs/",
                data=json.dumps({"limit": 2}),
                content_type="application/json",
            )
        self.assertEqual(response.status_code, 202)
        data = self.data(response)
        self.assertEqual(data["id"], job.id)
        self.assertEqual(data["status"], "queued")
        self.assertEqual(response["Location"], f"/api/v1/pipeline/runs/{job.id}/")
        payload = submit.call_args.args[0]
        self.assertEqual(payload["limit"], 2)
        self.assertEqual(payload["input_csv"], flow.UNIQUE_CSV_PATH)

    def test_invalid_run_payloads_return_400(self):
        cases = [
            ("invalid_limit", {"limit": 0}),
            ("invalid_limit", {"limit": "many"}),
            ("invalid_limit", {"limit": True}),
            ("unknown_field", {"rows": 3}),
            ("invalid_field", {"scrape": "yes"}),
            ("invalid_path", {"input": "../../outside.csv"}),
            ("invalid_path", {"output": str(flow.RAW_CSV_PATH)}),
        ]
        with patch("news.api.jobs.submit") as submit:
            for expected_code, body in cases:
                with self.subTest(body=body):
                    response = self.client.post(
                        "/api/v1/pipeline/runs/",
                        data=json.dumps(body),
                        content_type="application/json",
                    )
                    self.assertEqual(response.status_code, 400)
                    self.assertEqual(self.error(response)["code"], expected_code)
            submit.assert_not_called()

    def test_run_all_is_accepted(self):
        with patch("news.api.jobs.submit") as submit:
            submit.return_value = jobs.PipelineJob({"limit": None})
            response = self.client.post(
                "/api/v1/pipeline/runs/",
                data=json.dumps({"limit": "all"}),
                content_type="application/json",
            )
        self.assertEqual(response.status_code, 202)
        self.assertIsNone(submit.call_args.args[0]["limit"])


class RunLifecycleTests(ApiTestCase):
    def test_run_completes_with_summary(self):
        def runner(**kwargs):
            return pd.DataFrame({"status": ["APPROVED", "CONTENT_REJECTED", "FACT_EXTRACTION_FAILED"]})

        job = jobs.submit({"input_csv": flow.UNIQUE_CSV_PATH, "limit": 3}, runner=runner)
        self.assertTrue(job.done.wait(10), "run did not finish")
        self.assertEqual(job.status, "succeeded")
        self.assertEqual(job.summary["processed"], 3)
        self.assertEqual(job.summary["approved"], 1)
        self.assertEqual(job.summary["failed"], 1)

        response = self.client.get(f"/api/v1/pipeline/runs/{job.id}/")
        self.assertEqual(response.status_code, 200)
        data = self.data(response)
        self.assertEqual(data["status"], "succeeded")
        self.assertEqual(data["summary"]["approved"], 1)
        self.assertEqual(data["request"]["limit"], 3)

        response = self.client.get("/api/v1/pipeline/runs/")
        data = self.data(response)
        self.assertEqual(data["meta"]["count"], 1)
        self.assertEqual(data["items"][0]["id"], job.id)

    def test_failed_runner_records_error(self):
        def runner(**kwargs):
            raise RuntimeError("service exploded")

        job = jobs.submit({"limit": 1}, runner=runner)
        self.assertTrue(job.done.wait(10))
        self.assertEqual(job.status, "failed")
        self.assertIn("service exploded", job.error)

    def test_second_run_conflicts_while_active(self):
        release = threading.Event()

        def runner(**kwargs):
            release.wait(10)
            return pd.DataFrame({"status": ["APPROVED"]})

        first = jobs.submit({"limit": 1}, runner=runner)
        try:
            with self.assertRaises(ApiError) as conflict:
                jobs.submit({"limit": 1}, runner=runner)
            self.assertEqual(conflict.exception.status, 409)
            self.assertEqual(conflict.exception.code, "job_conflict")
        finally:
            release.set()
        self.assertTrue(first.done.wait(10))

        # A finished run frees the slot.
        second = jobs.submit({"limit": 1}, runner=runner)
        self.assertTrue(second.done.wait(10))

    def test_unknown_run_returns_404(self):
        response = self.client.get("/api/v1/pipeline/runs/does-not-exist/")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.error(response)["code"], "not_found")
