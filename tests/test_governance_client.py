"""Tests for GovernanceClient."""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))

from governance_client import GovernanceClient  # noqa: E402


def test_client_init_with_base_url():
    client = GovernanceClient(base_url="http://myhost:9000")
    assert client.base_url == "http://myhost:9000"


def test_client_default_url():
    client = GovernanceClient()
    assert client.base_url == "http://localhost:8100"


def _make_mock_response(lines):
    mock_response = MagicMock()
    mock_response.iter_lines.return_value = iter(lines)
    mock_response.raise_for_status = MagicMock()
    mock_response.__enter__ = MagicMock(return_value=mock_response)
    mock_response.__exit__ = MagicMock(return_value=False)
    return mock_response


def test_chat_stream_yields_text():
    fake_lines = [
        'data: {"text": "Hello"}',
        'data: {"text": " world"}',
        "data: [DONE]",
    ]
    mock_response = _make_mock_response(fake_lines)

    with patch("governance_client.httpx.stream", return_value=mock_response):
        client = GovernanceClient()
        chunks = list(client.chat_stream("hi"))

    assert chunks == ["Hello", " world"]


def test_chat_stream_stores_conversation_id():
    fake_lines = [
        'data: {"conversation_id": "conv-abc123"}',
        'data: {"text": "Hi"}',
        "data: [DONE]",
    ]
    mock_response = _make_mock_response(fake_lines)

    with patch("governance_client.httpx.stream", return_value=mock_response):
        client = GovernanceClient()
        chunks = list(client.chat_stream("hello"))

    assert client.last_conversation_id == "conv-abc123"
    assert chunks == ["Hi"]


def test_chat_stream_handles_connection_error():
    with patch(
        "governance_client.httpx.stream",
        side_effect=__import__("httpx").ConnectError("refused"),
    ):
        client = GovernanceClient()
        chunks = list(client.chat_stream("hi"))

    assert len(chunks) == 1
    assert "Cannot reach agent server" in chunks[0]


def test_chat_stream_handles_timeout():
    with patch(
        "governance_client.httpx.stream",
        side_effect=__import__("httpx").TimeoutException("timed out"),
    ):
        client = GovernanceClient()
        chunks = list(client.chat_stream("hi"))

    assert len(chunks) == 1
    assert "timed out" in chunks[0].lower()
