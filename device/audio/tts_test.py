"""TTS pipeline test — runs on boot or standalone to verify voice works.

Tests each step independently with clear logging:
  1. Check env vars (SPEECHIFY_API_KEY present?)
  2. Test Speechify API (synthesize a short phrase)
  3. Test audio playback (play the synthesized WAV)
  4. Test full pipeline (TextToSpeech.speak())

Run standalone:  python3 -m device.audio.tts_test
Run from device: called by main.py on boot (background thread)
"""

from __future__ import annotations

import logging
import os
import tempfile
import time
from pathlib import Path

logger = logging.getLogger(__name__)


def test_speechify_api() -> dict:
    """Test Speechify API connectivity. Returns status dict."""
    result = {"step": "speechify_api", "ok": False, "detail": "", "duration_ms": 0}

    api_key = os.environ.get("SPEECHIFY_API_KEY")
    if not api_key:
        result["detail"] = "SPEECHIFY_API_KEY not set"
        logger.warning("tts_test: %s", result["detail"])
        return result

    voice_id = os.environ.get("SPEECHIFY_VOICE_ID", "sophia")
    logger.info("tts_test: speechify key=%s... voice=%s", api_key[:8], voice_id)

    try:
        from audio.speechify import synthesize

        out = Path(tempfile.mkstemp(prefix="bitos_tts_test_", suffix=".wav")[1])
        t0 = time.monotonic()
        ok = synthesize("test", out, voice_id=voice_id)
        elapsed = int((time.monotonic() - t0) * 1000)
        result["duration_ms"] = elapsed

        if ok and out.exists() and out.stat().st_size > 100:
            result["ok"] = True
            result["detail"] = f"ok size={out.stat().st_size}B in {elapsed}ms"
            logger.info("tts_test: speechify_api OK size=%d duration=%dms", out.stat().st_size, elapsed)
        else:
            result["detail"] = f"synthesize returned {ok}, size={out.stat().st_size if out.exists() else 0}"
            logger.warning("tts_test: speechify_api FAIL — %s", result["detail"])

        if out.exists():
            out.unlink(missing_ok=True)
    except Exception as exc:
        result["detail"] = str(exc)[:80]
        logger.error("tts_test: speechify_api ERROR — %s", exc)

    return result


def test_playback(wav_path: str | None = None) -> dict:
    """Test audio playback. If no wav_path, synthesizes first."""
    result = {"step": "playback", "ok": False, "detail": "", "duration_ms": 0}

    try:
        from audio.player import AudioPlayer

        # If no WAV provided, generate one via Speechify
        if not wav_path:
            api_key = os.environ.get("SPEECHIFY_API_KEY")
            if not api_key:
                result["detail"] = "no wav and no SPEECHIFY_API_KEY"
                return result

            from audio.speechify import synthesize
            tmp = Path(tempfile.mkstemp(prefix="bitos_play_test_", suffix=".wav")[1])
            ok = synthesize("hello", tmp)
            if not ok:
                result["detail"] = "could not synthesize test audio"
                return result
            wav_path = str(tmp)

        player = AudioPlayer()
        # Read volume setting
        try:
            import sys
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from storage.repository import DeviceRepository
            repo = DeviceRepository()
            vol = repo.get_setting("volume", 100)
            player.set_volume(max(0, min(100, int(vol))) / 100.0)
            logger.info("tts_test: playback volume=%s%%", vol)
        except Exception:
            pass

        t0 = time.monotonic()
        played = player.play_file(wav_path)
        elapsed = int((time.monotonic() - t0) * 1000)
        result["duration_ms"] = elapsed

        if played:
            result["ok"] = True
            result["detail"] = f"played in {elapsed}ms"
            logger.info("tts_test: playback OK duration=%dms", elapsed)
        else:
            result["detail"] = "play_file returned False"
            logger.warning("tts_test: playback FAIL")

    except Exception as exc:
        result["detail"] = str(exc)[:80]
        logger.error("tts_test: playback ERROR — %s", exc)

    return result


def test_full_pipeline() -> dict:
    """Test the full TTS pipeline (detect engine → synthesize → play)."""
    result = {"step": "full_pipeline", "ok": False, "detail": "", "duration_ms": 0}

    try:
        from audio.player import AudioPlayer
        from audio.tts import TextToSpeech

        tts = TextToSpeech(AudioPlayer())
        logger.info("tts_test: full_pipeline engine=%s", tts.engine)
        result["detail"] = f"engine={tts.engine}"

        if tts.engine == "silent":
            result["detail"] = "engine=silent (no TTS available)"
            logger.warning("tts_test: full_pipeline SKIP — engine=silent")
            return result

        t0 = time.monotonic()
        spoke = tts.speak("Voice test complete.")
        elapsed = int((time.monotonic() - t0) * 1000)
        result["duration_ms"] = elapsed

        if spoke:
            result["ok"] = True
            result["detail"] = f"engine={tts.engine} spoke in {elapsed}ms"
            logger.info("tts_test: full_pipeline OK engine=%s duration=%dms", tts.engine, elapsed)
        else:
            result["detail"] = f"engine={tts.engine} speak returned False"
            logger.warning("tts_test: full_pipeline FAIL — %s", result["detail"])

    except Exception as exc:
        import traceback
        result["detail"] = str(exc)[:80] or repr(exc)[:80]
        logger.error("tts_test: full_pipeline ERROR — %r", exc)
        logger.error("tts_test: full_pipeline TRACEBACK:\n%s", traceback.format_exc())

    return result


def run_boot_test() -> list[dict]:
    """Run all TTS tests. Called from main.py on boot in a background thread."""
    logger.info("tts_test: === BOOT TTS TEST START ===")
    results = []

    # Step 1: Speechify API
    r = test_speechify_api()
    results.append(r)

    # Step 2: Full pipeline (includes playback)
    if r["ok"]:
        r2 = test_full_pipeline()
        results.append(r2)
    else:
        logger.info("tts_test: skipping full_pipeline (speechify_api failed)")

    for r in results:
        status = "PASS" if r["ok"] else "FAIL"
        logger.info("tts_test: [%s] %s — %s", status, r["step"], r["detail"])

    logger.info("tts_test: === BOOT TTS TEST END ===")
    return results


if __name__ == "__main__":
    # Standalone test
    import sys
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")

    # Ensure device path is on PYTHONPATH
    device_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if device_dir not in sys.path:
        sys.path.insert(0, device_dir)

    print("=== BITOS TTS Test ===")
    print(f"SPEECHIFY_API_KEY: {'set (' + os.environ.get('SPEECHIFY_API_KEY', '')[:8] + '...)' if os.environ.get('SPEECHIFY_API_KEY') else 'NOT SET'}")
    print(f"SPEECHIFY_VOICE_ID: {os.environ.get('SPEECHIFY_VOICE_ID', 'sophia (default)')}")
    print()

    results = run_boot_test()
    print()
    for r in results:
        status = "PASS" if r["ok"] else "FAIL"
        print(f"  [{status}] {r['step']}: {r['detail']}")
    print()

    all_ok = all(r["ok"] for r in results)
    print("RESULT:", "ALL PASS" if all_ok else "SOME FAILED")
    sys.exit(0 if all_ok else 1)
