"""Open Interpreter 01-compatible WebSocket endpoint.

Implements the 01 Light Server protocol so that the native iOS app,
Android app, ESP32 (M5Atom Echo), and desktop Python client can connect
directly to the BITOS server for voice interaction.

Protocol (single WebSocket, /ws/01):
  Client -> Server:
    1. JSON  {"role":"user","type":"audio","format":"bytes.raw","start":true}
       (or   {"role":"user","type":"message","start":true})
    2. Raw 16-bit PCM bytes (16 kHz, mono)
    3. JSON  {"role":"user","type":"audio","format":"bytes.raw","end":true}
       (or   {"role":"user","type":"message","end":true})

  Server -> Client:
    1. JSON  {"role":"assistant","type":"audio","format":"bytes.raw","start":true}
    2. Raw 16-bit PCM bytes (response audio, 24 kHz mono)
    3. JSON  {"role":"assistant","type":"audio","format":"bytes.raw","end":true}

  Text-only content messages are also supported:
    {"role":"assistant","type":"message","content":"Hello there"}
"""

from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import struct
import tempfile
import wave
from pathlib import Path

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

router = APIRouter()

# Audio constants matching 01 protocol
INPUT_SAMPLE_RATE = 16000   # 01 clients send 16 kHz
INPUT_CHANNELS = 1
INPUT_SAMPLE_WIDTH = 2      # 16-bit
OUTPUT_SAMPLE_RATE = 24000  # 01 clients expect 24 kHz
OUTPUT_CHANNELS = 1
OUTPUT_SAMPLE_WIDTH = 2     # 16-bit


# ── Helpers ───────────────────────────────────────────────────────────

def parse_01_message(raw: str | bytes) -> dict | None:
    """Parse a JSON control message from a 01 client.

    Returns the parsed dict, or None if the data is raw audio bytes.
    """
    if isinstance(raw, bytes):
        # Try to decode as JSON; if it fails, it's audio data
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None
    # String data is always JSON
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def is_start_message(msg: dict) -> bool:
    """Check if this is an audio/message start marker."""
    return msg.get("role") == "user" and msg.get("start") is True


def is_end_message(msg: dict) -> bool:
    """Check if this is an audio/message end marker."""
    return msg.get("role") == "user" and msg.get("end") is True


def pcm_to_wav(pcm_bytes: bytes, sample_rate: int = INPUT_SAMPLE_RATE,
               channels: int = INPUT_CHANNELS,
               sample_width: int = INPUT_SAMPLE_WIDTH) -> str:
    """Write raw PCM bytes to a temporary WAV file. Returns the file path."""
    fd, path = tempfile.mkstemp(prefix="bitos_01_", suffix=".wav")
    os.close(fd)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)
    return path


def wav_to_pcm(wav_path: str) -> bytes:
    """Read a WAV file and return raw PCM bytes."""
    with wave.open(wav_path, "rb") as wf:
        return wf.readframes(wf.getnframes())


async def transcribe_audio(wav_path: str) -> str:
    """Run STT on a WAV file using the BITOS STT pipeline.

    Runs in a thread executor since the STT backends are synchronous.
    """
    loop = asyncio.get_event_loop()

    def _transcribe():
        from device.audio.stt import SpeechToText
        stt = SpeechToText()
        return stt.transcribe(wav_path)

    return await loop.run_in_executor(None, _transcribe)


async def get_chat_response(text: str) -> str:
    """Send text to the BITOS LLM bridge and collect the full response.

    Uses the same LLM bridge as the /chat endpoint but in non-streaming mode.
    """
    loop = asyncio.get_event_loop()

    def _chat():
        from server.llm_bridge import create_llm_bridge
        from server.agent_modes import get_system_prompt
        bridge = create_llm_bridge()
        system_prompt = get_system_prompt("producer")
        response_text, _, _ = bridge.complete_text(text, system_prompt=system_prompt)
        return response_text

    return await loop.run_in_executor(None, _chat)


async def synthesize_tts(text: str) -> str | None:
    """Generate TTS audio as a WAV file. Returns path or None on failure.

    Tries edge-tts first (free, no API key), then falls back gracefully.
    Runs in a thread executor since TTS synthesis is synchronous.
    """
    loop = asyncio.get_event_loop()

    def _synthesize():
        fd, path = tempfile.mkstemp(prefix="bitos_01_tts_", suffix=".wav")
        os.close(fd)
        out_path = Path(path)

        # Try edge-tts
        try:
            from device.audio.edge_tts_provider import synthesize, is_available
            if is_available():
                ok = synthesize(text, out_path)
                if ok:
                    return str(out_path)
        except Exception as exc:
            logger.warning("01_tts_edge_failed: %s", exc)

        # Try OpenAI TTS
        try:
            import httpx
            api_key = os.environ.get("OPENAI_API_KEY", "")
            if api_key:
                resp = httpx.post(
                    "https://api.openai.com/v1/audio/speech",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={"model": "tts-1", "input": text, "voice": "alloy",
                          "response_format": "wav"},
                    timeout=30,
                )
                resp.raise_for_status()
                out_path.write_bytes(resp.content)
                return str(out_path)
        except Exception as exc:
            logger.warning("01_tts_openai_failed: %s", exc)

        # Cleanup on total failure
        out_path.unlink(missing_ok=True)
        return None

    return await loop.run_in_executor(None, _synthesize)


