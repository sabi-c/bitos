"""Priority classifier — rule-based fast path with VIP boost and focus modes.

Handles ~90% of notifications via rules. The remaining ambiguous cases
can be refined by an LLM slow path (not implemented here — see research doc).
"""
from __future__ import annotations

from enum import IntEnum
from typing import Sequence

from .models import NotificationEvent, Priority


# ── Focus modes ──────────────────────────────────────────────────────

class FocusMode(IntEnum):
    NORMAL = 0
    DO_NOT_DISTURB = 1
    SLEEP = 2
    FOCUS = 3


# Which priorities are allowed through in each mode
_FOCUS_ALLOW: dict[FocusMode, set[Priority]] = {
    FocusMode.NORMAL: {Priority.CRITICAL, Priority.HIGH, Priority.NORMAL, Priority.LOW, Priority.SILENT},
    FocusMode.DO_NOT_DISTURB: {Priority.CRITICAL},
    FocusMode.SLEEP: {Priority.CRITICAL},
    FocusMode.FOCUS: {Priority.CRITICAL},
}

# ── Rule-based category → priority mapping ───────────────────────────

CATEGORY_RULES: dict[str, Priority] = {
    "reminder": Priority.CRITICAL,
    "calendar": Priority.HIGH,
    "sms": Priority.HIGH,
    "task": Priority.HIGH,
    "agent": Priority.HIGH,
    "mail": Priority.NORMAL,
    "tool": Priority.NORMAL,
    "system": Priority.LOW,
}

# Sub-type overrides (category:sub_type → priority)
SUBTYPE_RULES: dict[str, Priority] = {
    "mail:newsletter": Priority.LOW,
    "calendar:event_now": Priority.CRITICAL,
    "sms:group": Priority.NORMAL,
    "agent:idle_check": Priority.NORMAL,
    "agent:greeting": Priority.HIGH,
    "system:health": Priority.LOW,
    "system:ota": Priority.LOW,
}

# ── Default VIP contacts ────────────────────────────────────────────

DEFAULT_VIP_CONTACTS: list[str] = []


class PriorityClassifier:
    """Classify notification priority and filter by focus mode.

    Two-step process:
    1. Assign priority from rules + VIP boost
    2. Filter against current focus mode (with VIP bypass)
    """

    def __init__(
        self,
        vip_contacts: Sequence[str] | None = None,
        focus_mode: FocusMode = FocusMode.NORMAL,
    ):
        self._vip_contacts: list[str] = list(vip_contacts or DEFAULT_VIP_CONTACTS)
        self._focus_mode = focus_mode

    # ── Configuration ────────────────────────────────────────────────

    @property
    def focus_mode(self) -> FocusMode:
        return self._focus_mode

    @focus_mode.setter
    def focus_mode(self, mode: FocusMode) -> None:
        self._focus_mode = mode

    @property
    def vip_contacts(self) -> list[str]:
        return list(self._vip_contacts)

    @vip_contacts.setter
    def vip_contacts(self, contacts: Sequence[str]) -> None:
        self._vip_contacts = list(contacts)

    # ── Classification ───────────────────────────────────────────────

    def classify(self, event: NotificationEvent) -> Priority:
        """Assign priority based on rules + VIP boost.

        Priority assignment order:
        1. Check sub-type override (category:sub_type)
        2. Fall back to category default
        3. Apply VIP sender boost (+1 tier, min CRITICAL)
        """
        priority = self._rule_priority(event)
        if self._is_vip_sender(event):
            priority = Priority(max(Priority.CRITICAL, priority - 1))
        return priority

    def should_deliver(self, event: NotificationEvent, priority: Priority | None = None) -> bool:
        """Check if the event should be delivered under the current focus mode.

        VIP senders bypass DO_NOT_DISTURB and FOCUS modes.
        SLEEP mode only allows P1 (CRITICAL), even from VIPs.
        """
        if priority is None:
            priority = self.classify(event)

        is_vip = self._is_vip_sender(event)
        mode = self._focus_mode

        # NORMAL mode: everything through
        if mode == FocusMode.NORMAL:
            return True

        # SLEEP mode: only P1, no VIP bypass
        if mode == FocusMode.SLEEP:
            return priority == Priority.CRITICAL

        # DND / FOCUS: allowed priorities + VIP bypass
        allowed = _FOCUS_ALLOW.get(mode, set())
        if priority in allowed:
            return True
        if is_vip and mode in (FocusMode.DO_NOT_DISTURB, FocusMode.FOCUS):
            return True

        return False

    def classify_and_filter(self, event: NotificationEvent) -> tuple[Priority, bool]:
        """Classify priority and check delivery in one call.

        Returns (priority, should_deliver).
        """
        priority = self.classify(event)
        deliver = self.should_deliver(event, priority)
        return priority, deliver

    # ── Internal ─────────────────────────────────────────────────────

    def _rule_priority(self, event: NotificationEvent) -> Priority:
        """Determine priority from category + sub_type rules."""
        sub_type = event.payload.get("sub_type", "")
        if sub_type:
            key = f"{event.category}:{sub_type}"
            if key in SUBTYPE_RULES:
                return SUBTYPE_RULES[key]
        return CATEGORY_RULES.get(event.category, Priority.NORMAL)

    def _is_vip_sender(self, event: NotificationEvent) -> bool:
        """Check if the event sender matches any VIP contact."""
        if not self._vip_contacts:
            return False
        sender = event.payload.get("sender", "")
        if not sender:
            return False
        sender_lower = sender.lower()
        return any(vip.lower() in sender_lower for vip in self._vip_contacts)
