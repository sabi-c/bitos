"""Antigravity Voice Handler: 01-compatible WebSocket that routes through Antigravity.

Same protocol as ws_01_compat.py but instead of calling the local LLM bridge,
it transcribes audio → injects text into Antigravity via AG Bridge → captures
the response → sends back TTS audio.

Protocol (reuses the 01 wire format):
  Client -> Server:
    1. JSON  {"role":"user","type":"audio","format":"bytes.raw","start":true}
    2. Raw 16-bit PCM bytes (16 kHz, mono)
    3. JSON  {"role":"user","type":"audio","format":"bytes.raw","end":true}
    (or text messages with {"role":"user","type":"message","content":"..."})

  Server -> Client:
    1. JSON  {"role":"assistant","type":"message","content":"<Antigravity's response>"}
    2. JSON  {"role":"assistant","type":"audio","format":"bytes.raw","start":true}
    3. Raw 16-bit PCM bytes (response audio, 24 kHz mono)
    4. JSON  {"role":"assistant","type":"audio","format":"bytes.raw","end":true}
"""

from __future__ import annotations

import asyncio
import logging
import os
import wave

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ag_bridge import AGBridge
from stt_provider import create_stt_provider
from config import (
    AG_BRIDGE_URL,
    AG_RESPONSE_TIMEOUT_MS,
    AG_POLL_INTERVAL_MS,
    DEEPGRAM_API_KEY,
    STT_PROVIDER,
)

