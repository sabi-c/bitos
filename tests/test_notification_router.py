"""Tests for NotificationRouter — DND-aware event routing by priority tier."""
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

from notifications.router import NotificationRouter


@pytest.fixture
def callbacks():
    return {
        "banner": MagicMock(),
        "toast": MagicMock(),
        "badge": MagicMock(),
    }


@pytest.fixture
def router(callbacks):
    return NotificationRouter(
        on_banner=callbacks["banner"],
        on_toast=callbacks["toast"],
        on_badge=callbacks["badge"],
    )


def _event(priority: int, **extra) -> dict:
    return {"priority": priority, "app": "test", "message": "hello", **extra}


# ── Routing by priority ──────────────────────────────────────────────


def test_p1_shows_banner(router, callbacks):
    router.on_event(_event(1))
    callbacks["banner"].assert_called_once()
    callbacks["toast"].assert_not_called()


def test_p2_shows_banner(router, callbacks):
    router.on_event(_event(2))
    callbacks["banner"].assert_called_once()
    callbacks["toast"].assert_not_called()


def test_p3_shows_toast(router, callbacks):
    router.on_event(_event(3))
    callbacks["toast"].assert_called_once()
    callbacks["banner"].assert_not_called()


def test_p4_shows_badge_only(router, callbacks):
    router.on_event(_event(4))
    callbacks["banner"].assert_not_called()
    callbacks["toast"].assert_not_called()
    callbacks["badge"].assert_called_once_with(1)


# ── DND behaviour ────────────────────────────────────────────────────


def test_dnd_queues_notification(router, callbacks):
    router.set_dnd(True, reason="focus")
    router.on_event(_event(2))
    callbacks["banner"].assert_not_called()
    callbacks["toast"].assert_not_called()
    # Badge still updated
    callbacks["badge"].assert_called()


def test_dnd_clear_drains_queue(router, callbacks):
    router.set_dnd(True)
    router.on_event(_event(2))
    router.on_event(_event(3))
    callbacks["banner"].assert_not_called()
    callbacks["toast"].assert_not_called()

    router.set_dnd(False)
    callbacks["banner"].assert_called_once()
    callbacks["toast"].assert_called_once()


def test_p1_breaks_through_dnd(router, callbacks):
    router.set_dnd(True, reason="sleeping")
    router.on_event(_event(1))
    callbacks["banner"].assert_called_once()


def test_coalesce_when_queue_exceeds_threshold(router, callbacks):
    router.set_dnd(True)
    for i in range(7):
        router.on_event(_event(3, message=f"msg-{i}"))
    callbacks["toast"].assert_not_called()

    router.set_dnd(False)
    # Should get a single coalesced toast, not 7 individual ones
    assert callbacks["toast"].call_count == 1
    summary = callbacks["toast"].call_args[0][0]
    assert summary.get("coalesced") is True
    assert summary["count"] == 7
