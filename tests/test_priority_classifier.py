"""Tests for the notification priority classifier."""
from __future__ import annotations

import pytest

from server.notifications.models import NotificationEvent, Priority
from server.notifications.priority import (
    FocusMode,
    PriorityClassifier,
    CATEGORY_RULES,
    SUBTYPE_RULES,
)


def _evt(
    category: str = "sms",
    body: str = "hello",
    source_id: str = "src1",
    sender: str = "",
    sub_type: str = "",
    **kw,
) -> NotificationEvent:
    payload = {"body": body, "source_id": source_id}
    if sender:
        payload["sender"] = sender
    if sub_type:
        payload["sub_type"] = sub_type
    return NotificationEvent(
        type="notification",
        priority=kw.pop("priority", Priority.NORMAL),
        category=category,
        payload=payload,
    )


# ── Category-based classification ────────────────────────────────────


class TestCategoryRules:
    def test_sms_is_high(self):
        c = PriorityClassifier()
        assert c.classify(_evt(category="sms")) == Priority.HIGH

    def test_mail_is_normal(self):
        c = PriorityClassifier()
        assert c.classify(_evt(category="mail")) == Priority.NORMAL

    def test_reminder_is_critical(self):
        c = PriorityClassifier()
        assert c.classify(_evt(category="reminder")) == Priority.CRITICAL

    def test_system_is_low(self):
        c = PriorityClassifier()
        assert c.classify(_evt(category="system")) == Priority.LOW

    def test_unknown_category_defaults_to_normal(self):
        c = PriorityClassifier()
        assert c.classify(_evt(category="unknown_thing")) == Priority.NORMAL


# ── Sub-type overrides ───────────────────────────────────────────────


class TestSubtypeOverrides:
    def test_mail_newsletter_is_low(self):
        c = PriorityClassifier()
        evt = _evt(category="mail", sub_type="newsletter")
        assert c.classify(evt) == Priority.LOW

    def test_calendar_event_now_is_critical(self):
        c = PriorityClassifier()
        evt = _evt(category="calendar", sub_type="event_now")
        assert c.classify(evt) == Priority.CRITICAL

    def test_sms_group_is_normal(self):
        c = PriorityClassifier()
        evt = _evt(category="sms", sub_type="group")
        assert c.classify(evt) == Priority.NORMAL

    def test_unknown_subtype_uses_category(self):
        c = PriorityClassifier()
        evt = _evt(category="sms", sub_type="unknown_sub")
        assert c.classify(evt) == Priority.HIGH  # falls back to sms default


# ── VIP boost ────────────────────────────────────────────────────────


class TestVIPBoost:
    def test_vip_sender_boosts_priority(self):
        c = PriorityClassifier(vip_contacts=["Mom", "Dad"])
        evt = _evt(category="sms", sender="Mom")
        # sms = HIGH (2), VIP boost -> CRITICAL (1)
        assert c.classify(evt) == Priority.CRITICAL

    def test_vip_boost_on_normal(self):
        c = PriorityClassifier(vip_contacts=["Boss"])
        evt = _evt(category="mail", sender="Boss")
        # mail = NORMAL (3), VIP boost -> HIGH (2)
        assert c.classify(evt) == Priority.HIGH

    def test_vip_case_insensitive(self):
        c = PriorityClassifier(vip_contacts=["mom"])
        evt = _evt(category="mail", sender="MOM")
        assert c.classify(evt) == Priority.HIGH

    def test_vip_partial_match(self):
        c = PriorityClassifier(vip_contacts=["Mom"])
        evt = _evt(category="mail", sender="Mom (mobile)")
        assert c.classify(evt) == Priority.HIGH

    def test_no_vip_no_boost(self):
        c = PriorityClassifier(vip_contacts=["Mom"])
        evt = _evt(category="mail", sender="Newsletter Bot")
        assert c.classify(evt) == Priority.NORMAL

    def test_empty_vip_list(self):
        c = PriorityClassifier(vip_contacts=[])
        evt = _evt(category="mail", sender="Mom")
        assert c.classify(evt) == Priority.NORMAL

    def test_critical_stays_critical_with_vip(self):
        c = PriorityClassifier(vip_contacts=["Mom"])
        evt = _evt(category="reminder", sender="Mom")
        # reminder = CRITICAL (1), VIP boost can't go below 1
        assert c.classify(evt) == Priority.CRITICAL

    def test_set_vip_contacts(self):
        c = PriorityClassifier()
        c.vip_contacts = ["Alice", "Bob"]
        evt = _evt(category="mail", sender="Alice")
        assert c.classify(evt) == Priority.HIGH


