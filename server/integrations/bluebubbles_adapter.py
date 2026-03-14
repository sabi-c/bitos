"""BlueBubbles iMessage adapter for BITOS server."""

from __future__ import annotations

import logging
import os

import requests

logger = logging.getLogger(__name__)


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

    def _p(self, extra=None):
        p = {"password": self._pw}
        if extra:
            p.update(extra)
        return p

    def get_conversations(self, limit=25) -> list[dict]:
        if self._mock:
            return self.MOCK_DATA["conversations"]
        response = requests.get(
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
        response = requests.get(
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
        response = requests.post(
            f"{self._base}/api/v1/message/text",
            params=self._p(),
            json={"chatGuid": chat_id, "message": text},
            timeout=10,
        )
        return response.status_code == 200

    def get_unread_count(self) -> int:
        conversations = self.get_conversations()
        return sum(conversation.get("unread", 0) for conversation in conversations)

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
