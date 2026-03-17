"""Tests for the BlobRendererLite and gesture system."""
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import math
import sys
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pygame
import pytest

# Ensure device/ is on path
_device_dir = str(Path(__file__).resolve().parent.parent / "device")
if _device_dir not in sys.path:
    sys.path.insert(0, _device_dir)

from blob.renderer import BlobRendererLite, _spring_lerp, RENDER_W, RENDER_H
from blob.gestures import (
    GestureQueueLite, GestureLite, GESTURE_DURATIONS, GESTURE_NEUTRAL, _compute, _ActiveGesture,
)
from blob.states import BlobStateLite, STATE_CONFIGS_LITE, StateConfigLite
from blob.noise import noise2d


@pytest.fixture(autouse=True, scope="module")
def _init_pygame():
    pygame.init()
    yield
    pygame.quit()


# ── Noise ──────────────────────────────────────────────────────

class TestNoise:
    def test_noise_returns_float(self):
        val = noise2d(0.5, 0.5)
        assert isinstance(val, float)

    def test_noise_range(self):
        """Noise values should stay roughly within [-1, 1]."""
        for x in range(20):
            for y in range(20):
                val = noise2d(x * 0.3, y * 0.3)
                assert -1.5 <= val <= 1.5

    def test_noise_deterministic(self):
        a = noise2d(1.23, 4.56)
        b = noise2d(1.23, 4.56)
        assert a == b

    def test_noise_varies(self):
        """Different inputs should produce different outputs."""
        a = noise2d(0.0, 0.0)
        b = noise2d(10.0, 10.0)
        assert a != b


# ── States ─────────────────────────────────────────────────────

class TestStates:
    def test_all_states_have_config(self):
        for state in BlobStateLite:
            assert state in STATE_CONFIGS_LITE
            cfg = STATE_CONFIGS_LITE[state]
            assert isinstance(cfg, StateConfigLite)

    def test_config_values_reasonable(self):
        for state, cfg in STATE_CONFIGS_LITE.items():
            assert 0.0 < cfg.breathing_speed < 5.0
            assert 0.0 <= cfg.breathing_amount < 0.5
            assert 0.0 <= cfg.movement_speed < 5.0
            assert 0.0 <= cfg.noise_amount < 0.2
            assert 0.5 <= cfg.base_scale <= 1.5
            assert len(cfg.color) == 3

    def test_sleeping_is_slowest(self):
        sleeping = STATE_CONFIGS_LITE[BlobStateLite.SLEEPING]
        for state, cfg in STATE_CONFIGS_LITE.items():
            if state != BlobStateLite.SLEEPING:
                assert cfg.breathing_speed > sleeping.breathing_speed


# ── Spring Lerp ────────────────────────────────────────────────

class TestSpringLerp:
    def test_spring_moves_toward_target(self):
        pos, vel = _spring_lerp(0.0, 1.0, 0.0, 0.1)
        assert pos > 0.0, "Should move toward target"

    def test_spring_reaches_target(self):
        pos = 0.0
        vel = 0.0
        for _ in range(200):
            pos, vel = _spring_lerp(pos, 1.0, vel, 0.016)
        assert abs(pos - 1.0) < 0.01, f"Should converge: got {pos}"

    def test_spring_zero_dt(self):
        pos, vel = _spring_lerp(0.5, 1.0, 0.0, 0.0)
        assert pos == 0.5


# ── Gestures ───────────────────────────────────────────────────

class TestGestures:
    def test_all_gestures_have_duration(self):
        for g in GestureLite:
            assert g in GESTURE_DURATIONS
            assert GESTURE_DURATIONS[g] > 0

    def test_neutral_values(self):
        assert GESTURE_NEUTRAL["offset_x"] == 0.0
        assert GESTURE_NEUTRAL["offset_y"] == 0.0
        assert GESTURE_NEUTRAL["scale"] == 1.0

    def test_trigger_valid_gesture(self):
        q = GestureQueueLite()
        q.trigger("bounce")
        assert q.active

    def test_trigger_invalid_ignored(self):
        q = GestureQueueLite()
        q.trigger("nonexistent_gesture")
        assert not q.active

    def test_tick_returns_neutral_when_idle(self):
        q = GestureQueueLite()
        result = q.tick(16)
        assert result["scale"] == 1.0
        assert result["offset_x"] == 0.0

    def test_gesture_modifies_params(self):
        q = GestureQueueLite()
        q.trigger("pulse")
        # Advance a few frames into the gesture
        result = q.tick(100)
        result = q.tick(100)
        # Pulse should modify scale
        assert result["scale"] != 1.0

    def test_gesture_completes(self):
        q = GestureQueueLite()
        q.trigger("pulse")
        # Run well past duration + blend-out
        for _ in range(100):
            q.tick(50)
        assert not q.active

    def test_new_gesture_replaces_current(self):
        q = GestureQueueLite()
        q.trigger("bounce")
        q.tick(50)
        q.trigger("pulse")
        # Internal should now be pulse
        assert q.active
        assert q._current.gesture == GestureLite.PULSE

    def test_all_gestures_produce_output(self):
        """Every gesture type should produce non-neutral output at mid-point."""
        for g in GestureLite:
            active = _ActiveGesture(gesture=g, duration=GESTURE_DURATIONS[g])
            active.time = GESTURE_DURATIONS[g] * 0.2  # at 20% progress
            result = _compute(active)
            # At least one parameter should differ from neutral
            differs = (
                abs(result["offset_x"]) > 1e-6
                or abs(result["offset_y"]) > 1e-6
                or abs(result["scale"] - 1.0) > 1e-6
                or abs(result["squish_x"] - 1.0) > 1e-6
                or abs(result["squish_y"] - 1.0) > 1e-6
            )
            assert differs, f"Gesture {g.name} produced neutral output at t=0.3"


