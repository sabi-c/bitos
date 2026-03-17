# Voice & Typewriter Fine-Tuning Foundation

**Goal:** Give users full control over agent voice selection and text typing feel from the companion app, with live test-on-device capability.

**Architecture:** Multi-provider voice catalog + per-provider parameter exposure + typewriter config sliders + test infrastructure, all synced via existing HTTP settings pipeline.

**Scope:** Foundation layer only. Live conversation mode, TTS-typewriter sync, and interruption handling are next sprint.

---

## 1. Voice Catalog API

### Server endpoint: `GET /settings/voices`

Queries each TTS provider for available voices and their tunable parameters. Returns a structured catalog the companion app renders as a picker.

```json
{
  "engines": {
    "edge_tts": {
      "available": true,
      "requires_key": false,
      "voices": [
        {"id": "en-US-AriaNeural", "name": "Aria", "gender": "female", "accent": "US"},
        {"id": "en-US-GuyNeural", "name": "Guy", "gender": "male", "accent": "US"},
        {"id": "en-US-JennyNeural", "name": "Jenny", "gender": "female", "accent": "US"},
        {"id": "en-GB-SoniaNeural", "name": "Sonia", "gender": "female", "accent": "British"},
        {"id": "en-AU-NatashaNeural", "name": "Natasha", "gender": "female", "accent": "Australian"}
      ],
      "params": {
        "rate": {"type": "range", "label": "Speed", "min": "-50%", "max": "+50%", "default": "+0%"},
        "pitch": {"type": "range", "label": "Pitch", "min": "-50Hz", "max": "+50Hz", "default": "+0Hz"},
        "volume": {"type": "range", "label": "Volume", "min": "-50%", "max": "+50%", "default": "+0%"}
      }
    },
    "cartesia": {
      "available": true,
      "requires_key": true,
      "voices": [
        {"id": "79a125e8-cd45-4c13-8a67-188112f4dd22", "name": "Friendly", "gender": "neutral"}
      ],
      "params": {
        "speed": {"type": "choice", "label": "Speed", "options": ["slowest", "slow", "normal", "fast", "fastest"], "default": "normal"}
      }
    },
    "speechify": {
      "available": true,
      "requires_key": true,
      "voices": [
        {"id": "sophia", "name": "Sophia", "gender": "female"},
        {"id": "henry", "name": "Henry", "gender": "male"},
        {"id": "george", "name": "George", "gender": "male"}
      ],
      "params": {
        "model": {"type": "choice", "label": "Model", "options": ["simba-english", "simba-turbo"], "default": "simba-english"}
      }
    },
    "openai": {
      "available": false,
      "requires_key": true,
      "voices": [
        {"id": "alloy", "name": "Alloy", "gender": "neutral"},
        {"id": "echo", "name": "Echo", "gender": "male"},
        {"id": "fable", "name": "Fable", "gender": "neutral"},
        {"id": "onyx", "name": "Onyx", "gender": "male"},
        {"id": "nova", "name": "Nova", "gender": "female"},
        {"id": "shimmer", "name": "Shimmer", "gender": "female"}
      ],
      "params": {
        "model": {"type": "choice", "label": "Model", "options": ["tts-1", "tts-1-hd"], "default": "tts-1"},
        "speed": {"type": "slider", "label": "Speed", "min": 0.25, "max": 4.0, "step": 0.25, "default": 1.0}
      }
    },
    "espeak": {
      "available": true,
      "requires_key": false,
      "voices": [
        {"id": "en-us", "name": "English US", "gender": "neutral"}
      ],
      "params": {
        "speed": {"type": "slider", "label": "Speed (wpm)", "min": 80, "max": 350, "step": 10, "default": 150},
        "pitch": {"type": "slider", "label": "Pitch", "min": 0, "max": 99, "step": 1, "default": 50}
      }
    }
  },
  "current": {
    "engine": "edge_tts",
    "voice_id": "en-US-AriaNeural",
    "params": {}
  }
}
```

### Implementation

- Server-side: `server/voice_catalog.py` — builds the catalog from env checks and hardcoded voice lists
- Edge TTS voices are well-known (hardcoded list). Cartesia/Speechify voices could be fetched from API but hardcoded is fine for now.
- `current` reads from device settings cache (`tts_engine`, `voice_id`, `voice_params`)

---

## 2. Voice Settings Storage

### New device settings keys

