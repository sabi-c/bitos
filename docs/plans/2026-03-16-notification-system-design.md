# Agent Notification System — Design

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:writing-plans to create the implementation plan.

**Goal:** Replace poll-based notification delivery with a real-time WebSocket event bus, add tiered notification rendering with animations, DND awareness, and in-chat tool result banners.

**Architecture:** Server-side Notification Dispatcher collects events from integrations (BlueBubbles, Gmail, Calendar, Vikunja), agent heartbeat (greetings, reminders, suggestions), and tool use (task created, reminder set). Events are deduplicated, assigned priority tiers, and pushed to connected devices via a persistent WebSocket. Device-side NotificationRouter checks DND state and routes to the appropriate delivery style (banner, toast, badge, or queue).

---

## 1. WebSocket Event Bus

### Transport: `/ws/device`

Single persistent WebSocket connection replaces all notification-related polling. Device connects on boot, auto-reconnects on drop (exponential backoff: 1s, 2s, 4s, 8s, max 30s).

### Event Schema

```json
{
  "type": "notification",
  "id": "evt_abc123",
  "priority": 2,
  "category": "sms",
  "payload": {
    "title": "Alex",
    "body": "Hey, are we still on for dinner?",
    "app": "iMessage",
    "icon": "message",
    "source_id": "chat_12345",
    "actions": ["reply", "dismiss"],
    "color": "blue",
    "duration_s": 5
  },
  "timestamp": "2026-03-16T14:30:00Z"
}
```

### Event Types

| type | Description |
|------|------------|
| `notification` | Standard notification (SMS, email, calendar, system) |
| `reminder` | Scheduled reminder firing at exact time |
| `agent_message` | Proactive agent message (greeting, check-in, suggestion) |
| `tool_result` | Agent tool use result (task created, calendar event, etc.) |
| `activity_sync` | Bulk unread count update (badge refresh) |
| `heartbeat_ping` | Keep-alive ping (every 30s) |

### Fallback

If WebSocket disconnects for >60s, device falls back to polling `/notifications/pending` every 10s until WS reconnects. Server queues events in SQLite so nothing is lost during disconnection.

---

## 2. Server-Side Notification Dispatcher

### Location: `server/notifications/dispatcher.py`

Central hub that all notification sources write to.

```python
class NotificationDispatcher:
    def dispatch(self, event: NotificationEvent) -> None:
        """Deduplicate, assign priority, persist, push to devices."""

    def register_device(self, ws: WebSocket, device_id: str) -> None:
        """Track connected device WebSocket."""
```

### Deduplication

- Key: `(category, source_id, body_hash)`
- Window: 60 seconds
- Same SMS from BlueBubbles won't fire twice if polled and pushed overlap

### Priority Assignment

Sources declare a default priority, but dispatcher can override based on:
- User preferences (companion app settings)
- Time of day (lower priority at night)
- Context (if user is in a chat with the sender, elevate SMS from them)

### Notification Sources

| Source | Trigger | Default Priority | Category |
|--------|---------|-----------------|----------|
| BlueBubbles webhook | New iMessage | P2 | sms |
| Gmail push/poll | New email | P3 | mail |
| Apple Calendar | Event in 15min | P2 | calendar |
| Vikunja | Task overdue | P2 | task |
| Heartbeat greeting | Morning/evening | P2 | agent |
| Heartbeat idle check | 30min no interaction | P3 | agent |
| Agent suggestion | Context-triggered | P3 | agent |
| Reminder (scheduled) | Exact time fires | P1 | reminder |
| Tool result | Agent creates/edits | P3 | tool |
| System health | AI online/offline | P4 | system |
| OTA update | New version | P4 | system |

### Persistent Queue

SQLite table `notification_queue`:
```sql
CREATE TABLE notification_queue (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    priority INTEGER NOT NULL,
    category TEXT NOT NULL,
    payload TEXT NOT NULL,  -- JSON
    created_at TEXT NOT NULL,
    delivered_at TEXT,       -- NULL until device ACKs
    expired_at TEXT          -- auto-expire after 24h
);
```

Events persist so disconnected devices can catch up on reconnect.

---

## 3. Device-Side Notification Router

### Location: `device/notifications/router.py`

```python
class NotificationRouter:
    def on_event(self, event: dict) -> None:
        """Receive WS event, check DND, route to delivery."""

    def drain_queue(self) -> None:
        """Called when DND ends — deliver queued notifications one by one."""
```

### DND States

| State | Condition | Behavior |
|-------|-----------|----------|
| **Clear** | Normal browsing | Deliver immediately by priority tier |
| **Recording** | ChatPreviewPanel._rec_state == RECORDING | Queue everything, drain on stop |
| **Speaking** | ChatPanel state == SPEAKING | Queue everything, drain on idle |
| **Transitioning** | Screen transition in progress | Delay 300ms then deliver |

When DND clears: 500ms pause, then drain queue one-by-one with 300ms gap between notifications.

### Priority → Delivery Routing

| Priority | Delivery | Wake Screen | Sound |
|----------|----------|-------------|-------|
| P1 Critical | Full banner (10s) | Yes, always | Chime |
| P2 High | Banner (5s) | Yes if sleeping | Soft tick |
| P3 Normal | Toast strip (3s) | No | None |
| P4 Low | Badge only | No | None |
| P5 Silent | Queue only | No | None |

---

## 4. Notification Rendering

### 4.1 Banner (P1-P2)

Full-width overlay, 60-72px tall depending on content:

