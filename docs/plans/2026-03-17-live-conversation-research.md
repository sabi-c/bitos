# Live Conversation Mode — Research & Planning

**Date:** 2026-03-17
**Sprint focus:** Always-listening, real-time dialogue with intelligent end-of-speech detection, interruption handling, and synchronized audio-visual output.
**Hardware target:** Pi Zero 2W (512MB RAM, ARM Cortex-A53) + 240x280 OLED + WM8960 mic/speaker + Mac mini server (Apple Silicon)

---

## Table of Contents

1. [End-of-Speech Detection](#1-end-of-speech-detection)
2. [Interruption Handling](#2-interruption-handling)
3. [Real-Time STT Options](#3-real-time-stt-options)
4. [TTS-Typewriter Synchronization](#4-tts-typewriter-synchronization)
5. [Architecture Sketch](#5-architecture-sketch)
6. [Recommendations & Sprint Plan](#6-recommendations--sprint-plan)
7. [Sources](#7-sources)

---

## 1. End-of-Speech Detection

The core challenge: knowing when a user has finished their thought versus when they are pausing mid-sentence. Get this wrong in either direction and the experience breaks — either the device cuts the user off (too aggressive) or sits in awkward silence (too conservative).

### 1.1 Voice Activity Detection (VAD) Libraries

VAD answers a simpler question first: "Is someone speaking right now?" This is the foundation layer. End-of-speech detection builds on top of it.

#### Silero VAD (Recommended for Mac mini, fallback on Pi)

- **What:** Deep learning VAD, MIT licensed, trained on 6000+ languages
- **Performance:** RTF 0.004 on AMD CPU (processes 1 hour of audio in 15.4 seconds). Sub-millisecond per chunk on a single CPU thread
- **Accuracy:** 87.7% TPR at 5% FPR — misses ~1 in 8 speech frames. Better at detecting speech than WebRTC VAD
- **Sampling rates:** 8kHz and 16kHz (our mic records at 16kHz, perfect match)
- **Pi Zero 2W concern:** Uses ~50% CPU on Pi Zero. This is borderline. Could work if nothing else is running, but risky for always-on. Better to run on Mac mini and stream results back
- **Repo:** [snakers4/silero-vad](https://github.com/snakers4/silero-vad)

#### WebRTC VAD (Best for on-device Pi fallback)

- **What:** Google's classic GMM-based VAD. Traditional signal processing, no neural network
- **Performance:** Extremely lightweight. Negligible CPU on Pi Zero 2W
- **Accuracy:** Lowest of the three options. Better at detecting silence than speech (many false positives on speech). Good enough for a "is there any audio at all?" gate
- **Trade-off:** Fast and cheap but dumb. Good as a first-pass gate before sending audio to a smarter VAD
- **Package:** `py-webrtcvad` (pip install webrtcvad)

#### Picovoice Cobra VAD (Best accuracy, but commercial)

- **What:** Proprietary deep learning VAD optimized for edge devices. Pure C, no runtime dependencies
- **Performance:** RTF 0.05 on Pi Zero — uses only ~5% CPU. This is 10x more efficient than Silero on the same hardware
- **Accuracy:** Highest AUC of all three. Twice the accuracy of WebRTC VAD
- **Catch:** Commercial license required. Free tier exists but has restrictions. Enterprise pricing for ARM Cortex support
- **Verdict:** Best technical option for on-device, but licensing adds friction. Worth evaluating the free tier

#### pyannote VAD (Heavy, server-only)

- **What:** PyTorch-based, primarily for speaker diarization. Has streaming VAD support with rolling audio buffers
- **Performance:** Too heavy for Pi Zero 2W. ~300MB+ RAM. Server-only option
- **Strength:** Can do speaker diarization (who is speaking) alongside VAD, useful if multiple people talk near the device
- **Verdict:** Overkill for our use case. Silero covers our needs at lower cost

### 1.2 Pause-Length Heuristics

Research on human conversation timing reveals important thresholds:

| Pause Duration | Meaning |
|---|---|
| 0-200ms | Normal inter-word gap. Never trigger on this |
| 200-400ms | Natural between-turn gap in fast conversation |
| 400-600ms | Typical turn-taking pause. The "sweet spot" for end-of-turn |
| 600-800ms | Starting to feel long. User likely done, or thinking |
| 800-1200ms | Definitely done speaking, or something is wrong |
| >1200ms | Connection problem / user walked away |

**Key insight from research:** Human conversations average ~200ms between turns. When an AI takes more than 600ms to respond, users start speaking again, causing overlap. The target for our system: detect end-of-speech and begin processing within 400-600ms of silence.

**Adaptive pause thresholds (proposed):**
- After a question (detected by rising intonation / question words): wait 800ms (user is thinking)
- After a statement: wait 500ms
- After "um", "uh", filler words: wait 1000ms (user is still formulating)
- After trailing off (decreasing volume): wait 400ms

### 1.3 Semantic Completeness Detection (The Smart Layer)

This is where BITOS can differentiate from basic voice assistants. Instead of relying only on silence duration, use a lightweight LLM to judge whether an utterance is "complete."

#### LiveKit's End-of-Utterance (EOU) Model

The most impressive open-source approach found in research:

- **Architecture:** 135M parameter transformer based on SmolLM v2 from HuggingFace, fine-tuned specifically for end-of-turn prediction
- **How it works:** Uses a sliding window of the last 4 conversation turns. As the user speaks, words are appended to the context. The model predicts probability that the user is done
- **Performance:** ~25ms inference time, ~400MB RAM for the multilingual model
- **Impact:** Reduced false interruptions by 39% compared to silence-only detection
- **Languages:** English, French, Spanish, German, Italian, Portuguese, Dutch, Chinese, Japanese, Korean, Indonesian, Russian, Turkish, Hindi
- **Package:** `livekit-plugins-turn-detector` (pip)
- **Trade-off for BITOS:** 400MB RAM won't fit on Pi Zero 2W. Must run on Mac mini. But 25ms inference is fast enough for real-time

#### Haiku-Based Completeness Check (Custom approach)

An alternative using our existing Haiku integration:

- **Concept:** After VAD detects 300ms+ silence, send the current transcript to Haiku with a fast prompt: "Is this utterance complete? yes/no"
- **Inputs to the prompt:**
  - Current transcript text
  - Pause duration so far (in ms)
  - Whether the last word is a question word
  - Whether the sentence ends with a conjunction ("and", "but", "so")
  - Conversation context (last 2 turns)
- **Latency:** Haiku 4.5 TTFT is ~200-400ms. Combined with 300ms silence wait = 500-700ms total. Acceptable but tight
- **Cost:** ~$0.001 per check at Haiku pricing. At 10 checks per conversation minute = $0.01/min
- **Advantage:** No new model to host. Uses existing infrastructure
- **Disadvantage:** Network round-trip to Anthropic API. Higher latency than local EOU model

#### Recommended Hybrid Approach

```
Silence detected (VAD) at 300ms
  |
  v
Is last word a conjunction/filler? --> YES --> extend timeout to 1000ms
  |
  NO
  v
Is utterance clearly complete? (ends with ".", "?", or is a single command word)
  |
  YES --> immediately process
  |
  NO
  v
Run EOU model (25ms) on Mac mini
  |
  confidence > 0.8 --> process
  confidence < 0.3 --> keep waiting
  0.3-0.8 --> wait until 600ms total silence, then process
```

### 1.4 What Open-Source Projects Do This Well

| Project | Approach | Notes |
|---|---|---|
| **LiveKit Agents** | EOU transformer (135M params) + Silero VAD | Best-in-class. Open source. 39% fewer false interruptions |
| **Pipecat** | Plugin architecture, swappable VAD + STT | Good framework, uses Silero VAD by default. 500-800ms round-trip |
| **Open Interpreter 01** | Push-to-talk (ESP32) or OpenAI Realtime API | Sidesteps end-of-speech entirely with push-to-talk. Realtime API handles it server-side |
| **Vocalis** | Silero VAD + barge-in detection | Good reference for mid-speech interruption. FastAPI + React |
| **Ultravox** | Native speech LLM (no STT step) | Processes audio directly. 150ms TTFT. Eliminates the STT bottleneck entirely. Future direction |

---

## 2. Interruption Handling

When the user speaks while the device is talking back, the system needs to handle this gracefully. This is called "barge-in."

### 2.1 Detection: Is the User Actually Interrupting?

Not every sound during TTS playback is an interruption. The system needs to distinguish:

- **Echo/feedback:** Device speaker audio picked up by its own mic. This is the #1 source of false barge-ins
- **Background noise:** TV, traffic, other people talking
- **Genuine interruption:** User intentionally speaking over the device
- **Acknowledgment sounds:** "mhm", "yeah", "ok" — not interruptions, just backchannel

**Echo cancellation is critical.** The WM8960 codec on the WhisPlay board does not have hardware AEC (Acoustic Echo Cancellation). Options:
- **SpeexDSP:** Open-source echo cancellation library. Works on Pi Zero 2W. Moderate CPU usage
- **Software approach:** Mute the mic during TTS playback and unmute during pauses between sentences. Simple but prevents true barge-in
- **Subtraction approach:** Know what audio you're playing, subtract it from the mic input. Requires careful timing
- **WebRTC AEC:** Available in the `webrtc-audio-processing` package. More sophisticated than SpeexDSP

### 2.2 Response Strategies

Research shows two viable approaches:

#### Strategy A: Sentence-Level Chunking (Recommended)

- TTS output is pre-chunked into sentences
- When barge-in detected mid-sentence: finish the current sentence (100-300ms), then stop
- Gives the response a natural stopping point
- The user hears a complete thought before the device yields

#### Strategy B: Immediate Stop

- Stop TTS playback within one audio frame (~20ms)
- Apply a quick 50ms fade-out to avoid a jarring audio cut
- More responsive but can feel abrupt
- Use this for strong interruptions (user clearly started a new sentence)

#### Recommended Hybrid

```
Barge-in detected
  |
  v
Is the device mid-word? --> fade out in 50ms (never cut mid-word)
  |
  v
Is the device mid-sentence, <200ms from sentence end? --> finish sentence
  |
  v
Otherwise --> fade out over 100ms, yield turn
```

### 2.3 UX Patterns from Voice Assistants

- **Keep TTS chunks small:** 100-200ms audio chunks. Can stop between any two chunks without mid-word cuts
- **Block mic transcript during playback:** Prevents the system from "hearing itself" and hallucinating (echo hallucination). Re-enable transcript ingestion only when VAD detects speech that doesn't match the current TTS output
- **Visual feedback matters:** When the device yields, the blob animation should shift from "speaking" to "listening" expression immediately. The visual transition should precede the audio stop by ~50ms so it feels intentional
- **Don't discard context:** When interrupted, save the partial response. If the user asks "go on" or "continue," resume from where it stopped
- **Cooldown period:** After a barge-in, wait 200ms before starting to process the user's new input. Prevents processing the tail end of the TTS audio as user speech

### 2.4 Blob Animation During Interruption

The ferrofluid blob should make the interruption feel natural:

1. **Speaking state:** Blob is animated with audio-reactive pulses synced to TTS output
2. **Barge-in detected:** Quick `squish` gesture (50ms) — blob compresses as if startled
3. **Transition:** Blob morphs to listening expression (tilted, attentive) over 200ms
4. **Processing:** After user finishes, blob enters thinking state

This leverages the existing gesture system in `blob/gestures.py` and the expression pipeline.

---

## 3. Real-Time STT Options

Current state: `WhisperTranscriber` calls OpenAI Whisper API after recording is complete (batch mode). For live conversation, we need streaming partial results.

### 3.1 Comparison Matrix

| Engine | Location | Streaming | Latency (10s clip) | Partial Results | RAM | Cost | Notes |
|---|---|---|---|---|---|---|---|
| **Lightning Whisper MLX** | Mac mini | No (batch) | <1s | No | ~1GB | Free | 10x faster than whisper.cpp on Apple Silicon. distil-small.en recommended |
| **Lightning-SimulWhisper** | Mac mini | Yes | Real-time | Yes | ~1-2GB | Free | MLX/CoreML simultaneous transcription. Runs medium/large-v3-turbo in real-time on M2. 15x decoder speedup |
| **Groq Whisper API** | Cloud | Partial | ~0.5s + network | No (final only) | N/A | $0.02/hr | 164-300x real-time speed. 10min clip in 3.7s. No interim results |
| **Vosk (small-en-us)** | Pi Zero 2W | Yes | Real-time | Yes | ~300MB | Free | 40MB model. Streaming with partial results. Reports of input overflow on Pi Zero 2W |
| **OpenAI Whisper API** | Cloud | No | 1-3s + network | No | N/A | $0.006/min | Already integrated in `transcriber.py`. Batch only |
| **Deepgram** | Cloud | Yes | <300ms | Yes | N/A | $0.0043/min | True streaming with interim results. WebSocket API. Best cloud streaming option |
| **AssemblyAI** | Cloud | Yes | <500ms | Yes | N/A | $0.011/min | Real-time streaming. WebSocket. Good accuracy |

### 3.2 Recommended 3-Tier Architecture

**Tier 1 — Mac mini (primary, LAN):**
Lightning-SimulWhisper for true streaming transcription with partial results. Audio streams from Pi via WebSocket (Opus compressed), SimulWhisper returns partial transcripts in real-time. This is the new development — it replaces the batch-mode Lightning Whisper MLX from the previous research.

**Tier 2 — Cloud (Mac mini unavailable):**
Deepgram for streaming with partial results, or Groq Whisper for fastest batch transcription. Deepgram preferred because partial results enable the end-of-speech pipeline to start working before the user finishes speaking.

**Tier 3 — On-device (offline fallback):**
Vosk with small-en-us model. Provides streaming partial results directly on Pi. Accuracy is lower, but the device remains functional without network. The "input overflow" reports on Pi Zero 2W suggest the audio read loop needs careful buffering — use a dedicated thread with a ring buffer.

### 3.3 Latency Budget

For the full pipeline (user stops speaking -> device starts responding):

| Stage | Target | Notes |
|---|---|---|
| VAD end-of-speech | 400-600ms | Silence threshold (adaptive) |
| STT finalization | 100-300ms | Partial transcript likely already available |
| EOU model check | 25ms | LiveKit turn detector on Mac mini |
| LLM TTFT | 200-500ms | Haiku 4.5 or Sonnet 4.6 first token |
| TTS first audio | 100-200ms | Cartesia streaming |
| **Total** | **825-1625ms** | Target: under 1200ms for 90th percentile |

For comparison: human turn-taking averages ~200ms. Alexa/Google Home achieve ~800-1200ms. ChatGPT voice mode achieves ~500-800ms (using native speech-to-speech).

---

## 4. TTS-Typewriter Synchronization

The 240x280 OLED shows text while the speaker plays audio. These need to be synced — words appear on screen as they are spoken.

### 4.1 Word-Level Timestamps from TTS Providers

#### Cartesia (Recommended primary TTS)

- **WebSocket API** provides word-level timestamps natively: each response message includes `words`, `start_time`, and `end_time`
- Supports streaming — audio chunks arrive with their corresponding word timing data
- Handles interruption gracefully (can stop mid-stream)
- The `CartesiaTTSService` in Pipecat shows a clean integration pattern
- **Latency:** Sub-200ms to first audio chunk
- **CJK support:** Automatically combines individual characters into word units for timestamp purposes

#### Edge TTS (Current free fallback)

- Supports `WordBoundary` metadata through Microsoft's speech service
- Set `boundary="WordBoundary"` in the `Communicate` class
- Returns word text, offset (in audio ticks), and duration for each word
- **Limitation:** Audio must be fully generated before word boundaries are available (not truly streaming)
- Good enough for shorter responses; breaks down for long streaming outputs

#### Kokoro / Piper (Local fallback)

- Neither provides native word-level timestamps
- Must use the estimation fallback (see below)

### 4.2 Fallback: Estimation from Audio Duration

When word timestamps are not available:

**Method 1: Character-rate estimation**
```
words_per_second = len(text.split()) / audio_duration_seconds
chars_per_second = len(text) / audio_duration_seconds
# For each word, estimate start_time = cumulative_chars / chars_per_second
```
Accuracy: ~70-80%. Breaks down on words with unusual pronunciation length (numbers, abbreviations).

**Method 2: STT re-alignment**
Run the generated TTS audio through Whisper with `word_timestamps=True`. Whisper returns precise word-level timing. Adds ~200ms of processing but gives accurate alignment. This is the approach described in the edge-tts synchronization research.

**Method 3: Phoneme-based estimation**
Use a phonemizer (like `espeak-phonemize`) to convert text to phonemes, then estimate duration per phoneme (~80ms average). More accurate than character-rate but more complex.

**Recommendation:** Use Cartesia's native timestamps as primary. Fall back to character-rate estimation for other TTS engines (good enough for 240px-wide display where timing imprecision is less noticeable).

### 4.3 Display Implementation on 240x280 OLED

The OLED has limited space. Typewriter sync needs to account for:

- **Font size:** At readable sizes (14-18px), the screen fits ~15-20 characters per line, ~12-14 lines
- **Word wrapping:** Pre-calculate line breaks before starting playback. Don't reflow mid-display
- **Scroll behavior:** When text fills the screen, scroll up smoothly (not jump). Scroll timing synced to audio
- **Highlighting:** Current word could be highlighted (bold or inverted) — subtle enough not to distract
- **Pause indicator:** If the LLM is still generating and TTS catches up, show a subtle "..." or pulsing cursor. Don't let the typewriter stall visibly

### 4.4 How Others Handle This

| System | Approach |
|---|---|
| **ChatGPT Voice Mode** | No text display during voice. Full transcript appears after. Avoids the sync problem entirely |
| **Google Gemini Live** | Shows partial transcript in real-time. Text appears slightly ahead of audio |
| **Sesame CSM** | Focus on prosody/naturalness, not text sync. Speech-only interface |
| **Pipecat** | Frame-based pipeline syncs TTS audio frames with text frames. Clean abstraction |

---

## 5. Architecture Sketch

### 5.1 System Overview

```
                         Pi Zero 2W                              Mac mini (LAN)
                    +-------------------+                   +---------------------+
                    |                   |   WebSocket/UDP   |                     |
  Mic (WM8960) --> | Audio Capture     |=================> | SimulWhisper STT    |
                    | Ring Buffer       |                   | (streaming partial) |
                    | WebRTC VAD (gate) |                   |                     |
                    +-------------------+                   | Silero VAD          |
                                                            | (smart detection)   |
                    +-------------------+                   |                     |
                    | OLED Display      | <================ | EOU Turn Detector   |
                    | Typewriter Engine |   WebSocket        | (135M transformer)  |
                    | Word highlighting |                   |                     |
                    +-------------------+                   | LLM (Haiku/Sonnet)  |
                                                            |                     |
                    +-------------------+                   | Cartesia TTS        |
                    | Audio Playback    | <================ | (word timestamps)   |
                    | (WM8960 speaker)  |   WebSocket        |                     |
                    | Echo reference    |                   +---------------------+
                    +-------------------+
                           |
                    +-------------------+
                    | Blob Animator     |
                    | Expression sync   |
                    +-------------------+
```

### 5.2 Audio Input Pipeline

```
Mic (16kHz mono, WM8960)
  |
  v
Ring Buffer (2s, ~64KB)
  |
  v
WebRTC VAD (on-device, lightweight)
  |--- silence --> stay in IDLE, don't stream
  |--- speech detected --> start streaming to Mac mini
  v
Opus Compress (on-device)
  |
  v
WebSocket stream to Mac mini
  |
  +---> Silero VAD (smart detection, runs on Mac mini)
  |       |--- speech probability + segment boundaries
  |       v
  +---> SimulWhisper STT (streaming partial transcripts)
  |       |--- "Hello, I was wonder..."  (partial)
  |       |--- "Hello, I was wondering if..."  (partial)
  |       v
  +---> End-of-Speech Decision Engine
          |
          +-- Silence duration (from Silero VAD)
          +-- Transcript completeness (from EOU model)
          +-- Heuristic rules (conjunctions, fillers, questions)
          |
          v
        Decision: COMPLETE / WAIT / EXTEND_TIMEOUT
          |
          v (if COMPLETE)
        Send final transcript to LLM
```

### 5.3 Audio Output Pipeline

```
LLM streaming response (tokens)
  |
  v
Sentence Buffer
  |--- accumulate tokens until sentence boundary (., !, ?)
  |--- or flush after 3s if no boundary (long sentence)
  v
Cartesia TTS (WebSocket, streaming)
  |
  +---> Audio chunks (PCM/Opus)
  |       |
  |       v
  |     Stream to Pi Zero 2W via WebSocket
  |       |
  |       v
  |     Audio Playback (WM8960 speaker)
  |       |
  |       +---> Echo reference signal (for AEC)
  |
  +---> Word timestamps
          |
          v
        Stream to Pi Zero 2W via WebSocket
          |
          v
        Typewriter Engine (OLED)
          |--- reveal word at timestamp
          |--- scroll when line fills
          |
          +---> Blob Expression Sync
                  |--- audio-reactive pulse from PCM energy
                  |--- gesture triggers from LLM annotations
```

### 5.4 Conversation State Machine

```
                    +-------+
                    | IDLE  |<------ timeout (30s no speech)
                    +---+---+
                        |
                   wake word / button press / speech detected
                        |
                        v
                  +-----------+
           +----->| LISTENING |<----+
           |      +-----+-----+    |
           |            |           |
           |    end-of-speech       |
           |     detected           |
           |            |           |
           |            v           |
           |     +------------+     |
           |     | PROCESSING |     |
           |     +------+-----+     |
           |            |           |
           |     LLM first token    |
           |            |           |
           |            v           |
           |      +----------+      |
           |      | SPEAKING |------+
           |      +----+-----+  barge-in detected
           |           |
           |    response complete
           |           |
           |           v
           |    +-------------+
           +----| LISTENING   |  (auto-continue: keep mic hot)
                | (post-reply)|
                +-------------+
                       |
                  silence > 30s
                       |
                       v
                   +-------+
                   | IDLE  |
                   +-------+

Substates:
  LISTENING.PARTIAL  -- have partial transcript, waiting for more
  LISTENING.DECIDING -- silence detected, running EOU check
  SPEAKING.STREAMING -- TTS audio actively playing
  SPEAKING.PAUSED    -- between TTS sentences (natural breath)
```

### 5.5 Key Design Decisions

**Always-listening vs. push-to-talk:**
The current `recorder.py` is push-to-hold. Live Conversation Mode adds always-listening as a second mode. The button toggles between modes: tap to enter/exit live conversation mode. During live conversation, the device stays in the LISTENING-PROCESSING-SPEAKING loop until 30s of silence returns it to IDLE.

**Where does processing happen:**
Almost everything runs on Mac mini. The Pi Zero 2W handles only: mic capture, WebRTC VAD (gate), audio playback, display rendering, blob animation. This keeps Pi CPU/RAM usage manageable.

**WebSocket protocol:**
Extend the existing `/ws/voice` endpoint. Add message types:
- `audio_chunk` (Pi -> server): Opus-compressed audio
- `partial_transcript` (server -> Pi): Streaming STT result
- `final_transcript` (server -> Pi): Complete utterance
- `tts_audio` (server -> Pi): Audio chunk for playback
- `tts_word` (server -> Pi): Word + timestamp for typewriter
- `state_change` (bidirectional): State machine transitions
- `barge_in` (Pi -> server): User interrupted, stop TTS

---

## 6. Recommendations & Sprint Plan

### Priority Order

1. **VAD + STT streaming pipeline** — Get audio flowing from Pi to Mac mini with partial transcripts. This is the foundation everything else builds on
2. **End-of-speech detection** — Start with silence heuristics (500ms default), add EOU model in second iteration
3. **State machine** — Implement the IDLE/LISTENING/PROCESSING/SPEAKING states on both Pi and server
4. **TTS streaming with word timestamps** — Cartesia integration with typewriter sync
5. **Interruption handling** — Barge-in detection with echo cancellation
6. **Blob animation integration** — Expression sync with conversation states

### Technology Choices

| Component | Primary | Fallback |
|---|---|---|
| On-device VAD | WebRTC VAD | (always on) |
| Server VAD | Silero VAD | WebRTC VAD |
| Streaming STT | Lightning-SimulWhisper (Mac mini) | Deepgram (cloud) |
| Offline STT | Vosk small-en-us (Pi) | — |
| End-of-speech | LiveKit EOU model (Mac mini) | Silence heuristics only |
| TTS | Cartesia (streaming + timestamps) | Edge TTS (word boundaries) |
| Echo cancellation | SpeexDSP or WebRTC AEC | Mic mute during playback |
| Audio transport | Opus over WebSocket | Raw PCM (LAN only) |

### Open Questions for Sprint Planning

1. **Echo cancellation strategy:** SpeexDSP vs. mic-mute vs. WebRTC AEC. Need to test on actual hardware with WM8960. The speaker and mic are on the same board — echo will be significant
2. **SimulWhisper stability:** Lightning-SimulWhisper is newer and less battle-tested than batch-mode Lightning Whisper MLX. Need to validate it handles continuous streaming without memory leaks
3. **Cartesia pricing:** Need to evaluate cost at expected usage (assume 30-60 minutes of TTS per day). Compare with edge-tts (free) for cost-sensitive deployment
4. **LiveKit EOU model hosting:** Can we run the 135M param model on Mac mini alongside SimulWhisper and Silero VAD? Memory budget: model is ~400MB. Should fit comfortably on 8GB+ Mac mini
5. **Vosk accuracy:** The "input overflow" reports on Pi Zero 2W need investigation. May need to increase audio buffer size or reduce chunk processing frequency
6. **Single button UX:** How does the user indicate they want to enter/exit live conversation mode? Current proposal: double-press to toggle. Long-press for push-to-talk (existing behavior). Need to test if this feels natural

### Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Echo cancellation inadequate | High | High | Start with mic-mute approach, iterate to AEC |
| Pi Zero 2W can't keep up with audio streaming + display + blob | Medium | High | Profile early. Reduce blob FPS during conversation |
| SimulWhisper not stable for continuous streaming | Medium | Medium | Fall back to batch-mode Whisper with 1s chunks |
| Network latency spikes (Pi <-> Mac mini) | Low | High | Vosk offline fallback. Buffer audio on Pi |
| Cartesia API reliability | Low | Medium | Edge TTS fallback always available |

---

## 7. Sources

### VAD and End-of-Speech Detection
- [Silero VAD - GitHub](https://github.com/snakers4/silero-vad)
- [Choosing the Best VAD in 2026: Cobra vs Silero vs WebRTC VAD - Picovoice](https://picovoice.ai/blog/best-voice-activity-detection-vad/)
- [VAD: The Complete 2026 Guide - Picovoice](https://picovoice.ai/blog/complete-guide-voice-activity-detection-vad/)
- [Cobra Voice Activity Detection - Picovoice](https://picovoice.ai/platform/cobra/)
- [pyannote/voice-activity-detection - HuggingFace](https://huggingface.co/pyannote/voice-activity-detection)
- [Streaming VAD with pyannote.audio](https://herve.niderb.fr/fastpages/2021/08/05/Streaming-voice-activity-detection-with-pyannote.html)

### End-of-Turn Detection
- [Using a transformer to improve end of turn detection - LiveKit](https://blog.livekit.io/using-a-transformer-to-improve-end-of-turn-detection)
- [Improved End-of-Turn Model Cuts Voice AI Interruptions 39% - LiveKit](https://blog.livekit.io/improved-end-of-turn-model-cuts-voice-ai-interruptions-39/)
- [livekit-plugins-turn-detector - PyPI](https://pypi.org/project/livekit-plugins-turn-detector/)
- [LiveKit Turns Overview](https://docs.livekit.io/agents/logic/turns/)
- [How intelligent turn detection solves the biggest challenge in voice agents - AssemblyAI](https://www.assemblyai.com/blog/turn-detection-endpointing-voice-agent)

### Pause Duration and Conversation Timing
- [Timing in Conversation - PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC10077995/)
- [The 300ms rule: Why latency makes or breaks voice AI - AssemblyAI](https://www.assemblyai.com/blog/low-latency-voice-ai)
- [The Complete Guide to AI Turn-Taking 2025 - Tavus](https://www.tavus.io/post/ai-turn-taking)
- [The Latency Crisis in Voice AI Agents - Medium](https://medium.com/@reveorai/the-latency-crisis-in-voice-ai-agents-why-your-ai-caller-feels-like-a-bad-international-call-6e9c270df8e0)

### Interruption and Barge-In
- [Real-Time Barge-In AI for Voice Conversations - Gnani.ai](https://www.gnani.ai/resources/blogs/real-time-barge-in-ai-for-voice-conversations-31347)
- [Optimizing Voice Agent Barge-in Detection for 2025 - Sparkco](https://sparkco.ai/blog/optimizing-voice-agent-barge-in-detection-for-2025)
- [AI Voice Recognition: Barge-In, Turn-Taking, and VAD - SkyScribe](https://www.sky-scribe.com/en/blog/ai-voice-recognition-barge-in-turn-taking-and-vad)
- [Handling Interruptions in Speech-to-Speech Services - Medium](https://medium.com/@roshini.rafy/handling-interruptions-in-speech-to-speech-services-a-complete-guide-4255c5aa2d84)
- [Vocalis - GitHub](https://github.com/Lex-au/Vocalis)

### STT Engines
- [Lightning-SimulWhisper - GitHub](https://github.com/altalt-org/Lightning-SimulWhisper)
- [Streaming with Whisper in MLX vs Faster-Whisper - Medium](https://medium.com/@GenerationAI/streaming-with-whisper-in-mlx-vs-faster-whisper-vs-insanely-fast-whisper-37cebcfc4d27)
- [Updated mlx_whisper vs whisper.cpp benchmark](https://notes.billmill.org/dev_blog/2026/01/updated_my_mlx_whisper_vs._whisper.cpp_benchmark.html)
- [Groq Speech-to-Text Docs](https://console.groq.com/docs/speech-to-text)
- [Groq Whisper Large v3 at 164x Real-Time](https://groq.com/blog/groq-runs-whisper-large-v3-at-a-164x-speed-factor-according-to-new-artificial-analysis-benchmark)
- [Vosk Speech Recognition API - GitHub](https://github.com/alphacep/vosk-api)
- [Vosk on Pi Zero 2W - Raspberry Pi Forums](https://forums.raspberrypi.com/viewtopic.php?t=326417)

### TTS and Synchronization
- [Cartesia Text to Speech WebSocket API](https://docs.cartesia.ai/api-reference/tts/tts)
- [Cartesia Real-time TTS - Sonic-3](https://cartesia.ai/product/text-to-speech-tts)
- [Cartesia - Pipecat Integration](https://docs.pipecat.ai/server/services/tts/cartesia)
- [edge-tts - PyPI](https://pypi.org/project/edge-tts/)
- [Syncing Speech with Text: Timestamps in TTS - Medium](https://bar-offner.medium.com/syncing-speech-with-text-adding-timestamps-to-text-to-speech-using-python-13fe433b30a0)
- [Sesame Conversational Speech Model - GitHub](https://github.com/SesameAILabs/csm)

### Voice Agent Frameworks
- [Pipecat - GitHub](https://github.com/pipecat-ai/pipecat)
- [Pipecat Introduction](https://docs.pipecat.ai/getting-started/introduction)
- [LiveKit Agents - GitHub](https://github.com/livekit/agents)
- [Open Interpreter 01 - GitHub](https://github.com/openinterpreter/01)
- [Ultravox - GitHub](https://github.com/fixie-ai/ultravox)
- [How Ultravox Works](https://docs.ultravox.ai/gettingstarted/how-ultravox-works)
- [Voice AI Architectures: Traditional to Speech-to-Speech - Medium](https://medium.com/@ggarciabernardo/voice-ai-architectures-from-traditional-pipelines-to-speech-to-speech-and-hybrid-approaches-645b671d41ec)
- [One-Second Voice-to-Voice Latency with Modal and Pipecat](https://modal.com/blog/low-latency-voice-bot)
