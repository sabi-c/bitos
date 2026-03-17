# Voice & Typewriter Fine-Tuning Foundation — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Multi-provider voice selection with per-engine tunable parameters, typewriter fine-tuning sliders, and test-on-device capability — all controllable from the companion app.

**Architecture:** Server exposes a voice catalog API. Companion app renders voice picker + typewriter sliders. Settings sync via existing HTTP pending-changes pipeline. Device TTS reads voice_id/params from repository. Test commands queue as special pending changes.

**Tech Stack:** Python (FastAPI server, pygame device), JavaScript (companion app), edge-tts/cartesia/speechify/openai TTS providers, SQLite settings storage.

**CRITICAL import rule:** Files under `device/` must NOT use `device.` prefix. Use `from audio.tts import TextToSpeech`, not `from device.audio.tts import TextToSpeech`.

---

### Task 1: Voice Catalog API (Server)

**Files:**
- Create: `server/voice_catalog.py`
- Modify: `server/main.py:731` (add endpoint after `/settings/device/pending`)
- Test: `tests/test_voice_catalog.py`

**Step 1: Write the test**

Create `tests/test_voice_catalog.py`:

```python
import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))

from voice_catalog import build_catalog


class VoiceCatalogTests(unittest.TestCase):
    def test_catalog_has_engines(self):
        catalog = build_catalog()
        self.assertIn("engines", catalog)
        self.assertIn("current", catalog)

    def test_edge_tts_voices_listed(self):
        catalog = build_catalog()
        edge = catalog["engines"].get("edge_tts", {})
        self.assertGreater(len(edge.get("voices", [])), 0)
        # Each voice has id, name, gender
        v = edge["voices"][0]
        self.assertIn("id", v)
        self.assertIn("name", v)

    def test_engine_has_params(self):
        catalog = build_catalog()
        edge = catalog["engines"].get("edge_tts", {})
        self.assertIn("params", edge)
        self.assertIn("rate", edge["params"])

    def test_openai_voices_listed(self):
        catalog = build_catalog()
        oai = catalog["engines"].get("openai", {})
        ids = [v["id"] for v in oai.get("voices", [])]
        self.assertIn("alloy", ids)
        self.assertIn("nova", ids)

    def test_current_defaults(self):
        catalog = build_catalog()
        current = catalog["current"]
        self.assertIn("engine", current)
        self.assertIn("voice_id", current)


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_voice_catalog.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'voice_catalog'`

**Step 3: Implement `server/voice_catalog.py`**

```python
"""Voice catalog — lists available TTS voices and per-engine parameters."""

from __future__ import annotations

import os
import shutil


def build_catalog(current_engine: str = "auto", current_voice_id: str = "",
                  current_params: dict | None = None) -> dict:
    """Build the full voice catalog with availability checks."""

    engines = {
        "edge_tts": {
            "available": _check_edge_tts(),
            "requires_key": False,
            "voices": [
                {"id": "en-US-AriaNeural", "name": "Aria", "gender": "female", "accent": "US"},
                {"id": "en-US-GuyNeural", "name": "Guy", "gender": "male", "accent": "US"},
                {"id": "en-US-JennyNeural", "name": "Jenny", "gender": "female", "accent": "US"},
                {"id": "en-US-AndrewNeural", "name": "Andrew", "gender": "male", "accent": "US"},
                {"id": "en-GB-SoniaNeural", "name": "Sonia", "gender": "female", "accent": "British"},
                {"id": "en-GB-RyanNeural", "name": "Ryan", "gender": "male", "accent": "British"},
                {"id": "en-AU-NatashaNeural", "name": "Natasha", "gender": "female", "accent": "Australian"},
            ],
            "params": {
                "rate": {"type": "range", "label": "Speed", "min": "-50%", "max": "+50%", "default": "+0%",
                         "description": "Speaking rate adjustment"},
                "pitch": {"type": "range", "label": "Pitch", "min": "-50Hz", "max": "+50Hz", "default": "+0Hz",
                          "description": "Pitch adjustment in Hz"},
            },
        },
        "cartesia": {
            "available": _check_cartesia(),
            "requires_key": True,
            "voices": [
                {"id": "79a125e8-cd45-4c13-8a67-188112f4dd22", "name": "Friendly", "gender": "neutral"},
            ],
            "params": {
                "speed": {"type": "choice", "label": "Speed",
                          "options": ["slowest", "slow", "normal", "fast", "fastest"],
                          "default": "normal", "description": "Speaking speed preset"},
            },
        },
        "speechify": {
            "available": bool(os.environ.get("SPEECHIFY_API_KEY")),
            "requires_key": True,
            "voices": [
                {"id": "sophia", "name": "Sophia", "gender": "female"},
                {"id": "henry", "name": "Henry", "gender": "male"},
                {"id": "george", "name": "George", "gender": "male"},
            ],
            "params": {
                "model": {"type": "choice", "label": "Model",
                          "options": ["simba-english", "simba-turbo"],
                          "default": "simba-english", "description": "Speechify model variant"},
            },
        },
        "openai": {
            "available": bool(os.environ.get("OPENAI_API_KEY")),
            "requires_key": True,
            "voices": [
                {"id": "alloy", "name": "Alloy", "gender": "neutral"},
                {"id": "echo", "name": "Echo", "gender": "male"},
                {"id": "fable", "name": "Fable", "gender": "neutral"},
                {"id": "onyx", "name": "Onyx", "gender": "male"},
                {"id": "nova", "name": "Nova", "gender": "female"},
                {"id": "shimmer", "name": "Shimmer", "gender": "female"},
            ],
            "params": {
                "model": {"type": "choice", "label": "Model",
                          "options": ["tts-1", "tts-1-hd"],
                          "default": "tts-1", "description": "Quality tier (hd = higher quality, slower)"},
                "speed": {"type": "slider", "label": "Speed", "min": 0.25, "max": 4.0,
                          "step": 0.25, "default": 1.0, "description": "Playback speed multiplier"},
            },
        },
        "espeak": {
            "available": bool(shutil.which("espeak") or shutil.which("espeak-ng")),
            "requires_key": False,
            "voices": [
                {"id": "en-us", "name": "English US", "gender": "neutral"},
                {"id": "en-gb", "name": "English UK", "gender": "neutral"},
            ],
            "params": {
                "speed": {"type": "slider", "label": "Speed (wpm)", "min": 80, "max": 350,
                          "step": 10, "default": 150, "description": "Words per minute"},
                "pitch": {"type": "slider", "label": "Pitch", "min": 0, "max": 99,
                          "step": 1, "default": 50, "description": "Voice pitch (0-99)"},
            },
        },
    }

    return {
        "engines": engines,
        "current": {
            "engine": current_engine,
            "voice_id": current_voice_id,
            "params": current_params or {},
        },
    }


def _check_edge_tts() -> bool:
    try:
        import edge_tts  # noqa: F401
        return True
    except ImportError:
        return False


def _check_cartesia() -> bool:
    if not os.environ.get("CARTESIA_API_KEY"):
        return False
    try:
        import cartesia  # noqa: F401
        return True
    except ImportError:
        return False
```

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_voice_catalog.py -v`
Expected: PASS (all 5 tests)

**Step 5: Add `/settings/voices` endpoint to server**

In `server/main.py`, after the `/settings/device/pending` endpoint (line ~731), add:

```python
@app.get("/settings/voices")
async def get_voice_catalog():
    """Return available TTS voices and per-engine parameters."""
    from voice_catalog import build_catalog
    with _device_settings_lock:
        engine = _device_settings_cache.get("tts_engine", "auto")
        voice_id = _device_settings_cache.get("voice_id", "")
        params_raw = _device_settings_cache.get("voice_params", "{}")
    import json
    try:
        params = json.loads(params_raw) if isinstance(params_raw, str) else (params_raw or {})
    except (json.JSONDecodeError, TypeError):
        params = {}
    return build_catalog(current_engine=engine, current_voice_id=voice_id, current_params=params)