```
┌──────────────────────────────────────────┐
│  [icon]  App · Source              HH:MM │  <- header line (DIM2)
│  Message body text here, up to 2 lines   │  <- body (WHITE)
│  of content with word wrapping...        │
│ ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░░░░░░ │  <- progress bar (2px, colored)
│       tap:REPLY    hold:DISMISS          │  <- action hints (DIM3)
└──────────────────────────────────────────┘
```

**Animations:**
- **Enter:** Slide down from y=-72 to y=SAFE_INSET. 200ms ease-out-cubic with 2px overshoot bounce.
- **Progress bar:** Full width, colored by category. Shrinks left-to-right linearly over duration.
- **Exit (timeout):** Slide up + alpha fade. 150ms ease-in-quad.
- **Exit (dismissed):** Faster 100ms snap-up, no fade.

**Colors by category:**
- SMS: `(60, 130, 220)` — blue
- Mail: `(180, 140, 60)` — amber
- Calendar: `(80, 180, 120)` — green
- Task: `(160, 100, 220)` — purple
- Agent: `(100, 200, 200)` — cyan
- Reminder: `(220, 80, 80)` — red
- System: `(120, 120, 120)` — gray

### 4.2 Toast (P3)

28px single-line strip at top:

```
┌──────────────────────────────────────────┐
│ [icon] 3 new emails · Gmail    ▓▓▓░░░░░ │
└──────────────────────────────────────────┘
```

- Same slide-down/up animation, smaller scale
- 3s default duration
- Mini progress bar (2px) at bottom edge
- If multiple toasts queue, they stack (max 2 visible, 30px offset)

### 4.3 Badge (P4)

Status bar notification dot:
- Small colored circle (4px) right of the time display
- Color = highest-priority unread notification category
- Number overlay if >1 unread (tiny font)
- Pulses gently (0.5Hz alpha oscillation) when new

### 4.4 Tool Result Banner (In-Chat)

Rendered inline in chat message flow, not as an overlay:

```
┌──────────────────────────────────────────┐
│ ▎ ✓ Created task: Buy groceries          │  <- 4px left accent bar
│ ▎   Due: Tomorrow 5pm                    │  <- detail line (DIM3)
└──────────────────────────────────────────┘
```

- Left accent bar colored by tool type:
  - Task: purple `(160, 100, 220)`
  - Calendar: green `(80, 180, 120)`
  - Reminder: red `(220, 80, 80)`
  - HomeKit: orange `(220, 160, 60)`
- Compact: 2 lines max
- No animation (appears with chat message text)
- Font: same as chat body, slightly dimmed for detail line

---

## 5. Reminder System

### Server-Side: MCP Tool → Scheduled Action

Agent has a `schedule_reminder` tool (already exists in ai-agent-env consciousness layer):

```python
# Agent calls this during conversation
schedule_reminder(title="Dinner", time="17:00", repeat=None)
```

This writes to `scheduled_actions` table. Heartbeat loop (60s tick) checks for due reminders each tick and dispatches them as P1 events via the Notification Dispatcher.

### Device-Side: Reminder Banner

Reminders use the full banner (P1) with:
- Red accent color
- Title: "REMINDER"
- Body: reminder text
- Actions: `tap:DONE  hold:SNOOZE`
- Snooze re-schedules +10 minutes

---

## 6. Agent Suggestion Workflow

Heartbeat or context system can trigger suggestions:

```json
{
  "type": "agent_message",
  "priority": 3,
  "payload": {
    "title": "Suggestion",
    "body": "Want me to check your email?",
    "actions": ["yes", "dismiss"],
    "action_callback": "/agent/action/check_email"
  }
}
```

- Rendered as P3 toast or P2 banner (configurable)
- "Yes" taps POST to action_callback, which triggers the agent action
- "Dismiss" just clears the notification
- Max 2-3 suggestions per day (configurable, prevents annoyance)

---

## 7. Queue Drain Behavior

When DND ends (recording stops, speaking finishes):

1. **500ms pause** — let the screen settle
2. **Sort queue** by priority (P1 first), then by timestamp (oldest first)
3. **Deliver one by one** with 300ms gap between notifications
4. **Coalesce** if multiple of same category: "3 new messages" instead of 3 separate banners
5. **Max drain** — if queue has >5 items, show summary toast instead: "5 notifications while you were busy"

---

## 8. WebSocket Protocol Details

### Device → Server

```json
{"type": "ack", "id": "evt_abc123"}           // Notification delivered
{"type": "action", "id": "evt_abc123", "action": "reply"}  // User tapped action
{"type": "dnd", "active": true, "reason": "recording"}     // DND state change
{"type": "ping"}                                             // Keep-alive
```

### Server → Device

```json
{"type": "notification", ...}    // See event schema above
{"type": "reminder", ...}
{"type": "agent_message", ...}
{"type": "tool_result", ...}
{"type": "activity_sync", "payload": {"sms": 2, "mail": 5, "task": 1}}
{"type": "pong"}
```

### Reconnection

- Device sends `{"type": "reconnect", "last_event_id": "evt_xyz"}` on reconnect
- Server replays all events since that ID (from persistent queue)
- If >50 missed events, server sends summary instead

---

## 9. Testing Strategy

- **Unit tests:** NotificationRouter priority routing, DND state machine, queue drain logic, dedup, coalescing
- **Rendering tests:** Banner/toast/badge render without crash, animation progress math, progress bar shrink
- **Integration tests:** WS event → router → banner displayed, DND queue → drain on state change
- **Mock server:** Fake WS that sends canned events for device-side testing without real integrations
