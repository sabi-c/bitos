"""Screen capture and GIF recording for BITOS display.

Captures the pygame render surface as PNG screenshots or animated GIFs.
Designed for recording blob animations, tool status icons, and UI demos.

Usage:
    recorder = ScreenRecorder()

    # Single screenshot
    recorder.screenshot(surface, "/tmp/bitos_screenshot.png")

    # Animated GIF recording
    recorder.start_recording(fps=15)
    # ... in render loop: recorder.capture_frame(surface)
    recorder.stop_recording("/tmp/bitos_animation.gif")
"""
from __future__ import annotations

import logging
import threading
import time
from collections import deque
from pathlib import Path

import pygame

logger = logging.getLogger(__name__)

_DEFAULT_OUTPUT_DIR = "/tmp/bitos_captures"
_MAX_FRAMES = 300  # 20 seconds at 15 FPS


class ScreenRecorder:
    """Capture screenshots and record animated GIFs from the pygame surface."""

    def __init__(self, output_dir: str = _DEFAULT_OUTPUT_DIR):
        self._output_dir = Path(output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._recording = False
        self._frames: deque[bytes] = deque(maxlen=_MAX_FRAMES)
        self._frame_size: tuple[int, int] = (0, 0)
        self._fps = 15
        self._lock = threading.Lock()

    @property
    def is_recording(self) -> bool:
        return self._recording

    @property
    def frame_count(self) -> int:
        return len(self._frames)

    def screenshot(self, surface: pygame.Surface, path: str | None = None) -> str:
        """Save a single PNG screenshot. Returns the file path."""
        if path is None:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            path = str(self._output_dir / f"screenshot_{timestamp}.png")
        pygame.image.save(surface, path)
        logger.info("[RECORDER] Screenshot saved: %s", path)
        return path

    def start_recording(self, fps: int = 15) -> None:
        """Start recording frames for an animated GIF."""
        with self._lock:
            self._frames.clear()
            self._fps = fps
            self._recording = True
        logger.info("[RECORDER] Recording started (fps=%d, max=%d frames)", fps, _MAX_FRAMES)

    def capture_frame(self, surface: pygame.Surface) -> None:
        """Capture a single frame during recording. Call from render loop."""
        if not self._recording:
            return
        with self._lock:
            self._frame_size = surface.get_size()
            # Store as raw RGB bytes — fast, no encoding during render
            raw = pygame.image.tobytes(surface, "RGB")
            self._frames.append(raw)

    def stop_recording(self, path: str | None = None) -> str | None:
        """Stop recording and save as animated GIF. Returns file path or None on error."""
        with self._lock:
            self._recording = False
            frames = list(self._frames)
            size = self._frame_size
            fps = self._fps
            self._frames.clear()

        if not frames:
            logger.warning("[RECORDER] No frames captured")
            return None

        if path is None:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            path = str(self._output_dir / f"recording_{timestamp}.gif")

        # Encode in background thread to avoid blocking render
        def _encode():
            try:
                _save_gif(frames, size, fps, path)
                logger.info("[RECORDER] GIF saved: %s (%d frames)", path, len(frames))
            except Exception as exc:
                logger.error("[RECORDER] GIF save failed: %s", exc)

        threading.Thread(target=_encode, name="gif-encode", daemon=True).start()
        return path

    def stop_recording_sync(self, path: str | None = None) -> str | None:
        """Stop recording and save synchronously. For testing."""
        with self._lock:
            self._recording = False
            frames = list(self._frames)
            size = self._frame_size
            fps = self._fps
            self._frames.clear()

        if not frames:
            return None

        if path is None:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            path = str(self._output_dir / f"recording_{timestamp}.gif")

        _save_gif(frames, size, fps, path)
        return path


def _save_gif(frames: list[bytes], size: tuple[int, int], fps: int, path: str) -> None:
    """Convert raw RGB frames to an animated GIF.

    Uses PIL if available (better compression), falls back to
    a per-frame PNG dump when Pillow is not installed.
    """
    w, h = size
    duration_ms = int(1000 / fps)

    try:
        from PIL import Image
        pil_frames = []
        for raw in frames:
            img = Image.frombytes("RGB", (w, h), raw)
            # Quantize to palette for smaller GIF
            img = img.quantize(colors=16, method=Image.Quantize.MEDIANCUT)
            pil_frames.append(img)

        pil_frames[0].save(
            path,
            save_all=True,
            append_images=pil_frames[1:],
            duration=duration_ms,
            loop=0,  # infinite loop
            optimize=True,
        )
        return
    except ImportError:
        logger.info("[RECORDER] Pillow not available, falling back to frame dump")

    # Fallback: save individual PNGs (no GIF encoding without PIL)
    frame_dir = Path(path).parent / Path(path).stem
    frame_dir.mkdir(exist_ok=True)
    for i, raw in enumerate(frames):
        img = pygame.image.frombytes(raw, (w, h), "RGB")
        frame_path = frame_dir / f"frame_{i:04d}.png"
        pygame.image.save(img, str(frame_path))

    logger.info("[RECORDER] Saved %d PNG frames to %s/ (install Pillow for GIF)", len(frames), frame_dir)
