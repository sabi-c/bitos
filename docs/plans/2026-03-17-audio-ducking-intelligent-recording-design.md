# Audio Ducking, Intelligent Recording & Split-Ear Control for BITOS

**Date:** 2026-03-17
**Status:** Design
**Hardware:** Pi Zero 2W + WM8960 (WhisPlay HAT) + AirPods via BT A2DP

---

## Table of Contents

1. [Current Audio Architecture Summary](#1-current-audio-architecture-summary)
2. [Music Ducking During Agent Interaction](#2-music-ducking-during-agent-interaction)
3. [Long-Pause Intelligent Recording](#3-long-pause-intelligent-recording)
4. [Split-Ear AirPod Control](#4-split-ear-airpod-control)
5. [Simultaneous Music + Agent Audio Architecture](#5-simultaneous-music--agent-audio-architecture)
6. [Audio Routing Diagram](#6-audio-routing-diagram)
7. [Concrete File Changes](#7-concrete-file-changes)

---

## 1. Current Audio Architecture Summary

**What exists today:**

| Component | File | What It Does |
|---|---|---|
| `AudioPipeline` / `WM8960Pipeline` | `device/audio/pipeline.py` | Records via `arecord`, plays TTS via `AudioPlayer`. Single-stream: one thing at a time. |
| `AudioPlayer` | `device/audio/player.py` | Plays WAV via `aplay` (ALSA), `paplay` (PulseAudio/BT), or `pygame.mixer` (desktop). Detects BT sink with `_is_bt_audio_active()`. |
| `TextToSpeech` | `device/audio/tts.py` | Fallback chain: Cartesia -> Edge TTS -> Speechify -> Chatterbox -> Piper -> OpenAI -> eSpeak. Synthesizes to temp WAV, plays via `AudioPlayer`. |
| `AudioRecorder` | `device/audio/recorder.py` | PyAudio push-to-talk recorder. Opens mic, captures frames in thread, returns WAV bytes. |
| `SharedAudioStream` | (worktree) `device/audio/shared_stream.py` | Single mic stream distributed to multiple consumers (wake word, VAD, recorder). Not yet in main branch. |
| `VoiceActivityDetector` | (worktree) `device/audio/vad.py` | WebRTC VAD wrapper. `is_speech()`, `trim_silence()`, `detect_silence_duration()`. Not yet in main branch. |
| `BluetoothAudioManager` | `device/bluetooth/audio_manager.py` | Full BT scan/pair/connect. Routes audio via `pactl set-default-sink` (PulseAudio) or `.asoundrc` rewrite (ALSA). |

**Key architectural fact:** There is currently no concept of simultaneous audio streams. `WM8960Pipeline.speak()` blocks until TTS playback completes. There is no music player. No ducking. No mixing.

---

## 2. Music Ducking During Agent Interaction

### 2.1 The Problem

Music plays through spotifyd (PulseAudio sink). Agent needs to speak (TTS). Both route through the same output (WM8960 speaker or BT A2DP sink to AirPods). The agent voice must be clearly audible over music.

### 2.2 Approach Evaluation

#### Option A: PulseAudio Per-Stream Volume Control (RECOMMENDED)

PulseAudio (and PipeWire's PulseAudio compatibility layer) supports **per-stream (sink-input) volume control**. When spotifyd plays music, it creates a sink-input. When `paplay` plays TTS, it creates a separate sink-input. We can control each independently.

```
spotifyd ──> [sink-input #42] ──┐
                                ├──> [default sink] ──> AirPods / Speaker
paplay TTS ──> [sink-input #57] ┘
```

**How it works:**

```bash
# List current sink-inputs (playing streams)
pactl list short sink-inputs
# Output: 42  1  spotifyd  float32le 2ch 44100Hz  RUNNING
#         57  1  paplay    s16le 2ch 48000Hz       RUNNING

# Duck spotifyd's stream to 20%
pactl set-sink-input-volume 42 13107   # 20% of 65536

# Restore to 100%
pactl set-sink-input-volume 42 65536
```

**Per-stream volume works over BT A2DP.** PulseAudio mixes the streams at the software level before encoding to A2DP (SBC/AAC). The BT device receives a single mixed audio stream. Ducking one stream while boosting another works identically whether output is speaker or BT.

**Identifying the music stream:** Use the application name. `spotifyd` identifies itself as `spotifyd` in PulseAudio. We can find it by name:

```bash
pactl list sink-inputs | grep -A5 "application.name.*spotifyd"
```

Or programmatically via `pulsectl` (Python PulseAudio client library):

```python
import pulsectl

with pulsectl.Pulse('bitos-ducker') as pulse:
    for si in pulse.sink_input_list():
        if 'spotifyd' in (si.proplist.get('application.name', '') or '').lower():
            # Duck to 20%
            pulse.volume_set_all_chans(si, 0.2)
```

**Advantages:**
- Per-stream control: duck music without affecting TTS volume
- Works over BT A2DP (mixing happens before BT encoding)
- Works with PipeWire (PulseAudio compatibility)
- No codec switch, no quality degradation
- `pulsectl` is a lightweight pure-Python library

#### Option B: ALSA Mixer Hardware Volume

The WM8960 has hardware volume registers accessible via `amixer`. But `amixer sset Speaker N%` controls **master volume** -- it affects ALL audio equally. You cannot duck one stream and not another at the ALSA level.

The WM8960 does have separate DAC L/R volume and headphone volume registers, but these are output-stage controls, not per-stream. Multiple software streams are mixed before hitting the DAC.

**Verdict: ALSA mixer cannot do per-stream ducking.** Useful only for global volume (which the existing `AudioPlayer.set_volume()` already does).

#### Option C: Application-Level Mixing (pygame.mixer)

`pygame.mixer` supports channels: `Sound` objects play on numbered channels, each with independent volume. Music can play on the `music` channel, TTS on a `Sound` channel.

```python
import pygame
pygame.mixer.init()
pygame.mixer.music.load("song.mp3")
pygame.mixer.music.play()
pygame.mixer.music.set_volume(0.2)  # duck music

tts_sound = pygame.mixer.Sound("tts_output.wav")
tts_channel = tts_sound.play()
tts_channel.set_volume(1.0)
```

**Problem:** This only works when pygame controls both streams. spotifyd is a separate process with its own audio output. pygame cannot intercept or control spotifyd's stream. This approach only works if BITOS itself plays music files (no Spotify Connect). Not recommended.

#### Option D: PulseAudio Default Sink Volume (Current Design Doc Approach)

The existing design doc (`2026-03-17-airpods-spotify-music-intelligence-design.md`) uses `pactl set-sink-volume @DEFAULT_SINK@ N%`. This controls **master output volume**, affecting both music AND TTS simultaneously. If you duck the master to 20%, TTS also plays at 20%.

**This is wrong for ducking.** It would require boosting TTS volume to compensate, creating a fragile volume dance. Per-sink-input control (Option A) is strictly better.

### 2.3 Ducking Implementation

New module: `device/audio/music_ducker.py`

```python
"""Music volume ducking for agent TTS output.

Uses PulseAudio per-sink-input volume to duck music streams (spotifyd)
while keeping TTS at full volume. Works over BT A2DP and local speaker.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import pulsectl
    _HAS_PULSECTL = True
except ImportError:
    _HAS_PULSECTL = False
    logger.warning("pulsectl not available -- music ducking disabled")

# Music source application names (any of these will be ducked)
MUSIC_APP_NAMES = {"spotifyd", "spotify", "librespot", "mpv", "vlc", "mplayer"}

DUCK_VOLUME = 0.15         # 15% during TTS
NORMAL_VOLUME = 1.0        # 100% restored
FADE_STEPS = 8             # number of interpolation steps
FADE_DURATION_S = 0.25     # total fade time (8 steps * ~31ms each)


class MusicDucker:
    """Duck music sink-inputs during TTS playback.

    Usage:
        ducker = MusicDucker()
        ducker.duck()       # before TTS starts
        # ... TTS plays ...
        ducker.restore()    # after TTS finishes
    """

    def __init__(self, duck_volume: float = DUCK_VOLUME):
        self._duck_volume = duck_volume
        self._original_volumes: dict[int, float] = {}  # sink_input_index -> original_volume
        self._ducked = False
        self._lock = threading.Lock()

    def is_music_playing(self) -> bool:
        """Check if any music sink-input is currently active."""
        if not _HAS_PULSECTL:
            return False
        try:
            with pulsectl.Pulse('bitos-ducker-check') as pulse:
                for si in pulse.sink_input_list():
                    app_name = (si.proplist.get('application.name', '') or '').lower()
                    if app_name in MUSIC_APP_NAMES:
                        return True
        except Exception as exc:
            logger.debug("music_check_failed: %s", exc)
        return False

    def duck(self) -> None:
        """Smoothly lower music volume for TTS. Non-blocking fade."""
        if not _HAS_PULSECTL:
            return
        with self._lock:
            if self._ducked:
                return
            self._ducked = True

        def _fade():
            try:
                with pulsectl.Pulse('bitos-ducker-duck') as pulse:
                    music_inputs = self._find_music_inputs(pulse)
                    if not music_inputs:
                        return

                    # Save original volumes
                    for si in music_inputs:
                        vol = si.volume.value_flat  # average across channels
                        self._original_volumes[si.index] = vol

                    # Smooth fade down
                    for step in range(1, FADE_STEPS + 1):
                        t = step / FADE_STEPS
                        for si in music_inputs:
                            orig = self._original_volumes.get(si.index, 1.0)
                            target = orig * self._duck_volume
                            current = orig - (orig - target) * t
                            pulse.volume_set_all_chans(si, max(0.0, current))
                        time.sleep(FADE_DURATION_S / FADE_STEPS)

                    logger.info("music_ducked: %d streams to %.0f%%",
                                len(music_inputs), self._duck_volume * 100)
            except Exception as exc:
                logger.warning("music_duck_failed: %s", exc)

        threading.Thread(target=_fade, daemon=True, name="music-duck").start()

    def restore(self) -> None:
        """Smoothly restore music volume after TTS. Non-blocking fade."""
        if not _HAS_PULSECTL:
            return
        with self._lock:
            if not self._ducked:
                return
            self._ducked = False
            saved = dict(self._original_volumes)
            self._original_volumes.clear()

        def _fade():
            try:
                with pulsectl.Pulse('bitos-ducker-restore') as pulse:
                    for si in pulse.sink_input_list():
                        if si.index in saved:
                            orig = saved[si.index]
                            current_vol = si.volume.value_flat
                            for step in range(1, FADE_STEPS + 1):
                                t = step / FADE_STEPS
                                v = current_vol + (orig - current_vol) * t
                                pulse.volume_set_all_chans(si, min(1.0, v))
                                time.sleep(FADE_DURATION_S / FADE_STEPS)

                    logger.info("music_restored: %d streams", len(saved))
            except Exception as exc:
                logger.warning("music_restore_failed: %s", exc)

        threading.Thread(target=_fade, daemon=True, name="music-restore").start()

    @staticmethod
    def _find_music_inputs(pulse) -> list:
        """Find all PulseAudio sink-inputs that are music sources."""
        results = []
        for si in pulse.sink_input_list():
            app_name = (si.proplist.get('application.name', '') or '').lower()
            if app_name in MUSIC_APP_NAMES:
                results.append(si)
        return results
```

### 2.4 Integration with TTS Pipeline

Modify `device/audio/pipeline.py` -- `WM8960Pipeline.speak()`:

```python
class WM8960Pipeline(AudioPipeline):
    def __init__(self):
        # ... existing init ...
        self._ducker: Optional["MusicDucker"] = None
        try:
            from audio.music_ducker import MusicDucker
            self._ducker = MusicDucker()
        except Exception:
            pass

    def speak(self, text: str) -> None:
        from audio.player import AudioPlayer
        from audio.tts import TextToSpeech

        logger.info("wm8960_speak: text_len=%d starting TTS pipeline", len(text))

        # Duck music before speaking
        should_duck = self._ducker and self._ducker.is_music_playing()
        if should_duck:
            self._ducker.duck()
            time.sleep(0.3)  # let fade complete before TTS starts

        player = AudioPlayer()
        self._player = player
        self._speaking_flag = True
        try:
            tts = TextToSpeech(player)
            ok = tts.speak(text)
        finally:
            self._speaking_flag = False
            self._player = None
            # Restore music after speaking
            if should_duck:
                self._ducker.restore()
```

### 2.5 Why This Works Over Bluetooth

PulseAudio's mixing pipeline:

```
spotifyd audio  ---\
                    >--- PulseAudio mixer (software) ---> BT A2DP encoder ---> AirPods
paplay TTS audio --/
```

Per-sink-input volume is applied BEFORE the mixer combines streams. The A2DP encoder receives a single pre-mixed PCM stream. The BT device (AirPods) has no knowledge of individual streams. Ducking is fully transparent to BT.

**This means:** ducking works identically on speaker output and BT A2DP output. No special BT handling needed.

### 2.6 Fallback for ALSA-Only (No PulseAudio)

If running without PulseAudio (Pi OS Lite, ALSA-only path), per-stream ducking is not possible. Fallback strategy:

1. **Pause music instead of ducking:** Call `spotifyd` to pause via Spotify Web API or D-Bus MPRIS.
2. **Use master volume approach:** Duck `amixer sset Speaker 20%`, play TTS at hardware volume, restore after. Less elegant but functional.

The `MusicDucker` class already handles this gracefully -- if `pulsectl` is not available, ducking is a no-op.

---

## 3. Long-Pause Intelligent Recording

### 3.1 The Problem

Current `AudioRecorder` does simple push-to-talk: start on button press, stop on button release. The user's natural speaking pattern involves pauses up to 30 seconds while thinking. Standard VAD would cut off at 2 seconds of silence and send incomplete input.

### 3.2 Recording State Machine

```
                    wake word / button press
                           |
                           v
     +---------+     +------------+     +---------+
     |  IDLE   | --> | LISTENING  | --> | SENDING |
     +---------+     +------------+     +---------+
                           |  ^               |
                           |  |               v
                           |  |         +----------+
                           |  +-------- | THINKING |
                           |            +----------+
                           |
                           v
                     +-----------+
                     | CANCELLED |
                     +-----------+

Transitions:
  IDLE -> LISTENING:        wake word detected OR button SHORT_PRESS
  LISTENING -> THINKING:    silence detected (>2s of no speech)
  THINKING -> LISTENING:    speech resumes within 30s
  THINKING -> SENDING:      silence exceeds 30s (auto-send)
  LISTENING -> SENDING:     button DOUBLE_PRESS (manual send)
  THINKING -> SENDING:      button DOUBLE_PRESS (manual send)
  LISTENING -> CANCELLED:   button LONG_PRESS (cancel)
  THINKING -> CANCELLED:    button LONG_PRESS (cancel)
  SENDING -> IDLE:          transcription complete, sent to server
  CANCELLED -> IDLE:        discard audio
```

### 3.3 Smart Silence Detection

The `VoiceActivityDetector` (from worktree) provides frame-level speech detection. We need a higher-level classifier that distinguishes:

| Silence Type | Duration | Characteristics | Action |
|---|---|---|---|
| Natural pause (breathing) | < 2s | Brief gaps between sentences | Keep recording, stay in LISTENING |
| Thinking pause | 2-30s | No speech, but ambient noise present | Switch to THINKING, show indicator |
| Done speaking | > 30s | Extended silence | Auto-send (SENDING) |
| Walked away | > 30s | Near-zero ambient energy | Auto-cancel or auto-send |

**Energy-based presence detection:** Beyond VAD (which detects speech), we can measure ambient energy to distinguish "still here, thinking" from "left the room":

```python
def classify_silence(self, frames: list[np.ndarray]) -> str:
    """Classify the nature of a silence period.

    Returns: 'breathing' | 'thinking' | 'absent'
    """
    if not frames:
        return 'absent'

    # RMS energy of recent frames
    recent = np.concatenate(frames[-10:])  # last ~320ms
    rms = np.sqrt(np.mean(recent.astype(np.float32) ** 2))

    # Baseline noise floor (calibrated at startup or from first 2s)
    noise_floor = self._noise_floor or 100.0

    if rms > noise_floor * 3.0:
        return 'breathing'   # ambient sounds, movement, breathing
    elif rms > noise_floor * 1.2:
        return 'thinking'    # room noise present, user likely still nearby
    else:
        return 'absent'      # near-silence, user may have left
```

### 3.4 Implementation: IntelligentRecorder

New module: `device/audio/intelligent_recorder.py`

```python
"""Intelligent audio recorder with long-pause tolerance.

Records continuously after activation. Uses WebRTC VAD to detect speech
segments. Tolerates up to 30s of silence (thinking pauses) before
auto-sending. Shows real-time status (recording/thinking/elapsed time).
"""
from __future__ import annotations

import io
import logging
import threading
import time
import wave
from collections import deque
from enum import Enum, auto
from typing import Callable, Optional

import numpy as np

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000
FRAME_SIZE = 512       # ~32ms at 16kHz
CHANNELS = 1

# Timing thresholds
THINKING_THRESHOLD_S = 2.0     # silence > 2s = "thinking"
AUTO_SEND_THRESHOLD_S = 30.0   # silence > 30s = auto-send
MIN_SPEECH_FRAMES = 10         # minimum speech frames to be worth sending (~320ms)

# Energy thresholds for presence detection
NOISE_CALIBRATION_S = 1.0      # calibrate noise floor from first 1s


class RecordingState(Enum):
    IDLE = auto()
    LISTENING = auto()      # speech detected, actively recording
    THINKING = auto()       # silence detected, waiting for more speech
    SENDING = auto()        # recording complete, processing
    CANCELLED = auto()


class IntelligentRecorder:
    """Recorder with long-pause tolerance and smart silence detection.

    Callbacks:
        on_state_change(state: RecordingState) -- called on every state transition
        on_auto_send(wav_bytes: bytes) -- called when auto-send triggers
        on_status(info: dict) -- called periodically with status info for UI:
            {state, elapsed_s, silence_s, speech_segments, has_speech}
    """

    def __init__(
        self,
        shared_stream=None,
        on_state_change: Optional[Callable] = None,
        on_auto_send: Optional[Callable] = None,
        on_status: Optional[Callable] = None,
        thinking_threshold: float = THINKING_THRESHOLD_S,
        auto_send_threshold: float = AUTO_SEND_THRESHOLD_S,
    ):
        self._stream = shared_stream    # SharedAudioStream (optional)
        self._on_state_change = on_state_change
        self._on_auto_send = on_auto_send
        self._on_status = on_status
        self._thinking_threshold = thinking_threshold
        self._auto_send_threshold = auto_send_threshold

        self._state = RecordingState.IDLE
        self._frames: list[np.ndarray] = []
        self._speech_frame_count = 0
        self._start_time = 0.0
        self._last_speech_time = 0.0
        self._noise_floor: Optional[float] = None
        self._noise_frames: list[np.ndarray] = []

        self._vad = None
        self._recording_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        try:
            from audio.vad import VoiceActivityDetector
            self._vad = VoiceActivityDetector(aggressiveness=2)
            if not self._vad.available:
                self._vad = None
        except ImportError:
            pass

    @property
    def state(self) -> RecordingState:
        return self._state

    @property
    def elapsed(self) -> float:
        if self._state in (RecordingState.LISTENING, RecordingState.THINKING):
            return time.monotonic() - self._start_time
        return 0.0

    @property
    def silence_duration(self) -> float:
        if self._state in (RecordingState.LISTENING, RecordingState.THINKING):
            return time.monotonic() - self._last_speech_time
        return 0.0

    def start(self) -> None:
        """Begin recording. Call from wake word callback or button press."""
        if self._state != RecordingState.IDLE:
            return

        self._frames = []
        self._speech_frame_count = 0
        self._start_time = time.monotonic()
        self._last_speech_time = time.monotonic()
        self._noise_floor = None
        self._noise_frames = []
        self._stop_event.clear()

        self._set_state(RecordingState.LISTENING)

        self._recording_thread = threading.Thread(
            target=self._recording_loop, daemon=True, name="intelligent-recorder"
        )
        self._recording_thread.start()

    def stop_and_send(self) -> Optional[bytes]:
        """Manual send (button DOUBLE_PRESS). Returns WAV bytes or None."""
        if self._state not in (RecordingState.LISTENING, RecordingState.THINKING):
            return None
        self._set_state(RecordingState.SENDING)
        self._stop_event.set()
        if self._recording_thread:
            self._recording_thread.join(timeout=2.0)
        return self._finalize()

    def cancel(self) -> None:
        """Cancel recording (button LONG_PRESS). Discards all audio."""
        self._set_state(RecordingState.CANCELLED)
        self._stop_event.set()
        if self._recording_thread:
            self._recording_thread.join(timeout=2.0)
        self._frames = []
        self._set_state(RecordingState.IDLE)

    def _set_state(self, new_state: RecordingState) -> None:
        old = self._state
        self._state = new_state
        if old != new_state:
            logger.info("recorder_state: %s -> %s", old.name, new_state.name)
            if self._on_state_change:
                try:
                    self._on_state_change(new_state)
                except Exception:
                    pass

    def _recording_loop(self) -> None:
        """Main recording loop. Reads from SharedAudioStream or opens own mic."""
        import pyaudio

        # If we have a SharedAudioStream, register as consumer
        consumer_buf = None
        pa = None
        mic_stream = None

        if self._stream and self._stream.is_running:
            consumer_buf = self._stream.register("intelligent_recorder", maxlen=200)
        else:
            # Open our own mic stream
            try:
                pa = pyaudio.PyAudio()
                mic_stream = pa.open(
                    format=pyaudio.paInt16,
                    channels=CHANNELS,
                    rate=SAMPLE_RATE,
                    input=True,
                    frames_per_buffer=FRAME_SIZE,
                )
            except Exception as exc:
                logger.error("recorder_mic_open_failed: %s", exc)
                self._set_state(RecordingState.IDLE)
                return

        status_interval = 0.25  # send status updates 4x/sec
        last_status = 0.0

        try:
            while not self._stop_event.is_set():
                # Read frame
                frame = None
                if consumer_buf is not None:
                    try:
                        frame = consumer_buf.popleft()
                    except IndexError:
                        time.sleep(0.01)
                        continue
                elif mic_stream:
                    try:
                        raw = mic_stream.read(FRAME_SIZE, exception_on_overflow=False)
                        frame = np.frombuffer(raw, dtype=np.int16)
                    except Exception:
                        time.sleep(0.01)
                        continue

                if frame is None:
                    continue

                self._frames.append(frame)

                # Calibrate noise floor from first second
                elapsed = time.monotonic() - self._start_time
                if elapsed < NOISE_CALIBRATION_S:
                    self._noise_frames.append(frame)
                elif self._noise_floor is None and self._noise_frames:
                    all_noise = np.concatenate(self._noise_frames)
                    self._noise_floor = float(np.sqrt(np.mean(all_noise.astype(np.float32) ** 2)))
                    self._noise_frames = []
                    logger.info("recorder_noise_floor: %.1f", self._noise_floor)

                # VAD check
                is_speech = True
                if self._vad:
                    is_speech = self._vad.is_speech(frame)

                if is_speech:
                    self._speech_frame_count += 1
                    self._last_speech_time = time.monotonic()
                    if self._state == RecordingState.THINKING:
                        self._set_state(RecordingState.LISTENING)

                # Check silence duration
                silence_s = time.monotonic() - self._last_speech_time

                if silence_s >= self._auto_send_threshold:
                    # 30s silence -- auto-send
                    logger.info("recorder_auto_send: silence=%.1fs", silence_s)
                    self._set_state(RecordingState.SENDING)
                    break
                elif silence_s >= self._thinking_threshold:
                    if self._state == RecordingState.LISTENING:
                        self._set_state(RecordingState.THINKING)

                # Periodic status update
                now = time.monotonic()
                if now - last_status >= status_interval and self._on_status:
                    self._on_status({
                        "state": self._state.name,
                        "elapsed_s": round(now - self._start_time, 1),
                        "silence_s": round(silence_s, 1),
                        "speech_segments": self._speech_frame_count,
                        "has_speech": self._speech_frame_count >= MIN_SPEECH_FRAMES,
                    })
                    last_status = now

        finally:
            if consumer_buf is not None and self._stream:
                self._stream.unregister("intelligent_recorder")
            if mic_stream:
                mic_stream.stop_stream()
                mic_stream.close()
            if pa:
                pa.terminate()

        # Auto-send if we exited due to timeout
        if self._state == RecordingState.SENDING:
            wav_bytes = self._finalize()
            if wav_bytes and self._on_auto_send:
                self._on_auto_send(wav_bytes)
            self._set_state(RecordingState.IDLE)

    def _finalize(self) -> Optional[bytes]:
        """Convert recorded frames to WAV bytes. Trims silence if VAD available."""
        if self._speech_frame_count < MIN_SPEECH_FRAMES:
            logger.info("recorder_too_short: speech_frames=%d", self._speech_frame_count)
            self._set_state(RecordingState.IDLE)
            return None

        audio = np.concatenate(self._frames) if self._frames else np.array([], dtype=np.int16)

        # Trim leading/trailing silence
        if self._vad:
            audio = self._vad.trim_silence(audio)

        # Encode as WAV
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(2)  # int16
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(audio.tobytes())

        wav_bytes = buf.getvalue()
        logger.info("recorder_finalized: %d bytes, %.1fs audio",
                     len(wav_bytes), len(audio) / SAMPLE_RATE)
        self._frames = []
        self._set_state(RecordingState.IDLE)
        return wav_bytes

    def classify_silence(self) -> str:
        """Classify current silence: 'breathing', 'thinking', or 'absent'.

        Uses RMS energy of recent frames compared to calibrated noise floor.
        """
        if not self._frames or len(self._frames) < 5:
            return 'absent'

        recent = np.concatenate(self._frames[-10:])
        rms = float(np.sqrt(np.mean(recent.astype(np.float32) ** 2)))

        noise = self._noise_floor or 100.0

        if rms > noise * 3.0:
            return 'breathing'
        elif rms > noise * 1.2:
            return 'thinking'
        else:
            return 'absent'
```

### 3.5 UI Integration: "Still Listening..." Indicator

The `on_status` callback provides real-time data for the UI. In the chat panel or agent overlay:

```python
# In the recording UI render loop:
def _render_recording_status(self, surface, status: dict):
    state = status["state"]
    elapsed = status["elapsed_s"]
    silence = status["silence_s"]

    if state == "LISTENING":
        # Pulsing red dot + timer
        self._draw_recording_indicator(surface, elapsed)

    elif state == "THINKING":
        # Amber "still listening..." with silence countdown
        remaining = 30.0 - silence
        text = f"Still listening... ({int(remaining)}s)"
        self._draw_thinking_indicator(surface, text, elapsed)
        # Optionally show a progress bar draining from 30s to 0
```

Visual design:
- **LISTENING:** Pulsing red dot + `REC 0:05` (existing pattern from `FieldRecordingPanel`)
- **THINKING:** Amber dot (steady) + `THINKING... 12s` + fading progress bar
- **Auto-send approaching:** Progress bar turns red in last 5 seconds

### 3.6 Button Interactions During Recording

| State | SHORT_PRESS | DOUBLE_PRESS | LONG_PRESS |
|---|---|---|---|
| LISTENING | (ignored, or add marker) | Send now | Cancel |
| THINKING | (ignored) | Send now | Cancel |

### 3.7 Configurable Thresholds

Store in `DeviceRepository` settings:

```python
# Default thresholds (overridable in companion app settings)
"recording_thinking_threshold_s": 2.0    # silence before THINKING state
"recording_auto_send_threshold_s": 30.0  # silence before auto-send
"recording_min_speech_ms": 300           # minimum speech to be sendable
```

---

## 4. Split-Ear AirPod Control

### 4.1 Can AVRCP Distinguish Which Ear Generated the Tap?

**No.** AVRCP is a transport-level protocol. AirPods send a single AVRCP command (Play/Pause, Next, Previous) from the combined device. The command does not include metadata about which earbud originated it.

At the Bluetooth protocol level, AirPods appear as a single audio device with one MAC address. The left and right buds communicate with each other via a proprietary Apple protocol (using NFMI -- Near-Field Magnetic Induction for Gen 1/2, or Bluetooth for Pro). The host device (Pi) only sees unified commands.

**Apple's own solution:** On iPhone, you can set different actions per ear (e.g., left double-tap = previous, right double-tap = next). But this configuration is done in iPhone Settings -> Bluetooth -> AirPods, and the AirPods firmware handles the mapping internally. It still sends standard AVRCP commands to the connected device -- just different ones per ear.

### 4.2 What BITOS Can Detect

From the research doc (`2026-03-17-airpod-gesture-controls-research.md`):

| AirPod Gesture | AVRCP Command | Detectable? |
|---|---|---|
| Single tap/squeeze | Play/Pause | YES |
| Double tap/squeeze | Next Track | YES |
| Triple tap/squeeze | Previous Track | YES |
| Long press/squeeze | Siri/ANC | NO (internal) |
| Pro stem slide | Volume Up/Down | YES |

### 4.3 Workaround: Gesture-Based Function Splitting

Since we cannot identify which ear, we use **different gesture types** for different functions:

**Proposed mapping:**

| Gesture | Function | Category |
|---|---|---|
| Single tap (Play/Pause) | Toggle agent voice input | Agent control |
| Double tap (Next) | Next track / skip | Music control |
| Triple tap (Previous) | Previous track | Music control |
| Stem slide up (Volume Up) | Volume up | Music control |
| Stem slide down (Volume Down) | Volume down | Music control |

**Context-dependent override:** When agent is speaking (TTS active):

| Gesture | Function |
|---|---|
| Single tap | Stop/skip TTS |
| Double tap | (no action) |
| Triple tap | (no action) |

**When recording:**

| Gesture | Function |
|---|---|
| Single tap | Stop recording, send to agent |
| Double tap | (no action) |
| Triple tap | Cancel recording |

### 4.4 Alternative: User Configures Per-Ear on iPhone

The most practical approach is to instruct the user to configure their AirPods via iPhone Settings:

1. **Left AirPod double-tap:** Set to "Previous Track" (AVRCP Previous)
2. **Right AirPod double-tap:** Set to "Next Track" (AVRCP Next)

Then map in BITOS:
- Previous = "go back / dismiss"
- Next = "next item / skip"
- Play/Pause = "toggle agent input" (either ear single-tap)

This gives effective split-ear control without any protocol tricks.

### 4.5 How AirPods Report Tap Events to Non-Apple Devices

AirPods use standard Bluetooth A2DP + AVRCP profiles when connected to non-Apple devices. The tap/squeeze gestures are translated to AVRCP commands by the AirPods firmware. The Pi receives these as:

1. **D-Bus MediaPlayer1 `Status` property changes** (playing/paused) for Play/Pause
2. **D-Bus MediaPlayer1 `Track` property changes** for Next/Previous
3. **evdev `KEY_PLAYPAUSE` / `KEY_NEXTSONG` / `KEY_PREVIOUSSONG`** events (if BlueZ registers the AVRCP as HID input)

The events arrive within 50-150ms of the physical gesture. No special Apple protocol handling is needed on the Pi side.

**Battery and ear detection** use Apple-proprietary extensions to HFP (AT commands) and BLE advertisements. These are not reliably available on Linux.

---

## 5. Simultaneous Music + Agent Audio Architecture

### 5.1 The Mixing Problem

BITOS needs three concurrent audio paths:

1. **Music playback** (spotifyd / librespot) -- continuous background audio
2. **TTS output** (agent voice) -- intermittent, must be clearly audible
3. **Mic recording** (WM8960 or AirPod HFP) -- must NOT capture playback loopback

### 5.2 PulseAudio Handles This Natively

PulseAudio was designed for exactly this scenario. Each application opens its own playback stream (sink-input), and PulseAudio mixes them in software before sending to the output device (sink).

```
┌──────────────┐    ┌────────────────────────┐    ┌──────────────────┐
│   spotifyd   │───>│ PulseAudio Mixer       │───>│ Output Sink      │
│  (music)     │    │                        │    │                  │
├──────────────┤    │  Per-stream volume      │    │ WM8960 speaker   │
│   paplay     │───>│  Software mixing        │    │    -OR-          │
│  (TTS)       │    │  Resampling             │    │ BT A2DP (AirPods)│
└──────────────┘    └────────────────────────┘    └──────────────────┘

┌──────────────┐    ┌────────────────────────┐
│   arecord /  │<───│ Input Source            │
│   pyaudio    │    │ WM8960 mic (capture)    │
│  (recording) │    │  -OR-                   │
└──────────────┘    │ BT HFP mic (AirPods)   │
                    └────────────────────────┘
```

**Recording does NOT capture loopback.** PulseAudio's input source (WM8960 mic) is hardware capture -- it records from the physical microphone. It does not loop back audio from the output sink. This is the default and correct behavior. Speaker output and mic input are separate hardware paths on the WM8960 codec.

**BT A2DP + WM8960 mic coexistence:** When AirPods are connected for A2DP output, the WM8960 mic remains available as a separate input device. No conflict. Recording uses the local mic while playback routes to AirPods.

### 5.3 Spatial Separation (Agent vs Music)

Can we make the agent voice "sound different" from music when both play through AirPods?

**What works:**
- **EQ/frequency profile:** The agent's TTS already has a distinct voice character. Cartesia/Edge TTS voices are clearly synthetic and naturally distinguishable from music.
- **Volume differential:** Music ducked to 15%, TTS at 100%. This 6:1 ratio makes the agent voice dominant.
- **Pre-TTS notification sound:** Play a brief "ping" before agent speaks. Gives the listener a moment to shift attention. Many smart assistants do this.

**What does NOT work on standard BT A2DP:**
- **Stereo panning** (e.g., music to left, agent to right): This would require mixing audio ourselves and outputting a single stereo stream where channels carry different content. Technically possible but creates a disorienting experience -- music in one ear, voice in the other.
- **Spatial audio / head tracking:** Requires Apple's proprietary spatial audio protocol. Not available to non-Apple BT hosts.
- **Separate BT audio channels:** A2DP is a single stereo stream. No multi-channel routing to BT.

**Recommendation:** Rely on volume ducking + distinct TTS voice + optional notification ping. This matches what every smart speaker and car audio system does.

### 5.4 Notification Ping Before Agent Speech

Add a short audio cue before TTS to signal "agent is about to speak":

```python
# In WM8960Pipeline.speak():
AGENT_PING_PATH = "/home/pi/bitos/assets/sounds/agent_ping.wav"

def speak(self, text: str) -> None:
    # Duck music
    if self._ducker and self._ducker.is_music_playing():
        self._ducker.duck()
        time.sleep(0.15)
        # Play subtle notification sound
        if os.path.exists(AGENT_PING_PATH):
            AudioPlayer().play_file(AGENT_PING_PATH)
            time.sleep(0.1)

    # Play TTS
    # ...
```

The ping WAV should be a short (100-200ms) soft tone. Not jarring.

---

## 6. Audio Routing Diagram

```
╔══════════════════════════════════════════════════════════════════════════╗
║                        BITOS Audio Architecture                         ║
╠══════════════════════════════════════════════════════════════════════════╣
║                                                                          ║
║  ┌─────────────┐                                                        ║
║  │  spotifyd   │──> PulseAudio sink-input #A ──┐                        ║
║  │ (Spotify    │    vol: 100% normal / 15% duck │                       ║
║  │  Connect)   │                                │                       ║
║  └─────────────┘                                │                       ║
║                                                 v                       ║
║  ┌─────────────┐                          ┌──────────┐                  ║
║  │   paplay    │──> PulseAudio sink-input  │ PA Mixer │                 ║
║  │ (TTS audio) │   #B, vol: 100%      ──> │ (softw.) │                 ║
║  └─────────────┘                          └────┬─────┘                  ║
║                                                │                        ║
║  ┌─────────────┐                               v                       ║
║  │  ping.wav   │──> PulseAudio sink-input  ┌──────────────────┐        ║
║  │ (notif.)    │   #C (brief)          ──> │  Output Sink     │        ║
║  └─────────────┘                           │                  │        ║
║                                            │  IF BT connected:│        ║
║                                            │   bluez_sink     │──> AirPods
║                                            │  ELSE:           │        ║
║                                            │   alsa_output    │──> WM8960 Spk
║                                            └──────────────────┘        ║
║                                                                         ║
║  ═══ INPUT PATH ═══                                                     ║
║                                                                         ║
║  ┌─────────────┐     ┌──────────────────┐                              ║
║  │  WM8960 Mic │──>  │ SharedAudioStream │                             ║
║  │ (always on) │     │  (pyaudio)       │                              ║
║  └─────────────┘     └───────┬──────────┘                              ║
║                              │                                          ║
║                    ┌─────────┼──────────────┐                           ║
║                    v         v              v                           ║
║              ┌──────────┐ ┌───────────┐ ┌──────────────────┐           ║
║              │ Wake     │ │ Intelli-  │ │ Future:          │           ║
║              │ Word     │ │ gent      │ │ Always-on        │           ║
║              │ Detector │ │ Recorder  │ │ ambient noise    │           ║
║              └──────────┘ └───────────┘ │ classifier       │           ║
║                                         └──────────────────┘           ║
║                                                                         ║
║  ═══ DUCKING FLOW ═══                                                   ║
║                                                                         ║
║  Agent needs to speak:                                                  ║
║    1. MusicDucker.duck() → fade spotifyd sink-input to 15% (250ms)     ║
║    2. Play agent_ping.wav (150ms)                                       ║
║    3. TTS synthesize + play via paplay                                  ║
║    4. MusicDucker.restore() → fade spotifyd sink-input to 100% (250ms) ║
║                                                                         ║
║  ═══ RECORDING FLOW ═══                                                 ║
║                                                                         ║
║  Wake word / button press:                                              ║
║    1. IntelligentRecorder.start()                                       ║
║    2. UI shows "Listening..." (pulsing red dot)                         ║
║    3. VAD detects speech segments, records all audio                    ║
║    4. Silence > 2s → UI shows "Still listening... (28s)"               ║
║    5. Speech resumes → back to "Listening..."                           ║
║    6. Silence > 30s → auto-send to server                              ║
║    7. DOUBLE_PRESS at any time → manual send                            ║
║    8. LONG_PRESS → cancel                                               ║
║                                                                         ║
╚══════════════════════════════════════════════════════════════════════════╝
```

---

## 7. Concrete File Changes

### 7.1 New Files

| File | Purpose |
|---|---|
| `device/audio/music_ducker.py` | PulseAudio per-sink-input volume ducking |
| `device/audio/intelligent_recorder.py` | Long-pause-tolerant recording state machine |
| `device/audio/vad.py` | WebRTC VAD wrapper (promote from worktree) |
| `device/audio/shared_stream.py` | Single mic stream for multiple consumers (promote from worktree) |
| `assets/sounds/agent_ping.wav` | Short notification tone before agent speaks |

### 7.2 Modified Files

#### `device/audio/pipeline.py`

Changes to `WM8960Pipeline`:
- Add `MusicDucker` instance in `__init__`
- Wrap `speak()` with `duck()` / `restore()` calls
- Add optional pre-speech ping sound

```python
# In __init__:
self._ducker = None
try:
    from audio.music_ducker import MusicDucker
    self._ducker = MusicDucker()
except Exception:
    pass

# In speak():
should_duck = self._ducker and self._ducker.is_music_playing()
if should_duck:
    self._ducker.duck()
    time.sleep(0.3)
# ... existing TTS code ...
# In finally block:
if should_duck:
    self._ducker.restore()
```

#### `device/audio/recorder.py`

No changes needed -- `AudioRecorder` remains as the simple push-to-talk recorder. `IntelligentRecorder` is a new class that can coexist. Screens choose which to use based on context.

#### `device/ui/panels/chat_preview.py`

Wire `IntelligentRecorder` for voice input:
- Replace simple record/stop with `IntelligentRecorder.start()` / `.stop_and_send()`
- Add status callback for "Still listening..." UI
- Handle auto-send callback

#### `device/audio/recording_adapter.py`

Add `IntelligentRecordingAdapter` variant:

```python
class IntelligentRecordingAdapter:
    """Adapts IntelligentRecorder to the start/stop/cancel interface."""

    def __init__(self, on_auto_send=None, on_status=None):
        from audio.intelligent_recorder import IntelligentRecorder
        self._recorder = IntelligentRecorder(
            on_auto_send=on_auto_send,
            on_status=on_status,
        )

    def start_recording(self) -> None:
        self._recorder.start()

    def stop_and_process(self) -> RecordingResult:
        wav_bytes = self._recorder.stop_and_send()
        if wav_bytes:
            # Write to temp file for compatibility with existing transcribe() path
            import tempfile
            fd, path = tempfile.mkstemp(prefix="bitos_irec_", suffix=".wav")
            os.close(fd)
            Path(path).write_bytes(wav_bytes)
            return RecordingResult(path=path)
        return RecordingResult(path=None)

    def cancel(self) -> None:
        self._recorder.cancel()

    @property
    def state(self):
        return self._recorder.state
```

#### `device/bluetooth/audio_manager.py`

Add device type detection (already designed in the other doc):

```python
def detect_device_type(self, address: str) -> str:
    info = self._get_device_info(address)
    if info:
        name = info.get("Name", "").lower()
        if "airpods" in name:
            return "airpods"
    return "headphones"
```

### 7.3 New Dependencies

Add to `requirements-device.txt`:

```
pulsectl>=23.5.0     # PulseAudio Python client for per-stream ducking
webrtcvad>=2.0.10    # WebRTC VAD for silence detection
```

`pulsectl` is pure Python, no compiled extensions. Works on Pi Zero 2W.
`webrtcvad` has a small C extension but pre-built wheels exist for ARM.

### 7.4 Settings (DeviceRepository)

New settings keys for companion app configuration:

```python
"music_ducking_enabled": True          # master toggle for ducking
"music_duck_volume": 15                # ducked volume percent (0-100)
"music_duck_fade_ms": 250              # fade duration in ms
"recording_mode": "intelligent"        # "intelligent" or "push_to_talk"
"recording_thinking_threshold_s": 2.0  # silence before THINKING state
"recording_auto_send_threshold_s": 30  # silence before auto-send
"recording_pre_ping": True             # play notification ping before TTS
"airpod_tap_action": "agent"           # single tap: "agent" or "music"
```

---

## Appendix A: Why Not PipeWire Directly?

Pi OS Bookworm ships PipeWire by default, but it provides a PulseAudio compatibility layer (`pipewire-pulse`). The `pactl` commands and `pulsectl` Python library work identically on both. There is no need to use PipeWire-native APIs (`pw-cli`, `libpipewire`).

If the Pi is running Pi OS Lite (no PipeWire, no PulseAudio), the `MusicDucker` gracefully disables itself (no `pulsectl` available). In this case, the fallback is to pause music via Spotify API before TTS and resume after.

## Appendix B: Loopback / Echo Cancellation

**Q: Will the mic pick up the speaker output?**

On the WM8960, the speaker and mic are physically close. At low volumes, loopback is minimal. At high volumes, the mic will pick up some TTS audio. This is not a problem for the intended flow because:

1. Recording and TTS playback do not happen simultaneously. The user speaks first, then the agent responds. There is no full-duplex conversation (yet).
2. If wake word detection runs during TTS, it may false-trigger. Solution: pause wake word detection during `speak()`.
3. For future barge-in (interrupt agent mid-speech), acoustic echo cancellation (AEC) would be needed. The WM8960 does NOT have hardware AEC. Software AEC (e.g., `speexdsp` or `webrtc-audio-processing`) would be needed. This is a future concern, not needed for current design.

When AirPods are the output device, loopback is zero -- the speaker is in the user's ears, not near the WM8960 mic.

## Appendix C: CPU Budget on Pi Zero 2W

| Component | CPU (approx) |
|---|---|
| spotifyd (audio decode) | 10-15% |
| PulseAudio/PipeWire mixer | 2-5% |
| BITOS device UI (pygame) | 15-25% |
| pyaudio mic capture | 1-2% |
| WebRTC VAD | < 1% |
| BT A2DP encoding | 5-10% |
| **Total** | **34-58%** |

This leaves headroom for TTS playback and HTTP client activity. The quad-core ARM Cortex-A53 can distribute these across cores. spotifyd and BT A2DP encoding are the heaviest items. If CPU becomes tight, reducing spotifyd bitrate from 160 to 96 kbps halves its CPU load.
