"""Tests for device-side notification renderer."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Device imports use non-prefixed paths
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

from notifications.renderer import (
    NotificationRenderer,
    RenderedNotification,
    MODALITY_FULL_SCREEN,
    MODALITY_BANNER,
    MODALITY_TOAST,
    MODALITY_BADGE,
    MODALITY_SILENT,
    DISMISS_MS,
)


def _delivery(
    modality: str = MODALITY_TOAST,
    category: str = "sms",
    title: str = "Mom",
    body: str = "hello",
    event_id: str = "evt_001",
    count: int = 1,
    play_earcon: bool = False,
    tts_text: str = "",
    wake_screen: bool = False,
) -> dict:
    return {
        "event": {
            "id": event_id,
            "category": category,
            "payload": {"title": title, "body": body},
        },
        "modality": modality,
        "count": count,
        "play_earcon": play_earcon,
        "tts_text": tts_text,
        "wake_screen": wake_screen,
    }


@pytest.fixture
def callbacks():
    return {
        "toast": MagicMock(),
        "banner": MagicMock(),
        "full_screen": MagicMock(),
        "badge": MagicMock(),
        "wake": MagicMock(),
        "tts": MagicMock(),
        "earcon": MagicMock(),
    }


@pytest.fixture
def renderer(callbacks):
    return NotificationRenderer(
        on_toast=callbacks["toast"],
        on_banner=callbacks["banner"],
        on_full_screen=callbacks["full_screen"],
        on_badge=callbacks["badge"],
        on_wake=callbacks["wake"],
        on_tts=callbacks["tts"],
        on_earcon=callbacks["earcon"],
    )


# ── Toast rendering ─────────────────────────────────────────────────


class TestToast:
    def test_toast_calls_callback(self, renderer, callbacks):
        result = renderer.handle_delivery(_delivery(modality=MODALITY_TOAST))
        callbacks["toast"].assert_called_once()
        args = callbacks["toast"].call_args[0]
        assert args[0] == "Mom"     # title
        assert args[1] == "hello"   # body
        assert args[2] == "sms"     # category
        assert args[3] == DISMISS_MS[MODALITY_TOAST]

    def test_toast_auto_dismiss_3s(self, renderer, callbacks):
        renderer.handle_delivery(_delivery(modality=MODALITY_TOAST))
        duration = callbacks["toast"].call_args[0][3]
        assert duration == 3000

    def test_toast_increments_badge(self, renderer):
        renderer.handle_delivery(_delivery(modality=MODALITY_TOAST))
        assert renderer.badge_count == 1


# ── Banner rendering ────────────────────────────────────────────────


class TestBanner:
    def test_banner_calls_callback(self, renderer, callbacks):
        renderer.handle_delivery(_delivery(modality=MODALITY_BANNER))
        callbacks["banner"].assert_called_once()

    def test_banner_15s_duration(self, renderer, callbacks):
        renderer.handle_delivery(_delivery(modality=MODALITY_BANNER))
        duration = callbacks["banner"].call_args[0][3]
        assert duration == 15000

    def test_banner_increments_badge(self, renderer):
        renderer.handle_delivery(_delivery(modality=MODALITY_BANNER))
        assert renderer.badge_count == 1


# ── Full screen ──────────────────────────────────────────────────────


class TestFullScreen:
    def test_full_screen_calls_callback(self, renderer, callbacks):
        renderer.handle_delivery(_delivery(
            modality=MODALITY_FULL_SCREEN, tts_text="urgent message"
        ))
        callbacks["full_screen"].assert_called_once()
        callbacks["tts"].assert_called_once_with("urgent message")

    def test_full_screen_no_auto_dismiss(self):
        assert DISMISS_MS[MODALITY_FULL_SCREEN] == 0

    def test_full_screen_increments_badge(self, renderer):
        renderer.handle_delivery(_delivery(modality=MODALITY_FULL_SCREEN))
        assert renderer.badge_count == 1


# ── Badge ────────────────────────────────────────────────────────────


class TestBadge:
    def test_badge_only_no_toast_or_banner(self, renderer, callbacks):
        renderer.handle_delivery(_delivery(modality=MODALITY_BADGE))
        callbacks["toast"].assert_not_called()
        callbacks["banner"].assert_not_called()
        callbacks["badge"].assert_called()

    def test_badge_accumulates(self, renderer):
        for i in range(5):
            renderer.handle_delivery(_delivery(
                modality=MODALITY_BADGE, event_id=f"evt_{i}"
            ))
        assert renderer.badge_count == 5

    def test_clear_badge(self, renderer, callbacks):
        renderer.handle_delivery(_delivery(modality=MODALITY_BADGE))
        assert renderer.badge_count == 1
        renderer.clear_badge()
        assert renderer.badge_count == 0
        callbacks["badge"].assert_called_with(0)


# ── Silent ───────────────────────────────────────────────────────────


class TestSilent:
    def test_silent_no_callbacks(self, renderer, callbacks):
        renderer.handle_delivery(_delivery(modality=MODALITY_SILENT))
        callbacks["toast"].assert_not_called()
        callbacks["banner"].assert_not_called()
        callbacks["full_screen"].assert_not_called()
        # Badge NOT incremented for silent
        assert renderer.badge_count == 0


# ── Earcon and wake ──────────────────────────────────────────────────


class TestEarconAndWake:
    def test_earcon_played_when_flagged(self, renderer, callbacks):
        renderer.handle_delivery(_delivery(play_earcon=True))
        callbacks["earcon"].assert_called_once_with("sms")

    def test_earcon_not_played_when_not_flagged(self, renderer, callbacks):
        renderer.handle_delivery(_delivery(play_earcon=False))
        callbacks["earcon"].assert_not_called()

    def test_wake_screen_when_flagged(self, renderer, callbacks):
        renderer.handle_delivery(_delivery(wake_screen=True))
        callbacks["wake"].assert_called_once()

    def test_wake_screen_not_called_when_not_flagged(self, renderer, callbacks):
        renderer.handle_delivery(_delivery(wake_screen=False))
        callbacks["wake"].assert_not_called()


# ── Coalesced count ──────────────────────────────────────────────────


class TestCoalescedCount:
    def test_count_prepended_to_body(self, renderer, callbacks):
        renderer.handle_delivery(_delivery(
            modality=MODALITY_TOAST, body="latest msg", count=5
        ))
        body = callbacks["toast"].call_args[0][1]
        assert body == "(5) latest msg"

    def test_count_1_no_prefix(self, renderer, callbacks):
        renderer.handle_delivery(_delivery(
            modality=MODALITY_TOAST, body="single msg", count=1
        ))
        body = callbacks["toast"].call_args[0][1]
        assert body == "single msg"


# ── History tracking ─────────────────────────────────────────────────


class TestHistory:
    def test_history_tracked(self, renderer):
        renderer.handle_delivery(_delivery(event_id="e1"))
        renderer.handle_delivery(_delivery(event_id="e2"))
        assert len(renderer.history) == 2
        assert renderer.history[0].event_id == "e1"

    def test_history_capped_at_max(self, renderer):
        for i in range(60):
            renderer.handle_delivery(_delivery(event_id=f"e{i}"))
        assert len(renderer.history) == 50  # _max_history

    def test_history_returns_copy(self, renderer):
        renderer.handle_delivery(_delivery())
        h1 = renderer.history
        h2 = renderer.history
        assert h1 is not h2


# ── Unknown modality ────────────────────────────────────────────────


class TestUnknownModality:
    def test_unknown_returns_none(self, renderer):
        result = renderer.handle_delivery(_delivery(modality="hologram"))
        assert result is None


# ── No callbacks ────────────────────────────────────────────────────


class TestNoCallbacks:
    def test_renders_without_callbacks(self):
        r = NotificationRenderer()  # all None
        result = r.handle_delivery(_delivery(
            modality=MODALITY_FULL_SCREEN,
            play_earcon=True,
            wake_screen=True,
            tts_text="test",
        ))
        assert result is not None
        assert result.modality == MODALITY_FULL_SCREEN
