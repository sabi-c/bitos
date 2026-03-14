# BITOS · OFFLINE AI IMPLEMENTATION PLAN
## docs/planning/OFFLINE_AI.md
## v1.0 · March 2026

---

## OVERVIEW

When no network is available, BITOS should degrade gracefully —
not go completely dark. This document covers the full offline
capability stack from simplest (local TTS) to most complex
(local LLM inference).

**Implementation priority (lowest to highest effort):**
1. Piper TTS — local text-to-speech (S, do this first)
2. Whisper.cpp STT — local speech-to-text (S, already partly solved)
3. Cached responses — replay previous answers (S, data already in DB)
4. Llama.cpp LLM — local inference (L, Pi Zero 2W is marginal)

---

## 1. LOCAL TTS — PIPER

### What it does
Converts Claude's text responses to speech without ElevenLabs or
OpenAI TTS API. MIT license, no cost, runs on Pi Zero 2W.

### Performance on Pi Zero 2W
- Model: `en_US-lessac-medium` (63MB)
- Speed: ~2-4x realtime (2 seconds of speech takes 0.5-1s to generate)
- Quality: clearly intelligible, robotic but acceptable
- RAM: ~80MB while running

### Installation

```bash
pip install piper-tts

# Download voice model (one-time, ~63MB)
mkdir -p /home/pi/bitos/models/tts
cd /home/pi/bitos/models/tts
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json
```

### Integration into TTS Bridge

```python
# device/audio/tts_bridge.py

from abc import ABC, abstractmethod
import subprocess, os

class TTSBridge(ABC):
    @abstractmethod
    def speak(self, text: str) -> None: ...

class ElevenLabsTTS(TTSBridge):
    def speak(self, text: str) -> None:
        # existing ElevenLabs implementation
        ...

class OpenAITTS(TTSBridge):
    def speak(self, text: str) -> None:
        # existing OpenAI TTS implementation
        ...

class PiperTTS(TTSBridge):
    MODEL_PATH = "/home/pi/bitos/models/tts/en_US-lessac-medium.onnx"
    
    def speak(self, text: str) -> None:
        out = "/tmp/bitos_tts.wav"
        result = subprocess.run(
            ["piper", "--model", self.MODEL_PATH,
             "--output_file", out],
            input=text.encode(),
            capture_output=True,
            timeout=10
        )
        if result.returncode == 0:
            subprocess.run(["aplay", "-D", "hw:0", out],
                          capture_output=True)
        else:
            # Piper failed — log and continue silently
            logger.warning("piper_tts_failed",
                          extra={"stderr": result.stderr.decode()})

def get_tts_bridge() -> TTSBridge:
    provider = os.environ.get("TTS_PROVIDER", "openai")
    if provider == "elevenlabs":
        return ElevenLabsTTS()
    elif provider == "piper":
        return PiperTTS()
    else:
        return OpenAITTS()

# Automatic offline fallback:
class AutoFallbackTTS(TTSBridge):
    """Try primary provider, fall back to piper on failure."""
    def __init__(self):
        self._primary = get_tts_bridge()
        self._fallback = PiperTTS()
    
    def speak(self, text: str) -> None:
        try:
            self._primary.speak(text)
        except Exception as e:
            logger.warning("tts_primary_failed_using_piper",
                          extra={"error": str(e)})
            self._fallback.speak(text)
```

Add to `.env.template`:
```bash
TTS_PROVIDER=openai      # openai | elevenlabs | piper | auto
```

Use `auto` in production — tries cloud first, falls back to piper.

---

## 2. LOCAL STT — WHISPER.CPP

### What it does
Transcribes voice input without the Whisper API. The whisplay-ai-chatbot
repo already ports the Python Whisper library — whisper.cpp is the
faster C++ alternative.

### Performance on Pi Zero 2W
- Model: `tiny.en` (75MB) — fastest, English only
- Model: `base.en` (148MB) — better accuracy, still usable
- Speed on `tiny.en`: ~3-5x realtime (10s audio takes 2-3s to transcribe)
- RAM: ~200MB for base.en (watch memory budget)

### Installation

```bash
# Build whisper.cpp (one-time)
git clone https://github.com/ggerganov/whisper.cpp
cd whisper.cpp
make

# Download model
bash ./models/download-ggml-model.sh tiny.en
# or
bash ./models/download-ggml-model.sh base.en
```

