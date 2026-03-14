import unittest

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))

from llm_bridge import EchoBridge, OpenAICompatibleBridge, _extract_openai_content


class LLMBridgeTests(unittest.TestCase):
    def test_echo_bridge_streams_tokens(self):
        bridge = EchoBridge()
        out = "".join(list(bridge.stream_text("hello world"))).strip()
        self.assertEqual(out, "[echo] hello world")

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

    def test_openai_compatible_requires_api_key(self):
        bridge = OpenAICompatibleBridge(
            provider="openclaw",
            api_key="",
            base_url="https://example.com/v1",
            model="x",
        )
        with self.assertRaises(RuntimeError):
            list(bridge.stream_text("hello"))


if __name__ == "__main__":
    unittest.main()