# ── Focus mode filtering ─────────────────────────────────────────────


class TestFocusModeFiltering:
    def test_normal_allows_everything(self):
        c = PriorityClassifier(focus_mode=FocusMode.NORMAL)
        for cat in ("sms", "mail", "system"):
            evt = _evt(category=cat)
            assert c.should_deliver(evt, c.classify(evt)) is True

    def test_dnd_blocks_non_critical(self):
        c = PriorityClassifier(focus_mode=FocusMode.DO_NOT_DISTURB)
        # mail = NORMAL, should be blocked
        evt = _evt(category="mail")
        assert c.should_deliver(evt, Priority.NORMAL) is False

    def test_dnd_allows_critical(self):
        c = PriorityClassifier(focus_mode=FocusMode.DO_NOT_DISTURB)
        evt = _evt(category="reminder")
        assert c.should_deliver(evt, Priority.CRITICAL) is True

    def test_dnd_allows_vip(self):
        c = PriorityClassifier(
            vip_contacts=["Mom"],
            focus_mode=FocusMode.DO_NOT_DISTURB,
        )
        evt = _evt(category="mail", sender="Mom")
        assert c.should_deliver(evt, Priority.NORMAL) is True

    def test_sleep_blocks_everything_except_critical(self):
        c = PriorityClassifier(focus_mode=FocusMode.SLEEP)
        evt_high = _evt(category="sms")
        evt_crit = _evt(category="reminder")
        assert c.should_deliver(evt_high, Priority.HIGH) is False
        assert c.should_deliver(evt_crit, Priority.CRITICAL) is True

    def test_sleep_blocks_vip_non_critical(self):
        c = PriorityClassifier(
            vip_contacts=["Mom"],
            focus_mode=FocusMode.SLEEP,
        )
        evt = _evt(category="mail", sender="Mom")
        # VIP does NOT bypass SLEEP
        assert c.should_deliver(evt, Priority.NORMAL) is False

    def test_focus_allows_critical(self):
        c = PriorityClassifier(focus_mode=FocusMode.FOCUS)
        evt = _evt(category="reminder")
        assert c.should_deliver(evt, Priority.CRITICAL) is True

    def test_focus_allows_vip(self):
        c = PriorityClassifier(
            vip_contacts=["Partner"],
            focus_mode=FocusMode.FOCUS,
        )
        evt = _evt(category="sms", sender="Partner")
        assert c.should_deliver(evt, Priority.HIGH) is True

    def test_focus_blocks_non_critical_non_vip(self):
        c = PriorityClassifier(focus_mode=FocusMode.FOCUS)
        evt = _evt(category="mail")
        assert c.should_deliver(evt, Priority.NORMAL) is False

    def test_set_focus_mode(self):
        c = PriorityClassifier()
        assert c.focus_mode == FocusMode.NORMAL
        c.focus_mode = FocusMode.DO_NOT_DISTURB
        assert c.focus_mode == FocusMode.DO_NOT_DISTURB


# ── classify_and_filter combined ─────────────────────────────────────


class TestClassifyAndFilter:
    def test_returns_tuple(self):
        c = PriorityClassifier()
        priority, deliver = c.classify_and_filter(_evt(category="sms"))
        assert priority == Priority.HIGH
        assert deliver is True

    def test_dnd_blocks_in_combined(self):
        c = PriorityClassifier(focus_mode=FocusMode.DO_NOT_DISTURB)
        priority, deliver = c.classify_and_filter(_evt(category="mail"))
        assert priority == Priority.NORMAL
        assert deliver is False
