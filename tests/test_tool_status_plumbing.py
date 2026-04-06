"""Test that tool_status events flow from SSE through both clients."""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))


def _make_mock_response(lines):
    mock_response = MagicMock()
    mock_response.iter_lines.return_value = iter(lines)
    mock_response.raise_for_status = MagicMock()
    mock_response.__enter__ = MagicMock(return_value=mock_response)
    mock_response.__exit__ = MagicMock(return_value=False)
    return mock_response


def test_governance_client_yields_tool_status():
    """GovernanceClient yields tool_status dicts from SSE."""
    from governance_client import GovernanceClient

    fake_lines = [
        'data: {"tool_status": "Searching..."}',
        'data: {"text": "Found it"}',
        "data: [DONE]",
    ]
    mock_response = _make_mock_response(fake_lines)

    with patch("governance_client.httpx.stream", return_value=mock_response):
        client = GovernanceClient(base_url="http://fake")
        chunks = list(client.chat_stream("test"))

    assert {"tool_status": "Searching..."} in chunks
    assert "Found it" in chunks


def test_backend_client_yields_tool_status():
    """BackendClient._stream_chat_sse yields tool_status dicts from SSE."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

    # Stub out device-only imports that BackendClient.chat() uses
    with patch.dict(sys.modules, {
        "power": MagicMock(),
        "storage": MagicMock(),
        "storage.repository": MagicMock(),
    }):
        from client.api import BackendClient

    fake_lines = [
        'data: {"tool_status": "Reading email..."}',
        'data: {"text": "Done"}',
        "data: [DONE]",
    ]
    mock_response = _make_mock_response(fake_lines)

    with patch("client.api.httpx.stream", return_value=mock_response):
        client = BackendClient(base_url="http://fake")
        # Call _stream_chat_sse directly to avoid chat()'s device dependencies
        chunks = list(client._stream_chat_sse("test", "producer", [], None))

    assert {"tool_status": "Reading email..."} in chunks
    assert "Done" in chunks