| Key | Type | Example | Description |
|-----|------|---------|-------------|
| `tts_engine` | string | `"edge_tts"` | Already exists |
| `voice_id` | string | `"en-US-GuyNeural"` | Voice within engine |
| `voice_params` | JSON string | `{"rate": "+10%"}` | Engine-specific params |

### Device-side changes

**`audio/tts.py`** — `TextToSpeech` reads `voice_id` and `voice_params` from repository instead of env vars. Each `_run_*` method passes these through:

```python
# In speak():
voice_id = repo.get_setting("voice_id", None)  # falls back to provider default
voice_params = json.loads(repo.get_setting("voice_params", "{}"))
```

**Provider updates:**
- `edge_tts_provider.py` — `synthesize()` already accepts `voice` param. Add `rate`/`pitch` support via `edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)`
- `cartesia_provider.py` — already accepts `voice` param. Add `speed` to API call if supported.
- `speechify.py` — already accepts `voice_id` param. Pass `model` from params.
- `tts.py._run_openai_tts()` — pass `voice` and `speed` params to OpenAI client.
- `tts.py._run_espeak()` — pass `-s` (speed) and `-p` (pitch) flags.

### Server-side validation

Add to `SETTING_VALIDATORS` in `agent_tools.py`:
```python
"voice_id": {"type": "str"},
"voice_params": {"type": "json"},
```

---

## 3. Typewriter Fine-Tuning

### Parameters (companion app sliders)

| Parameter | Key in config | Range | Default | What it controls |
|-----------|--------------|-------|---------|-----------------|
| Base Speed | `base_speed_ms` | 10–120 ms | 45 | Milliseconds per character |
| Punctuation Pause | `punctuation_multiplier` | 0.5–3.0x | 1.0 | Scale factor on `.!?,;:\n` pauses |
| Jitter | `jitter_amount` | 0–0.30 | 0.15 | +/- randomness (0=robotic) |
| Common Letter Speed | `common_speedup` | 0.5–1.0x | 0.8 | Multiplier for "etaoinsrhld" |
| Rare Letter Speed | `rare_slowdown` | 1.0–2.0x | 1.3 | Multiplier for "zxqj" |

### Storage

Single JSON setting: `typewriter_config`
```json
{"base_speed_ms": 45, "punctuation_multiplier": 1.0, "jitter_amount": 0.15, "common_speedup": 0.8, "rare_slowdown": 1.3}
```

### TypewriterRenderer changes

`display/typewriter.py`:
- Add `TypewriterConfig` dataclass with the 5 params above
- `SPEED_PRESETS` map to preset configs (e.g., "slow" = `TypewriterConfig(base_speed_ms=80, ...)`)
- Constructor accepts either `speed: str` (preset) or `config: TypewriterConfig` (custom)
- `_char_delay_ms()` reads from config instead of module-level constants
- On device boot, load `typewriter_config` from repository; if absent, use "normal" preset

### Server validation

```python
"typewriter_config": {"type": "json"},
```

---

## 4. Companion App — Voice & Text Tab

### Updated SETTING_GROUPS in `settings.js`

Replace current voice group and add new sections:

```javascript
{
  id: 'voice',
  label: 'VOICE',
  settings: [
    { key: 'voice_enabled', label: 'Voice output', type: 'toggle', default: false },
    { key: 'voice_mode', label: 'Voice mode', type: 'picker', options: ['off', 'on', 'auto'], default: 'auto' },
    { key: 'volume', label: 'Volume', type: 'slider', min: 0, max: 100, step: 5, default: 70 },
    { key: 'tts_engine', label: 'TTS engine', type: 'picker', options: ['auto', 'edge_tts', 'cartesia', 'speechify', 'openai', 'espeak'], default: 'auto' },
    // Dynamic: voice picker loads from /settings/voices based on selected engine
    { key: 'voice_id', label: 'Voice', type: 'voice_picker', default: '' },
    // Dynamic: engine-specific params rendered from catalog
    { key: 'voice_params', label: 'Voice settings', type: 'voice_params', default: {} },
    { key: '_test_voice', label: 'Preview voice', type: 'action', action: 'test_voice' },
  ],
},
{
  id: 'text',
  label: 'TEXT',
  settings: [
    { key: 'text_speed', label: 'Speed preset', type: 'picker', options: ['slow', 'normal', 'fast', 'custom'], default: 'normal' },
    // Custom sliders shown when text_speed === 'custom'
    { key: 'tw_base_speed_ms', label: 'Base speed (ms/char)', type: 'slider', min: 10, max: 120, step: 5, default: 45, showWhen: { text_speed: 'custom' } },
    { key: 'tw_punctuation', label: 'Punctuation pause', type: 'slider', min: 0.5, max: 3.0, step: 0.1, default: 1.0, showWhen: { text_speed: 'custom' } },
    { key: 'tw_jitter', label: 'Jitter', type: 'slider', min: 0, max: 0.30, step: 0.01, default: 0.15, showWhen: { text_speed: 'custom' } },
    { key: 'tw_common_speed', label: 'Common letter speed', type: 'slider', min: 0.5, max: 1.0, step: 0.05, default: 0.8, showWhen: { text_speed: 'custom' } },
    { key: 'tw_rare_speed', label: 'Rare letter speed', type: 'slider', min: 1.0, max: 2.0, step: 0.05, default: 1.3, showWhen: { text_speed: 'custom' } },
    { key: '_test_typewriter', label: 'Test on device', type: 'action', action: 'test_typewriter' },
  ],
},
```

