"""Tests for voice notification summary generation."""
from __future__ import annotations

import pytest

from server.notifications.models import NotificationEvent, Priority
from server.notifications.voice_summary import (
    build_summary,
    build_detail,
    tts_readout,
)


def _evt(
    category: str = "sms",
    body: str = "hello",
    sender: str = "",
    priority: Priority = Priority.NORMAL,
    source_id: str = "src1",
    **extra,
) -> NotificationEvent:
    payload = {"body": body, "source_id": source_id, **extra}
    if sender:
        payload["sender"] = sender
    return NotificationEvent(
        type="notification",
        priority=priority,
        category=category,
        payload=payload,
    )


# ── build_summary ────────────────────────────────────────────────────


class TestBuildSummary:
    def test_empty_list(self):
        assert build_summary([]) == "No new notifications."

    def test_single_sms_with_sender(self):
        result = build_summary([_evt(category="sms", sender="Mom", body="hi")])
        assert "1 message from Mom" in result
        assert "hi" in result

    def test_single_sms_no_sender(self):
        result = build_summary([_evt(category="sms", body="anonymous msg")])
        assert "1 message" in result
        assert "anonymous msg" in result

    def test_single_mail_sender_only(self):
        result = build_summary([_evt(category="mail", sender="Boss")])
        assert "1 email from Boss" in result

    def test_single_no_body_no_sender(self):
        result = build_summary([_evt(category="system", body="", sender="")])
        assert "1 new system alert" in result

    def test_multiple_same_category(self):
        events = [
            _evt(category="sms", sender="Mom", body="msg1"),
            _evt(category="sms", sender="Mom", body="msg2"),
            _evt(category="sms", sender="Alex", body="msg3"),
        ]
        result = build_summary(events)
        assert "3 messages" in result
        assert "Mom" in result
        assert "Alex" in result

    def test_multiple_categories(self):
        events = [
            _evt(category="sms", sender="Mom"),
            _evt(category="mail", sender="Boss"),
        ]
        result = build_summary(events)
        assert "message" in result.lower()
        assert "email" in result.lower()
        assert result.startswith("You have")

    def test_three_categories(self):
        events = [
            _evt(category="sms", sender="Mom"),
            _evt(category="mail", sender="Boss"),
            _evt(category="task", body="Do laundry"),
        ]
        result = build_summary(events)
        assert result.startswith("You have")
        assert "." in result  # ends with period

    def test_unknown_category_shows_count(self):
        events = [
            _evt(category="weird1", body="a"),
            _evt(category="weird2", body="b"),
        ]
        result = build_summary(events)
        assert "2 notifications" in result


# ── build_detail ─────────────────────────────────────────────────────


class TestBuildDetail:
    def test_empty_list(self):
        assert build_detail([]) == []

    def test_single_item(self):
        details = build_detail([_evt(sender="Mom", body="hi")])
        assert len(details) == 1
        assert "Mom" in details[0]
        assert "hi" in details[0]

    def test_sorted_by_priority(self):
        events = [
            _evt(category="mail", body="low", priority=Priority.NORMAL),
            _evt(category="reminder", body="urgent", priority=Priority.CRITICAL),
        ]
        details = build_detail(events)
        assert "urgent" in details[0]  # CRITICAL first

    def test_max_items_respected(self):
        events = [_evt(body=f"msg{i}") for i in range(10)]
        details = build_detail(events, max_items=3)
        assert len(details) == 4  # 3 items + "And 7 more."
        assert "7 more" in details[-1]

    def test_detail_with_sender_and_body(self):
        details = build_detail([_evt(category="sms", sender="Alex", body="hey")])
        assert details[0] == "Message from Alex: hey"

    def test_detail_body_only(self):
        details = build_detail([_evt(category="mail", body="subject line")])
        assert details[0] == "Email: subject line"

    def test_detail_sender_only(self):
        details = build_detail([_evt(category="sms", sender="Mom", body="")])
        assert details[0] == "Message from Mom"

    def test_detail_no_sender_no_body(self):
        details = build_detail([_evt(category="calendar", sender="", body="")])
        assert details[0] == "Calendar event"


# ── tts_readout ──────────────────────────────────────────────────────


class TestTTSReadout:
    def test_sms_with_sender_and_body(self):
        result = tts_readout(_evt(category="sms", sender="Mom", body="Are you okay?"))
        assert result == "Message from Mom: Are you okay?"

    def test_mail_sender_only(self):
        result = tts_readout(_evt(category="mail", sender="Boss", body=""))
        assert result == "Email from Boss"

    def test_body_only(self):
        result = tts_readout(_evt(category="calendar", body="Meeting at 3pm"))
        assert result == "New Calendar event: Meeting at 3pm"

    def test_no_sender_no_body(self):
        result = tts_readout(_evt(category="reminder"))
        # Falls back to payload title if available
        assert "Reminder" in result

    def test_uses_title_as_fallback_sender(self):
        evt = _evt(category="sms", body="hello")
        evt.payload["title"] = "GroupChat"
        result = tts_readout(evt)
        assert "GroupChat" in result

    def test_unknown_category(self):
        result = tts_readout(_evt(category="unknown", body="test"))
        assert result == "New notification: test"
