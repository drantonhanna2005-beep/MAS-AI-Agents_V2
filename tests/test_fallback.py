"""اختبارات المزود الاحتياطي التلقائي (Fallback) — بدون شبكة.

تتحقق من:
1. get_fallback لا يُرجع إعداداً ناقصاً.
2. get_fallback يُرجع إعداداً صحيحاً لـ custom و openrouter.
3. سلسلة المرشحين في المنسّق تُضيف الاحتياطي في النهاية فقط.
4. stream_chat لمزود custom يرفض الطلب بوضوح عند غياب base_url.
"""
from __future__ import annotations

import copy
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.config import DEFAULT_CONFIG, get_fallback  # noqa: E402
from core.llm import LLMError, stream_chat  # noqa: E402
from agents.orchestrator import _chat_candidates  # noqa: E402


def _cfg(fallback: dict) -> dict:
    cfg = copy.deepcopy(DEFAULT_CONFIG)
    cfg["api_keys"] = {"groq": "", "openrouter": "sk-or-test", "gemini": ""}
    cfg["fallback"] = fallback
    return cfg


class FallbackConfigTests(unittest.TestCase):
    def test_disabled_returns_none(self):
        self.assertIsNone(get_fallback(_cfg({"enabled": False, "api_key": "k", "model": "m",
                                            "base_url": "https://x/v1"})))

    def test_incomplete_returns_none(self):
        # ناقص base_url لمزود custom
        self.assertIsNone(get_fallback(_cfg({"enabled": True, "provider": "custom",
                                            "api_key": "k", "model": "m", "base_url": ""})))
        # ناقص model
        self.assertIsNone(get_fallback(_cfg({"enabled": True, "provider": "custom",
                                            "api_key": "k", "model": "", "base_url": "https://x/v1"})))
        # ناقص api_key
        self.assertIsNone(get_fallback(_cfg({"enabled": True, "provider": "custom",
                                            "api_key": "", "model": "m", "base_url": "https://x/v1"})))

    def test_custom_complete(self):
        fb = get_fallback(_cfg({"enabled": True, "provider": "custom", "api_key": "sk-test",
                                "model": "my-model", "base_url": "https://api.example.com/v1/"}))
        self.assertIsNotNone(fb)
        self.assertEqual(fb["provider"], "custom")
        self.assertEqual(fb["model"], "my-model")
        self.assertEqual(fb["base_url"], "https://api.example.com/v1")

    def test_openrouter_complete_uses_official_base(self):
        fb = get_fallback(_cfg({"enabled": True, "provider": "openrouter", "api_key": "sk-or-test",
                                "model": "openrouter/free", "base_url": ""}))
        self.assertIsNotNone(fb)
        self.assertEqual(fb["provider"], "openrouter")
        self.assertEqual(fb["base_url"], "https://openrouter.ai/api/v1")

    def test_openrouter_incomplete_returns_none(self):
        self.assertIsNone(get_fallback(_cfg({"enabled": True, "provider": "openrouter",
                                            "api_key": "sk-or-test", "model": "", "base_url": ""})))


class FallbackCandidateTests(unittest.TestCase):
    def test_fallback_appended_last(self):
        cfg = _cfg({"enabled": True, "provider": "custom", "api_key": "sk-fb",
                    "model": "fb-model", "base_url": "https://api.example.com/v1"})
        prov = {"provider": "openrouter", "model": "openrouter/free"}
        cands = _chat_candidates(cfg, prov, "openrouter/free")
        self.assertGreaterEqual(len(cands), 2)
        self.assertEqual(cands[0]["provider"], "openrouter")
        last = cands[-1]
        self.assertEqual(last["provider"], "custom")
        self.assertEqual(last["model"], "fb-model")
        self.assertEqual(last["base_url"], "https://api.example.com/v1")

    def test_fallback_absent_when_incomplete(self):
        cfg = _cfg({"enabled": True, "provider": "custom", "api_key": "sk-fb",
                    "model": "fb-model", "base_url": ""})
        prov = {"provider": "openrouter", "model": "openrouter/free"}
        cands = _chat_candidates(cfg, prov, "openrouter/free")
        self.assertFalse(any(c["provider"] == "custom" for c in cands))

    def test_fallback_filtered_for_vision(self):
        cfg = _cfg({"enabled": True, "provider": "custom", "api_key": "sk-fb",
                    "model": "fb-model", "base_url": "https://api.example.com/v1"})
        prov = {"provider": "openrouter", "model": "openrouter/free", "vision_model": "openrouter/free"}
        cands = _chat_candidates(cfg, prov, "openrouter/free")
        self.assertFalse(any(c["provider"] == "custom" for c in cands))


class _SSEHandler(BaseHTTPRequestHandler):
    """خادم OpenAI-compatible وهمي محلي لإثبات أن مسار custom يعمل فعلياً (بدون شبكة خارجية)."""

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length") or 0)
        self.rfile.read(length)
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        for chunk in (b'data: {"choices":[{"delta":{"content":"OK"}}]}\n\n',
                      b'data: [DONE]\n\n'):
            self.wfile.write(chunk)
            self.wfile.flush()

    def log_message(self, *args):  # كتم سجلات الخادم الوهمي
        pass


class FallbackTransportTests(unittest.TestCase):
    def test_custom_openai_compatible_stream_works_end_to_end(self):
        from core.llm import complete
        srv = HTTPServer(("127.0.0.1", 0), _SSEHandler)
        port = srv.server_address[1]
        t = threading.Thread(target=srv.serve_forever, daemon=True)
        t.start()
        try:
            thinking, content = complete(
                "custom", "test-model", [{"role": "user", "content": "hi"}],
                api_key="sk-test", base_url=f"http://127.0.0.1:{port}/v1", temperature=0.0)
        finally:
            srv.shutdown()
            srv.server_close()
            t.join(timeout=5)
        self.assertEqual(thinking, "")
        self.assertEqual(content, "OK")


class FallbackStreamTests(unittest.TestCase):
    def test_custom_requires_base_url(self):
        with self.assertRaises(LLMError):
            list(stream_chat("custom", "m", [{"role": "user", "content": "hi"}],
                             api_key="sk-test", base_url=""))

    def test_custom_requires_key(self):
        with self.assertRaises(LLMError):
            list(stream_chat("custom", "m", [{"role": "user", "content": "hi"}],
                             api_key="", base_url="https://api.example.com/v1"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