### Integration

```python
# device/audio/stt_bridge.py

class WhisperAPISTT(STTBridge):
    def transcribe(self, audio_path: str) -> str:
        with open(audio_path, "rb") as f:
            return openai_client.audio.transcriptions.create(
                model="whisper-1", file=f
            ).text

class WhisperCppSTT(STTBridge):
    BINARY = "/home/pi/whisper.cpp/main"
    MODEL = "/home/pi/whisper.cpp/models/ggml-base.en.bin"
    
    def transcribe(self, audio_path: str) -> str:
        result = subprocess.run(
            [self.BINARY, "-m", self.MODEL, "-f", audio_path,
             "--output-txt", "--no-prints"],
            capture_output=True, text=True, timeout=30
        )
        # whisper.cpp writes {audio_path}.txt
        txt_path = audio_path + ".txt"
        if os.path.exists(txt_path):
            text = open(txt_path).read().strip()
            os.remove(txt_path)
            return text
        return ""

class AutoFallbackSTT(STTBridge):
    def __init__(self):
        self._primary = WhisperAPISTT()
        self._fallback = WhisperCppSTT()
    
    def transcribe(self, audio_path: str) -> str:
        try:
            return self._primary.transcribe(audio_path)
        except Exception:
            logger.warning("stt_api_failed_using_local")
            return self._fallback.transcribe(audio_path)
```

---

## 3. CACHED RESPONSE REPLAY

### What it does
When AI is offline, Claude can still "respond" by replaying
semantically similar previous responses. Useful for:
- Common questions ("what are my tasks?") — answer was cached from last online session
- Frequently asked things ("how's the weather?") — show last known value

### Implementation

```python
# server/cache/response_cache.py

class ResponseCache:
    """
    Lightweight semantic cache using FTS5.
    Stores (query_text, response_text, embedding_hash).
    On offline: fuzzy-match incoming query against stored queries.
    """
    
    def store(self, query: str, response: str) -> None:
        """Store after every successful Claude response."""
        ...
    
    def find_similar(self, query: str, threshold: float = 0.7) -> str | None:
        """
        Returns cached response if similar query exists.
        Uses FTS5 for fast text matching (no embeddings needed for v1).
        Adds [CACHED · {days_ago}] prefix to response.
        """
        ...
```

### UI treatment for cached responses

When returning a cached response, show clearly:
```
┌─────────────────────────────────┐
│ AI  CACHED RESPONSE · 2D AGO    │ ← dim indicator
│                                 │
│ [response text]                 │
│                                 │
│ AI OFFLINE — SHOWING CACHED     │
│ LONG PRESS TO RETRY WHEN ONLINE │
└─────────────────────────────────┘
```

Never show cached responses without clear labeling.
User must know this is not a live response.

---

## 4. LOCAL LLM VIA LLAMA.CPP (EXPERIMENTAL)

### Feasibility on Pi Zero 2W

The Pi Zero 2W can run small quantized models, but slowly:

| Model | Size (Q4_K_M) | Tokens/sec (Pi Zero 2W) | Usable? |
|---|---|---|---|
| TinyLlama 1.1B | 669MB | ~1-3 tok/s | Barely — 30s for short response |
| Llama 3.2 1B | 770MB | ~1-2 tok/s | Marginal |
| Phi-3 Mini 3.8B | 2.3GB | Fails (OOM) | No |

At 1-3 tokens/second, a 100-token response takes 30-100 seconds.
That's long but not unusable for simple queries.

**Honest assessment:** Local LLM on Pi Zero 2W is a party trick
in v1. It's worth having as a fallback for the "phone is dead,
WiFi is down, but I really need to ask something" scenario.

If you get a **Pi 5 (8GB)** later, this becomes much more viable:
Llama 3.2 3B runs at ~20 tok/s on Pi 5 — genuinely useful.

### Installation on Pi Zero 2W

