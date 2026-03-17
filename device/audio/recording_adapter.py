"""Adapter that wraps AudioPipeline (record/stop_recording/transcribe) into the
inline-recording interface expected by ChatPreviewPanel:

    start_recording()          — begin capture
    stop_and_process() -> obj  — stop capture, return object with .path
    cancel()                   — abort capture, discard audio
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from audio.pipeline import AudioPipeline

logger = logging.getLogger(__name__)


@dataclass
class RecordingResult:
    """Lightweight result with a .path attribute."""
    path: str | None


class RecordingAdapter:
    """Adapts AudioPipeline to the start/stop/cancel interface used by
    ChatPreviewPanel for inline recording."""

    def __init__(self, pipeline: AudioPipeline):
        self._pipeline = pipeline
        self._recording_path: str | None = None

    def start_recording(self) -> None:
        """Begin recording via the underlying pipeline."""
        try:
            path = self._pipeline.record()
            self._recording_path = path
        except Exception:
            logger.exception("recording_adapter: start_recording failed")
            self._recording_path = None

    def stop_and_process(self) -> RecordingResult:
        """Stop recording and return a result with the audio file path."""
        try:
            self._pipeline.stop_recording()
        except Exception:
            logger.exception("recording_adapter: stop_recording failed")
        path = self._recording_path
        self._recording_path = None
        return RecordingResult(path=path)

    def cancel(self) -> None:
        """Cancel recording and discard any captured audio."""
        try:
            self._pipeline.stop_recording()
        except Exception:
            logger.exception("recording_adapter: cancel stop_recording failed")
        self._recording_path = None
