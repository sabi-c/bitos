"""Tests for CheckmarkAnimation and ToastAnimation."""
import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

from screens.components.animations import (
    CheckmarkAnimation,
    ToastAnimation,
    TOAST_STYLES,
    TOAST_DEFAULT_Y,
)


@pytest.fixture(scope="module", autouse=True)
def _init_pygame():
    pygame.init()
    pygame.font.init()
    yield
    pygame.quit()


def _surface() -> pygame.Surface:
    return pygame.Surface((240, 280))


# ── CheckmarkAnimation: lifecycle ────────────────────────────────────


def test_checkmark_starts_not_finished():
    anim = CheckmarkAnimation()
    assert not anim.finished
    assert anim.elapsed_ms == 0


def test_checkmark_finishes_after_duration():
    anim = CheckmarkAnimation(duration_ms=500)
    assert anim.tick(250)      # still alive
    assert not anim.finished
    assert not anim.tick(250)  # now done
    assert anim.finished


def test_checkmark_tick_returns_false_when_already_finished():
    anim = CheckmarkAnimation(duration_ms=100)
    anim.tick(200)
    assert anim.finished
    assert not anim.tick(50)


def test_checkmark_custom_text():
    anim = CheckmarkAnimation(text="SAVED")
    assert anim.text == "SAVED"


# ── CheckmarkAnimation: render ───────────────────────────────────────


def test_checkmark_render_phase1_no_crash():
    """Phase 1 (0-30%): box drawing in."""
    surf = _surface()
    anim = CheckmarkAnimation(duration_ms=1000)
    anim.elapsed_ms = 150  # 15% — mid phase 1
    anim.render(surf)  # must not raise


def test_checkmark_render_phase2_no_crash():
    """Phase 2 (30-60%): checkmark drawing."""
    surf = _surface()
    anim = CheckmarkAnimation(duration_ms=1000)
    anim.elapsed_ms = 450  # 45% — mid phase 2
    anim.render(surf)


def test_checkmark_render_phase3_no_crash():
    """Phase 3 (60-100%): text + fade out."""
    surf = _surface()
    anim = CheckmarkAnimation(duration_ms=1000)
    anim.elapsed_ms = 800  # 80% — phase 3
    anim.render(surf)


def test_checkmark_render_after_finished_is_noop():
    """Render does nothing after animation is finished."""
    surf = _surface()
    anim = CheckmarkAnimation(duration_ms=100)
    anim.tick(200)
    assert anim.finished
    surf.fill((0, 0, 0))
    before = surf.get_at((120, 140))
    anim.render(surf)
    after = surf.get_at((120, 140))
    assert before == after


# ── ToastAnimation: lifecycle ────────────────────────────────────────


def test_toast_starts_not_finished():
    toast = ToastAnimation(text="Saved", style="success")
    assert not toast.finished
    assert toast.elapsed_ms == 0


def test_toast_finishes_after_duration():
    toast = ToastAnimation(text="Saved", duration_ms=500)
    toast.tick(500)
    assert toast.finished


def test_toast_tick_advances_time():
    toast = ToastAnimation(text="OK", duration_ms=1000)
    assert toast.tick(300)
    assert toast.elapsed_ms == 300
    assert toast.tick(300)
    assert toast.elapsed_ms == 600


# ── ToastAnimation: styles ───────────────────────────────────────────


def test_toast_style_success():
    toast = ToastAnimation(text="Done", style="success")
    assert toast.style_def["color"] == (0, 204, 102)
    assert toast.style_def["icon"] == "checkmark"


def test_toast_style_warning():
    toast = ToastAnimation(text="Careful", style="warning")
    assert toast.style_def["color"] == (255, 204, 0)
    assert toast.style_def["icon"] == "!"


def test_toast_style_error():
    toast = ToastAnimation(text="Failed", style="error")
    assert toast.style_def["color"] == (244, 68, 68)
    assert toast.style_def["icon"] == "X"


def test_toast_unknown_style_falls_back_to_success():
    toast = ToastAnimation(text="Hmm", style="unknown")
    assert toast.style_def == TOAST_STYLES["success"]


# ── ToastAnimation: render ───────────────────────────────────────────


def test_toast_render_no_crash():
    surf = _surface()
    toast = ToastAnimation(text="Task done", style="success", duration_ms=1000)
    toast.elapsed_ms = 500
    toast.render(surf)  # must not raise


def test_toast_render_custom_y():
    surf = _surface()
    toast = ToastAnimation(text="Warning!", style="warning", duration_ms=1000)
    toast.elapsed_ms = 100
    toast.render(surf, y=100)  # custom y position


def test_toast_render_after_finished_is_noop():
    surf = _surface()
    toast = ToastAnimation(text="X", duration_ms=100)
    toast.tick(200)
    assert toast.finished
    surf.fill((0, 0, 0))
    before = surf.get_at((120, 250))
    toast.render(surf)
    after = surf.get_at((120, 250))
    assert before == after