# ── BlobRendererLite ───────────────────────────────────────────

class TestBlobRendererLite:
    def test_init_defaults(self):
        r = BlobRendererLite()
        assert r.width == RENDER_W
        assert r.height == RENDER_H
        assert r.blob_count == 3
        assert r.state == "idle"

    def test_init_custom_blobs(self):
        r = BlobRendererLite(num_blobs=2)
        assert r.blob_count == 2

    def test_init_clamps_blobs(self):
        r = BlobRendererLite(num_blobs=0)
        assert r.blob_count >= 1
        r = BlobRendererLite(num_blobs=10)
        assert r.blob_count <= 5

    def test_set_state_valid(self):
        r = BlobRendererLite()
        r.set_state("listening")
        assert r.state == "listening"
        r.set_state("thinking")
        assert r.state == "thinking"

    def test_set_state_invalid_ignored(self):
        r = BlobRendererLite()
        r.set_state("exploding")
        assert r.state == "idle"  # unchanged

    def test_tick_returns_surface(self):
        r = BlobRendererLite()
        surface = r.tick(33)
        assert isinstance(surface, pygame.Surface)
        assert surface.get_width() == RENDER_W
        assert surface.get_height() == RENDER_H

    def test_tick_with_audio(self):
        r = BlobRendererLite()
        surface = r.tick(33, audio_amplitude=0.8)
        assert isinstance(surface, pygame.Surface)

    def test_tick_zero_dt(self):
        """Should handle zero dt gracefully (clamped to min)."""
        r = BlobRendererLite()
        surface = r.tick(0)
        assert isinstance(surface, pygame.Surface)

    def test_multiple_frames(self):
        """Run 60 frames without crashing."""
        r = BlobRendererLite()
        for i in range(60):
            amp = 0.5 * math.sin(i * 0.1)
            surface = r.tick(16, audio_amplitude=max(0, amp))
        assert isinstance(surface, pygame.Surface)

    def test_state_changes_during_animation(self):
        r = BlobRendererLite()
        r.tick(33)
        r.set_state("speaking")
        r.tick(33)
        r.set_state("sleeping")
        r.tick(33)
        assert r.state == "sleeping"

    def test_gesture_integration(self):
        r = BlobRendererLite()
        r.gestures.trigger("wiggle")
        surface = r.tick(33)
        assert isinstance(surface, pygame.Surface)

    def test_render_produces_white_pixels(self):
        """The blob should produce at least some white pixels."""
        r = BlobRendererLite(num_blobs=1)
        surface = r.tick(33)
        arr = pygame.surfarray.array3d(surface)
        white_count = np.sum(arr[:, :, 0] > 200)
        assert white_count > 0, "Blob should produce visible pixels"

    def test_render_not_all_white(self):
        """Should not fill the entire frame — there should be black background."""
        r = BlobRendererLite(num_blobs=1)
        surface = r.tick(33)
        arr = pygame.surfarray.array3d(surface)
        black_count = np.sum(arr[:, :, 0] < 10)
        assert black_count > 0, "Should have black background around blob"

    def test_sleeping_state_smaller(self):
        """Sleeping state should produce a smaller blob (fewer white pixels)."""
        r_idle = BlobRendererLite(num_blobs=1)
        r_sleep = BlobRendererLite(num_blobs=1)
        r_sleep.set_state("sleeping")

        # Run a few frames to let params settle
        for _ in range(30):
            s_idle = r_idle.tick(33)
            s_sleep = r_sleep.tick(33)

        idle_white = np.sum(pygame.surfarray.array3d(s_idle)[:, :, 0] > 200)
        sleep_white = np.sum(pygame.surfarray.array3d(s_sleep)[:, :, 0] > 200)
        assert sleep_white < idle_white, "Sleeping blob should be smaller"