# Reuse audio helpers from the 01 compat module
from endpoints.ws_01_compat import (
    parse_01_message,
    is_start_message,
    is_end_message,
    pcm_to_wav,
    synthesize_tts,
    resample_pcm,
    wav_to_pcm,
    OUTPUT_SAMPLE_RATE,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Singleton setup ──────────────────────────────────────────────────

_ag_bridge: AGBridge | None = None
_stt_provider = None


def get_ag_bridge() -> AGBridge:
    global _ag_bridge
    if _ag_bridge is None:
        _ag_bridge = AGBridge(
            base_url=AG_BRIDGE_URL,
            timeout_ms=AG_RESPONSE_TIMEOUT_MS,
            poll_ms=AG_POLL_INTERVAL_MS,
        )
    return _ag_bridge


def get_stt():
    global _stt_provider
    if _stt_provider is None:
        _stt_provider = create_stt_provider(
            provider=STT_PROVIDER,
            api_key=DEEPGRAM_API_KEY,
        )
    return _stt_provider


# ── WebSocket endpoint ───────────────────────────────────────────────

@router.websocket("/ws/ag-voice")
async def ws_ag_voice(ws: WebSocket):
    """01-compatible voice WebSocket routed through Antigravity.

    Same protocol as /ws/01 but uses Antigravity as the AI backend
    instead of the local BITOS LLM bridge.
    """
    await ws.accept()
    logger.info("[AG-Voice] Client connected")

    bridge = get_ag_bridge()
    stt = get_stt()

    # Check AG Phone Chat is reachable
    if not await bridge.health_check():
        logger.error("[AG-Voice] AG Phone Chat not reachable at %s", AG_BRIDGE_URL)
        await ws.send_json({
            "role": "assistant", "type": "message",
            "content": "Antigravity is not available right now. Is the AG Phone Chat server running?",
        })
        await ws.close()
        return

    try:
        while True:
            audio_buffer = bytearray()
            recording = False
            text_content = None

            # ── Phase 1: Receive user input ──────────────────────────
            while True:
                try:
                    raw = await ws.receive()
                except WebSocketDisconnect:
                    raise

                if "text" in raw and raw["text"]:
                    msg = parse_01_message(raw["text"])
                    if msg is None:
                        continue

                    if is_start_message(msg):
                        recording = True
                        audio_buffer = bytearray()
                        logger.info("[AG-Voice] Recording started")
                        continue

                    if is_end_message(msg):
                        logger.info("[AG-Voice] Recording ended, %d bytes", len(audio_buffer))
                        recording = False
                        break

                    if msg.get("role") == "user" and msg.get("content"):
                        text_content = msg["content"]
                        break

                elif "bytes" in raw and raw["bytes"]:
                    if recording:
                        audio_buffer.extend(raw["bytes"])

            # ── Phase 2: Transcribe audio (or use text) ──────────────
            if text_content:
                user_text = text_content
                logger.info("[AG-Voice] Text input: %s", user_text[:80])
            elif len(audio_buffer) > 0:
                # Use the new STT provider (Deepgram/Whisper)
                try:
                    user_text = await stt.transcribe(bytes(audio_buffer))
                    logger.info("[AG-Voice] Transcribed: %s", user_text[:80] if user_text else "(empty)")
                except Exception as exc:
                    logger.error("[AG-Voice] STT failed: %s", exc)
                    # Fallback to the 01 pipeline's built-in STT
                    wav_path = pcm_to_wav(bytes(audio_buffer))
                    try:
                        from server.endpoints.ws_01_compat import transcribe_audio
                        user_text = await transcribe_audio(wav_path)
                    finally:
                        try:
                            os.unlink(wav_path)
                        except OSError:
                            pass
            else:
                logger.warning("[AG-Voice] Empty input, skipping")
                continue

            if not user_text:
                await ws.send_json({
                    "role": "assistant", "type": "message",
                    "content": "I didn't catch that. Could you try again?",
                })
                continue

            # Send transcript back for display
            await ws.send_json({
                "role": "user", "type": "message",
                "content": user_text,
            })

            # ── Phase 3: Inject into Antigravity and wait ────────────
            await ws.send_json({
                "role": "assistant", "type": "message",
                "content": "💭 Thinking...",
            })

            try:
                result = await bridge.inject_and_wait(user_text)
            except Exception as exc:
                logger.error("[AG-Voice] AG Bridge failed: %s", exc)
                await ws.send_json({
                    "role": "assistant", "type": "message",
                    "content": "Sorry, I couldn't reach Antigravity.",
                })
                continue

            if not result.get("ok"):
                error_msg = result.get("error", "unknown")
                logger.warning("[AG-Voice] AG response failed: %s", error_msg)
                await ws.send_json({
                    "role": "assistant", "type": "message",
                    "content": f"Antigravity error: {error_msg}",
                })
                continue

            response_text = result.get("text", "")
            duration_ms = result.get("durationMs", 0)
            logger.info(
                "[AG-Voice] Response (%dms): %s",
                duration_ms,
                response_text[:100] if response_text else "(empty)",
            )

            # ── Phase 4: Send text response ──────────────────────────
            await ws.send_json({
                "role": "assistant", "type": "message",
                "content": response_text or "(empty response from Antigravity)",
            })

            # ── Phase 5: TTS and send audio ──────────────────────────
            # For long responses, truncate for TTS (voice shouldn't read pages)
            tts_text = response_text
            if len(tts_text) > 2000:
                tts_text = tts_text[:2000] + "... I've sent the full response as text."

            try:
                tts_path = await synthesize_tts(tts_text)
                if tts_path:
                    try:
                        pcm_data = wav_to_pcm(tts_path)

                        with wave.open(tts_path, "rb") as wf:
                            src_rate = wf.getframerate()

                        if src_rate != OUTPUT_SAMPLE_RATE:
                            pcm_data = resample_pcm(pcm_data, src_rate, OUTPUT_SAMPLE_RATE)

                        await ws.send_json({
                            "role": "assistant",
                            "type": "audio",
                            "format": "bytes.raw",
                            "start": True,
                        })

                        chunk_size = 4096
                        for i in range(0, len(pcm_data), chunk_size):
                            await ws.send_bytes(pcm_data[i:i + chunk_size])

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
                    logger.info("[AG-Voice] TTS unavailable, text-only")
            except Exception as exc:
                logger.warning("[AG-Voice] TTS failed: %s", exc)

    except WebSocketDisconnect:
        logger.info("[AG-Voice] Client disconnected")
    except Exception as exc:
        logger.error("[AG-Voice] Unexpected error: %s", exc)
    finally:
        logger.info("[AG-Voice] Session ended")


# ── REST endpoints for non-voice Antigravity access ──────────────────

from pydantic import BaseModel


class AgTextRequest(BaseModel):
    text: str


@router.post("/ag/text")
async def ag_text_endpoint(req: AgTextRequest):
    """Send text to Antigravity and get the response (no voice)."""
    bridge = get_ag_bridge()

    if not await bridge.health_check():
        return {"ok": False, "error": "AG Phone Chat not reachable"}

    result = await bridge.inject_and_wait(req.text)
    return result


@router.get("/ag/health")
async def ag_health():
    """Check if the Antigravity pipeline is operational."""
    bridge = get_ag_bridge()
    reachable = await bridge.health_check()

    if reachable:
        state = await bridge.get_state()
        return {"ok": True, "agState": state}

    return {"ok": False, "error": f"AG Phone Chat not reachable at {AG_BRIDGE_URL}"}


@router.get("/ag/history")
async def ag_history():
    """Get the full Antigravity conversation history."""
    bridge = get_ag_bridge()
    return await bridge.get_history()


@router.post("/ag/history/clear")
async def ag_history_clear():
    """Clear the Antigravity conversation history."""
    bridge = get_ag_bridge()
    return await bridge.clear_history()