```

**Step 6: Commit**

```bash
git add server/voice_catalog.py tests/test_voice_catalog.py server/main.py
git commit -m "feat: add voice catalog API with per-engine params and voices"
```

---

### Task 2: Setting Validators for Voice & Typewriter (Server)

**Files:**
- Modify: `server/agent_tools.py:402-413` (SETTING_VALIDATORS dict)
- Modify: `server/agent_tools.py:416-443` (validate_setting function)

**Step 1: Add new setting validators**

In `server/agent_tools.py`, update `SETTING_VALIDATORS` (line 402):

Add `"edge_tts"` and `"cartesia"` to the `tts_engine` choices, and add new keys:

```python
SETTING_VALIDATORS: dict[str, Any] = {
    "volume": {"type": "int", "min": 0, "max": 100},
    "voice_mode": {"type": "choice", "choices": ["off", "on", "auto"]},
    "tts_engine": {"type": "choice", "choices": ["auto", "edge_tts", "cartesia", "speechify", "chatterbox", "piper", "openai", "espeak"]},
    "ai_model": {"type": "choice", "choices": ["default", "haiku", "sonnet", "opus", ""]},
    "web_search": {"type": "bool"},
    "memory": {"type": "bool"},
    "extended_thinking": {"type": "bool"},
    "agent_mode": {"type": "choice", "choices": ["producer", "hacker", "clown", "monk", "storyteller", "director"]},
    "meta_prompt": {"type": "str"},
    "text_speed": {"type": "choice", "choices": ["slow", "normal", "fast", "custom"]},
    "voice_id": {"type": "str"},
    "voice_params": {"type": "json"},
    "typewriter_config": {"type": "json"},
}
```

**Step 2: Add JSON validator type**

In `validate_setting()` (line 416), add a `"json"` type handler after the `"str"` handler:

```python
        if spec["type"] == "str":
            return True, "", str(value)
        if spec["type"] == "json":
            import json
            if isinstance(value, dict):
                return True, "", json.dumps(value)
            if isinstance(value, str):
                try:
                    parsed = json.loads(value)
                    if not isinstance(parsed, dict):
                        return False, f"{key} must be a JSON object", None
                    return True, "", value
                except json.JSONDecodeError as e:
                    return False, f"{key} is not valid JSON: {e}", None
            return False, f"{key} must be a JSON object or string", None
```

**Step 3: Run existing settings tests**

Run: `python3 -m pytest tests/test_settings_wiring.py -v`
Expected: PASS

**Step 4: Commit**

```bash
git add server/agent_tools.py
git commit -m "feat: add voice_id, voice_params, typewriter_config setting validators"
```

---

### Task 3: TypewriterConfig Dataclass & Renderer Update (Device)

**Files:**
- Modify: `device/display/typewriter.py`
- Test: `tests/test_typewriter.py` (create)

**Step 1: Write the test**

Create `tests/test_typewriter.py`:

```python
import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

from display.typewriter import TypewriterRenderer, TypewriterConfig, SPEED_PRESETS


class TypewriterConfigTests(unittest.TestCase):
    def test_default_config(self):
        cfg = TypewriterConfig()
        self.assertEqual(cfg.base_speed_ms, 45.0)
        self.assertEqual(cfg.jitter_amount, 0.15)

    def test_from_preset(self):
        cfg = TypewriterConfig.from_preset("slow")
        self.assertEqual(cfg.base_speed_ms, 80.0)

    def test_from_dict(self):
        cfg = TypewriterConfig.from_dict({"base_speed_ms": 60, "jitter_amount": 0.05})
        self.assertEqual(cfg.base_speed_ms, 60.0)
        self.assertEqual(cfg.jitter_amount, 0.05)
        # Non-specified fields keep defaults
        self.assertEqual(cfg.common_speedup, 0.8)

    def test_renderer_with_config(self):
        cfg = TypewriterConfig(base_speed_ms=10.0, jitter_amount=0.0)
        tw = TypewriterRenderer("Hello", config=cfg)
        tw.update(1.0)  # 1 second should reveal all at 10ms/char
        self.assertTrue(tw.finished)
        self.assertEqual(tw.get_visible_text(), "Hello")

    def test_renderer_with_speed_preset(self):
        tw = TypewriterRenderer("Hi", speed="fast")
        tw.update(1.0)
        self.assertTrue(tw.finished)

    def test_renderer_instant(self):
        tw = TypewriterRenderer("Test", speed="instant")
        self.assertTrue(tw.finished)
        self.assertEqual(tw.get_visible_text(), "Test")

    def test_config_to_dict(self):
        cfg = TypewriterConfig(base_speed_ms=50.0)
        d = cfg.to_dict()
        self.assertEqual(d["base_speed_ms"], 50.0)
        self.assertIn("punctuation_multiplier", d)


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_typewriter.py -v`
Expected: FAIL — `ImportError: cannot import name 'TypewriterConfig'`

**Step 3: Implement TypewriterConfig**

Rewrite `device/display/typewriter.py`:

```python
"""TypewriterRenderer — character-by-character text reveal.

Reveals text one character at a time with natural typing cadence:
- Common letters faster, rare letters slower
- Micro-jitter for organic feel
- Punctuation pauses at sentence/clause boundaries
- Speed presets and custom config for fine-tuning

Call update(dt) each frame, then get_visible_text() for the current state.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field, asdict


# Post-character pauses in ms (base values, scaled by punctuation_multiplier)
_PAUSE_MS = {
    ".": 280,
    "!": 300,
    "?": 300,
    ",": 120,
    ":": 150,
    ";": 140,
    "\n": 200,
}

_COMMON = frozenset("etaoinsrhld")
_RARE = frozenset("zxqjZXQJ")


@dataclass
class TypewriterConfig:
    """All tunable parameters for typewriter text reveal."""
    base_speed_ms: float = 45.0
    punctuation_multiplier: float = 1.0
    jitter_amount: float = 0.15
    common_speedup: float = 0.8
    rare_slowdown: float = 1.3

    @classmethod
    def from_preset(cls, preset: str) -> TypewriterConfig:
        """Create config from a named preset."""
        presets = {
            "slow": cls(base_speed_ms=80.0),
            "normal": cls(),
            "fast": cls(base_speed_ms=20.0),
            "instant": cls(base_speed_ms=0.0),
        }
        return presets.get(preset, cls())

    @classmethod
    def from_dict(cls, d: dict) -> TypewriterConfig:
        """Create config from a dict, using defaults for missing keys."""
        defaults = cls()
        return cls(
            base_speed_ms=float(d.get("base_speed_ms", defaults.base_speed_ms)),
            punctuation_multiplier=float(d.get("punctuation_multiplier", defaults.punctuation_multiplier)),
            jitter_amount=float(d.get("jitter_amount", defaults.jitter_amount)),
            common_speedup=float(d.get("common_speedup", defaults.common_speedup)),
            rare_slowdown=float(d.get("rare_slowdown", defaults.rare_slowdown)),
        )

    @classmethod
    def from_json(cls, json_str: str) -> TypewriterConfig:
        """Create config from a JSON string."""
        try:
            return cls.from_dict(json.loads(json_str))
        except (json.JSONDecodeError, TypeError):
            return cls()

    def to_dict(self) -> dict:
        return asdict(self)


# Speed presets for backward compatibility
SPEED_PRESETS: dict[str, float] = {
    "slow": 80.0,
    "normal": 45.0,
    "fast": 20.0,
    "instant": 0.0,
}


def _char_delay_ms(char: str, config: TypewriterConfig) -> float:
    """Delay in ms after revealing this character."""
    base = config.base_speed_ms

    if char == " ":
        d = base * 0.6
    elif char in _COMMON:
        d = base * config.common_speedup
    elif char in _RARE:
        d = base * config.rare_slowdown
    else:
        d = base

    # Jitter for organic feel
    if config.jitter_amount > 0:
        jitter = config.jitter_amount
        d *= random.uniform(1.0 - jitter, 1.0 + jitter)

    # Add punctuation pause (scaled by multiplier)
    pause = _PAUSE_MS.get(char, 0)
    if pause:
        d += pause * config.punctuation_multiplier

    return d


class TypewriterRenderer:
    """Character-by-character text reveal with natural typing cadence."""

    def __init__(self, text: str, speed: str = "normal", config: TypewriterConfig | None = None):
        self._text = text or ""
        if config:
            self._config = config
        else:
            self._config = TypewriterConfig.from_preset(speed)

        self._cursor = 0
        self._elapsed = 0.0
        self._next_reveal_at = 0.0
        self._finished = not self._text or self._config.base_speed_ms == 0.0

        if self._finished and self._text:
            self._cursor = len(self._text)

    def update(self, dt: float) -> None:
        if self._finished:
            return

        self._elapsed += dt

        while self._cursor < len(self._text) and self._elapsed >= self._next_reveal_at:
            char = self._text[self._cursor]
            self._cursor += 1
            delay_ms = _char_delay_ms(char, self._config)
            self._next_reveal_at += delay_ms / 1000.0

        if self._cursor >= len(self._text):
            self._finished = True

    def get_visible_text(self) -> str:
        return self._text[:self._cursor]

    @property
    def finished(self) -> bool:
        return self._finished

    def reset(self, text: str, speed: str | None = None, config: TypewriterConfig | None = None) -> None:
        if config:
            self._config = config
        elif speed:
            self._config = TypewriterConfig.from_preset(speed)
        self._text = text or ""
        self._cursor = 0
        self._elapsed = 0.0
        self._next_reveal_at = 0.0
        self._finished = not self._text or self._config.base_speed_ms == 0.0
        if self._finished and self._text:
            self._cursor = len(self._text)
```

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_typewriter.py -v`
Expected: PASS (all 7 tests)

**Step 5: Run existing tests to verify no regressions**

Run: `python3 -m pytest tests/ -x -q -k "not test_render_draws_sidebar and not test_double_on_thread" 2>&1 | tail -5`
Expected: All pass (TypewriterRenderer API is backward-compatible — `speed` param still works)

**Step 6: Commit**

```bash
git add device/display/typewriter.py tests/test_typewriter.py
git commit -m "feat: add TypewriterConfig dataclass for fine-grained typewriter tuning"
```

---

### Task 4: Device TTS — Read voice_id/params from Repository

**Files:**
- Modify: `device/audio/tts.py:33-47` (constructor), `device/audio/tts.py:133-160` (speak method)
- Modify: `device/audio/edge_tts_provider.py:91-108` (add rate/pitch params)
- Modify: `device/audio/speechify.py:28-53` (accept model param)

**Step 1: Update `tts.py` to read voice settings from repository**

In `TextToSpeech.__init__()`, after the volume setup (line ~42), add:

```python
        # Load voice settings from repository
        self._voice_id = None
        self._voice_params = {}
        try:
            self._voice_id = repo.get_setting("voice_id", None)
            import json
            params_raw = repo.get_setting("voice_params", "{}")
            self._voice_params = json.loads(params_raw) if isinstance(params_raw, str) else (params_raw or {})
        except Exception:
            pass
```

**Step 2: Update `speak()` to pass voice_id/params to providers**

In `speak()` (line ~146), update each engine call to pass voice settings:

```python
            if self.engine == "cartesia":
                self._run_cartesia(text, out)
            elif self.engine == "edge_tts":
                self._run_edge_tts(text, out)
            # ... (same for each engine)
```

Update `_run_cartesia`:
```python
    def _run_cartesia(self, text: str, output_file: Path) -> None:
        t0 = time.monotonic()
        from . import cartesia_provider
        voice = self._voice_id or None
        ok = cartesia_provider.synthesize(text, output_file, voice=voice)
        # ... rest unchanged
```

Update `_run_edge_tts`:
```python
    def _run_edge_tts(self, text: str, output_file: Path) -> None:
        t0 = time.monotonic()
        from . import edge_tts_provider
        voice = self._voice_id or None
        rate = self._voice_params.get("rate")
        pitch = self._voice_params.get("pitch")
        ok = edge_tts_provider.synthesize(text, output_file, voice=voice, rate=rate, pitch=pitch)
        # ... rest unchanged
```

Update `_run_speechify`:
```python
    def _run_speechify(self, text: str, output_file: Path) -> None:
        from .speechify import synthesize
        voice = self._voice_id or None
        model = self._voice_params.get("model")
        if not synthesize(text, output_file, voice_id=voice, model=model):
            # ... fallback
```

Update `_run_openai_tts`:
```python
    def _run_openai_tts(self, text: str, output_file: Path) -> None:
        import openai
        client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        voice = self._voice_id or "alloy"
        speed = float(self._voice_params.get("speed", 1.0))
        model = self._voice_params.get("model", "tts-1")
        with client.audio.speech.with_streaming_response.create(
            model=model, voice=voice, input=text, speed=speed
        ) as resp:
            resp.stream_to_file(str(output_file))
```

Update `_run_espeak`:
```python
    def _run_espeak(self, text: str, output_file: Path) -> None:
        espeak_cmd = shutil.which("espeak-ng") or shutil.which("espeak")
        if not espeak_cmd:
            return
        voice = self._voice_id or "en-us"
        speed = str(self._voice_params.get("speed", 150))
        pitch = str(self._voice_params.get("pitch", 50))
        env = os.environ.copy()
        env["ALSA_DEFAULT_PCM"] = PLAYBACK_DEVICE
        subprocess.run([espeak_cmd, "-v", voice, "-s", speed, "-p", pitch, "-w", str(output_file), text],
                       check=False, timeout=20, env=env)
```

**Step 3: Update `edge_tts_provider.py` to accept rate/pitch**

Change `synthesize()` signature (line 42):
```python
def synthesize(text: str, output_path: Path, voice: str | None = None,
               rate: str | None = None, pitch: str | None = None) -> bool:
```

And in `_synthesize_async()` (line 91):
```python
async def _synthesize_async(text: str, output_path: Path, voice: str,
                             rate: str | None = None, pitch: str | None = None) -> bool:
    import edge_tts
    communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
    # ... rest unchanged
```

Pass `rate`/`pitch` through from `synthesize` → `_synthesize_async`.

**Step 4: Update `speechify.py` to accept model param**

Change `synthesize()` signature (line 28):
```python
def synthesize(text: str, output_path: Path, voice_id: str | None = None,
               model: str | None = None) -> bool:
```

In the JSON payload (line 46):
```python
            json={
                "input": text,
                "voice_id": voice,
                "model": model or DEFAULT_MODEL,
                "audio_format": "wav",
            },
```

**Step 5: Add a `reload_voice_settings()` method to TextToSpeech**

```python
    def reload_voice_settings(self) -> None:
        """Re-read voice_id and voice_params from repository. Called after settings sync."""
        try:
            from storage.repository import DeviceRepository
            import json
            repo = DeviceRepository()
            self._voice_id = repo.get_setting("voice_id", None)
            params_raw = repo.get_setting("voice_params", "{}")
            self._voice_params = json.loads(params_raw) if isinstance(params_raw, str) else (params_raw or {})
            # Also re-detect engine in case tts_engine changed
            self.engine = self._detect_engine()
        except Exception:
            pass
```

**Step 6: Run tests**

Run: `python3 -m pytest tests/ -x -q -k "not test_render_draws_sidebar and not test_double_on_thread" 2>&1 | tail -5`
Expected: All pass

**Step 7: Commit**

```bash
git add device/audio/tts.py device/audio/edge_tts_provider.py device/audio/speechify.py
git commit -m "feat: TTS reads voice_id and per-engine params from device settings"
```

---

### Task 5: Test-on-Device Infrastructure (Server + Device)

**Files:**
- Modify: `server/main.py` (add test endpoints after `/settings/voices`)
- Modify: `device/client/api.py:287-305` (_apply_setting_change)
- Create: `device/overlays/test_typewriter.py`

**Step 1: Add server test endpoints**

In `server/main.py`, after the `/settings/voices` endpoint:

```python
@app.post("/settings/device/test-voice")
async def test_voice_on_device(request: Request):
    """Queue a voice test command for the device to play."""
    body = await request.json()
    text = body.get("text", "Hello! This is how I sound.")
    engine = body.get("engine", "auto")
    voice_id = body.get("voice_id", "")
    params = body.get("params", {})
    import json

    with _device_settings_lock:
        if "_pending_changes" not in _device_settings_cache:
            _device_settings_cache["_pending_changes"] = []
        _device_settings_cache["_pending_changes"].append({
            "key": "_test_voice",
            "value": json.dumps({"text": text, "engine": engine, "voice_id": voice_id, "params": params}),
        })
    return {"ok": True, "queued": "test_voice"}


@app.post("/settings/device/test-typewriter")
async def test_typewriter_on_device(request: Request):
    """Queue a typewriter test command for the device to render."""
    body = await request.json()
    text = body.get("text", "The quick brown fox jumps over the lazy dog.")
    config = body.get("config", {})
    import json

    with _device_settings_lock:
        if "_pending_changes" not in _device_settings_cache:
            _device_settings_cache["_pending_changes"] = []
        _device_settings_cache["_pending_changes"].append({
            "key": "_test_typewriter",
            "value": json.dumps({"text": text, "config": config}),
        })
    return {"ok": True, "queued": "test_typewriter"}
```

**Step 2: Create `device/overlays/test_typewriter.py`**

```python
"""Test typewriter overlay — renders sample text with custom config, auto-dismisses."""

from __future__ import annotations

import time
import pygame

from display.typewriter import TypewriterRenderer, TypewriterConfig
from display.theme import get_font
from display.tokens import PHYSICAL_W, PHYSICAL_H


class TestTypewriterOverlay:
    """Overlay that renders a typewriter test, auto-dismisses when done + 2s."""

    def __init__(self, text: str, config: dict, on_dismiss: callable):
        self._text = text
        self._config = TypewriterConfig.from_dict(config)
        self._tw = TypewriterRenderer(text, config=self._config)
        self._on_dismiss = on_dismiss
        self._finished_at: float | None = None
        self._dismissed = False

    def tick(self, dt: float) -> None:
        if self._dismissed:
            return
        self._tw.update(dt)
        if self._tw.finished and self._finished_at is None:
            self._finished_at = time.time()
        # Auto-dismiss 2s after typewriter finishes
        if self._finished_at and time.time() - self._finished_at > 2.0:
            self._dismissed = True
            if self._on_dismiss:
                self._on_dismiss()

    def render(self, surface: pygame.Surface) -> None:
        surface.fill((0, 0, 0))
        font = get_font(9)
        WHITE = (255, 255, 255)
        DIM2 = (100, 100, 100)

        # Title
        title_font = get_font(11)
        title = title_font.render("TYPEWRITER TEST", False, DIM2)
        surface.blit(title, ((PHYSICAL_W - title.get_width()) // 2, 8))

        # Visible text with word wrapping
        visible = self._tw.get_visible_text()
        y = 32
        max_w = PHYSICAL_W - 16
        words = visible.split(" ")
        line = ""
        for word in words:
            test = (line + " " + word).strip()
            if font.size(test)[0] > max_w and line:
                surf = font.render(line, False, WHITE)
                surface.blit(surf, (8, y))
                y += font.get_height() + 2
                line = word
            else:
                line = test
        if line:
            surf = font.render(line, False, WHITE)
            surface.blit(surf, (8, y))

        # Config info at bottom
        info_font = get_font(7)
        info = f"{self._config.base_speed_ms:.0f}ms  jit={self._config.jitter_amount:.2f}  punc={self._config.punctuation_multiplier:.1f}x"
        info_surf = info_font.render(info, False, DIM2)
        surface.blit(info_surf, ((PHYSICAL_W - info_surf.get_width()) // 2, PHYSICAL_H - info_surf.get_height() - 4))

    def handle_action(self, event: str) -> bool:
        if event == "LONG_PRESS":
            self._dismissed = True
            if self._on_dismiss:
                self._on_dismiss()
        return True  # consume all input while overlay is active
```

**Step 3: Update `device/client/api.py` — handle test commands in `_apply_setting_change`**

After the volume handling (line ~303), add handlers for test commands:

```python
            # Test commands (prefixed with _) — not persisted
            if key == "_test_voice":
                self._handle_test_voice(value)
                return
            if key == "_test_typewriter":
                self._handle_test_typewriter(value)
                return
```

And add the handler methods:

```python
    def _handle_test_voice(self, value: str) -> None:
        """Play a voice test with specified engine/voice/params."""
        import json
        try:
            data = json.loads(value) if isinstance(value, str) else value
            text = data.get("text", "Hello!")
            engine = data.get("engine", "auto")
            voice_id = data.get("voice_id", "")
            params = data.get("params", {})

            from storage.repository import DeviceRepository
            repo = DeviceRepository()
            # Temporarily set voice settings for this test
            if engine and engine != "auto":
                repo.set_setting("tts_engine", engine)
            if voice_id:
                repo.set_setting("voice_id", voice_id)
            if params:
                repo.set_setting("voice_params", json.dumps(params))

            from audio.tts import TextToSpeech
            tts = TextToSpeech()
            tts.speak(text)
        except Exception as exc:
            logging.warning("test_voice_failed: %s", exc)

    def _handle_test_typewriter(self, value: str) -> None:
        """Trigger a typewriter test overlay on the device."""
        import json
        try:
            data = json.loads(value) if isinstance(value, str) else value
            if self.on_test_typewriter:
                self.on_test_typewriter(data.get("text", "Test"), data.get("config", {}))
        except Exception as exc:
            logging.warning("test_typewriter_failed: %s", exc)
```

Note: `self.on_test_typewriter` is a callback that main.py will wire up to push the TestTypewriterOverlay.

**Step 4: Add `on_test_typewriter` to BackendClient init**

In `BackendClient.__init__()`, add:
```python
        self.on_test_typewriter: callable | None = None
```

**Step 5: Wire test typewriter overlay in `device/main.py`**

After BackendClient initialization, add:

```python
    def _show_test_typewriter(text: str, config: dict):
        from overlays.test_typewriter import TestTypewriterOverlay
        overlay = TestTypewriterOverlay(
            text=text,
            config=config,
            on_dismiss=lambda: screen_mgr.dismiss_banner(),
        )
        screen_mgr.show_banner(overlay)

    backend_client.on_test_typewriter = _show_test_typewriter
```

**Step 6: Run tests**

Run: `python3 -m pytest tests/ -x -q -k "not test_render_draws_sidebar and not test_double_on_thread" 2>&1 | tail -5`
Expected: All pass

**Step 7: Commit**

```bash
git add server/main.py device/client/api.py device/overlays/test_typewriter.py device/main.py
git commit -m "feat: test-on-device infrastructure for voice and typewriter"
```

---

### Task 6: Companion App — Voice Picker & Typewriter Sliders

**Files:**
- Modify: `companion/js/settings.js:242-290` (SETTING_GROUPS)
- Modify: `companion/settings.html` (add voice picker components)

**Step 1: Update SETTING_GROUPS in `companion/js/settings.js`**

Replace the existing voice and display groups:

```javascript
const SETTING_GROUPS = [
  {
    id: 'voice',
    label: 'VOICE',
    settings: [
      { key: 'voice_enabled', label: 'Voice output', type: 'toggle', default: false },
      { key: 'voice_mode', label: 'Voice mode', type: 'picker', options: ['off', 'on', 'auto'], default: 'auto' },
      { key: 'volume', label: 'Volume', type: 'slider', min: 0, max: 100, step: 5, default: 70 },
      { key: 'tts_engine', label: 'TTS engine', type: 'picker',
        options: ['auto', 'edge_tts', 'cartesia', 'speechify', 'openai', 'espeak'], default: 'auto' },
      { key: 'voice_id', label: 'Voice', type: 'voice_picker', default: '' },
      { key: 'voice_params', label: 'Voice tuning', type: 'voice_params', default: '{}' },
      { key: '_test_voice', label: 'Preview on device', type: 'action', action: 'test_voice' },
    ],
  },
  {
    id: 'text',
    label: 'TEXT',
    settings: [
      { key: 'text_speed', label: 'Speed preset', type: 'picker', options: ['slow', 'normal', 'fast', 'custom'], default: 'normal' },
      { key: 'tw_base_speed_ms', label: 'Base speed (ms/char)', type: 'slider', min: 10, max: 120, step: 5, default: 45, showWhen: 'custom' },
      { key: 'tw_punctuation', label: 'Punctuation pause', type: 'slider', min: 0.5, max: 3.0, step: 0.1, default: 1.0, showWhen: 'custom' },
      { key: 'tw_jitter', label: 'Jitter amount', type: 'slider', min: 0, max: 0.30, step: 0.01, default: 0.15, showWhen: 'custom' },
      { key: 'tw_common_speed', label: 'Common letter speed', type: 'slider', min: 0.5, max: 1.0, step: 0.05, default: 0.8, showWhen: 'custom' },
      { key: 'tw_rare_speed', label: 'Rare letter speed', type: 'slider', min: 1.0, max: 2.0, step: 0.05, default: 1.3, showWhen: 'custom' },
      { key: '_test_typewriter', label: 'Test on device', type: 'action', action: 'test_typewriter' },
    ],
  },
  {
    id: 'ai',
    label: 'AI',
    settings: [
      { key: 'agent_mode', label: 'Agent mode', type: 'picker', options: ['producer', 'hacker', 'clown', 'monk', 'storyteller', 'director'], default: 'producer' },
      { key: 'ai_model', label: 'AI model', type: 'picker', options: ['default', 'haiku', 'sonnet', 'opus'], default: 'default' },
      { key: 'extended_thinking', label: 'Extended thinking', type: 'toggle', default: false },
      { key: 'web_search', label: 'Web search', type: 'toggle', default: true },
      { key: 'memory', label: 'Memory', type: 'toggle', default: true },
    ],
  },
  {
    id: 'display',
    label: 'DISPLAY',
    settings: [
      { key: 'font_family', label: 'Font', type: 'picker', options: ['press_start_2p', 'monocraft'], default: 'monocraft' },
      { key: 'font_scale', label: 'Font size', type: 'slider', min: 0.8, max: 1.5, step: 0.1, default: 1.0 },
    ],
  },
  {
    id: 'wakeword',
    label: 'WAKE WORD',
    settings: [
      { key: 'wake_word_enabled', label: 'Wake word', type: 'toggle', default: false },
      { key: 'wake_word_phrase', label: 'Phrase', type: 'picker', options: ['hey bitos', 'ok bitos', 'bitos'], default: 'hey bitos' },
      { key: 'wake_word_sensitivity', label: 'Sensitivity', type: 'slider', min: 0.1, max: 1.0, step: 0.1, default: 0.5 },
    ],
  },
  {
    id: 'sleep',
    label: 'SLEEP',
    settings: [
      { key: 'sleep_timeout_seconds', label: 'Sleep after', type: 'picker', options: ['30', '60', '120', '300', '600', 'never'], default: '60' },
      { key: 'safe_shutdown_pct', label: 'Auto-shutdown at %', type: 'slider', min: 0, max: 20, step: 1, default: 5 },
    ],
  },
];
```

**Step 2: Add voice catalog fetch and dynamic rendering to settings.html**

Add a `<script>` section in `settings.html` with voice catalog logic. This needs:

1. **Voice catalog loader** — fetches `/settings/voices` when engine changes
2. **Voice picker renderer** — radio buttons for voices in the selected engine
3. **Voice params renderer** — dynamic sliders/pickers from catalog `params`
4. **Action handlers** — "Preview on device" POSTs to `/settings/device/test-voice`, "Test on device" POSTs to `/settings/device/test-typewriter`
5. **Conditional visibility** — typewriter sliders only show when `text_speed === 'custom'`
6. **Typewriter config bundling** — when any `tw_*` slider changes, bundle all 5 into a `typewriter_config` JSON and PUT to server

Add this JavaScript after the existing settings render logic:

```javascript
// Voice catalog cache
let voiceCatalog = null;

async function loadVoiceCatalog() {
  try {
    const resp = await fetch(`${serverUrl}/settings/voices`, { signal: AbortSignal.timeout(5000) });
    if (resp.ok) voiceCatalog = await resp.json();
  } catch (_) {}
}

function renderVoicePicker(container, currentEngine, currentVoiceId) {
  container.innerHTML = '';
  if (!voiceCatalog) { container.textContent = 'Loading voices...'; return; }
  const engine = voiceCatalog.engines[currentEngine];
  if (!engine || !engine.voices.length) { container.textContent = 'No voices available'; return; }

  engine.voices.forEach(v => {
    const row = document.createElement('label');
    row.className = 'voice-option' + (v.id === currentVoiceId ? ' selected' : '');
    row.innerHTML = `<input type="radio" name="voice_id" value="${v.id}" ${v.id === currentVoiceId ? 'checked' : ''}>
      <span class="voice-name">${v.name}</span>
      <span class="voice-meta">${v.gender}${v.accent ? ', ' + v.accent : ''}</span>`;
    row.querySelector('input').addEventListener('change', () => settings.setSetting('voice_id', v.id));
    container.appendChild(row);
  });
}

function renderVoiceParams(container, currentEngine, currentParams) {
  container.innerHTML = '';
  if (!voiceCatalog) return;
  const engine = voiceCatalog.engines[currentEngine];
  if (!engine || !engine.params) return;

  for (const [key, spec] of Object.entries(engine.params)) {
    const val = currentParams[key] ?? spec.default;
    const row = document.createElement('div');
    row.className = 'setting-row';

    if (spec.type === 'slider') {
      row.innerHTML = `<label>${spec.label}</label>
        <input type="range" min="${spec.min}" max="${spec.max}" step="${spec.step}" value="${val}">
        <span class="val">${val}</span>`;
      const slider = row.querySelector('input');
      slider.addEventListener('input', () => {
        row.querySelector('.val').textContent = slider.value;
        const params = JSON.parse(settings.settings.voice_params || '{}');
        params[key] = parseFloat(slider.value);
        settings.setSetting('voice_params', JSON.stringify(params));
      });
    } else if (spec.type === 'choice') {
      const opts = spec.options.map(o => `<option value="${o}" ${o === val ? 'selected' : ''}>${o}</option>`).join('');
      row.innerHTML = `<label>${spec.label}</label><select>${opts}</select>`;
      row.querySelector('select').addEventListener('change', e => {
        const params = JSON.parse(settings.settings.voice_params || '{}');
        params[key] = e.target.value;
        settings.setSetting('voice_params', JSON.stringify(params));
      });
    } else if (spec.type === 'range') {
      // Edge TTS uses string ranges like "-50%" to "+50%"
      row.innerHTML = `<label>${spec.label}</label>
        <input type="text" value="${val}" placeholder="${spec.default}" class="range-input">`;
      row.querySelector('input').addEventListener('change', e => {
        const params = JSON.parse(settings.settings.voice_params || '{}');
        params[key] = e.target.value;
        settings.setSetting('voice_params', JSON.stringify(params));
      });
    }
    container.appendChild(row);
  }
}

// Action handlers
async function testVoiceOnDevice() {
  const engine = settings.settings.tts_engine || 'auto';
  const voice_id = settings.settings.voice_id || '';
  const params = JSON.parse(settings.settings.voice_params || '{}');
  try {
    await fetch(`${serverUrl}/settings/device/test-voice`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: 'Hello! This is how I sound.', engine, voice_id, params }),
    });
  } catch (_) {}
}

async function testTypewriterOnDevice() {
  const config = {
    base_speed_ms: parseFloat(settings.settings.tw_base_speed_ms ?? 45),
    punctuation_multiplier: parseFloat(settings.settings.tw_punctuation ?? 1.0),
    jitter_amount: parseFloat(settings.settings.tw_jitter ?? 0.15),
    common_speedup: parseFloat(settings.settings.tw_common_speed ?? 0.8),
    rare_slowdown: parseFloat(settings.settings.tw_rare_speed ?? 1.3),
  };
  // Also persist the typewriter_config
  settings.setSetting('typewriter_config', JSON.stringify(config));
  try {
    await fetch(`${serverUrl}/settings/device/test-typewriter`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: 'The quick brown fox jumps over the lazy dog.', config }),
    });
  } catch (_) {}
}
```

**Step 3: Add HTML markup for voice picker and params containers**

In the voice settings pane of `settings.html`, add containers that the JS will populate:

```html
<div id="voice-picker-container" class="voice-picker"></div>
<div id="voice-params-container" class="voice-params"></div>
```

And CSS for voice picker styling:

```css
.voice-option { display: flex; align-items: center; padding: 8px 12px; border: 1px solid #333; margin: 4px 0; border-radius: 6px; cursor: pointer; }
.voice-option.selected { border-color: #fff; background: #222; }
.voice-name { font-weight: bold; margin-left: 8px; }
.voice-meta { color: #888; margin-left: auto; font-size: 12px; }
.range-input { width: 80px; background: #222; border: 1px solid #444; color: #fff; padding: 4px 8px; border-radius: 4px; }
```

**Step 4: Wire event listeners**

When `tts_engine` changes → call `loadVoiceCatalog()` then `renderVoicePicker()` and `renderVoiceParams()`.

When any `tw_*` slider changes → bundle into `typewriter_config` JSON and `setSetting()`.

When action buttons are clicked → call `testVoiceOnDevice()` or `testTypewriterOnDevice()`.

**Step 5: Commit**

```bash
git add companion/js/settings.js companion/settings.html
git commit -m "feat: companion app voice picker and typewriter fine-tuning UI"
```

---

### Task 7: Device Typewriter Config Loading from Repository

**Files:**
- Modify: `device/screens/panels/chat_settings.py` (add "custom" to text_speed options)
- Modify: chat rendering code where `TypewriterRenderer` is instantiated

**Step 1: Find where TypewriterRenderer is created in chat rendering**

Search for `TypewriterRenderer(` in chat-related files. Update each instantiation to load config from repository when `text_speed === 'custom'`:

```python
# Load typewriter config
from storage.repository import DeviceRepository
import json
repo = DeviceRepository()
speed = repo.get_setting("text_speed", "normal")
if speed == "custom":
    config_raw = repo.get_setting("typewriter_config", "{}")
    config = TypewriterConfig.from_json(config_raw)
    tw = TypewriterRenderer(text, config=config)
else:
    tw = TypewriterRenderer(text, speed=speed)
```

**Step 2: Update chat_settings.py text_speed options**

In the text_speed setting definition, add `"custom"` to the options list.

**Step 3: Run tests**

Run: `python3 -m pytest tests/ -x -q -k "not test_render_draws_sidebar and not test_double_on_thread" 2>&1 | tail -5`
Expected: All pass

**Step 4: Commit**

```bash
git add device/screens/panels/chat_settings.py [chat files that create TypewriterRenderer]
git commit -m "feat: load typewriter config from repository when text_speed=custom"
```

---

### Task 8: Settings Apply — Re-init TTS on Voice Change

**Files:**
- Modify: `device/client/api.py:287-305` (_apply_setting_change)

**Step 1: Add TTS re-initialization on voice setting changes**

In `_apply_setting_change()`, after the volume handler, add:

```python
            # Re-init TTS when voice settings change
            if key in ("tts_engine", "voice_id", "voice_params"):
                # The next speak() call will pick up new settings via TextToSpeech()
                logging.info("voice_setting_changed: %s — TTS will reload on next speak", key)
```

The TTS class already reads settings from repository in `__init__()`, so creating a new TextToSpeech instance (which happens per-speak in the current chat flow) will pick up changes automatically.

**Step 2: Commit**

```bash
git add device/client/api.py
git commit -m "feat: log voice setting changes for TTS reload"
```

---

### Task 9: Integration Test — End-to-End Voice Setting Sync

**Files:**
- Create: `tests/test_voice_settings_sync.py`

**Step 1: Write integration test**

```python
"""Test that voice settings flow through the system correctly."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))

