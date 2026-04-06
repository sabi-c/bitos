"""Tests for ScreenRecorder — screenshot and GIF capture."""
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

import pygame
pygame.init()


def test_screenshot_saves_png():
    from display.screen_recorder import ScreenRecorder
    with tempfile.TemporaryDirectory() as tmpdir:
        recorder = ScreenRecorder(output_dir=tmpdir)
        surface = pygame.Surface((240, 280))
        surface.fill((255, 255, 255))
        path = recorder.screenshot(surface)
        assert os.path.exists(path)
        assert path.endswith(".png")


def test_recording_lifecycle():
    from display.screen_recorder import ScreenRecorder
    recorder = ScreenRecorder()
    assert not recorder.is_recording
    recorder.start_recording(fps=10)
    assert recorder.is_recording

    surface = pygame.Surface((240, 280))
    for i in range(10):
        surface.fill((i * 25, 0, 0))
        recorder.capture_frame(surface)

    assert recorder.frame_count == 10


def test_stop_recording_returns_path():
    from display.screen_recorder import ScreenRecorder
    with tempfile.TemporaryDirectory() as tmpdir:
        recorder = ScreenRecorder(output_dir=tmpdir)
        recorder.start_recording(fps=10)

        surface = pygame.Surface((240, 280))
        for _ in range(5):
            recorder.capture_frame(surface)

        path = recorder.stop_recording_sync()
        assert path is not None
        assert os.path.exists(path) or os.path.isdir(Path(path).parent / Path(path).stem)


def test_no_frames_returns_none():
    from display.screen_recorder import ScreenRecorder
    recorder = ScreenRecorder()
    recorder.start_recording()
    path = recorder.stop_recording_sync()
    assert path is None


def test_capture_when_not_recording_is_noop():
    from display.screen_recorder import ScreenRecorder
    recorder = ScreenRecorder()
    surface = pygame.Surface((240, 280))
    recorder.capture_frame(surface)  # should not crash
    assert recorder.frame_count == 0
