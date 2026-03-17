# Open Interpreter 01 — Integration Analysis for BITOS

**Date:** 2026-03-16
**Status:** Research complete, pending decision

---

## 1. What is Open Interpreter 01?

The 01 is an open-source platform for building voice-controlled AI assistant devices, created by Open Interpreter (5.1k GitHub stars, AGPL-3.0 license). Think of it as the open-source version of Rabbit R1 or Humane Pin — a natural language voice interface that can execute code on your computer, browse the web, manage files, and control software.

The project explicitly positions itself as "the UNIX of AI devices" — a hackable platform for building custom AI hardware. Their CONTEXT.md cites UNIX, Linux, Raspberry Pi, and Arduino as inspiration, aiming to be affordable (<$100), modular, and developer-friendly.

**Core capability:** You speak to a device, it transcribes your speech, sends it to an LLM, the LLM can run arbitrary Python code on your machine (via Open Interpreter), and speaks the response back. It can control your Mac, search the web, manage calendar/email/SMS, and learn new "skills."

---

## 2. Architecture Breakdown

### 2.1 Two Server Modes

**Light Server** — Simple WebSocket server built on FastAPI (via Open Interpreter's built-in server). Runs STT locally via `faster-whisper` (tiny.en model). TTS via OpenAI, Coqui (local), or ElevenLabs. Designed for direct ESP32 connections.

- Protocol: Raw WebSocket on port 10001
- Audio in: 16-bit PCM, 16kHz, mono (raw bytes over WS)
- Audio out: 16-bit PCM, 24kHz, mono (raw bytes over WS)
- Control messages: JSON over same WebSocket
  - `{"role": "user", "type": "audio", "format": "bytes.raw", "start": true}`
  - `{"role": "user", "type": "audio", "format": "bytes.raw", "end": true}`
  - `{"role": "assistant", "type": "audio", "format": "bytes.wav", "start": true}`
  - `{"role": "assistant", "type": "audio", "format": "bytes.wav", "end": true}`
- Health check: `GET /ping` returns "pong"

**LiveKit Server** — Full-featured voice server using LiveKit (WebRTC infrastructure). Runs a LiveKit media server locally, with an agent worker that connects to it. Used by the mobile app.

- Protocol: LiveKit/WebRTC (not raw WebSocket)
- STT: Deepgram (cloud)
- TTS: OpenAI, ElevenLabs, or Cartesia (cloud)
- VAD: Silero (local)
- The LiveKit worker connects to a Light Server (running on a different port) as an "OpenAI-compatible" LLM backend
- QR code generated for mobile app connection, encodes `{"livekit_server": url}`
- Supports ngrok tunneling for remote access

**Multimodal Mode** — Uses OpenAI's Realtime API (Advanced Voice Mode) directly through LiveKit. Requires OpenAI API key. Gives the LLM a `execute_code` tool that runs Python via Open Interpreter.

### 2.2 LLM Integration

The LLM layer is powered by the `open-interpreter` Python package (AsyncInterpreter), which uses LiteLLM under the hood. This means it supports:

- **Claude/Anthropic** — The default profile literally uses `interpreter.llm.model = "claude-3.5"`
- **OpenAI** — gpt-4o, gpt-4o-mini
- **Local models** — Ollama (codestral, etc.) via the `local.py` profile
- **Any LiteLLM-supported model**

The key insight: Open Interpreter exposes itself as an OpenAI-compatible API (`/openai` endpoint), so the LiveKit worker treats it as just another OpenAI model with `base_url` pointing to localhost.

### 2.3 Code Execution Model

Open Interpreter runs code **directly on the host machine** with no sandboxing. From their README: *"This experimental project is under rapid development and lacks basic safeguards."*

- Executes Python in a stateful Jupyter-like environment
- Has a `computer` module with APIs for: browser (Selenium), calendar, contacts, mail, SMS, files, keyboard/mouse control, display capture
- The multimodal mode has a basic safety check (blocks `os.remove`, `shutil.rmtree`, `rm -`) but it is trivially bypassable
- `auto_run = True` means no confirmation before executing code
- **This is a significant security concern** for any production deployment

### 2.4 Client Implementations

**React Native App (01-app repo):**
- Expo + React Native + TypeScript + MobX State Tree
- Connects to LiveKit server via QR code scan
- Push-to-talk or voice activity detection
- "Wearable mode" for small screens (full-screen button)
- Available on App Store and Google Play
- Customizable: `theme/` directory, `screens/`, standard React Native architecture
- Package manager: Bun

**Native iOS App:**
- Swift/Xcode, connects to Light Server via WebSocket
- Manual WebSocket address entry in settings
- Simple UI: speak button (yellow circle), settings, reconnect indicator, terminal view
- Available via TestFlight or build from source

**ESP32 Client (M5Atom Echo):**
- Arduino/PlatformIO firmware (`client.ino`)
- M5Atom board with built-in mic + speaker
- I2S audio: 16kHz record, 24kHz playback, 16-bit mono
- WebSocket connection to Light Server
- Button press to record, release to send
- Captive portal for WiFi + server setup (creates "01-Light" AP)
- Stored credentials in ESP32 Preferences (persistent flash)
- Libraries: M5Atom, WebSockets, AsyncTCP, ESPAsyncWebServer

**Light Python Client:**
- Desktop client using PyAudio + websockets + pynput
- Push-to-talk via CTRL key
- Same WebSocket protocol as ESP32

### 2.5 Technology Stack Summary

| Component | Technology |
|-----------|-----------|
| Server framework | FastAPI (via Open Interpreter) |
| Voice transport (light) | Raw WebSocket, 16-bit PCM |
| Voice transport (livekit) | WebRTC via LiveKit |
| STT (light) | faster-whisper (local, tiny.en) |
| STT (livekit) | Deepgram (cloud) |
| TTS | OpenAI / ElevenLabs / Cartesia / Coqui (local) |
| VAD | Silero |
| LLM | LiteLLM (Claude, GPT-4o, Ollama, etc.) |
| Code execution | Open Interpreter (unsandboxed Python) |
| Mobile app | React Native / Expo / TypeScript |
| ESP32 firmware | Arduino/PlatformIO, M5Atom |
| Tunneling | ngrok |

---

## 3. Integration Strategies

### Strategy A: BITOS Server as 01-Compatible Backend

**Concept:** Make the BITOS FastAPI server speak the 01 Light Server protocol, so any 01 client (ESP32, mobile app native iOS, desktop) can connect directly to BITOS.

**What to implement:**
1. Add a WebSocket endpoint that accepts the 01 audio protocol (JSON control messages + raw PCM bytes)
2. Add a `GET /ping` endpoint returning "pong"
3. Wire incoming audio to BITOS's existing STT pipeline
4. Route transcribed text through BITOS's agent (consciousness, memory, tools, etc.)
5. Stream TTS audio back as raw PCM bytes over the same WebSocket

**Tradeoffs:**

| Pro | Con |
|-----|-----|
| Full control — BITOS agent personality, memory, consciousness layer all active | Must implement the audio WS protocol (moderate effort) |
| 01 ESP32 hardware becomes a BITOS fob with zero firmware changes | No code execution capability (but BITOS doesn't need/want unsandboxed code exec) |
| Native iOS app works immediately (just point WebSocket at BITOS) | LiveKit app requires more work (need LiveKit server setup) |
| Mini phone with native iOS app = instant BITOS mobile client | 01 protocol is underdocumented and may change |
| Keeps BITOS as the single brain | |

**Effort:** Medium (1-2 weeks). The WebSocket audio protocol is straightforward — JSON start/end markers plus raw PCM bytes. BITOS already has `/ws/voice` which does something similar.

### Strategy B: Use 01 Server as BITOS Backend

**Concept:** Run the 01 server and point it at BITOS's LLM/agent layer instead of raw Open Interpreter.

**What to implement:**
1. Create a BITOS profile for 01 (like `default.py`) that configures the interpreter to use BITOS's agent
2. Or: expose BITOS's chat endpoint as an OpenAI-compatible API so 01's LiveKit worker can call it
3. Run 01's server infrastructure (LiveKit, STT, TTS) as-is

**Tradeoffs:**

| Pro | Con |
|-----|-----|
| Get LiveKit (WebRTC) + mobile app for free | Adds heavy dependencies (LiveKit server, deepgram, etc.) |
| Battle-tested voice pipeline | BITOS agent features (consciousness, blob, memory) harder to integrate |
| Multimodal mode available | Two servers to manage and keep running |
| Less custom code to write | Open Interpreter's unsandboxed code exec is a liability |
| | AGPL license is viral — any modifications must be open-sourced |
| | Lose direct control of the voice pipeline |

**Effort:** Medium-High (2-3 weeks). Getting the LLM bridge right is fiddly. LiveKit setup adds operational complexity.

### Strategy C: Cherry-Pick Components

**Concept:** Don't adopt 01 wholesale. Instead, extract specific valuable pieces and integrate them into BITOS's existing architecture.

**What to cherry-pick:**
1. **ESP32 firmware** — Fork the `client.ino`, adapt it for BITOS's WebSocket protocol (or adapt BITOS to match)
2. **React Native app** — Fork `01-app`, rip out LiveKit, replace with direct WebSocket to BITOS, reskin with BITOS branding and blob animation
3. **Captive portal pattern** — The ESP32's WiFi setup flow is well-engineered, adopt it for BITOS fob
4. **Profile system** — The idea of swappable LLM profiles is clean, could inform BITOS agent modes

**Tradeoffs:**

| Pro | Con |
|-----|-----|
| Take only what you need | More upfront work to extract and adapt |
| No AGPL concerns if you rewrite (vs. forking) | Must maintain forked components yourself |
| BITOS identity stays pure | React Native app fork = ongoing merge conflicts |
| Can evolve independently | |
| Best long-term flexibility | |

**Effort:** Variable. ESP32 firmware adaptation is small (days). React Native app fork is large (weeks).

---

## 4. Recommended Approach

**Strategy A (BITOS as 01-compatible backend) for the mini phone, combined with selective cherry-picking from Strategy C for hardware.**

Here is the reasoning:

### For the Mini Phone (Immediate Win)

The 01 **native iOS app** connects via plain WebSocket to a Light Server. The protocol is dead simple:

```
Client → Server:  JSON {"role":"user","type":"audio","format":"bytes.raw","start":true}
Client → Server:  [raw 16-bit PCM bytes at 16kHz]
Client → Server:  JSON {"role":"user","type":"audio","format":"bytes.raw","end":true}

Server → Client:  JSON {"role":"assistant","type":"audio","format":"bytes.wav","start":true}
Server → Client:  [raw 16-bit PCM bytes at 24kHz]
Server → Client:  JSON {"role":"assistant","type":"audio","format":"bytes.wav","end":true}
```

BITOS already has `/ws/voice` for device audio streaming. Adding a `/ws/01-compat` endpoint (or adapting `/ws/voice`) that speaks this protocol would let the native iOS 01 app connect to BITOS. Install the native iOS app on the mini phone, point it at the BITOS server's IP, and you have a BITOS mobile client with zero app development.

**Steps:**
1. Add `GET /ping` returning "pong" to BITOS server
2. Add WebSocket endpoint accepting the 01 audio protocol
3. On `{"start": true}`: begin buffering incoming PCM audio
4. On `{"end": true}`: run STT on buffered audio, feed text to BITOS agent
5. Stream TTS response back as PCM bytes with start/end markers
6. Install native iOS 01 app on mini phone, enter BITOS server address

### For the ESP32 Fob (Near-Term)

The 01 ESP32 firmware (M5Atom Echo) uses the exact same WebSocket protocol. If BITOS implements Strategy A, the ESP32 fob works automatically. The key difference from the current BITOS fob plan:

- 01 uses M5Atom Echo ($13 board with mic + speaker + button + LED)
- Same ESP32-S3 family as BITOS's planned fob
- Captive portal for WiFi setup is production-quality code worth studying
- Could use 01's firmware directly, or adapt BITOS's planned firmware to match

### For the React Native App (Future)

The 01 React Native app connects via LiveKit, which is heavier infrastructure. Two options:
1. **Quick:** Fork the native iOS app (simpler, WebSocket-based) and reskin it
2. **Long-term:** Fork the React Native app, replace LiveKit with direct WebSocket, add blob animation, BITOS branding

### What NOT to Adopt

- **Open Interpreter's code execution** — BITOS is a companion, not a code runner. The unsandboxed execution model is a security nightmare.
- **LiveKit server** — Adds operational complexity with minimal benefit over direct WebSocket for BITOS's use case.
- **The 01 server itself** — BITOS's FastAPI server with consciousness/memory/blob is far more sophisticated. The 01 server is essentially just a voice wrapper around Open Interpreter.

---

## 5. Risks and Limitations

### License (AGPL-3.0)
The 01 project is AGPL-licensed. If you fork and modify their code (app or server), you must open-source your modifications. This applies to the React Native app and ESP32 firmware. However:
- **Using the unmodified app as-is** to connect to BITOS is fine (no modification)
- **Reimplementing the protocol** in BITOS server code is fine (no copying)
- **Forking the ESP32 firmware** would require open-sourcing the fork

If BITOS is intended to stay proprietary, either use the 01 apps unmodified or reimplement protocols from scratch.

### Protocol Stability
The 01 project is at version 0.0.14 and explicitly warns it's "under rapid development." The WebSocket protocol could change. Mitigation: the Light Server protocol is so simple (JSON markers + PCM bytes) that any changes would be trivial to adapt to.

### Audio Format Assumptions
The ESP32 firmware hardcodes 16kHz input / 24kHz output sample rates. The native iOS app likely does the same. BITOS's audio pipeline must match these rates or resample.

### No Authentication
The 01 Light Server has no authentication by default (there's a commented-out auth mechanism in the client code). Anyone on the network can connect. BITOS should add authentication to the 01-compatible endpoint.

### Quality of 01 Codebase
The code is functional but rough — commented-out blocks, duplicate settings, `if False:` debug code, inconsistent patterns. It's a fast-moving prototype, not production-grade. This is fine for protocol reference but means forked code needs cleanup.

### M5Atom Echo Hardware Limitations
The M5Atom Echo is a $13 dev board with a tiny built-in speaker. Audio quality is limited. The BITOS fob design (ESP32-S3 + external speaker + OLED) would be significantly better hardware.

---

## 6. Quick Reference

| Question | Answer |
|----------|--------|
| App framework? | React Native (Expo) for cross-platform, Swift for native iOS |
| Server protocol? | WebSocket (Light Server) or WebRTC/LiveKit (LiveKit Server) |
| Audio format? | 16-bit PCM mono, 16kHz in / 24kHz out, raw bytes over WS |
| Can it use Claude? | Yes — default profile already uses `claude-3.5` via LiteLLM |
| Code execution sandboxing? | None. Full unsandboxed access to host machine. |
| Can BITOS be an 01 server? | Yes — implement the simple WS audio protocol |
| Can 01 server be BITOS backend? | Possible but not recommended (loses BITOS features) |
| ESP32 for BITOS fob? | Same family (ESP32-S3), protocol compatible, but BITOS hardware is better |
| Can you reskin the app? | Yes — standard React Native theming, or use native iOS app |
| Mini phone support? | Install native iOS 01 app, point at BITOS server address |

---

## 7. Implementation Priority

1. **Week 1:** Add 01-compatible WebSocket endpoint to BITOS server (`/ws/01` or adapt `/ws/voice`)
2. **Week 1:** Test with native iOS app on mini phone
3. **Week 2:** Test with 01 ESP32 firmware on M5Atom Echo (cheap validation)
4. **Week 3+:** Decide whether to fork native iOS app for custom BITOS UI or keep using stock 01 app
5. **Future:** Consider React Native app fork with blob animation for a premium BITOS mobile experience
