"""Tests for server/memory/fact_extractor.py — LLM-powered fact extraction."""

import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

SERVER_DIR = os.path.join(os.path.dirname(__file__), "..", "server")
sys.path.insert(0, SERVER_DIR)

from memory.memory_store import MemoryStore
from memory.fact_extractor import FactExtractor


@pytest.fixture
def store(tmp_path):
    db_path = tmp_path / "test_extractor.db"
    s = MemoryStore(db_path=db_path)
    yield s
    s.close()


@pytest.fixture
def extractor(store):
    return FactExtractor(store, api_key="test-key")


class TestTurnBuffering:
    def test_initial_turn_count(self, extractor):
        assert extractor.turn_count == 0

    def test_add_turn_increments_count(self, extractor):
        extractor.add_turn("hello", "hi there")
        assert extractor.turn_count == 1

    def test_should_extract_at_threshold(self, extractor):
        for i in range(7):
            extractor.add_turn(f"msg {i}", f"reply {i}")
        assert not extractor.should_extract()

        extractor.add_turn("msg 8", "reply 8")
        assert extractor.should_extract()

    def test_extract_if_ready_does_nothing_under_threshold(self, extractor):
        extractor.add_turn("hello", "hi")
        result = extractor.extract_if_ready("conv-1")
        assert result == []


class TestJSONParsing:
    def test_parse_direct_array(self):
        text = '[{"content": "fact", "category": "preference", "confidence": 0.9}]'
        result = FactExtractor._parse_json(text)
        assert isinstance(result, list)
        assert len(result) == 1

    def test_parse_wrapped_object(self):
        text = '{"facts": [{"content": "fact one"}]}'
        result = FactExtractor._parse_json(text)
        assert isinstance(result, dict)
        assert "facts" in result

    def test_parse_code_fence(self):
        text = '```json\n[{"content": "fenced"}]\n```'
        result = FactExtractor._parse_json(text)
        assert isinstance(result, list)

    def test_parse_with_surrounding_text(self):
        text = 'Here are the facts:\n{"facts": [{"content": "found"}]}\nDone.'
        result = FactExtractor._parse_json(text)
        assert result is not None

    def test_parse_invalid_json(self):
        assert FactExtractor._parse_json("not json at all") is None

    def test_parse_empty_array(self):
        result = FactExtractor._parse_json("[]")
        assert result == []


class TestExtraction:
    def _mock_anthropic_response(self, facts_json):
        """Build a mock Anthropic response returning the given JSON string."""
        mock_response = MagicMock()
        mock_block = MagicMock()
        mock_block.text = facts_json
        mock_response.content = [mock_block]
        return mock_response

    @patch("memory.fact_extractor.anthropic.Anthropic")
    def test_extract_from_turn_stores_facts(self, mock_anthropic_cls, store, extractor):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client

        facts = [
            {"content": "User prefers dark mode", "category": "preference", "confidence": 0.95},
            {"content": "User lives in Berlin", "category": "biographical", "confidence": 0.9},
        ]
        mock_client.messages.create.return_value = self._mock_anthropic_response(json.dumps(facts))

        result = extractor.extract_from_turn(
            "I really prefer dark mode and I live in Berlin",
            "Noted! Dark mode it is.",
            conversation_id="conv-test",
        )

        assert len(result) == 2
        assert result[0]["content"] == "User prefers dark mode"
        assert result[1]["category"] == "biographical"

        # Verify facts are in the store
        assert store.count_facts() == 2

    @patch("memory.fact_extractor.anthropic.Anthropic")
    def test_extract_handles_empty_response(self, mock_anthropic_cls, extractor):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.return_value = self._mock_anthropic_response("[]")

        result = extractor.extract_from_turn("hello", "hi there", "conv-1")
        assert result == []

    @patch("memory.fact_extractor.anthropic.Anthropic")
    def test_extract_handles_wrapped_format(self, mock_anthropic_cls, store, extractor):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client

        response_json = '{"facts": [{"content": "User likes espresso", "category": "preference", "confidence": 0.85}]}'
        mock_client.messages.create.return_value = self._mock_anthropic_response(response_json)

        result = extractor.extract_from_turn("I love espresso", "Great taste!", "conv-2")
        assert len(result) == 1
        assert store.count_facts() == 1

    @patch("memory.fact_extractor.anthropic.Anthropic")
    def test_extract_skips_short_messages(self, mock_anthropic_cls, extractor):
        result = extractor.extract_from_turn("hi", "hello", "conv-3")
        assert result == []
        # Anthropic should NOT have been called
        mock_anthropic_cls.assert_not_called()

    @patch("memory.fact_extractor.anthropic.Anthropic")
    def test_extract_handles_api_error(self, mock_anthropic_cls, extractor):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.side_effect = Exception("API down")

        result = extractor.extract_from_turn(
            "Some meaningful message here",
            "A response",
            "conv-4",
        )
        assert result == []  # Should not raise

    @patch("memory.fact_extractor.anthropic.Anthropic")
    def test_extract_skips_low_quality_facts(self, mock_anthropic_cls, store, extractor):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client

        # One good fact, one too short
        facts = [
            {"content": "User prefers Python", "category": "preference", "confidence": 0.9},
            {"content": "hi", "category": "general", "confidence": 0.5},
        ]
        mock_client.messages.create.return_value = self._mock_anthropic_response(json.dumps(facts))

        result = extractor.extract_from_turn("I code in Python", "Nice!", "conv-5")
        assert len(result) == 1
        assert store.count_facts() == 1

    @patch("memory.fact_extractor.anthropic.Anthropic")
    def test_batch_extraction(self, mock_anthropic_cls, store, extractor):
        """Test the batch mode: buffer 8 turns then extract."""
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client

        facts = [{"content": "User is a software engineer", "category": "biographical", "confidence": 0.9}]
        mock_client.messages.create.return_value = self._mock_anthropic_response(json.dumps(facts))

        # Buffer 8 turns
        for i in range(8):
            extractor.add_turn(f"Message about coding project {i}", f"Response {i}")

        assert extractor.should_extract()
        result = extractor.extract_now("conv-batch")

        assert len(result) == 1
        assert extractor.turn_count == 0  # Reset after extraction
