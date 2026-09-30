import contextlib
import io
import json
from pathlib import Path
import tempfile
from unittest.mock import Mock, patch

import pandas as pd
from django.test import SimpleTestCase

from ai.llm import LLMResponseError, generate_text
from pipeline.pipeline import run_pipeline


def response(payload):
    result = Mock()
    result.json.return_value = payload
    return result


class TransportTests(SimpleTestCase):
    def test_invalid_envelopes_fail_without_key_or_attribute_errors(self):
        for payload in (None, [], {}, {"response": None}, {"response": []},
                        {"response": "  "}, {"error": "unavailable"},
                        {"response": "partial", "done": False},
                        {"response": "truncated", "done_reason": "length"}):
            with self.subTest(payload=payload), patch("ai.llm.requests.post", return_value=response(payload)):
                with self.assertRaises(LLMResponseError):
                    generate_text("test")

    def test_invalid_http_json_and_valid_token_limit(self):
        with patch("ai.llm.requests.post") as post:
            post.return_value.json.side_effect = ValueError("invalid")
            with self.assertRaises(LLMResponseError):
                generate_text("test")
        with patch("ai.llm.requests.post", return_value=response({"response": "Hello"})) as post:
            self.assertEqual(generate_text("test"), "Hello")
            self.assertGreater(post.call_args.kwargs["json"]["options"]["num_predict"], 0)

    def test_real_pipeline_saves_bad_service_payload_and_continues(self):
        news = {"title": "Fixture headline", "content": "Source content. " * 30,
                "source": "Fixture", "url": "https://example.com/news"}
        good = [response({"response": json.dumps({"what": "An event"})}),
                response({"response": "HEADLINE: Event\nARTICLE: Source-grounded text"}),
                response({"response": json.dumps({"approved": True})})]
        for stage, status in enumerate(("FACT_EXTRACTION_FAILED", "ARTICLE_GENERATION_FAILED",
                                        "ARTICLE_VERIFICATION_FAILED")):
            with self.subTest(stage=stage), tempfile.TemporaryDirectory() as directory:
                source, output = Path(directory) / "source.csv", Path(directory) / "output.csv"
                pd.DataFrame([news, news]).to_csv(source, index=False)
                with patch("ai.llm.requests.post", side_effect=good[:stage] + [response({})] + good), contextlib.redirect_stdout(io.StringIO()):
                    result = run_pipeline(source, output)
                self.assertEqual(result["status"].tolist(), [status, "APPROVED"])
                self.assertEqual(pd.read_csv(output)["status"].tolist(), [status, "APPROVED"])
