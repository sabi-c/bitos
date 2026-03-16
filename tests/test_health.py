"""Tests for ServiceHealth — service connectivity checker."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

from health import ServiceHealth, check_mic


class ServiceHealthTests(unittest.TestCase):
    def test_initial_state(self):
        h = ServiceHealth()
        self.assertFalse(h.is_complete())
        self.assertFalse(h.all_ok())
        self.assertEqual(h.summary_line(), "checking...")

    def test_mock_mic_passes(self):
        with patch.dict("os.environ", {"BITOS_AUDIO": "mock"}):
            result = check_mic()
        self.assertTrue(result["ok"])
        self.assertEqual(result["detail"], "mock mode")

    def test_summary_shows_failures(self):
        h = ServiceHealth()
        h.results = {
            "internet": {"ok": True, "detail": "50ms", "latency_ms": 50},
            "backend": {"ok": True, "detail": "30ms", "latency_ms": 30},
            "groq": {"ok": False, "detail": "GROQ_API_KEY not set", "latency_ms": 0},
            "mic": {"ok": True, "detail": "mock mode", "latency_ms": 0},
        }
        self.assertTrue(h.is_complete())
        self.assertFalse(h.all_ok())
        self.assertIn("groq", h.summary_line())

    def test_all_ok_when_passing(self):
        h = ServiceHealth()
        h.results = {
            "internet": {"ok": True, "detail": "50ms", "latency_ms": 50},
            "backend": {"ok": True, "detail": "30ms", "latency_ms": 30},
            "groq": {"ok": True, "detail": "100ms", "latency_ms": 100},
            "mic": {"ok": True, "detail": "mock mode", "latency_ms": 0},
        }
        self.assertTrue(h.all_ok())
        self.assertEqual(h.summary_line(), "all services ok")


if __name__ == "__main__":
    unittest.main()
