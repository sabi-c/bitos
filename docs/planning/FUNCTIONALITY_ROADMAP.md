# BITOS · FUNCTIONALITY ROADMAP
## docs/planning/FUNCTIONALITY_ROADMAP.md
## v1.0 · March 2026

---

## HOW TO READ THIS DOCUMENT

Each feature is tagged with:
- **Phase** — when it fits in the build order
- **Effort** — S (days) / M (1-2 weeks) / L (month+)
- **Dependency** — what must be built first
- **Value** — why it matters

Features are grouped by theme. Within each group they're ordered
by recommended build sequence.

---

## THEME 1: HOME SCREEN WIDGETS

### 1.1 Configurable Widget System
**Phase:** v1.5 · **Effort:** M · **Dependency:** Home panel stable

Replace the fixed home panel layout with a widget system.
Each widget is a small class:

```python
class Widget(Protocol):
    def render(self, surface, rect, tokens) -> None: ...
    def tick(self, dt_ms: int) -> None: ...  # optional animation
    def handle_input(self, event) -> bool: ...  # optional interactivity
```

User can configure which widgets appear in Settings → Home.
Widget slots: top (large, clock area), middle (medium, info area),
bottom (small, status area).

Built-in widgets v1: Clock, Weather, Next Task, AI Status.
Built-in widgets v2: Pomodoro Status, Now Playing, Unread Count,
Calendar Next Event, Streak Counter.

### 1.2 Streak / Habit Tracker Widget
**Phase:** v2 · **Effort:** S · **Dependency:** Widget system