def resample_pcm(pcm_bytes: bytes, src_rate: int, dst_rate: int,
                 sample_width: int = 2) -> bytes:
    """Simple linear resampling of PCM audio between sample rates.

    For production use you'd want a proper resampler (e.g. scipy.signal.resample),
    but this is good enough for voice audio.
    """
    if src_rate == dst_rate:
        return pcm_bytes

    # Unpack samples
    fmt = f"<{len(pcm_bytes) // sample_width}h"
    try:
        samples = struct.unpack(fmt, pcm_bytes)
    except struct.error:
        return pcm_bytes

    # Linear interpolation
    ratio = dst_rate / src_rate
    new_len = int(len(samples) * ratio)
    resampled = []
    for i in range(new_len):
        src_idx = i / ratio
        idx = int(src_idx)
        frac = src_idx - idx
        if idx + 1 < len(samples):
            val = samples[idx] * (1 - frac) + samples[idx + 1] * frac
        else:
            val = samples[min(idx, len(samples) - 1)]
        resampled.append(int(max(-32768, min(32767, val))))

    return struct.pack(f"<{len(resampled)}h", *resampled)


# ── Health check (01 compatibility) ──────────────────────────────────

@router.get("/ping")
async def ping():
    """01 Light Server health check."""
    return "pong"


# ── WebSocket endpoint ───────────────────────────────────────────────

@router.websocket("/ws/01")
async def ws_01(ws: WebSocket):
    """01-compatible voice WebSocket.

    Handles the start/audio/end protocol, transcribes audio, gets a
    response from the BITOS agent, and sends back audio + text.
    """
    await ws.accept()
    logger.info("[01] Client connected")

    try:
        while True:
            audio_buffer = bytearray()
            recording = False
            text_content = None

            # Phase 1: Receive user input (start -> audio bytes -> end)
            while True:
                try:
                    raw = await ws.receive()
                except WebSocketDisconnect:
                    raise

                # Handle both text and bytes WebSocket frames
                if "text" in raw and raw["text"]:
                    msg = parse_01_message(raw["text"])
                    if msg is None:
                        continue

                    if is_start_message(msg):
                        recording = True
                        audio_buffer = bytearray()
                        logger.info("[01] Recording started")
                        continue

                    if is_end_message(msg):
                        logger.info("[01] Recording ended, %d bytes", len(audio_buffer))
                        recording = False
                        break

                    # Text content message (no audio)
                    if msg.get("role") == "user" and msg.get("content"):
                        text_content = msg["content"]
                        break

                elif "bytes" in raw and raw["bytes"]:
                    if recording:
                        audio_buffer.extend(raw["bytes"])

            # Phase 2: Transcribe audio or use text content
            if text_content:
                user_text = text_content
                logger.info("[01] Text input: %s", user_text[:80])
            elif len(audio_buffer) > 0:
                wav_path = pcm_to_wav(bytes(audio_buffer))
                try:
                    user_text = await transcribe_audio(wav_path)
                    logger.info("[01] Transcribed: %s", user_text[:80] if user_text else "(empty)")
                finally:
                    try:
                        os.unlink(wav_path)
                    except OSError:
                        pass
            else:
                logger.warning("[01] Empty input, skipping")
                continue

            if not user_text:
                # Send empty response
                await ws.send_json({
                    "role": "assistant", "type": "message",
                    "content": "I didn't catch that. Could you try again?"
                })
                continue

            # Phase 3: Get response from BITOS agent
            try:
                response_text = await get_chat_response(user_text)
            except Exception as exc:
                logger.error("[01] Chat failed: %s", exc)
                response_text = "Sorry, I had trouble processing that."

            logger.info("[01] Response: %s", response_text[:80] if response_text else "(empty)")

            # Phase 4: Send text content (always — 01 app displays this)
            await ws.send_json({
                "role": "assistant", "type": "message",
                "content": response_text,
            })

            # Phase 5: Try to send audio response
            try:
                tts_path = await synthesize_tts(response_text)
                if tts_path:
                    try:
                        pcm_data = wav_to_pcm(tts_path)

                        # Read source sample rate from the TTS WAV
                        with wave.open(tts_path, "rb") as wf:
                            src_rate = wf.getframerate()

                        # Resample to 24 kHz if needed (01 protocol expects 24 kHz output)
                        if src_rate != OUTPUT_SAMPLE_RATE:
                            pcm_data = resample_pcm(pcm_data, src_rate, OUTPUT_SAMPLE_RATE)

                        # Send audio start
                        await ws.send_json({
                            "role": "assistant",
                            "type": "audio",
                            "format": "bytes.raw",
                            "start": True,
                        })

                        # Send audio in chunks (4KB ~ 83ms at 24kHz/16-bit/mono)
                        chunk_size = 4096
                        for i in range(0, len(pcm_data), chunk_size):
                            await ws.send_bytes(pcm_data[i:i + chunk_size])

                        # Send audio end
                        await ws.send_json({
                            "role": "assistant",
                            "type": "audio",
                            "format": "bytes.raw",
                            "end": True,
                        })
                    finally:
                        try:
                            os.unlink(tts_path)
                        except OSError:
                            pass
                else:
                    logger.info("[01] TTS unavailable, text-only response")
            except Exception as exc:
                logger.warning("[01] TTS failed, text-only: %s", exc)

    except WebSocketDisconnect:
        logger.info("[01] Client disconnected")
    except Exception as exc:
        logger.error("[01] Unexpected error: %s", exc)
    finally:
        logger.info("[01] Session ended")