### Voice picker UI flow

1. User selects TTS engine → companion fetches `GET /settings/voices`
2. Voices for that engine populate a radio list
3. Engine-specific params render as sliders/pickers below the voice list
4. "Preview voice" sends test command to device
5. Typewriter "custom" mode reveals fine-tuning sliders
6. "Test on device" sends typewriter test command

### New companion app component types

- `voice_picker` — radio list populated from voice catalog API
- `voice_params` — dynamic sliders/pickers rendered from catalog `params` field
- `action` — button that triggers a test endpoint
- `showWhen` — conditional visibility for slider groups

---

## 5. Test-on-Device Infrastructure

### Server endpoints

**`POST /settings/device/test-voice`**
```json
{"text": "Hello! This is how I sound.", "engine": "edge_tts", "voice_id": "en-US-GuyNeural", "params": {"rate": "+10%"}}
```
Queues a `_test_voice` pending change → device picks it up → plays TTS with specified config.

**`POST /settings/device/test-typewriter`**
```json
{"text": "The quick brown fox jumps over the lazy dog.", "config": {"base_speed_ms": 50, "punctuation_multiplier": 1.2, "jitter_amount": 0.1, "common_speedup": 0.8, "rare_slowdown": 1.3}}
```
Queues a `_test_typewriter` pending change → device renders a test overlay.

### Device-side test handlers

In `client/api.py._apply_setting_change()`:
- `_test_voice` → calls `TextToSpeech.speak()` with provided engine/voice/params
- `_test_typewriter` → pushes a `TestTypewriterOverlay` that renders sample text with given config, auto-dismisses after completion + 2s

### TestTypewriterOverlay

Simple overlay (like PowerOverlay pattern):
- Black background, sample text typed out with provided config
- Shows current config values as small labels at bottom
- Auto-dismisses when typewriter finishes + 2s pause
- LONG_PRESS to dismiss early

---

## 6. Settings Sync

### HTTP (primary path)

Uses existing infrastructure:
1. Companion app → `PUT /settings/device` with `{key: "voice_id", value: "en-US-GuyNeural"}`
2. Server validates and queues in pending
3. Device polls `GET /settings/device/pending` every 5s
4. Device applies: stores in repository, re-initializes TTS if engine/voice changed

### BLE (future, not this sprint)

Would add a `SETTINGS_SYNC` characteristic to BITOS BLE service for direct companion→device settings when no WiFi. Deferred — HTTP path covers all current use cases.

---

## 7. Files to Create/Modify

### New files
- `server/voice_catalog.py` — voice catalog builder
- `device/overlays/test_typewriter.py` — test overlay for typewriter fine-tuning

### Modified files
- `server/main.py` — add `/settings/voices`, `/settings/device/test-voice`, `/settings/device/test-typewriter` endpoints
- `server/agent_tools.py` — add `voice_id`, `voice_params`, `typewriter_config` validators
- `device/audio/tts.py` — read `voice_id`/`voice_params` from repository, pass to providers
- `device/audio/edge_tts_provider.py` — accept `rate`/`pitch` params
- `device/audio/cartesia_provider.py` — accept `speed` param
- `device/audio/speechify.py` — accept `model` param
- `device/display/typewriter.py` — add `TypewriterConfig`, accept config dict
- `device/client/api.py` — handle `_test_voice` and `_test_typewriter` pending changes
- `companion/js/settings.js` — add voice picker, voice params, typewriter sliders, test buttons
- `companion/settings.html` — add voice picker UI components, typewriter slider section
