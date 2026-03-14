# BITOS · FUNCTIONALITY ROADMAP

Each feature tagged: Phase / Effort (S=days, M=1-2wk, L=month+) /
Dependency / Value.

## Theme 1: Home Screen Widgets
1.1 Configurable Widget System (v1.5, M) — replace fixed home panel.
    Widget protocol: render(surface, rect, tokens), tick(dt_ms), handle_input.
    Slots: top (clock), middle (info), bottom (status). Config in Settings.
1.2 Streak/Habit Tracker Widget (v2, S) — daily habit + 7-day heatmap.
1.3 Calendar Next Event Widget (v2, S) — next event within 24h.

## Theme 2: Conversation Features
2.1 Conversation Branching (v2, M) — parent_message_id in schema NOW
    (add column even if UI comes later). Context menu: BRANCH option.
2.2 Conversation Templates / Starter Prompts (v1.5, S) — pre-configured
    prompts in Settings → Templates. Show as Quick Replies before first message.
2.3 In-Thread Search (v2, S) — uses existing FTS5 table.

## Theme 3: Voice + Audio
3.1 Wake Word (v1.5, S) — "Hey Bitos" via openWakeWord (MIT, no API cost).
    Background thread, low sensitivity, toggle in Settings.
3.2 Piper TTS Fallback (v1.5, S) — local TTS when ElevenLabs/OpenAI unavailable.
    Model: en_US-lessac-medium (63MB). AutoFallbackTTS tries cloud first.
3.3 Voice Notes (v2, M) — dedicated section, record+transcribe+Obsidian sync.
3.4 Music Playback (v2, M) — WM8960 speaker, conflict resolution with mic needed.

## Theme 4: AI Intelligence
4.1 Global Workspace (v2, L) — persistent shared memory, injected every turn.
    TodayContext + BackgroundCtx + recent Insights. Updated by background workers.
4.2 Agent Mode Injection (v1.5, S) — server reads agent_mode setting,
    selects from AGENT_MODES dict, injects before user message. Already specced.
4.3 Proactive Notifications (v2, M) — max 3/day, rate-limited.
    Sources: overdue tasks, upcoming events, pattern detection, daily brief.
4.4 Memory/Fact Store (v3, L) — explicit facts from conversation.
    Stored in facts table, retrieved via FTS5 or embeddings.

## Theme 5: Connectivity + Companion
5.1 BLE Companion WiFi (v1.5, M) — QR code + PWA. Core use case. (P5-011/012)
5.2 BLE Keyboard Input (v1.5, M) — phone keyboard → device compose fields.
5.3 PWA vs Native iOS (decision) — PWA for v1 (no review), native for v2.

## Theme 6: Developer + Ops
6.1 Tailscale Remote Access (v1.5, S) — SSH/VNC/DB browser. Do this first.
6.2 sqlite-web (v1.5, S) — browse conversation DB remotely via browser.
6.3 Performance Debug Overlay (v1.5, S) — long press during boot.
6.4 OTA Updates (v3, L) — device polls backend, user confirms, never auto.

## Theme 7: Camera
7.1 Pi Camera Module 3 (v3, M) — CSI port, visual Claude input.
    "What is this?" / "Read this label". Quick Capture PHOTO option.
    whisplay-ai-chatbot case designs already accommodate camera module.

## Deprioritized
| Feature | Reason |
|---|---|
| LLM8850 offline AI | Different hardware |
| Speaker recognition | Privacy + training data |
| Multi-device sync | One device in v1 |
| n8n workflows | Infrastructure complexity before core stable |
| Image generation | Not core |
| Spotify streaming | OAuth complexity |
| Email compose full | Read + view enough for v1 |

## Build Sequence
v1   (now): Core voice loop + nav + tasks + settings + notifications + BLE
v1.5 (next): Tailscale + wake word + Piper TTS + BLE companion + widget system
v2   (month 2-3): Global workspace + proactive AI + voice notes + branching
v3   (month 4+): OTA updates + camera + memory/facts + multi-device
