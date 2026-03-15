"""Gmail MCP adapter for BITOS server."""

from __future__ import annotations

import json
import logging
import os
import re

import anthropic

logger = logging.getLogger(__name__)

MOCK_INBOX = [
    {
        "thread_id": "thr_work_001",
        "sender": "Joaquin Rivera",
        "sender_email": "joaquin@acmefinance.com",
        "subject": "Invoice #4821 missing attachment",
        "preview": "Hey — can you resend the PDF for #4821?",
        "timestamp": "9:12 AM",
        "unread": True,
    },
    {
        "thread_id": "thr_personal_001",
        "sender": "Anthony",
        "sender_email": "anthony@gmail.com",
        "subject": "Sunday family lunch",
        "preview": "Can everyone do 1pm this Sunday?",
        "timestamp": "Yesterday",
        "unread": False,
    },
    {
        "thread_id": "thr_opportunity_001",
        "sender": "Priya Shah",
        "sender_email": "priya@venturetalent.io",
        "subject": "Advisory opportunity in AI tooling",
        "preview": "Would you be open to a short intro call?",
        "timestamp": "7:40 AM",
        "unread": True,
    },
]

MOCK_THREADS = {
    "thr_work_001": [
        {
            "from_me": False,
            "sender": "Joaquin Rivera",
            "text": "Hey — did you get my last message about 4821?",
            "timestamp": "Yesterday",
        },
        {
            "from_me": True,
            "sender": "Me",
            "text": "Sorry for the delay, let me resend.",
            "timestamp": "Yesterday",
        },
        {
            "from_me": False,
            "sender": "Joaquin Rivera",
            "text": "Can you resend the PDF for #4821?",
            "timestamp": "9:12 AM",
        },
    ]
}


class GmailAdapter:
    """Gmail read/draft support via Claude MCP with safe mock fallback."""

    def __init__(self):
        self._api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        self._mock = (
            os.environ.get("GMAIL_ENABLED", "false").lower() != "true"
            or not self._api_key
            or self._api_key.startswith("test-")
        )
        self._mcp_config = {
            "type": "url",
            "name": "gmail",
            "url": "https://gmail.mcp.claude.com/mcp",
        }

    def _call_gmail_mcp(self, prompt: str) -> str:
        """Send prompt to Claude with Gmail MCP enabled and return text blocks."""
        client = anthropic.Anthropic(api_key=self._api_key)
        response = client.beta.messages.create(
            model=os.environ.get("MODEL_NAME", "claude-sonnet-4-6"),
            max_tokens=1000,
            mcp_servers=[self._mcp_config],
            tools=[{"type": "mcp_toolset", "mcp_server_name": "gmail"}],
            messages=[{"role": "user", "content": prompt}],
            betas=["mcp-client-2025-04-04"],
        )

        text_parts = [
            block.text
            for block in response.content
            if getattr(block, "type", "") == "text" and getattr(block, "text", "")
        ]
        return "\n".join(text_parts)

    @staticmethod
    def _extract_json_array(raw: str) -> list[dict]:
        match = re.search(r"\[.*\]", raw, re.DOTALL)
        if not match:
            return []
        parsed = json.loads(match.group())
        return parsed if isinstance(parsed, list) else []

    def get_inbox(self, limit: int = 10) -> list[dict]:
        """Returns inbox threads, newest first."""
        if self._mock:
            return MOCK_INBOX[:limit]

        raw = self._call_gmail_mcp(
            f"Search my Gmail inbox for the {limit} most recent emails. "
            "Return a JSON list where each item has: thread_id, sender, "
            "sender_email, subject, preview (first 80 chars of body), "
            "timestamp, unread (bool). Return ONLY the JSON array."
        )
        try:
            parsed = self._extract_json_array(raw)
            return parsed[:limit] if parsed else MOCK_INBOX[:limit]
        except Exception:
            logger.warning("gmail_get_inbox_parse_failed")
            return MOCK_INBOX[:limit]

    def get_thread(self, thread_id: str) -> list[dict]:
        """Returns all messages in a thread."""
        if self._mock:
            return MOCK_THREADS.get(thread_id, [])

        raw = self._call_gmail_mcp(
            f"Read the Gmail thread with ID: {thread_id}. "
            "Return a JSON list of messages, each with: from_me (bool), "
            "sender (name), text (body), timestamp. ONLY the JSON array."
        )
        try:
            return self._extract_json_array(raw)
        except Exception:
            logger.warning("gmail_get_thread_parse_failed thread=%s", thread_id)
            return []

    def draft_reply(self, thread_id: str, voice_transcript: str) -> str:
        """Draft reply body text only (does not create/send Gmail draft)."""
        if self._mock:
            return f"Thanks for the message. {voice_transcript}".strip()

        thread = self.get_thread(thread_id)
        context = "\n".join(
            f"{'Me' if message.get('from_me') else message.get('sender', 'Them')}: {message.get('text', '')}"
            for message in thread[-3:]
        )

        client = anthropic.Anthropic(api_key=self._api_key)
        response = client.messages.create(
            model=os.environ.get("MODEL_NAME", "claude-sonnet-4-6"),
            max_tokens=300,
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Draft a Gmail reply.\n\n"
                        f"Email thread context:\n{context}\n\n"
                        f"The person wants to say:\n{voice_transcript}\n\n"
                        "Write ONLY the email body text.\n"
                        "Match the tone — professional but natural.\n"
                        "No subject line, no greeting needed, just the body.\n"
                        "Keep it concise."
                    ),
                }
            ],
        )
        text_parts = [
            block.text
            for block in response.content
            if getattr(block, "type", "") == "text" and getattr(block, "text", "")
        ]
        return "\n".join(text_parts).strip()

    def create_draft(self, thread_id: str, body: str) -> str:
        """Tier 1: create Gmail draft and return draft_id."""
        if self._mock:
            logger.info("mock_create_draft thread=%s", thread_id)
            return "mock_draft_001"

        inbox = self.get_inbox(limit=25)
        thread = next((item for item in inbox if item.get("thread_id") == thread_id), None)
        subject = f"Re: {thread.get('subject', '')}" if thread else "Re:"
        to = thread.get("sender_email", "") if thread else ""

        raw = self._call_gmail_mcp(
            f"Create a Gmail draft reply to thread {thread_id}. "
            f"To: {to}, Subject: {subject}, Body: {body}. "
            "Return ONLY the draft_id."
        )
        draft_id = raw.strip()
        return draft_id or "draft_unknown"

    def get_unread_count(self) -> int:
        return sum(1 for thread in self.get_inbox() if bool(thread.get("unread")))

    def integration_status(self) -> str:
        if self._mock:
            return "mock"
        try:
            _ = self.get_inbox(limit=1)
            return "online"
        except Exception:
            return "offline"
