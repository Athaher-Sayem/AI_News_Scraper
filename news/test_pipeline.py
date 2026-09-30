import contextlib
import importlib
import io
import json
from pathlib import Path
import runpy
import tempfile
import types
import unittest
from unittest.mock import patch

import pandas as pd
import numpy as np
from requests.exceptions import ConnectionError, Timeout

from pipeline.content_checker import check_content
from pipeline.pipeline import run_pipeline


class ContentCheckTests(unittest.TestCase):
    def test_missing_values_are_rejected(self):
        news = {
            "title": "A news headline",
            "content": "Original source material. " * 20,
            "url": "https://example.com/news",
            "source": "Example News",
        }
        for field in news:
            for missing in (None, float("nan"), pd.NA, "", "   "):
                with self.subTest(field=field, missing=missing):
                    self.assertFalse(check_content({**news, field: missing})[0])


class PipelineTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.input = Path(directory.name) / "input.csv"
        self.output = Path(directory.name) / "output.csv"
        self.news = {
            "title": "A news headline",
            "content": "Original source material. " * 20,
            "url": "https://example.com/news",
            "source": "Example News",
        }
        self.facts = self.enterContext(
            patch("pipeline.pipeline.extract_facts", return_value={"what": "An event"})
        )
        self.article = self.enterContext(
            patch("pipeline.pipeline.generate_article", return_value="A generated article")
        )
        self.verify = self.enterContext(
            patch("pipeline.pipeline.verify_article", return_value={"approved": True})
        )
        self.enterContext(contextlib.redirect_stdout(io.StringIO()))

    def run_rows(self, rows, **kwargs):
        pd.DataFrame(rows, columns=self.news.keys()).to_csv(self.input, index=False)
        run_pipeline(self.input, self.output, **kwargs)
        return pd.read_csv(self.output, keep_default_na=False)

    def test_all_rows_are_saved_with_stage_results(self):
        result = self.run_rows([self.news, {**self.news, "title": "Another headline"}])
        self.assertEqual(result["status"].tolist(), ["APPROVED", "APPROVED"])
        self.assertEqual(self.verify.call_count, 2)
        self.assertEqual(json.loads(result.iloc[0]["facts"]), {"what": "An event"})
        self.assertEqual(json.loads(result.iloc[0]["verification"]), {"approved": True})

    def test_rejected_content_does_not_call_ai(self):
        result = self.run_rows([{**self.news, "title": None}])
        self.assertEqual(result.iloc[0]["status"], "CONTENT_REJECTED")
        self.facts.assert_not_called()

    def test_invalid_facts_stop_generation(self):
        for facts in (None, [], ["fact"], "fact", {}, {"error": "Invalid JSON"}):
            with self.subTest(facts=facts):
                self.facts.return_value = facts
                result = self.run_rows([self.news])
                self.assertEqual(result.iloc[0]["status"], "FACT_EXTRACTION_FAILED")
        self.article.assert_not_called()

    def test_empty_article_retains_facts(self):
        self.article.return_value = "   "
        result = self.run_rows([self.news])
        self.assertEqual(result.iloc[0]["status"], "ARTICLE_GENERATION_FAILED")
        self.assertEqual(json.loads(result.iloc[0]["facts"]), {"what": "An event"})
        self.verify.assert_not_called()

    def test_verification_requires_boolean_true(self):
        for verification in (None, [], "approved", {}, {"approved": "false"}, {"approved": 1}, {"approved": False}):
            with self.subTest(verification=verification):
                self.verify.return_value = verification
                result = self.run_rows([self.news])
                self.assertEqual(result.iloc[0]["status"], "ARTICLE_REJECTED")

    def test_request_failure_is_saved_and_next_row_continues(self):
        for mock, status in (
            (self.facts, "FACT_EXTRACTION_FAILED"),
            (self.article, "ARTICLE_GENERATION_FAILED"),
            (self.verify, "ARTICLE_VERIFICATION_FAILED"),
        ):
            with self.subTest(stage=status):
                mock.side_effect = [ConnectionError("Service unavailable"), mock.return_value]
                result = self.run_rows([self.news, self.news])
                self.assertEqual(result["status"].tolist(), [status, "APPROVED"])
                mock.side_effect = None

    def test_timeout_preserves_generated_article(self):
        self.verify.side_effect = Timeout("Timed out")
        result = self.run_rows([self.news])
        self.assertEqual(result.iloc[0]["status"], "ARTICLE_VERIFICATION_FAILED")
        self.assertEqual(result.iloc[0]["generated_article"], "A generated article")

    def test_empty_input_writes_headers_instead_of_leaving_stale_output(self):
        self.run_rows([self.news])
        result = self.run_rows([])
        self.assertTrue(result.empty)
        self.assertIn("status", result.columns)

    def test_limit_is_explicit(self):
        result = self.run_rows([self.news, self.news], limit=1)
        self.assertEqual(len(result), 1)

    def test_same_input_and_output_is_rejected(self):
        pd.DataFrame([self.news]).to_csv(self.input, index=False)
        with self.assertRaises(ValueError):
            run_pipeline(self.input, self.input)
        self.assertNotIn("status", pd.read_csv(self.input).columns)

    def test_invalid_input_does_not_replace_previous_results(self):
        self.run_rows([self.news])
        before = self.output.read_bytes()
        pd.DataFrame([{"other": "value"}]).to_csv(self.input, index=False)
        with self.assertRaises(ValueError):
            run_pipeline(self.input, self.output)
        self.assertEqual(self.output.read_bytes(), before)

    def test_failed_write_preserves_previous_results_and_cleans_temporary_file(self):
        self.run_rows([self.news])
        before = self.output.read_bytes()
        def broken_write(frame, handle, **kwargs):
            handle.write("partial CSV")
            raise OSError("Disk full")
        with patch.object(pd.DataFrame, "to_csv", broken_write), self.assertRaises(OSError):
            run_pipeline(self.input, self.output)
        self.assertEqual(self.output.read_bytes(), before)
        self.assertEqual(list(self.output.parent.glob("*.tmp")), [])

    def test_reader_sees_old_snapshot_until_unicode_output_is_complete(self):
        self.run_rows([self.news])
        before = self.output.read_bytes()
        self.article.return_value = "বাংলা সংবাদ — verified Unicode output"
        from utils.csv_utils import os
        replace = os.replace
        def inspect_before_replace(source, target):
            self.assertEqual(self.output.read_bytes(), before)
            completed = pd.read_csv(source)
            self.assertEqual(completed.iloc[0]["generated_article"], self.article.return_value)
            replace(source, target)
        with patch("utils.csv_utils.os.replace", side_effect=inspect_before_replace):
            result = run_pipeline(self.input, self.output)
        self.assertEqual(pd.read_csv(self.output).iloc[0]["generated_article"], result.iloc[0]["generated_article"])


