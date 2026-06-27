"""Integration tests for the HTTP API (app.py), via Flask's test client.

These formalize the M3-M5 endpoint checks that were previously run by hand with curl:
POST /submit (+ validation), GET /log, POST /appeal (+ 404), the appeal queue, and rate
limiting. The Groq call is stubbed so the tests are deterministic, free, and offline; the
audit log is redirected to a temp file so tests never touch logs/audit.jsonl.

Run: python -m unittest discover -s tests -t .
"""
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
import detector  # noqa: F401  (patched below)
import app as app_module

app = app_module.app


def _fake_llm_signal(text):
    """Deterministic stand-in for the Groq call."""
    return {"p_ai": 0.5, "rationale": "stub"}


class ApiTestBase(unittest.TestCase):
    def setUp(self):
        # Redirect the audit log to a temp file for the duration of each test.
        fd, self._log_path = tempfile.mkstemp(suffix=".jsonl")
        os.close(fd)
        self._log_patch = mock.patch.object(config, "LOG_PATH", self._log_path)
        self._log_patch.start()

        # Stub the LLM signal so no API call happens.
        self._llm_patch = mock.patch.object(detector, "llm_signal", _fake_llm_signal)
        self._llm_patch.start()

        # Disable rate limiting by default; the rate-limit test re-enables it explicitly.
        app_module.limiter.enabled = False

        app.testing = True
        self.client = app.test_client()

    def tearDown(self):
        self._llm_patch.stop()
        self._log_patch.stop()
        app_module.limiter.enabled = False
        if os.path.exists(self._log_path):
            os.remove(self._log_path)

    def _submit(self, text="some submitted text for analysis", creator_id="tester"):
        return self.client.post("/submit", json={"text": text, "creator_id": creator_id})


class TestSubmit(ApiTestBase):
    def test_submit_returns_expected_fields(self):
        resp = self._submit()
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        for key in ("content_id", "attribution", "confidence", "label"):
            self.assertIn(key, data)
        self.assertIn(data["attribution"], config.VALID_ATTRIBUTIONS)
        self.assertGreaterEqual(data["confidence"], 0.0)
        self.assertLessEqual(data["confidence"], 1.0)
        self.assertTrue(data["label"])  # non-empty label text

    def test_submit_missing_fields_returns_400(self):
        self.assertEqual(self.client.post("/submit", json={"text": "hi"}).status_code, 400)
        self.assertEqual(self.client.post("/submit", json={"creator_id": "x"}).status_code, 400)

    def test_submit_writes_audit_entry(self):
        self._submit()
        resp = self.client.get("/log")
        entries = resp.get_json()["entries"]
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["event"], "submission")
        self.assertEqual(entries[0]["status"], "classified")
        self.assertIn("llm_score", entries[0])
        self.assertIn("style_score", entries[0])


class TestLog(ApiTestBase):
    def test_log_returns_most_recent_first(self):
        self._submit(creator_id="first")
        self._submit(creator_id="second")
        entries = self.client.get("/log").get_json()["entries"]
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0]["creator_id"], "second")  # most recent first


class TestAppeal(ApiTestBase):
    def test_appeal_updates_status_and_logs(self):
        content_id = self._submit().get_json()["content_id"]
        resp = self.client.post("/appeal", json={
            "content_id": content_id,
            "creator_reasoning": "I wrote this myself.",
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["status"], "under_review")

        queue = self.client.get("/log?status=under_review").get_json()["entries"]
        self.assertEqual(len(queue), 1)
        self.assertEqual(queue[0]["event"], "appeal")
        self.assertEqual(queue[0]["content_id"], content_id)
        self.assertIn("appeal_reasoning", queue[0])
        self.assertIn("original_attribution", queue[0])

    def test_appeal_unknown_content_id_returns_404(self):
        resp = self.client.post("/appeal", json={
            "content_id": "does-not-exist",
            "creator_reasoning": "test",
        })
        self.assertEqual(resp.status_code, 404)

    def test_appeal_missing_fields_returns_400(self):
        resp = self.client.post("/appeal", json={"content_id": "x"})
        self.assertEqual(resp.status_code, 400)


class TestRateLimiting(ApiTestBase):
    def test_eleventh_request_is_rejected(self):
        # The submit limit is "10 per minute"; enable limiting just for this test.
        app_module.limiter.enabled = True
        codes = [self._submit().status_code for _ in range(12)]
        self.assertEqual(codes[:10], [200] * 10)
        self.assertTrue(all(c == 429 for c in codes[10:]),
                        msg=f"expected 429s after 10 requests, got {codes}")


if __name__ == "__main__":
    unittest.main()
