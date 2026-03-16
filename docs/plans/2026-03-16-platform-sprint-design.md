# BITOS Platform Sprint Design

**Goal:** Wire up OTA update notifications, agent permission popups, companion app settings, and recording UX fix. Lay groundwork for ai-agent-env consciousness patterns.

**Architecture:** Extend existing notification banner, agent tools, and companion PWA. BLE + HTTP dual-path for companion. Incremental adoption of GWT/context engineering from ai-agent-env.

---

## 1. Update Notification Flow

**Current state:** OTA system fully implemented (`/device/update`, `/device/version`, `scripts/ota_update.sh`). No UI notification when updates land.

**Design:**
- On service restart (detected via version change or startup flag), check `/device/version` for `update_available`
- If update available, show notification banner: **"Update ready"**
- Hints: `tap: install` / `hold: dismiss`
- Tap → POST `/device/update` with `confirmed: true`, show "Updating..." toast, services restart automatically
- Hold → dismiss, no snooze (update available persists in version check)
- In main Settings panel: show firmware version + "Update Firmware" action item
- Selecting it triggers manual version check and update

**Files to modify:**
- `device/main.py` — add version check on startup
- `device/screens/panels/settings.py` — add firmware version + update item
- Existing notification banner handles the UI

---

## 2. Agent Permission Popups (Approval Overlay)

**Purpose:** Reusable overlay for agent-initiated approval requests. The agent asks permission before high-impact actions.

**Design:**

### Overlay UI
- Bottom card overlay (similar to SpeakingOverlay but taller)
- Shows: request text (1-2 lines) + selectable options (2-3 items)
- Options rendered as horizontal pills or vertical list
- Selected option highlighted in white, others dim

### Gestures
- **Tap:** cycle to next option
- **Double-tap:** select highlighted option
- **Hold:** dismiss/cancel (always available)

### Agent Tool
New tool: `request_approval`
```json
{
  "prompt": "Turn on voice mode?",
  "options": ["Yes", "No"],
  "blocking": true
}
```

### SSE Event
```json
{"approval_request": {"id": "req_abc", "prompt": "...", "options": [...], "blocking": true}}
```

### Flow
- **Blocking mode:** Agent tool call pauses, server holds connection, device sends choice back via POST `/chat/approval` → server returns tool result → agent continues
- **Side-channel mode:** Agent finishes response, approval shows as follow-up notification. Choice stored in device settings (`pending_approval`), included in next chat context

### Guardrails
- Max 3 options per request
- Timeout: 60s for blocking, then auto-dismiss with "no response"
- Agent cannot chain more than 2 approval requests per conversation turn

**Files to create/modify:**
- `device/overlays/approval_overlay.py` — new overlay
- `device/screens/panels/chat.py` — wire overlay, handle SSE event
- `device/client/api.py` — parse `approval_request` events, POST choice
- `server/agent_tools.py` — add `request_approval` tool
- `server/main.py` — add `/chat/approval` endpoint for blocking mode

---

## 3. Companion App — Settings Audit

**Current state:** PWA at `companion/` with Web Bluetooth. Setup, pairing, WiFi config work. Settings read/write not implemented.

**Design:**

### Dual-Path Architecture
- **BLE path** (always available when nearby): Core settings via GATT characteristics
- **HTTP path** (when on same WiFi): Full settings catalog via server REST API

### BLE Settings (subset for offline use)
Implement `SETTINGS_READ` characteristic — returns JSON with:
- volume, voice_mode, tts_engine, agent_mode, ai_model
- web_search, memory, extended_thinking
- firmware_version, battery_pct, wifi_status

Implement `SETTINGS_WRITE` characteristic — accepts JSON:
- `{"key": "volume", "value": 50}`
- Protected by BLE auth session token

### HTTP Settings (full catalog)
- GET `/settings/device` — new endpoint returning all device settings
- PUT `/settings/device` — update device settings (proxied to device via command queue or direct)
- Uses existing device token auth

### Companion Settings Page (`companion/settings.html`)
- Card-based layout grouped by category:
  - **Voice:** voice_mode, volume, tts_engine
  - **AI:** agent_mode, ai_model, extended_thinking, web_search, memory
  - **Display:** text_speed, font settings
  - **Device:** firmware version, update button, WiFi, Bluetooth
- Each card shows current value, tap to cycle/edit
- Auto-detects BLE vs HTTP availability
- Real-time sync: polls every 5s or listens for BLE notifications

### QR Pairing Flow
- Device Settings → "Connect Companion" → shows QR code with BLE address + pairing PIN
- Companion scans QR → connects BLE → PIN verification → paired
- This flow already exists in `companion/pair.html` — just needs a device-side trigger

**Files to create/modify:**
- `companion/settings.html` — new settings page
- `companion/js/settings.js` — settings read/write logic
- `device/network/ble_server.py` — implement SETTINGS_READ/WRITE characteristics
- `server/main.py` — add `/settings/device` endpoint

---

## 4. Recording Quick-Cancel

**Problem:** Accidental tap starts recording, no way to cancel quickly.

**Design:**
- Add 1.5-second grace period after recording starts
- During grace period: tap again → **cancel** recording (no send, return to IDLE)
- After grace period: tap → send (existing behavior)
- Visual: don't show "tap:send" hint until after grace period
- During grace period show: "recording... (tap: cancel)"

**Implementation:**
- `ChatPanel._handle_recording()` — check `time.time() - self._recording_start_time < 1.5`
- If within grace period and SHORT_PRESS → cancel (set `_recording_cancelled = True`, trigger stop event)
- Update hint text in `_get_action_bar_content()` based on elapsed time

**Files to modify:**
- `device/screens/panels/chat.py` — modify `_handle_recording` and hint logic

---

## 5. North Star: ai-agent-env Pattern Adoption (Future)

Incrementally port patterns from the ai-agent-env orchestrator:

### Phase 1: Context Engineering
- Three-tier system prompt (static cached + live context + dynamic per-request)
- Prompt caching for identity blocks (saves tokens + latency)
- Modular context sections (add/remove independently)

### Phase 2: Tool Management
- Dynamic tool gathering at request time (not hardcoded)
- Tool namespacing (`{server}__{tool}`)
- Lightweight Haiku sub-agent for tool selection/routing

### Phase 3: Consciousness Layer
- Global Workspace blackboard with WorkspaceSignals
- Salience competition with exponential decay
- Sub-agent coordination (InnerThoughts, GestureAnnotator patterns)
- Transparency endpoint (`/consciousness/trace`)

### Phase 4: Memory & Self-Model
- Persistent self-model blocks (identity, capabilities, operating principles)
- 3-layer memory deduplication
- Memory consolidation every N turns

**These are future sprints** — documented here as architectural direction.

---

## Sprint Priority

| # | Feature | Effort | Dependencies |
|---|---------|--------|-------------|
| 1 | Recording quick-cancel | Small | None |
| 2 | Update notification flow | Small | Existing OTA + banner |
| 3 | Agent permission popups | Medium | Approval overlay (new) |
| 4 | Companion app settings | Medium-Large | BLE characteristics + new page |
