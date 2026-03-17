"""Edge TTS provider — Microsoft's free TTS API via edge-tts package.

Very low latency (~200-400ms to first audio), no API key required.
Supports streaming: writes audio chunks to file as they arrive,
enabling playback to start before synthesis completes.

Install: pip install edge-tts
"""

from __future__ import annotations

import asyncio
import io
import logging
import os
import struct
import tempfile
import wave
from pathlib import Path

logger = logging.getLogger(__name__)

# Good general-purpose voices (natural sounding, low latency)
DEFAULT_VOICE = os.getenv("EDGE_TTS_VOICE", "en-US-AriaNeural")

# Voices worth trying:
#   en-US-AriaNeural (female, warm)
#   en-US-GuyNeural (male, clear)
#   en-US-JennyNeural (female, friendly)
#   en-GB-SoniaNeural (British female)


def is_available() -> bool:
    """Return True if edge-tts is importable."""
    try:
        import edge_tts  # noqa: F401
        return True
    except ImportError:
        return False


def synthesize(text: str, output_path: Path, voice: str | None = None) -> bool:
    """Synthesize text to WAV file using Edge TTS.

    Returns True on success, False on failure.
    """
    if not is_available():
        logger.warning("edge_tts: package not installed (pip install edge-tts)")
        return False

    voice = voice or DEFAULT_VOICE

    try:
        # edge-tts is async, so we run it in a new event loop
        # (safe even if called from sync code in a thread)
        loop = _get_or_create_loop()
        return loop.run_until_complete(_synthesize_async(text, output_path, voice))
    except Exception as exc:
        logger.warning("edge_tts_error: %s", exc)
        return False


def synthesize_streaming(text: str, output_path: Path, voice: str | None = None,
                         on_first_chunk: callable = None) -> bool:
    """Synthesize text to WAV with streaming — calls on_first_chunk as soon
    as the first audio data arrives, so playback can begin immediately.

    Args:
        text: Text to synthesize.
        output_path: Path to write WAV file.
        voice: Edge TTS voice ID.
        on_first_chunk: Called with (output_path,) when first audio bytes are written.

    Returns True on success.
    """
    if not is_available():
        return False

    voice = voice or DEFAULT_VOICE

    try:
        loop = _get_or_create_loop()
        return loop.run_until_complete(
            _synthesize_streaming_async(text, output_path, voice, on_first_chunk)
        )
    except Exception as exc:
        logger.warning("edge_tts_streaming_error: %s", exc)
        return False


async def _synthesize_async(text: str, output_path: Path, voice: str) -> bool:
    """Core async synthesis — collects all audio then writes WAV."""
    import edge_tts

    communicate = edge_tts.Communicate(text, voice)

    # Collect MP3 chunks
    audio_chunks: list[bytes] = []
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_chunks.append(chunk["data"])

    if not audio_chunks:
        logger.warning("edge_tts: no audio chunks received")
        return False

    mp3_data = b"".join(audio_chunks)
    return _mp3_to_wav(mp3_data, output_path)


async def _synthesize_streaming_async(text: str, output_path: Path, voice: str,
                                       on_first_chunk: callable = None) -> bool:
    """Streaming synthesis — writes WAV progressively."""
    import edge_tts

    communicate = edge_tts.Communicate(text, voice)

    # We need to collect MP3 data and convert to WAV
    # Edge TTS streams MP3 chunks. We collect and convert since WAV
    # needs a header with total size. For streaming playback, we signal
    # on first chunk so the caller can start playing the partial file.
    audio_chunks: list[bytes] = []
    first_chunk_signaled = False

    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_chunks.append(chunk["data"])

            # After accumulating ~4KB of audio, write a partial WAV and signal
            if not first_chunk_signaled and len(audio_chunks) >= 3:
                partial_mp3 = b"".join(audio_chunks)
                if _mp3_to_wav(partial_mp3, output_path):
                    first_chunk_signaled = True
                    if on_first_chunk:
                        on_first_chunk(output_path)

    if not audio_chunks:
        logger.warning("edge_tts_streaming: no audio chunks")
        return False

    # Write final complete WAV
    mp3_data = b"".join(audio_chunks)
    return _mp3_to_wav(mp3_data, output_path)


def _mp3_to_wav(mp3_data: bytes, output_path: Path) -> bool:
    """Convert MP3 bytes to WAV file. Uses pydub if available, otherwise
    falls back to writing raw MP3 and letting the player handle it."""
    try:
        # Try pydub first (best quality conversion)
        from pydub import AudioSegment
        audio = AudioSegment.from_mp3(io.BytesIO(mp3_data))
        audio.export(str(output_path), format="wav")
        logger.debug("edge_tts: pydub mp3->wav %d bytes", output_path.stat().st_size)
        return True
    except ImportError:
        pass
    except Exception as exc:
        logger.debug("edge_tts: pydub failed (%s), trying ffmpeg", exc)

    # Try ffmpeg/avconv subprocess
    try:
        import subprocess
        # Write MP3 to temp file
        mp3_tmp = Path(tempfile.mkstemp(suffix=".mp3")[1])
        mp3_tmp.write_bytes(mp3_data)

        result = subprocess.run(
            ["ffmpeg", "-y", "-i", str(mp3_tmp), "-ar", "24000", "-ac", "1",
             "-f", "wav", str(output_path)],
            capture_output=True, timeout=10,
        )
        mp3_tmp.unlink(missing_ok=True)

        if result.returncode == 0 and output_path.exists():
            logger.debug("edge_tts: ffmpeg mp3->wav %d bytes", output_path.stat().st_size)
            return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Last resort: write MP3 directly (player may or may not handle it)
    output_path.write_bytes(mp3_data)
    logger.warning("edge_tts: wrote raw MP3 (no pydub/ffmpeg for conversion)")
    return True


def _get_or_create_loop() -> asyncio.AbstractEventLoop:
    """Get existing event loop or create a new one for sync callers."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # We're inside an async context — create a new loop in thread
            loop = asyncio.new_event_loop()
        return loop
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop
