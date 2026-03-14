import unittest

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))

from llm_bridge import (
    EchoBridge,
    OpenAICompatibleBridge,
    _extract_openai_content,
    _normalise_base_url,
)


class LLMBridgeTests(unittest.TestCase):
    def test_echo_bridge_streams_tokens(self):
        bridge = EchoBridge()
        out = "".join(list(bridge.stream_text("hello world"))).strip()
        self.assertEqual(out, "[echo] hello world")

    def test_echo_bridge_streams_without_api_calls(self):
        """Echo bridge must yield token-by-token without any network I/O."""
        bridge = EchoBridge()
        tokens = list(bridge.stream_text("one two three"))
        self.assertTrue(len(tokens) >= 3, "should yield at least one token per word")
        full = "".join(tokens).strip()
        self.assertEqual(full, "[echo] one two three")

    def test_extract_openai_content_handles_string(self):
        payload = {
            "choices": [
                {"message": {"content": "hello from provider"}}
            ]
        }
        self.assertEqual(_extract_openai_content(payload), "hello from provider")

    def test_extract_openai_content_handles_part_list(self):
        payload = {
            "choices": [
                {
                    "message": {
                        "content": [
                            {"type": "text", "text": "hello "},
                            {"type": "text", "text": "world"},
                        ]
                    }
                }
            ]
        }
        self.assertEqual(_extract_openai_content(payload), "hello world")

    def test_openai_compatible_allows_empty_api_key(self):
        """Local servers (OpenClaw, NanoClaw) often need no auth."""
        bridge = OpenAICompatibleBridge(
            provider="openclaw",
            api_key="",
            base_url="http://localhost:18789",
            model="x",
        )
        # Should not raise on construction; only fails on actual network call.
        self.assertEqual(bridge.provider, "openclaw")

    def test_normalise_base_url_ws_to_http(self):
        self.assertEqual(
            _normalise_base_url("ws://localhost:18789"),
            "http://localhost:18789/v1",
        )

    def test_normalise_base_url_wss_to_https(self):
        self.assertEqual(
            _normalise_base_url("wss://example.com"),
            "https://example.com/v1",
        )

    def test_normalise_base_url_preserves_existing_v1(self):
        self.assertEqual(
            _normalise_base_url("https://api.openai.com/v1"),
            "https://api.openai.com/v1",
        )

    def test_normalise_base_url_appends_v1(self):
        self.assertEqual(
            _normalise_base_url("http://localhost:18789"),
            "http://localhost:18789/v1",
        )


if __name__ == "__main__":
    unittest.main()
