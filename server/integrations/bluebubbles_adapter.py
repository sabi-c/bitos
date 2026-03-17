"""BlueBubbles iMessage adapter for BITOS server."""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Chat GUID for agent-initiated messages (e.g. proactive heartbeat via iMessage).
# Set via BLUEBUBBLES_SELF_CHAT_GUID env var, or use the API to look up by address.
_DEFAULT_SELF_CHAT_GUID = os.environ.get("BLUEBUBBLES_SELF_CHAT_GUID", "")


class BlueBubblesAdapter:
    MOCK_DATA = {
        "conversations": [
            {
                "chat_id": "iMessage;+;+13105550001",
                "title": "Joaquin",
                "snippet": "re: invoice — can you resend?",
                "timestamp": "2m ago",
                "unread": 2,
            },
            {
                "chat_id": "iMessage;+;+13105550002",
                "title": "Anthony",
                "snippet": "furniture looks great btw",
                "timestamp": "15m ago",
                "unread": 0,
            },
            {
                "chat_id": "iMessage;+;+13105550003",
                "title": "Mom",
                "snippet": "Sunday dinner?",
                "timestamp": "1h ago",
                "unread": 1,
            },
        ],
        "messages": {
            "iMessage;+;+13105550001": [
                {
                    "id": "1",
                    "sender": "me",
                    "text": "Sent the invoice draft yesterday",
                    "timestamp": "yesterday",
                    "from_me": True,
                },
                {
                    "id": "2",
                    "sender": "Joaquin",
                    "text": "Did you get my last message?",
                    "timestamp": "10m ago",
                    "from_me": False,
                },
                {
                    "id": "3",
                    "sender": "Joaquin",
                    "text": "re: invoice — can you resend?",
                    "timestamp": "2m ago",
                    "from_me": False,
                },
            ]
        },
    }

    def __init__(self):
        self._base = os.environ.get("BLUEBUBBLES_BASE_URL", "http://localhost:1234")
        self._pw = os.environ.get("BLUEBUBBLES_PASSWORD", "")
        self._mock = not self._pw

    @property
    def is_mock(self) -> bool:
        return self._mock

    @property
    def base_url(self) -> str:
        return self._base

    def _p(self, extra=None):
        p = {"password": self._pw}
        if extra:
            p.update(extra)
        return p

    def get_conversations(self, limit=25) -> list[dict]:
        if self._mock:
            return self.MOCK_DATA["conversations"]
        response = httpx.get(
            f"{self._base}/api/v1/chat/query",
            params=self._p({"limit": limit}),
            timeout=10,
        )
        response.raise_for_status()
        chats = response.json().get("data", [])
        return [self._normalize_chat(chat) for chat in chats]

    def get_messages(self, chat_id: str, limit=15) -> list[dict]:
        if self._mock:
            return self.MOCK_DATA["messages"].get(chat_id, [])
        response = httpx.get(
            f"{self._base}/api/v1/chat/{chat_id}/message",
            params=self._p({"limit": limit}),
            timeout=10,
        )
        response.raise_for_status()
        messages = response.json().get("data", [])
        return [self._normalize_msg(message) for message in messages]

    def send_message(self, chat_id: str, text: str) -> bool:
        """Tier 1 — caller must pass confirmed=True."""
        if self._mock:
            logger.info("mock_send chat=%s", chat_id[:30])
            return True
        response = httpx.post(
            f"{self._base}/api/v1/message/text",
            params=self._p(),
            json={"chatGuid": chat_id, "message": text},
            timeout=10,
        )
        return response.status_code == 200

    def get_unread_count(self) -> int:
        conversations = self.get_conversations()
        return sum(conversation.get("unread", 0) for conversation in conversations)

    def ping(self) -> bool:
        if self._mock:
            return True
        response = httpx.get(
            f"{self._base}/api/v1/ping",
            params=self._p(),
            timeout=5,
        )
        response.raise_for_status()
        return True

    async def send_message_async(self, chat_id: str, text: str) -> bool:
        """Async version of send_message for use in async contexts."""
        if self._mock:
            logger.info("mock_send_async chat=%s", chat_id[:30])
            return True
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self._base}/api/v1/message/text",
                params=self._p(),
                json={"chatGuid": chat_id, "message": text},
                timeout=10,
            )
            return response.status_code == 200

    @property
    def self_chat_guid(self) -> str:
        """The chat GUID to use for agent-initiated messages to the owner.

        Configured via BLUEBUBBLES_SELF_CHAT_GUID env var.
        """
        return _DEFAULT_SELF_CHAT_GUID

    def get_chat_guid_for_address(self, address: str) -> str | None:
        """Look up a chat GUID by phone number or email address.

        Returns the chat GUID string, or None if not found.
        """
        if self._mock:
            # Return a mock GUID matching the address pattern
            return f"iMessage;+;{address}"
        try:
            response = httpx.post(
                f"{self._base}/api/v1/chat/query",
                params=self._p(),
                json={"with": [{"address": address}], "limit": 1},
                timeout=10,
            )
            response.raise_for_status()
            chats = response.json().get("data", [])
            if chats:
                return chats[0].get("guid")
        except Exception as exc:
            logger.warning("get_chat_guid_for_address failed: %s", exc)
        return None

    def _normalize_chat(self, chat: dict) -> dict:
        return {
            "chat_id": chat.get("guid", ""),
            "title": chat.get("displayName") or chat.get("participants", [{}])[0].get("address", "Unknown"),
            "snippet": "",
            "timestamp": "",
            "unread": 1 if chat.get("hasUnreadMessage") else 0,
        }

    def _normalize_msg(self, message: dict) -> dict:
        return {
            "id": message.get("guid", ""),
            "sender": message.get("handle", {}).get("address", ""),
            "text": message.get("text", ""),
            "timestamp": str(message.get("dateCreated", "")),
            "from_me": message.get("isFromMe", False),
        }
