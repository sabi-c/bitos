"""Tests for the SMS gateway, BlueBubbles webhook, and heartbeat SMS fallback."""
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# SDL dummy driver for tests that may import pygame indirectly
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server" / "integrations"))


class TestSMSGatewaySession(unittest.TestCase):
    """Test session management (create, reuse, timeout)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        # Patch DB_PATH to use temp dir
        self._db_path = Path(self._tmp.name) / "sms_sessions.db"

    def tearDown(self):
        self._tmp.cleanup()

    @patch("integrations.sms_gateway.DB_PATH")
    @patch("integrations.sms_gateway.DATA_DIR")
    def _make_gateway(self, mock_data_dir, mock_db_path):
        mock_db_path.__str__ = lambda s: str(self._db_path)
        mock_data_dir.mkdir = MagicMock()
        from integrations.sms_gateway import SMSGateway
        return SMSGateway()

    def test_get_or_create_session_new(self):
        """First contact creates a new session and conversation."""
        with patch("integrations.sms_gateway.DB_PATH", self._db_path), \
             patch("integrations.sms_gateway.DATA_DIR", Path(self._tmp.name)):
            from integrations.sms_gateway import SMSGateway
            gw = SMSGateway()
            conv_id = gw._get_or_create_session("imessage", "+15551234567")
            self.assertIsInstance(conv_id, str)
            self.assertTrue(len(conv_id) > 0)

    def test_get_or_create_session_reuse(self):
        """Same sender within 30 min gets the same conversation."""
        with patch("integrations.sms_gateway.DB_PATH", self._db_path), \
             patch("integrations.sms_gateway.DATA_DIR", Path(self._tmp.name)):
            from integrations.sms_gateway import SMSGateway
            gw = SMSGateway()
            conv1 = gw._get_or_create_session("imessage", "+15551234567")
            conv2 = gw._get_or_create_session("imessage", "+15551234567")
            self.assertEqual(conv1, conv2)

    def test_get_or_create_session_timeout(self):
        """After 30 min timeout, a new conversation is created."""
        with patch("integrations.sms_gateway.DB_PATH", self._db_path), \
             patch("integrations.sms_gateway.DATA_DIR", Path(self._tmp.name)):
            from integrations.sms_gateway import SMSGateway, _get_db
            gw = SMSGateway()
            conv1 = gw._get_or_create_session("imessage", "+15551234567")

            # Manually set last_activity to 31 min ago
            old_time = (datetime.now(timezone.utc) - timedelta(minutes=31)).isoformat()
            db = _get_db()
            db.execute(
                "UPDATE sms_sessions SET last_activity = ? WHERE id = ?",
                (old_time, "imessage:+15551234567"),
            )
            db.commit()
            db.close()

            conv2 = gw._get_or_create_session("imessage", "+15551234567")
            self.assertNotEqual(conv1, conv2)

    def test_different_senders_different_sessions(self):
        """Different senders get different conversations."""
        with patch("integrations.sms_gateway.DB_PATH", self._db_path), \
             patch("integrations.sms_gateway.DATA_DIR", Path(self._tmp.name)):
            from integrations.sms_gateway import SMSGateway
            gw = SMSGateway()
            conv1 = gw._get_or_create_session("imessage", "+15551234567")
            conv2 = gw._get_or_create_session("imessage", "+15559876543")
            self.assertNotEqual(conv1, conv2)


class TestSMSGatewaySendOutbound(unittest.TestCase):
    """Test outbound message routing."""

    def test_send_outbound_no_adapter(self):
        """Sending to an unregistered channel returns False."""
        import asyncio
        with patch("integrations.sms_gateway.DB_PATH", Path(tempfile.mktemp())), \
             patch("integrations.sms_gateway.DATA_DIR", Path(tempfile.mkdtemp())):
            from integrations.sms_gateway import SMSGateway
            gw = SMSGateway()
            result = asyncio.get_event_loop().run_until_complete(
                gw.send_outbound("telegram", "+1555", "hello")
            )
            self.assertFalse(result)

    def test_send_outbound_with_adapter(self):
        """Sending to a registered channel calls the adapter."""
        import asyncio
        with patch("integrations.sms_gateway.DB_PATH", Path(tempfile.mktemp())), \
             patch("integrations.sms_gateway.DATA_DIR", Path(tempfile.mkdtemp())):
            from integrations.sms_gateway import SMSGateway
            gw = SMSGateway()
            mock_adapter = MagicMock()
            mock_adapter.send_message.return_value = True
            gw.register_adapter("imessage", mock_adapter)
            result = asyncio.get_event_loop().run_until_complete(
                gw.send_outbound("imessage", "iMessage;+;+1555", "hello")
            )
            self.assertTrue(result)
            mock_adapter.send_message.assert_called_once_with("iMessage;+;+1555", "hello")


class TestBlueBubblesAdapterEnhancements(unittest.TestCase):
    """Test new BlueBubbles adapter methods."""

    def test_self_chat_guid_from_env(self):
        """self_chat_guid reads from the module-level default (set via env)."""
        import integrations.bluebubbles_adapter as bb_mod
        original = bb_mod._DEFAULT_SELF_CHAT_GUID
        try:
            bb_mod._DEFAULT_SELF_CHAT_GUID = "iMessage;+;+15551234567"
            adapter = bb_mod.BlueBubblesAdapter()
            self.assertEqual(adapter.self_chat_guid, "iMessage;+;+15551234567")
        finally:
            bb_mod._DEFAULT_SELF_CHAT_GUID = original

    def test_get_chat_guid_for_address_mock(self):
        """Mock mode returns a synthetic GUID."""
        from integrations.bluebubbles_adapter import BlueBubblesAdapter
        adapter = BlueBubblesAdapter()  # no password → mock mode
        guid = adapter.get_chat_guid_for_address("+15551234567")
        self.assertEqual(guid, "iMessage;+;+15551234567")

    def test_send_message_async_mock(self):
        """Async send in mock mode returns True."""
        import asyncio
        from integrations.bluebubbles_adapter import BlueBubblesAdapter
        adapter = BlueBubblesAdapter()
        result = asyncio.get_event_loop().run_until_complete(
            adapter.send_message_async("iMessage;+;+1555", "test")
        )
        self.assertTrue(result)


class TestWebhookBlueBubbles(unittest.TestCase):
    """Test the BlueBubbles webhook endpoint."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        settings_file = Path(self._tmp.name) / "ui_settings.json"

        import main as server_main
        from ui_settings import UISettingsStore
        from llm_bridge import EchoBridge

        server_main.settings_store = UISettingsStore(str(settings_file))
        server_main.llm_bridge = EchoBridge()

        from fastapi.testclient import TestClient
        self.client = TestClient(server_main.app)

    def tearDown(self):
        self._tmp.cleanup()

    def test_ignores_non_new_message(self):
        """Non 'new-message' types are skipped."""
        resp = self.client.post("/webhook/bluebubbles", json={
            "type": "chat-read-status-changed",
            "data": {},
        })
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body.get("ok"))
        self.assertEqual(body.get("skipped"), "chat-read-status-changed")

    def test_ignores_from_me(self):
        """Our own outgoing messages are skipped."""
        resp = self.client.post("/webhook/bluebubbles", json={
            "type": "new-message",
            "data": {"isFromMe": True, "text": "hi"},
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json().get("skipped"), "from_me")

    def test_ignores_empty_text(self):
        """Empty text messages are skipped."""
        resp = self.client.post("/webhook/bluebubbles", json={
            "type": "new-message",
            "data": {
                "isFromMe": False,
                "text": "",
                "handle": {"address": "+1555"},
            },
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json().get("skipped"), "empty_text")

    def test_rejects_no_sender(self):
        """Messages without a sender address return error."""
        resp = self.client.post("/webhook/bluebubbles", json={
            "type": "new-message",
            "data": {
                "isFromMe": False,
                "text": "hello",
                "handle": {},
            },
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json().get("error"), "no sender")

    def test_processes_valid_message(self):
        """A valid incoming message gets processed and replied to."""
        resp = self.client.post("/webhook/bluebubbles", json={
            "type": "new-message",
            "data": {
                "isFromMe": False,
                "text": "What time is it?",
                "handle": {"address": "+15551234567"},
                "chats": [{"guid": "iMessage;+;+15551234567"}],
            },
        })
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body.get("ok"))
        self.assertTrue(body.get("responded"))


class TestHeartbeatSMSFallback(unittest.TestCase):
    """Test that heartbeat falls back to iMessage when no WS clients."""

    def test_deliver_calls_sms_fallback_when_no_clients(self):
        """When no WS clients are connected, _deliver should call _sms_fallback."""
        import asyncio
        from heartbeat import _HeartbeatEngine, _proactive_clients

        # Ensure no clients
        _proactive_clients.clear()

        engine = _HeartbeatEngine()
        engine._sms_fallback = AsyncMock()

        now = datetime.now(timezone.utc)
        asyncio.get_event_loop().run_until_complete(
            engine._deliver("Test message", "morning_briefing", now)
        )
        engine._sms_fallback.assert_called_once_with("Test message", "morning_briefing")

    def test_deliver_skips_sms_fallback_with_clients(self):
        """When WS clients are connected, _deliver should NOT call _sms_fallback."""
        import asyncio
        from heartbeat import _HeartbeatEngine, _proactive_clients

        # Add a mock client
        mock_ws = AsyncMock()
        _proactive_clients.add(mock_ws)

        try:
            engine = _HeartbeatEngine()
            engine._sms_fallback = AsyncMock()

            now = datetime.now(timezone.utc)
            asyncio.get_event_loop().run_until_complete(
                engine._deliver("Test message", "morning_briefing", now)
            )
            engine._sms_fallback.assert_not_called()
        finally:
            _proactive_clients.discard(mock_ws)


if __name__ == "__main__":
    unittest.main()
