# BITOS · OFFLINE AI IMPLEMENTATION PLAN

Priority order (lowest to highest effort):
1. Piper TTS — local text-to-speech (S)
2. whisper.cpp STT — local speech-to-text (S)
3. Response cache — replay previous answers (S)
4. llama.cpp LLM — local inference (L, Pi Zero 2W marginal)

## 1. Piper TTS
Library: piper-tts (MIT license, no API cost)
Model: en_US-lessac-medium (63MB)
Performance on Pi Zero 2W: ~2-4x realtime (2s audio takes 0.5-1s to gen)
RAM: ~80MB while running
Install: pip install piper-tts + download model to ~/bitos/models/tts/

TTSBridge protocol:
  class TTSBridge(ABC):
      def speak(self, text: str) -> None: ...

Implementations: ElevenLabsTTS, OpenAITTS, PiperTTS
AutoFallbackTTS: try primary, fall back to PiperTTS on any exception.
Selected by TTS_PROVIDER env var: elevenlabs | openai | piper | auto
Default: auto (cloud first, piper fallback).

## 2. whisper.cpp STT
Repo: github.com/ggerganov/whisper.cpp
Model: tiny.en (75MB) — fastest; base.en (148MB) — better accuracy
Performance on tiny.en: ~3-5x realtime on Pi Zero 2W
RAM: ~200MB for base.en (watch budget)
Install: build from source + download model via models/download-ggml-model.sh

AutoFallbackSTT: WhisperAPISTT primary, WhisperCppSTT fallback.
Selected by STT_PROVIDER env var: api | local | auto

## 3. Response Cache
FTS5-based cache (no embeddings needed for v1).
Store after every successful Claude response.
On offline: fuzzy-match incoming query, return cached if similar.
UI treatment: "[CACHED · 2D AGO]" prefix shown clearly.
Never show cached responses without explicit labeling.

## 4. llama.cpp (Experimental)
Pi Zero 2W performance:
  TinyLlama 1.1B Q4_K_M (669MB): ~1-3 tok/s — marginal
  Llama 3.2 1B Q4_K_M (770MB): ~1-2 tok/s — marginal
  Phi-3 Mini 3.8B: OOM on Pi Zero 2W
Pi 5 (8GB): Llama 3.2 3B at ~20 tok/s — genuinely useful
Status: blocked until Pi 5 hardware available (P7-004)

UI: status bar shows "⚡ LOCAL AI" when using local model.
Clear labeling that this is slower and less capable.

## Offline Mode Feature Matrix
| Feature | Online | AI Offline | Fully Offline |
|---|---|---|---|
| Claude chat | Full | Cached only | Local LLM or none |
| STT | API | API | whisper.cpp |
| TTS | API | API | Piper |
| Tasks (read) | Live | Cached | Cached |
| Tasks (add) | Live | Queue | Queue (sync later) |
| Pomodoro | Works | Works | Works |
| World Clocks | Works | Works | Works |

## Implementation Sequence
Sprint 1: PiperTTS + AutoFallbackTTS
Sprint 2: whisper.cpp STT + AutoFallbackSTT
Sprint 3: Offline UI states + status bar indicators
Sprint 4: Response cache
Sprint 5: llama.cpp (Pi 5 only, experimental)
