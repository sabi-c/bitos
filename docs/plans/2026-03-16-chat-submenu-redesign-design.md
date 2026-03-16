# Chat Submenu Redesign — Design

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebuild the chat preview panel as an ambient agent presence with greeting sessions, voice-first interaction from the submenu, and gesture cleanup.

**Architecture:** Greeting sessions as a special session type in the repository. ChatPreviewPanel gets a response field as the first interactive element. Full ChatPanel removes LONG_PRESS (conflicts with hold), exit via actions menu only. Settings screen for agent configuration.

**Tech Stack:** pygame, existing CompositeScreen/PreviewPanel, TypewriterRenderer, BackendClient, DeviceRepository (SQLite)

---

## 1. Layout (156x208px preview panel)

```
┌──────────────────────┐
│ good morning. you've  │  ← greeting banner (top ~60px)
│ got 3 tasks today,   │    slow typewriter, dimmed
│ one from anthony_    │    blinking cursor while typing
├──────────────────────┤
│ > [● record]          │  ← response field (item 0)
├──────────────────────┤
│   START NEW CHAT      │  ← item 1
│   RESUME CHAT         │  ← item 2 (subtext: "morning brief · 2h ago")
│   CHAT HISTORY        │  ← item 3
│   SETTINGS            │  ← item 4
│   BACK TO MAIN MENU   │  ← item 5
└──────────────────────┘
```

- **Greeting banner**: ~3-4 lines, always visible, not selectable. Slow typewriter animation plays when first scrolling to CHAT. On subsequent visits in the same session, text is already revealed.
- **Response field**: first selectable item. Blinking cursor icon + dimmed "record" hint. DOUBLE_PRESS starts recording → transcribe → "starting conversation..." → opens full ChatPanel continuing the greeting session.
- **No highlight** on any submenu item when in sidebar mode. First item (response field) highlights only on DOUBLE_PRESS to enter submenu focus.
- **RESUME CHAT**: subtext shows last chat title + relative time (e.g., "morning brief · 2h ago").

## 2. Greeting Session Lifecycle

```
BOOT / 1hr+ idle
  → Backend call: POST /chat with greeting prompt (~80-100 chars)
  → Response stored as greeting session (session_type="greeting")
  → Preview panel shows response with slow typewriter

USER REPLIES (from response field)
  → Recording → transcribe → continues greeting session
  → Transitions to full ChatPanel with greeting session loaded
  → Banner updates on return to preview

RETURN TO PREVIEW (same session)
  → Greeting text persists (no re-fetch)
  → If conversation happened, agent can provide updated banner text

NEW BOOT / 1hr+ gap
  → New greeting session created
  → Old greeting session becomes regular history
```

Greeting prompt sent to backend includes:
- Instruction to keep response under 100 characters
- Living context (time, weather, tasks, calendar)
- Format: casual, lowercase, no emojis

## 3. Gesture Map (Full Chat Screen)

| Gesture | IDLE | RECORDING | ACTIONS | STREAMING | SPEAKING |
|---------|------|-----------|---------|-----------|----------|
| Tap | Field record | Stop & send | Next item | — | Stop |
| Hold+Release | Quick talk | — | — | — | — |
| Double | Actions menu | — | Select item | — | — |
| Triple | (reserved for page nav) | — | Prev item | — | — |
| Long press | **removed** | Cancel | Cancel | — | — |

- **No LONG_PRESS exit in chat** — conflicts with hold gesture.
- Exit via: Actions menu → "BACK TO MAIN MENU" item.
- Actions menu items: existing templates + BACK TO MAIN MENU at the end.
- LONG_PRESS during RECORDING still cancels (intentional — requires deliberate press, distinct from hold-to-record release).

## 4. Submenu Navigation (CompositeScreen)

Current behavior change:
- Sidebar focused: preview panel renders with **no highlighted item** (selected_index = -1 or similar).
- DOUBLE_PRESS on sidebar: enters submenu, sets selected_index to 0 (response field).
- SHORT_PRESS in submenu: next item.
- DOUBLE_PRESS in submenu: execute item action.
- LONG_PRESS in submenu: back to sidebar (unchanged).
- "BACK TO MAIN MENU" action: returns focus to sidebar.

## 5. Settings Screen (v1)

Full-screen panel opened from SETTINGS submenu item:

```
┌──────────────────────────────┐
│ CHAT SETTINGS                │  status bar
├──────────────────────────────┤
│ META PROMPT                  │
│ "you are a helpful assis..." │  ← truncated, dimmed
│                              │
│ TEXT SPEED         normal    │
│ VOICE SPEED        normal    │
├──────────────────────────────┤
│ tap: select · double: edit   │
│ hold: speak to update        │
└──────────────────────────────┘
```

- Tap cycles through settings items.
- Double-press selects a setting for editing.
- Hold to speak → agent transcribes intent → updates the setting value.
- v1 settings: meta prompt summary, text speed, voice speed. More added later.

## 6. Data Model Changes

**Sessions table** — add `session_type` column:
```sql
ALTER TABLE sessions ADD COLUMN session_type TEXT DEFAULT 'chat';
-- Values: 'greeting', 'chat'
```

**New repository methods:**
- `get_greeting_session()` → latest greeting session < 1hr old, or None
- `create_greeting_session(greeting_text)` → creates session with session_type="greeting"
- `get_latest_chat_session()` → latest session where session_type="chat" (for RESUME CHAT)

## 7. Typewriter Speed

Add `"slow"` preset to TypewriterRenderer:
```python
SPEED_PRESETS = {
    "slow": 80.0,      # ~8-10s for 100 chars — ambient greeting
    "normal": 30.0,    # ~3s for 100 chars — conversation
    "fast": 15.0,      # ~1.5s for 100 chars
    "instant": 0.0,
}
```

With existing punctuation pauses and jitter, a 4-line greeting (~100 chars) takes ~8-10 seconds. Feels calm and ambient.

## 8. Files to Create/Modify

- **Modify:** `device/ui/panels/chat_preview.py` — greeting banner, response field, slow typewriter, subtext on RESUME
- **Modify:** `device/ui/panels/base.py` — support selected_index=-1 (no highlight) state
- **Modify:** `device/ui/composite_screen.py` — no highlight on submenu entry until DOUBLE_PRESS
- **Modify:** `device/screens/panels/chat.py` — remove LONG_PRESS exit, add BACK TO MAIN MENU in actions
- **Modify:** `device/display/typewriter.py` — add "slow" speed preset
- **Modify:** `device/storage/repository.py` — session_type column, greeting session methods
- **Create:** `device/screens/settings_panel.py` — chat settings full-screen
- **Modify:** `device/ui/panel_registry.py` — wire settings opener
- **Modify:** `device/main.py` — greeting fetch on boot, settings opener, pass greeting session to preview
