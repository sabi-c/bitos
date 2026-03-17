"""Tests for the upgraded ApprovalOverlay (1-bit UI kit style)."""
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "device"))

import pygame
pygame.init()

import pytest
from overlays.approval_overlay import ApprovalOverlay, CATEGORY_HEADERS
from display.tokens import PHYSICAL_W, PHYSICAL_H


@pytest.fixture
def surface():
    return pygame.Surface((PHYSICAL_W, PHYSICAL_H))


@pytest.fixture
def overlay():
    return ApprovalOverlay(
        request_id="req-1",
        prompt="Allow agent to send email?",
        options=["Allow", "Deny"],
        description="The agent wants to send an email to john@example.com",
        category="permission",
    )


# ── New field tests ──────────────────────────────────────────────

def test_description_field_default():
    ov = ApprovalOverlay(request_id="r", prompt="p", options=["a"])
    assert ov.description == ""


def test_description_field_set(overlay):
    assert "email" in overlay.description


def test_category_field_default():
    ov = ApprovalOverlay(request_id="r", prompt="p", options=["a"])
    assert ov.category == "permission"


def test_category_field_custom():
    ov = ApprovalOverlay(
        request_id="r", prompt="p", options=["a"], category="action"
    )
    assert ov.category == "action"


def test_category_headers_mapping():
    assert "PERMISSION REQUEST" in CATEGORY_HEADERS.values()
    assert "ACTION REQUIRED" in CATEGORY_HEADERS.values()


# ── Render tests ─────────────────────────────────────────────────

def test_render_no_crash(overlay, surface):
    overlay.render(surface)


def test_render_with_description(surface):
    ov = ApprovalOverlay(
        request_id="r",
        prompt="Delete all data?",
        options=["Yes", "No"],
        description="This will permanently remove all stored data.",
        category="confirm",
    )
    ov.render(surface)


def test_render_without_description(surface):
    ov = ApprovalOverlay(
        request_id="r",
        prompt="Proceed?",
        options=["OK"],
    )
    ov.render(surface)


def test_render_three_options(surface):
    ov = ApprovalOverlay(
        request_id="r",
        prompt="Choose",
        options=["A", "B", "C"],
    )
    ov.render(surface)


def test_render_dismissed_is_noop(overlay, surface):
    overlay._dismissed = True
    overlay.render(surface)  # Should not crash


# ── Behavioral backward-compat ───────────────────────────────────

def test_short_press_cycles(overlay):
    assert overlay._selected == 0
    overlay.handle_action("SHORT_PRESS")
    assert overlay._selected == 1


def test_double_press_confirms(overlay):
    result = {}
    overlay.on_choice = lambda rid, chosen: result.update(rid=rid, chosen=chosen)
    overlay.handle_action("DOUBLE_PRESS")
    assert result["chosen"] == "Allow"
    assert overlay.dismissed is True


def test_long_press_cancels(overlay):
    cancelled = {}
    overlay.on_cancel = lambda rid: cancelled.update(rid=rid)
    overlay.handle_action("LONG_PRESS")
    assert cancelled["rid"] == "req-1"
    assert overlay.dismissed is True


def test_timeout(overlay):
    overlay.elapsed_ms = 59_998
    assert overlay.tick(1) is True  # 59999 < 60000, still alive
    assert overlay.tick(1) is False  # 60000 >= 60000, timed out
    assert overlay.dismissed is True


def test_tick_dismissed(overlay):
    overlay._dismissed = True
    assert overlay.tick(100) is False
