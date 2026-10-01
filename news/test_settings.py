import os
from pathlib import Path
import runpy
import tempfile
from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from config.environment import env_bool, load_environment

ROOT = Path(__file__).resolve().parents[1]


class EnvironmentTests(SimpleTestCase):
    def test_dotenv_preserves_environment_overrides(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text("NEWS_API_KEY=file-value\nOLLAMA_MAX_TOKENS=1500\n", encoding="utf-8")
            with patch.dict(os.environ, {"NEWS_API_KEY": "environment-value"}, clear=True):
                load_environment(path)
                self.assertEqual(os.environ["NEWS_API_KEY"], "environment-value")
                self.assertEqual(os.environ["OLLAMA_MAX_TOKENS"], "1500")

    def test_local_defaults_generate_separate_development_keys(self):
        with patch.dict(os.environ, {}, clear=True):
            first = runpy.run_path(str(ROOT / "config" / "settings.py"))
            second = runpy.run_path(str(ROOT / "config" / "settings.py"))
        self.assertTrue(first["DEBUG"])
        self.assertNotEqual(first["SECRET_KEY"], second["SECRET_KEY"])
        self.assertIn("127.0.0.1", first["ALLOWED_HOSTS"])

    def test_non_debug_settings_require_private_keys(self):
        with patch.dict(os.environ, {"DJANGO_DEBUG": "false"}, clear=True):
            with self.assertRaisesMessage(ImproperlyConfigured, "DJANGO_SECRET_KEY"):
                runpy.run_path(str(ROOT / "config" / "settings.py"))
            os.environ["DJANGO_SECRET_KEY"] = "test-only-value"
            with self.assertRaisesMessage(ImproperlyConfigured, "NEWS_API_KEY"):
                runpy.run_path(str(ROOT / "config" / "settings.py"))
            os.environ["NEWS_API_KEY"] = "test-only-api-key"
            settings = runpy.run_path(str(ROOT / "config" / "settings.py"))
        self.assertFalse(settings["DEBUG"])
        self.assertTrue(settings["SESSION_COOKIE_SECURE"])
        self.assertTrue(settings["CSRF_COOKIE_SECURE"])

    def test_generation_environment_and_invalid_values(self):
        values = {"OLLAMA_URL": "http://127.0.0.1:1234/api/generate", "OLLAMA_MAX_TOKENS": "100"}
        with patch.dict(os.environ, values, clear=True):
            settings = runpy.run_path(str(ROOT / "ai" / "config.py"))
            self.assertEqual(settings["MAX_TOKENS"], 100)
            self.assertEqual(settings["OLLAMA_URL"], values["OLLAMA_URL"])
            os.environ["OLLAMA_MAX_TOKENS"] = "0"
            with self.assertRaises(ValueError):
                runpy.run_path(str(ROOT / "ai" / "config.py"))
            os.environ["DJANGO_DEBUG"] = "maybe"
            with self.assertRaises(ValueError):
                env_bool("DJANGO_DEBUG")
