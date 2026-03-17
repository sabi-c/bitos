"""Voice notification UX — 'What did I miss?' summary and TTS readout.

Generates human-friendly notification summaries for voice delivery.
Used by the chat endpoint when user asks for missed notifications,
and by the proactive TTS system for P1-P2 idle readout.
"""
from __future__ import annotations

from collections import Counter
from typing import Sequence

from .models import NotificationEvent, Priority


def build_summary(events: Sequence[NotificationEvent]) -> str:
    """Build a concise voice-friendly summary of notification events.

    Example output:
        "You have 3 messages — 2 from Mom, 1 from Alex — and 5 emails."
        "You have 1 message from Mom: Are you coming for dinner?"

    Designed for TTS readout on the device speaker.
    """
    if not events:
        return "No new notifications."

    if len(events) == 1:
        return _single_summary(events[0])

    # Group by category
    by_cat: dict[str, list[NotificationEvent]] = {}
    for evt in events:
        by_cat.setdefault(evt.category, []).append(evt)

    parts: list[str] = []
    for cat in ("sms", "mail", "calendar", "task", "reminder", "agent", "system", "tool"):
        cat_events = by_cat.get(cat, [])
        if not cat_events:
            continue
        parts.append(_category_summary(cat, cat_events))

    if not parts:
        return f"You have {len(events)} notifications."

    if len(parts) == 1:
        return f"You have {parts[0]}."

    joined = ", and ".join([", ".join(parts[:-1]), parts[-1]]) if len(parts) > 1 else parts[0]
    return f"You have {joined}."


def build_detail(events: Sequence[NotificationEvent], max_items: int = 5) -> list[str]:
    """Build per-notification detail strings for drill-down readout.

    Returns a list of strings, one per notification, sorted by priority then time.
    """
    sorted_events = sorted(events, key=lambda e: (e.priority, e.timestamp))
    details: list[str] = []
    for evt in sorted_events[:max_items]:
        details.append(_detail_line(evt))
    remaining = len(events) - len(details)
    if remaining > 0:
        details.append(f"And {remaining} more.")
    return details


def tts_readout(event: NotificationEvent) -> str:
    """Generate a TTS-friendly string for a single notification.

    Used for P1-P2 push readout when user is idle.
    """
    sender = event.payload.get("sender", event.payload.get("title", ""))
    body = event.payload.get("body", "")
    cat_label = _CATEGORY_LABELS.get(event.category, "notification")

    if sender and body:
        return f"{cat_label} from {sender}: {body}"
    if sender:
        return f"{cat_label} from {sender}"
    if body:
        return f"New {cat_label}: {body}"
    return f"New {cat_label}"


# ── Internal helpers ─────────────────────────────────────────────────

_CATEGORY_LABELS = {
    "sms": "Message",
    "mail": "Email",
    "calendar": "Calendar event",
    "task": "Task",
    "reminder": "Reminder",
    "agent": "Note",
    "system": "System alert",
    "tool": "Update",
}

_CATEGORY_PLURAL = {
    "sms": "messages",
    "mail": "emails",
    "calendar": "calendar events",
    "task": "tasks",
    "reminder": "reminders",
    "agent": "notes",
    "system": "system alerts",
    "tool": "updates",
}


def _single_summary(event: NotificationEvent) -> str:
    """Summary for a single notification."""
    sender = event.payload.get("sender", "")
    body = event.payload.get("body", "")
    cat_label = _CATEGORY_LABELS.get(event.category, "notification")

    if sender and body:
        return f"1 {cat_label.lower()} from {sender}: {body}"
    if sender:
        return f"1 {cat_label.lower()} from {sender}"
    if body:
        return f"1 {cat_label.lower()}: {body}"
    return f"1 new {cat_label.lower()}"


def _category_summary(category: str, events: list[NotificationEvent]) -> str:
    """Summary for all events in one category."""
    count = len(events)
    plural = _CATEGORY_PLURAL.get(category, "notifications")

    # Count by sender
    senders: Counter[str] = Counter()
    for evt in events:
        sender = evt.payload.get("sender", "")
        if sender:
            senders[sender] += 1

    if count == 1:
        singular = _CATEGORY_LABELS.get(category, "notification").lower()
        sender = events[0].payload.get("sender", "")
        if sender:
            return f"1 {singular} from {sender}"
        return f"1 {singular}"

    if senders:
        sender_parts = [f"{c} from {s}" for s, c in senders.most_common(3)]
        return f"{count} {plural} — {', '.join(sender_parts)}"

    return f"{count} {plural}"


def _detail_line(event: NotificationEvent) -> str:
    """One-line detail for drill-down."""
    sender = event.payload.get("sender", event.payload.get("title", ""))
    body = event.payload.get("body", "")
    cat_label = _CATEGORY_LABELS.get(event.category, "Notification")

    if sender and body:
        return f"{cat_label} from {sender}: {body}"
    if body:
        return f"{cat_label}: {body}"
    if sender:
        return f"{cat_label} from {sender}"
    return cat_label
