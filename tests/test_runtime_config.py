import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core import config


class RuntimeConfigTests(unittest.TestCase):
    def test_dotenv_reads_only_supported_assignments_and_ignores_comments(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text("# ignored\nexport GROQ_API_KEY='real-key'\nUNRELATED=value\nMAS_PROVIDER=gemini\n", encoding="utf-8")
            self.assertEqual(config._read_dotenv(path), {"GROQ_API_KEY": "real-key", "MAS_PROVIDER": "gemini"})

    def test_placeholder_secret_is_not_accepted(self):
        self.assertFalse(config._is_configured_secret("your_groq_api_key_here"))
        self.assertFalse(config._is_configured_secret(""))
        self.assertTrue(config._is_configured_secret("actual-secret-value"))

    def test_environment_key_and_provider_are_applied(self):
        with patch.dict(os.environ, {"GROQ_API_KEY": "actual-secret-value", "MAS_PROVIDER": "groq"}, clear=False):
            cfg = config._apply_runtime_config_for_test(dotenv={})
        self.assertEqual(cfg["provider"], "groq")
        self.assertEqual(cfg["api_keys"]["groq"], "actual-secret-value")

    def test_placeholder_keys_are_not_reported_as_configured(self):
        with patch.dict(os.environ, {"GROQ_API_KEY": "your_groq_api_key_here"}, clear=False):
            cfg = config._apply_runtime_config_for_test(dotenv={})
        self.assertEqual(cfg["api_keys"]["groq"], "")


if __name__ == "__main__":
    unittest.main()