from storage.repository import DeviceRepository
from voice_catalog import build_catalog


class VoiceSettingsSyncTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = DeviceRepository(db_path=str(Path(self.tmp.name) / "bitos.db"))
        self.repo.initialize()

    def tearDown(self):
        self.tmp.cleanup()

    def test_voice_id_persists(self):
        self.repo.set_setting("voice_id", "en-US-GuyNeural")
        self.assertEqual(self.repo.get_setting("voice_id"), "en-US-GuyNeural")

    def test_voice_params_persists_json(self):
        params = {"rate": "+10%", "pitch": "-5Hz"}
        self.repo.set_setting("voice_params", json.dumps(params))
        stored = json.loads(self.repo.get_setting("voice_params"))
        self.assertEqual(stored["rate"], "+10%")

    def test_typewriter_config_persists(self):
        config = {"base_speed_ms": 60, "jitter_amount": 0.05}
        self.repo.set_setting("typewriter_config", json.dumps(config))
        stored = json.loads(self.repo.get_setting("typewriter_config"))
        self.assertEqual(stored["base_speed_ms"], 60)

    def test_catalog_reflects_current_settings(self):
        catalog = build_catalog(
            current_engine="edge_tts",
            current_voice_id="en-US-GuyNeural",
            current_params={"rate": "+10%"},
        )
        self.assertEqual(catalog["current"]["engine"], "edge_tts")
        self.assertEqual(catalog["current"]["voice_id"], "en-US-GuyNeural")
        self.assertEqual(catalog["current"]["params"]["rate"], "+10%")

    def test_setting_validators_accept_voice_id(self):
        from agent_tools import validate_setting
        ok, err, val = validate_setting("voice_id", "en-US-AriaNeural")
        self.assertTrue(ok)
        self.assertEqual(val, "en-US-AriaNeural")

    def test_setting_validators_accept_voice_params_json(self):
        from agent_tools import validate_setting
        ok, err, val = validate_setting("voice_params", '{"rate": "+10%"}')
        self.assertTrue(ok)

    def test_setting_validators_accept_typewriter_config(self):
        from agent_tools import validate_setting
        config = json.dumps({"base_speed_ms": 50})
        ok, err, val = validate_setting("typewriter_config", config)
        self.assertTrue(ok)

    def test_setting_validators_reject_bad_json(self):
        from agent_tools import validate_setting
        ok, err, val = validate_setting("voice_params", "not json")
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run test**

Run: `python3 -m pytest tests/test_voice_settings_sync.py -v`
Expected: PASS (all 8 tests)

**Step 3: Commit**

```bash
git add tests/test_voice_settings_sync.py
git commit -m "test: add voice and typewriter settings integration tests"
```

---

### Task 10: Final — Push and Verify

**Step 1: Run full test suite**

Run: `python3 -m pytest tests/ -x -q -k "not test_render_draws_sidebar and not test_double_on_thread" 2>&1 | tail -10`
Expected: All pass

**Step 2: Syntax check all new/modified files**

```bash
python3 -c "
import py_compile
for f in [
    'server/voice_catalog.py',
    'device/display/typewriter.py',
    'device/audio/tts.py',
    'device/audio/edge_tts_provider.py',
    'device/audio/speechify.py',
    'device/overlays/test_typewriter.py',
]:
    py_compile.compile(f, doraise=True)
print('All OK')
"
```

**Step 3: Push**

```bash
git push origin main
```

User can then `git pull` on the Pi and companion app is served from the same repo.