class MainTests(unittest.TestCase):
    def test_import_does_not_run_pipeline(self):
        with patch("pipeline.flow.run_flow", return_value=pd.DataFrame({"status": ["APPROVED"]})) as run:
            import Main

            importlib.reload(Main)
        run.assert_not_called()

    def test_cli_defaults_to_one_row_and_supports_all(self):
        import Main
        from pipeline import flow

        with patch("pipeline.flow.run_flow", return_value=pd.DataFrame({"status": ["APPROVED"]})) as run:
            self.assertEqual(Main.main([]), 0)
            self.assertEqual(run.call_args.kwargs["limit"], 1)
            self.assertEqual(run.call_args.kwargs["input_csv"], flow.UNIQUE_CSV_PATH)
            self.assertEqual(run.call_args.kwargs["output_csv"], flow.PROCESSED_CSV_PATH)
            self.assertFalse(run.call_args.kwargs["scrape"])

            self.assertEqual(Main.main(["--all"]), 0)
            self.assertIsNone(run.call_args.kwargs["limit"])

    def test_flow_runs_scrape_deduplicate_process_in_order(self):
        from pipeline import flow

        calls = []
        with patch.object(flow, "collect_news", side_effect=lambda *a, **k: calls.append("scrape")), patch.object(
            flow, "deduplicate_news", side_effect=lambda *a, **k: calls.append("deduplicate")
        ), patch.object(
            flow, "run_pipeline", side_effect=lambda *a, **k: (calls.append("process") or pd.DataFrame({"status": ["APPROVED"]}))
        ):
            result = flow.run_flow(scrape=True)
        self.assertEqual(calls, ["scrape", "deduplicate", "process"])
        self.assertEqual(result.iloc[0]["status"], "APPROVED")

    def test_flow_validates_before_doing_work(self):
        from pipeline import flow

        with patch.object(flow, "collect_news") as collect, self.assertRaises(ValueError):
            flow.run_flow(output_csv=flow.RAW_CSV_PATH, scrape=True)
        collect.assert_not_called()

    def test_flow_rejects_paths_outside_project(self):
        from pipeline import flow

        with self.assertRaises(ValueError):
            flow.run_flow(input_csv="C:/Windows/Temp/elsewhere.csv")

    def test_cli_returns_nonzero_for_service_failures(self):
        import Main

        with patch("pipeline.flow.run_flow", return_value=pd.DataFrame({"status": ["FACT_EXTRACTION_FAILED"]})):
            self.assertEqual(Main.main([]), 1)

    def test_cli_reports_validation_errors(self):
        import Main

        with patch("pipeline.flow.run_flow", side_effect=ValueError("bad path")), self.assertRaises(SystemExit) as exit_info:
            Main.main([])
        self.assertEqual(exit_info.exception.code, 1)


class DeduplicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = runpy.run_path(str(Path(__file__).resolve().parents[1] / "Sentence-BERT.py"))

    def test_empty_and_single_row_inputs_need_no_embeddings(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()):
            input_csv = Path(directory) / "input.csv"
            output_csv = Path(directory) / "output.csv"
            for titles in ([], ["A sufficiently long headline"]):
                with self.subTest(titles=titles):
                    pd.DataFrame({"title": titles}).to_csv(input_csv, index=False)
                    result, groups = self.module["deduplicate"](input_csv, output_csv)
                    self.assertEqual(len(result), len(titles))
                    self.assertEqual(groups, [])
                    self.assertEqual(len(pd.read_csv(output_csv)), len(titles))

    def test_identical_headlines_survive_tfidf_pruning(self):
        fake_module = types.ModuleType("sentence_transformers")
        fake_module.SentenceTransformer = lambda name: types.SimpleNamespace(
            encode=lambda titles, **kwargs: np.array([[1.0, 0.0]] * len(titles))
        )
        with patch.dict("sys.modules", {"sentence_transformers": fake_module}), contextlib.redirect_stdout(io.StringIO()):
            similarity = self.module["compute_hybrid_similarity"](["Identical news headline"] * 2)
            labels = self.module["cluster_titles"](similarity)
        self.assertEqual(labels[0], labels[1])

    def test_numeric_titles_missing_headers_and_bangla_normalization(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()):
            source = Path(directory) / "news.csv"
            pd.DataFrame({"Title": [1234567890123], "source": ["NA"]}).to_csv(source, index=False)
            frame = self.module["load_data"](source)
            self.assertEqual(frame.iloc[0]["title"], "1234567890123")
            self.assertEqual(frame.iloc[0]["source"], "NA")
            pd.DataFrame({"other": ["text"]}).to_csv(source, index=False)
            with self.assertRaises(ValueError):
                self.module["load_data"](source)
        normalized = self.module["normalize"]("বাংলা সংবাদ — Technology!")
        self.assertIn("বাংলা সংবাদ", normalized)
        self.assertIn("technology", normalized)

    def test_threshold_separates_unrelated_titles(self):
        similarity = np.array([[1, .95, .1], [.95, 1, .1], [.1, .1, 1]])
        with contextlib.redirect_stdout(io.StringIO()):
            labels = self.module["cluster_titles"](similarity, threshold=.73)
        self.assertEqual(labels[0], labels[1])
        self.assertNotEqual(labels[0], labels[2])