Shows a compact streak count for a habit (meditation, workout,
writing session). Incremented via Quick Capture ("did my morning
sit") or manually via the widget. Stored in DB. Shows a tiny
pixel heatmap of last 7 days.

### 1.3 Calendar Next Event Widget
**Phase:** v2 · **Effort:** S · **Dependency:** Calendar MCP (Phase 5)

Shows the next calendar event within 24 hours. Title truncated to
fit, time shown prominently. Long press opens full event detail.

---

## THEME 2: CONVERSATION FEATURES

### 2.1 Conversation Branching
**Phase:** v2 · **Effort:** M · **Dependency:** Chat thread stable

Allow branching from any message in a conversation — "take this
in a different direction from here." Stored as a tree
(parent_message_id column, add in schema now even if UI comes later).

Context menu on any message: COPY / REGEN / BRANCH / SAVE / DELETE.
BRANCH creates a new session starting from that message's context.
History screen shows branches as indented under parent session.

### 2.2 Conversation Templates / Starter Prompts
**Phase:** v1.5 · **Effort:** S · **Dependency:** None

Pre-configured prompt starters accessible from Chat panel.
User defines them in Settings → Templates.

Examples:
- "MORNING BRIEF" → "Give me a quick rundown of my tasks, events, and anything I should know today."
- "TENDER FEST BRAIN" → "I want to brainstorm Tender Fest. Here's what I'm thinking..."
- "CODE REVIEW" → "Review this code and suggest improvements focusing on..."

Quick Replies row in chat could show these as options before first message.

### 2.3 Conversation Search (In-Thread)
**Phase:** v2 · **Effort:** S · **Dependency:** Global search

Search within a single conversation thread.
Already served by the FTS5 table — just need a UI surface.
Context menu on history → SEARCH THIS CHAT.

---

## THEME 3: VOICE + AUDIO

### 3.1 Wake Word (Hands-Free Trigger)
**Phase:** v1.5 · **Effort:** S · **Dependency:** Audio pipeline

"Hey Bitos" triggers voice input without button press.
Infrastructure already in whisplay-ai-chatbot repo.
Library: openWakeWord (MIT license, no API cost, runs on Pi Zero 2W).

Toggle in Settings → Wake Word (off by default — increases power draw).

Implementation note: wake word detection runs in a background thread
at very low sensitivity. On detection, fire the same voice input
flow as LONG press. The main loop doesn't need to change.

### 3.2 Local TTS via Piper (Offline Fallback)
**Phase:** v1.5 · **Effort:** S · **Dependency:** Audio pipeline

When ElevenLabs/OpenAI TTS is unavailable (offline), fall back to
piper TTS (MIT license, runs on Pi Zero 2W at ~2-4x realtime).

```bash
# Install
pip install piper-tts

# Usage
echo "Hello Seb" | piper --model en_US-lessac-medium --output_file /tmp/tts.wav
aplay /tmp/tts.wav
```

Sound quality is noticeably lower than ElevenLabs but fully
intelligible. Show "LOCAL TTS" indicator in status bar when active.

LLM bridge already supports provider abstraction —
TTS bridge should mirror this pattern:
```python
class TTSBridge:
    def speak(self, text: str) -> None: ...
```
Provider selected by `TTS_PROVIDER` env var: elevenlabs / openai / piper.

### 3.3 Voice Notes as First-Class Type
**Phase:** v2 · **Effort:** M · **Dependency:** Audio pipeline

Dedicated Voice Notes section in sidebar.
Record → Whisper transcription → stored locally.
Optional: sync transcript to Obsidian via REST API.

Each note: audio file at /home/pi/bitos/audio/notes/, transcript in DB.
Playback: aplay through WM8960 speaker.

Long press on note: PLAY / TRANSCRIBE AGAIN / SEND TO CLAUDE / DELETE.
"SEND TO CLAUDE" opens chat with note transcript pre-loaded as context.

### 3.4 Music Playback via WM8960 Speaker
**Phase:** v2 · **Effort:** M · **Dependency:** Voice notes (conflict resolution)

The WM8960 speaker can play music, but using it for music conflicts
with mic use for voice. Architecture needed:

- Music player uses pygame.mixer or aplay subprocess
- Voice input detection: pause music on button hold, resume after response
- Never play music and record mic simultaneously

Music source v1: local MP3s in /home/pi/music/
Music source v2: Spotify via spotipy library (read-only, cast to device)

---

## THEME 4: AI INTELLIGENCE

### 4.1 Global Workspace / Persistent Context
**Phase:** v2 · **Effort:** L · **Dependency:** All Phase 1-5 stable

The "consciousness" layer. A persistent shared memory store that
all agents read and the orchestrator injects into every conversation.

```python
class GlobalWorkspace:
    """
    Updated by background workers.
    Read by orchestrator on every turn.
    Makes Claude feel like it knows you.
    """
    today: TodayContext        # tasks, events, weather, energy
    background: BackgroundCtx  # projects, people, patterns
    recent: list[Insight]      # distilled from last 7 days
    
    def get_injection(self) -> str:
        """Returns formatted context block for system prompt."""
```

Background workers (run on schedule, never blocking UI):
- **Morning Brief** (8am): pull tasks + events + weather
- **Session Distiller** (after each conversation): compress insights
- **Notification Dispatcher** (continuous, low-priority): watch triggers

### 4.2 Agent Mode Context Injection
**Phase:** v1.5 · **Effort:** S · **Dependency:** Settings wiring

Each agent mode gets a richer system prompt. Already specced in
BACKEND_SPEC.md. Implementation: server reads `agent_mode` setting
from request headers, selects prompt from AGENT_MODES dict,
injects before user message.

### 4.3 Proactive AI Notifications
**Phase:** v2 · **Effort:** M · **Dependency:** Global workspace + notifications

Claude proactively surfaces thoughts without being asked.
Triggered by:
- Task overdue (already in P4-004)
- Upcoming event (15min warning)
- Pattern recognition ("you haven't worked on Tender Fest in 5 days")
- Opportunity detection ("Joaquin hasn't replied in 48h — follow up?")
- Daily brief (8am, via scheduled task)

Rate limit: max 3 proactive notifications per day (configurable).
User can mute any source in Settings → Notifications.

### 4.4 Conversation Templates with AI Routing
**Phase:** v2 · **Effort:** S · **Dependency:** Agent modes

When user picks an agent mode template, switch mode automatically.
"CLOWN BRAINSTORM" → switches to Clown mode → opens chat.
"MORNING FOCUS" → switches to Monk mode → runs morning brief.
Feels like selecting a "preset" personality for the session.

### 4.5 Memory / Fact Store
**Phase:** v3 · **Effort:** L · **Dependency:** Global workspace

Explicit memory: Claude can save facts during conversation.
"Remember that Joaquin's extension is ext. 405."
Stored in a facts table, retrieved via semantic search (embeddings).
Shown in Settings → Memory → Manage Facts.

User can review, edit, and delete any stored fact.
No fact is stored without being shown to user in a toast:
"SAVING: Joaquin ext. 405 → FACTS" with dismiss option.

---

## THEME 5: CONNECTIVITY + COMPANION

### 5.1 BLE Companion — WiFi Provisioning
**Phase:** v1.5 · **Effort:** M · **Dependency:** BLE GATT server (P5)

Companion app (PWA or native) connects via BLE.
Primary use case v1: configure WiFi when device has no network.
See BLUETOOTH_NETWORK_SPEC.md for full protocol.

### 5.2 Companion App — Keyboard Input
**Phase:** v1.5 · **Effort:** M · **Dependency:** BLE companion

Phone keyboard → active compose field on device.
Essential for email compose, settings input, search.
BLE characteristic: KEYBOARD_INPUT (write, auth required).
Device renders text as it arrives.

### 5.3 PWA Companion vs Native iOS
**Phase:** v1.5 · **Effort:** S (decision) / L (native) / M (PWA)

**PWA (recommended for v1):**
- Web Bluetooth API supported in Chrome on Android, some iOS 16+
- No App Store review
- Deploy as a static site (GitHub Pages or Vercel, free)
- Limitations: iOS Safari has partial Web Bluetooth support

**Native iOS (v2):**
- Full CoreBluetooth access
- Background BLE connection (stays connected when app not visible)
- Can enable BT PAN internet sharing
- Requires App Store review

**Recommendation:** Ship PWA first, migrate to native when
background BLE connection becomes important.

### 5.4 SMS Sending (v2, not v1)
**Phase:** v2 · **Effort:** M · **Dependency:** Permission gate stable

Read-only in v1. v2 adds send via tier-2 permission gate.
Full message shown on screen before send.
Contact name shown prominently (not just number).
Only send to existing threads (no new numbers from voice — too risky).

---

## THEME 6: DEVELOPER + OPERATIONAL

### 6.1 Tailscale Remote Access
**Phase:** v1.5 · **Effort:** S · **Dependency:** None (infrastructure)

See BLUETOOTH_NETWORK_SPEC.md.
Enables: SSH, VNC, remote DB browser, remote log streaming.
Install this before doing hardware testing — you'll want it constantly.

### 6.2 sqlite-web for Remote DB Inspection
**Phase:** v1.5 · **Effort:** S · **Dependency:** Tailscale

```bash
pip install sqlite-web
sqlite_web ~/bitos/server/bitos.db --port 8080 --host 0.0.0.0
```

Access from Mac: http://bitos:8080
Browse conversations, check notification records, inspect settings.
Run as a systemd service on-demand (not always-on).

### 6.3 Performance Debug Overlay
**Phase:** v1.5 · **Effort:** S · **Dependency:** Main render loop stable

Hidden overlay: long press during boot screen.
Shows: frame time, DB query time, last API latency, RAM, CPU.
Invaluable for Pi-specific performance debugging.

### 6.4 OTA Updates (v3)
**Phase:** v3 · **Effort:** L · **Dependency:** Stable production

Device polls for updates via backend.
If new version available: download to /tmp, verify checksum,
show "UPDATE AVAILABLE" in status bar.
User confirms in Settings → About → Update.
Never auto-update — always user-confirmed.

---

## THEME 7: CAMERA (FUTURE HARDWARE)

### 7.1 Camera Module 3 Integration
**Phase:** v3 · **Effort:** M · **Dependency:** Additional hardware

Pi Camera Module 3 connects to CSI port on Pi Zero 2W.
Adds visual input to Claude: "what is this?" / "read this label" /
"who made this?" / "describe what you see."

Quick Capture overlay: add PHOTO option alongside VOICE.
Triple press → overlay → SHORT cycles VOICE/PHOTO.
PHOTO: camera preview on screen, button to capture, send to Claude.

Architecture: the multimodal Claude API call is identical to text,
just with an image block added. Already supported in claude-sonnet-4-6.

The whisplay-ai-chatbot case designs already accommodate the camera
module — physical space is available.

---

## DEPRIORITIZED (ASSESS LATER)

| Feature | Why deprioritized |
|---|---|
| LLM8850 offline AI | Different hardware, significant integration work |
| Speaker recognition | Requires training data, privacy implications |
| Multi-device sync | One device in v1; add when v2 hardware exists |
| n8n workflow automation | Infrastructure complexity before core is stable |
| LibreChat web UI | Device UI is the primary surface |
| Image generation | Useful but not core to the assistant use case |
| Spotify streaming | Music is v2; streaming adds OAuth complexity |
| Email client full features | Read + view is enough for v1 |

---

## BUILD SEQUENCE RECOMMENDATION

```
v1   (now):  Core voice loop + nav + tasks + settings + notifications
v1.5 (next): Tailscale + wake word + piper TTS + BLE companion (WiFi) + widget system
v2   (month 2-3): Global workspace + proactive AI + voice notes + branching + SMS send
v3   (month 4+): OTA updates + camera + memory/facts + multi-device
```

The line between v1.5 and v2 is roughly: "things that make the
device more reliable and connected" (v1.5) vs "things that make
the AI smarter and more proactive" (v2).