```bash
git clone https://github.com/ggerganov/llama.cpp
cd llama.cpp

# Compile with ARM optimizations
make LLAMA_OPENBLAS=1  # if you install OpenBLAS

# Download smallest usable model
python3 -c "
from huggingface_hub import hf_hub_download
hf_hub_download(
    repo_id='bartowski/Llama-3.2-1B-Instruct-GGUF',
    filename='Llama-3.2-1B-Instruct-Q4_K_M.gguf',
    local_dir='/home/pi/bitos/models/llm'
)
"
```

### Integration

```python
# server/agents/local_llm.py

class LocalLLM:
    BINARY = "/home/pi/llama.cpp/llama-cli"
    MODEL = "/home/pi/bitos/models/llm/Llama-3.2-1B-Instruct-Q4_K_M.gguf"
    
    def generate(self, prompt: str, max_tokens: int = 128) -> Generator[str, None, None]:
        """Stream tokens from local model. Very slow on Pi Zero 2W."""
        proc = subprocess.Popen(
            [self.BINARY, "-m", self.MODEL,
             "-p", prompt,
             "-n", str(max_tokens),
             "--temp", "0.7",
             "-c", "2048",   # context window
             "--threads", "4"],  # all cores
            stdout=subprocess.PIPE,
            text=True
        )
        for line in proc.stdout:
            yield line
```

### UI treatment for local LLM

When using local model, show clearly at all times:
```
STATUS BAR: LOCAL AI · SLOW MODE
```

And in chat header:
```
LLAMA 3.2 1B · LOCAL · ~2 TOK/S
```

Set user expectations — this will be noticeably slower.

---

## 5. OFFLINE MODE UI STATES

### Status bar indicators

```
▣ ONLINE         ← WiFi connected, backend reachable
◈ BT TETHER      ← Internet via phone Bluetooth PAN  
📱 HOTSPOT       ← Internet via phone WiFi hotspot
⊘ AI OFFLINE     ← Internet works but backend down
▣ CACHED         ← Showing cached AI responses
⚡ LOCAL AI      ← Running llama.cpp locally
✕ FULLY OFFLINE  ← No internet, no AI
```

### Feature availability matrix

| Feature | Online | AI Offline | Fully Offline |
|---|---|---|---|
| Claude chat | ✓ Full | Cached only | Local LLM or none |
| Voice input (STT) | ✓ API | ✓ API | ✓ Local (whisper.cpp) |
| Voice output (TTS) | ✓ API | ✓ API | ✓ Piper |
| Tasks (read) | ✓ | ✓ Cached | ✓ Cached |
| Tasks (add) | ✓ | Queue | ✓ Queue (sync later) |
| Mail (read) | ✓ | ✓ Cached | ✓ Cached |
| Mail (send) | ✓ | Queue | Queue (sync later) |
| Pomodoro | ✓ | ✓ | ✓ No network needed |
| World Clocks | ✓ | ✓ | ✓ No network needed |
| Weather | ✓ | ✓ Stale label | ✓ Stale label |
| Settings | ✓ | ✓ | ✓ All local |
| Quick Capture | ✓ | ✓ AI classify | Local classify |

### Offline queue (already in codebase as outbound queue)

Tasks added offline go into the outbound queue.
Queue drains automatically when connectivity returns.
Status visible in Settings → Queue (P3-005 already built this).

---

## 6. IMPLEMENTATION SEQUENCE

```
Sprint 1: Piper TTS + AutoFallbackTTS  (S — do this soon)
Sprint 2: WhisperCpp STT + AutoFallbackSTT  (S — pairs with sprint 1)
Sprint 3: Offline UI states + status bar indicators  (S)
Sprint 4: Response cache (store + retrieve + label)  (M)
Sprint 5: Local LLM (experimental, Pi Zero 2W)  (L — optional)
```

Sprints 1-3 should happen in v1.5.
Sprint 4 in v2.
Sprint 5 is optional and should only be tackled if Pi 5 hardware
becomes available or if offline use is a strong real-world requirement.

---

## GITHUB REPOS REFERENCED

- `whisper.cpp` — github.com/ggerganov/whisper.cpp
- `llama.cpp` — github.com/ggerganov/llama.cpp
- `piper` — github.com/rhasspy/piper
- `openWakeWord` — github.com/dscripka/openWakeWord
- `whisplay-ai-chatbot` — github.com/PiSugar/whisplay-ai-chatbot
  (reference implementation for audio pipeline on this exact hardware)
