# Notification Intelligence System — Deep Research Report

**Date:** 2026-03-17
**Scope:** BITOS pocket AI companion (Pi Zero 2W + 240x280 OLED + single button + speaker, Mac mini server)
**Builds on:** `2026-03-16-notification-system-design.md` (WebSocket event bus, tiered rendering, DND routing)

---

## Executive Summary

This report covers seven research areas for building notification intelligence into BITOS: coalescing/batching, priority routing, DND/quiet hours, delivery modalities, agent-initiated intelligence, voice-first UX, and reference implementations. The core recommendation is a four-layer pipeline — **Ingest → Classify → Queue → Deliver** — with LLM-based priority classification on the Mac mini, rule-based DND on the device, and a feedback loop that learns from user dismiss/engage patterns over time.

The existing notification system design (2026-03-16) already covers the WebSocket transport, event schema, priority tiers (P1-P5), and basic rendering. This report extends that foundation with intelligence: smarter classification, coalescing algorithms, proactive timing, and voice-first delivery patterns.

---

## 1. Notification Coalescing & Batching

### 1.1 How PebbleOS and watchOS Handle Grouping

**PebbleOS** uses a "timeline" model where everything is a "pin" — a unified data structure with an ID, timestamp, layout, and optional actions. Notifications from the same app are displayed in a chronological timeline rather than stacked. The OS supports DND modes (Notifications On / Phone Only / Notifications Off) but does not perform thread-based grouping natively — all notifications from the same app appear as separate timeline entries.

Key insight from PebbleOS: the timeline metaphor works well for small screens because it gives temporal context (when did this arrive?) rather than trying to show everything at once. PebbleOS runs on ARM Cortex-M microcontrollers, proving this approach works on constrained hardware.

**watchOS** uses three grouping strategies:
- **Automatic:** Groups by thread identifier, sender, or contextual similarity using on-device ML
- **By App:** All notifications from one app collapse into a single expandable stack
- **Off:** Every notification shown individually

watchOS uses `UNNotificationContent.threadIdentifier` to group related notifications. Apps set this to a conversation ID, and the OS groups them automatically. A summary text (e.g., "3 more messages") replaces individual entries when a group exceeds a threshold. watchOS also uses on-device ML to learn which notifications users engage with and adjusts stacking priority accordingly.

### 1.2 Thread-Based Coalescing Design for BITOS

Recommended approach — **coalesce by `coalesce_key`**, a composite identifier:

```
coalesce_key = f"{category}:{source_id}"
# Examples:
#   "sms:chat_alex_12345"    — all messages from Alex in same chat
#   "mail:thread_abc"        — all emails in same thread
#   "agent:morning_greeting"  — agent greeting (singleton)
#   "task:overdue"           — all overdue task reminders
```

**Coalescing rules:**
1. If a notification arrives with the same `coalesce_key` as a pending (unread) notification, increment count instead of creating a new entry
2. Display the most recent body text, with count: "Alex (3): Running late, be there in 10"
3. Cap visible pending notifications at 3 (matching the existing design). Excess goes to badge count.
4. If the user has already read/dismissed a notification with that key, the next one creates a fresh entry

### 1.3 Time-Based Batching

For low-priority notifications (P3-P5), implement a **batch window:**

| Priority | Batch Window | Delivery |
|----------|-------------|----------|
| P1 Critical | Immediate | Always interrupt |
| P2 High | Immediate | Interrupt if idle >30s |
| P3 Normal | 30-second window | Collect, deliver as batch |
| P4 Low | 5-minute window | Deliver on next screen wake |
| P5 Silent | No delivery | Badge only, visible on pull |

When the batch window closes, deliver a summary: "3 new emails, 1 Slack message" rather than 4 separate toasts.

### 1.4 Deduplication Algorithm

Based on OneUptime's alert deduplication patterns, use fingerprint-based dedup:

```python
import hashlib

def dedup_key(event: NotificationEvent) -> str:
    """Generate dedup fingerprint from stable fields only."""
    parts = f"{event.category}:{event.source_id}:{event.payload.get('body', '')[:100]}"
    return hashlib.sha256(parts.encode()).hexdigest()[:16]
```

**Rules:**
- Same fingerprint within 60-second window: suppress (increment count on existing)
- Same `coalesce_key` but different body: coalesce (update body, increment count)
- Different `coalesce_key`: new notification entry
- Never dedup P1 (critical) notifications — always deliver

The existing design already has `(category, source_id, body_hash)` dedup with 60s window, which is correct. The addition here is separating dedup (exact duplicate suppression) from coalescing (same-thread grouping).

---

## 2. Priority & Urgency Routing

### 2.1 Classification Approaches Compared

| Approach | Accuracy | Latency | Cost | Pi Zero 2W? | Mac mini? |
|----------|----------|---------|------|-------------|-----------|
| Rule-based | ~70% | <1ms | Free | Yes | Yes |
| TF-Lite classifier | ~80% | ~5ms | Free | Marginal | Yes |
| LLM few-shot (Haiku) | ~90% | ~200ms | ~$0.001/call | No | Yes |
| LLM fine-tuned | ~93% | ~200ms | Higher | No | Yes |

**Recommendation: Hybrid approach.** Rules handle the obvious cases (90% of notifications), LLM classifies the ambiguous ones.

### 2.2 Rule-Based Priority (Fast Path)

```python
PRIORITY_RULES = {
    # P1 Critical — always interrupt
    "reminder_due": P1,
    "calendar_event_now": P1,
    "vip_contact_sms": P1,

    # P2 High — interrupt if idle
    "sms_new": P2,
    "calendar_event_15min": P2,
    "task_overdue": P2,
    "agent_greeting": P2,

    # P3 Normal — toast
    "mail_new": P3,
    "agent_suggestion": P3,
    "agent_idle_check": P3,
    "task_reminder": P3,

    # P4 Low — badge only
    "system_health": P4,
    "ota_update": P4,
    "mail_newsletter": P4,

    # P5 Silent — queue only
    "activity_sync": P5,
}
```

### 2.3 LLM Classification (Slow Path, for Ambiguous Cases)

When rules assign P3 (default), optionally run a Haiku few-shot classification to refine:

```
Classify this notification's urgency for a personal AI companion device.
User context: {time_of_day}, {current_screen}, {last_interaction_ago}

Notification:
- Source: {source}
- Sender: {sender}
- Subject: {subject}
- Body preview: {body[:200]}

Categories:
- P1_CRITICAL: Needs immediate attention (emergency, time-critical)
- P2_HIGH: Important, should see soon (personal messages, upcoming events)
- P3_NORMAL: Informational, can wait (newsletters, low-priority updates)
- P4_LOW: Background info (system status, bulk updates)

Examples:
- "Mom: Are you okay? I haven't heard from you" → P1_CRITICAL
- "Alex: Want to grab lunch tomorrow?" → P2_HIGH
- "GitHub: New comment on PR #123" → P3_NORMAL
- "Spotify: Your weekly playlist is ready" → P4_LOW

Reply with only the category name.
```

This runs on the Mac mini via Haiku (~200ms, ~$0.001/call). Only invoke for genuinely ambiguous cases — maybe 10% of notifications. At 50 notifications/day, that's ~5 LLM calls/day, negligible cost.

### 2.4 VIP Contacts / Priority Senders

Store a `vip_contacts` list in device settings (synced from companion app):

```python
VIP_CONTACTS = ["Mom", "Dad", "Partner", "Boss"]  # names or identifiers

def apply_vip_boost(event, priority):
    """Boost priority for VIP senders."""
    sender = event.payload.get("sender", "")
    if any(vip.lower() in sender.lower() for vip in VIP_CONTACTS):
        return max(priority - 1, Priority.CRITICAL)  # Boost by one tier
    return priority
```

VIP contacts bypass DND in Priority Only mode (see section 3).

### 2.5 Focus Modes (Apple-Inspired)

Apple Focus modes use time, location, and app context to filter notifications. For BITOS, implement simpler rule-based modes:

| Mode | Allowed | Blocked | Trigger |
|------|---------|---------|---------|
| **Normal** | All | None | Default |
| **Priority Only** | P1 + P2 + VIP | P3-P5 | Manual or scheduled |
| **DND** | P1 only | P2-P5 | Sleep hours, calendar "busy" |
| **Focus** | P1 + VIP only | Everything else | Manual |

Mode selection via companion app settings or agent suggestion ("You have a meeting in 5 min, want me to enable Focus?").

---

## 3. Do Not Disturb / Quiet Hours

### 3.1 Schedule-Based DND

```python
DND_SCHEDULE = {
    "sleep": {"start": "22:00", "end": "07:00", "mode": "dnd"},
    "morning_routine": {"start": "07:00", "end": "08:00", "mode": "priority_only"},
}
```

Configurable from companion app. Device checks schedule on each notification arrival.

### 3.2 Context-Aware DND

Detect context from available signals:

| Signal | Source | Detection | Action |
|--------|--------|-----------|--------|
| Calendar busy | Google Calendar API | Check for current events | Auto-enable Focus |
| Late night | System clock | After sleep schedule start | Auto-enable DND |
| User recording | Device state | `_rec_state == RECORDING` | Queue all |
| Agent speaking | Device state | TTS playback active | Queue all |
| Long idle | Heartbeat | No interaction >2 hours | Assume away, queue P3+ |

The existing design already handles recording/speaking DND. Adding calendar-aware DND is the next step — query the Google Calendar integration for current events with "busy" status.

### 3.3 Break-Through Rules

Who/what can bypass DND:

```python
BREAKTHROUGH_RULES = {
    "dnd": {
        "allow": [Priority.CRITICAL],  # Only P1
        "allow_vip": True,              # VIP contacts always break through
        "repeated_call": True,          # Same person contacts 2x in 3 min
    },
    "priority_only": {
        "allow": [Priority.CRITICAL, Priority.HIGH],
        "allow_vip": True,
        "repeated_call": False,
    },
    "focus": {
        "allow": [Priority.CRITICAL],
        "allow_vip": True,
        "repeated_call": True,
    },
}
```

The "repeated call" pattern is from Apple's DND: if someone messages twice within 3 minutes, it breaks through on the assumption it's urgent.

### 3.4 Gradual Delivery After DND Ends

When DND clears, do NOT dump all queued notifications at once. Research from MoEngage's DND implementation shows configurable gap delivery is essential:

```python
async def drain_dnd_queue(queue: List[NotificationEvent]):
    """Deliver queued notifications gradually after DND ends."""
    if len(queue) == 0:
        return

    # Sort: P1 first, then P2, then by timestamp (oldest first)
    queue.sort(key=lambda e: (e.priority, e.timestamp))

    if len(queue) > 5:
        # Too many — deliver summary first
        summary = build_summary(queue)  # "While you were away: 3 messages, 7 emails, 2 reminders"
        await deliver(summary)
        await asyncio.sleep(2.0)  # Let user read summary

    # Deliver individually with gaps
    for i, event in enumerate(queue):
        if i >= 3:  # Max 3 individual deliveries, rest stay in badge
            break
        await deliver(event)
        await asyncio.sleep(0.5)  # 500ms gap between deliveries
```

The existing design specifies 500ms pause + 300ms gaps + max 5 items with summary. This is well-aligned with best practices. The addition here is the priority-sorted delivery order and the "while you were away" summary pattern.

---

## 4. Delivery Modalities for 240x280 OLED + Speaker

### 4.1 Visual Modalities

The existing design covers Banner (P1-P2), Toast (P3), and Badge (P4) well. Additional modalities to consider:

**Ambient Glow (P2-P3, idle screen only):**
When the device is showing the blob idle animation, notifications can be communicated through the blob's behavior rather than overlaying UI:
- Blob color shifts to notification category color (blue for SMS, amber for email)
- Blob performs a "glance" gesture toward the notification direction
- Subtle glow ring around screen edge (2px, category color, 50% opacity pulse)
- No text overlay — purely ambient awareness
- User can press button to "expand" and see the actual notification

This leverages the existing blob animation system and consciousness layer. The idle director already plans micro-gestures; notification-aware gestures are a natural extension.

**Full-Screen Takeover (P1 only, rare):**
For truly critical notifications (repeated VIP contact, emergency):
- Entire screen shows notification with large text
- Blob shrinks to corner, notification takes center
- Audio chime plays regardless of volume setting
- Requires explicit dismiss (DOUBLE_PRESS) or voice response

### 4.2 Audio Modalities

**Earcons (short distinctive sounds):**
Research shows earcons should be 125-5000 Hz, multi-harmonic, and <500ms. Design a set of 4-6 distinct earcons:

| Category | Earcon Character | Duration | Frequency Range |
|----------|-----------------|----------|-----------------|
| SMS | Two-tone chirp (ascending) | 200ms | 800-1200 Hz |
| Email | Single soft bell | 150ms | 600-900 Hz |
| Calendar | Three-note ascending | 300ms | 500-1000 Hz |
| Reminder | Two sharp tones | 250ms | 1000-1500 Hz |
| Agent | Soft whoosh/hum | 200ms | 400-800 Hz |
| System | Single low click | 100ms | 300-500 Hz |

Each earcon should be synthesizable (not requiring audio files) for minimal storage. Can be generated with `numpy` sine waves + envelope shaping.

**TTS Summary:**
For P1-P2 notifications when user is not looking at screen:
- "Message from Mom: Are you okay?"
- "Reminder: Dinner in 15 minutes"
- Keep to <5 seconds of speech
- Use existing TTS fallback chain (Cartesia > Edge TTS > ...)

### 4.3 Screen Interruption Strategy

When the user is mid-interaction, notifications must not destroy context:

| User State | P1 Behavior | P2 Behavior | P3+ Behavior |
|------------|-------------|-------------|--------------|
| Idle (blob screen) | Full takeover | Banner | Ambient glow |
| Browsing menu | Banner overlay | Toast overlay | Badge only |
| Reading chat | Banner overlay | Toast overlay | Badge only |
| Recording voice | Queue (deliver after) | Queue | Queue |
| TTS playing | Queue (deliver after) | Queue | Queue |
| Screen off | Wake + banner | Wake + banner | Stay off |

### 4.4 Queue Management Under Burst

When 10+ notifications arrive in 1 minute (e.g., group chat blowing up):

1. **First notification:** Deliver normally (banner/toast based on priority)
2. **Notifications 2-3:** Coalesce with first if same thread, else stack toasts (max 2 visible)
3. **Notifications 4+:** Switch to count mode — update existing toast: "Alex (7 new messages)"
4. **After 30s of burst:** Collapse to single summary toast: "12 new messages in 2 conversations"
5. **When user engages:** Expand to notification list view on demand

Rate limit: max 1 audio earcon per 10 seconds during burst. Visual updates can be more frequent.

---

## 5. Agent-Initiated Intelligence

### 5.1 When Should the Agent Proactively Reach Out?

Based on the ProactiveBench research paper (arxiv:2410.12361), proactive agents should use the decision framework:

**Pt = f(Et, At, St)** where:
- **Et** = environmental events (new email, weather change, calendar approaching)
- **At** = user activity (last interaction time, current screen, recent dismissals)
- **St** = environmental state (time of day, location context, task deadlines)

The agent should intervene only when all four checks pass:
1. **Relevance:** Is this information directly useful to the user right now?
2. **Importance:** Does it meet the threshold for interruption?
3. **User State:** Is the user in a receptive state (not recording, not in meeting)?
4. **Confidence:** Is the agent confident this will be welcomed (>70% based on feedback history)?

### 5.2 Proactive Trigger Categories

| Trigger | Example | Priority | Frequency Cap |
|---------|---------|----------|---------------|
| Weather change | "Rain starting in 30 min, you might want an umbrella" | P3 | 2x/day |
| Task due soon | "Grocery list task is due in 1 hour" | P2 | Per task |
| Calendar prep | "Meeting with Alex in 15 min. Want a briefing?" | P2 | Per event |
| Pattern anomaly | "You usually check email by now. 3 unread." | P3 | 1x/day |
| Idle check-in | "Been quiet for a while. Anything I can help with?" | P3 | 1x/2hr |
| Morning briefing | "Good morning. 4 tasks today, rain at 3pm, 12 emails." | P2 | 1x/day |
| Evening summary | "Today: completed 3 tasks, 2 remaining. Reminder at 9pm." | P3 | 1x/day |
| Context insight | "You asked about X yesterday — here's an update." | P3 | 2x/day |

### 5.3 Avoiding Notification Fatigue

Research from IBM and the ProactiveBench paper identifies these key anti-fatigue measures:

**Hard Caps:**
- Max 8 agent-initiated notifications per day
- Max 2 per hour
- Max 1 during DND (only P1 breakthrough)
- Zero agent notifications during active conversation (user is already engaged)

**Feedback Loop:**
Track user response to every agent notification:

```python
class NotificationFeedback:
    notification_id: str
    action: Literal["engaged", "dismissed", "ignored", "snoozed"]
    response_time_ms: int  # How quickly they responded

# Scoring:
# engaged (tapped, replied) = +1.0
# snoozed = +0.2 (wanted it, but not now)
# dismissed = -0.5
# ignored (expired without interaction) = -1.0
```

Running average per trigger category. If score drops below -0.3, reduce frequency. If below -0.7, disable that trigger type and log for review.

**ProactiveAgent Library Pattern:**
The open-source ProactiveAgent library (github.com/leomariga/ProactiveAgent) implements a useful pattern: a multi-factor decision engine with configurable `min_response_interval` (30s), `max_response_interval` (600s), and `probability_weight` for AI-driven decisions. This maps well to BITOS: the heartbeat loop (60s tick) already provides the wake-up cycle, and adding a decision gate before each proactive notification would prevent over-messaging.

### 5.4 Salience Scoring from Consciousness Layer

The existing GWT workspace already produces signals with salience scores (1-5). Wire notification decisions into this:

```python
async def should_notify_proactively(trigger: str, context: dict) -> bool:
    """Consult consciousness workspace for proactive notification decision."""
    signal = WorkspaceSignal(
        source="notification_intelligence",
        type=SignalType.INNER_THOUGHT,
        content=f"Should I tell the user about: {trigger}?",
        salience=3,
    )
    workspace.post(signal)

    # Check competing signals — if user is deeply engaged in something,
    # high-salience signals from other sources suppress proactive notifications
    competing = workspace.get_signals(min_salience=4)
    if any(s.source == "user_interaction" for s in competing):
        return False  # User is actively engaged, don't interrupt

    return feedback_score(trigger) > -0.3  # Check feedback history
```

---

## 6. Voice-First Notification UX

### 6.1 Pull-Based Model (Primary)

Both Alexa and Google Assistant use a **pull-based** model for notifications: the device indicates notifications are waiting (light ring on Alexa, visual indicator on Google), and the user explicitly asks to hear them. This is the right primary model for BITOS:

**Visual indicator:** Badge dot on status bar (existing P4 design), blob ambient glow
**Voice trigger:** User says "What did I miss?" or presses button on notification screen
**Agent response pattern:**

```
Agent: "You have 3 new messages and 2 emails. Want me to read them?"
User: [DOUBLE_PRESS = yes] or [LONG_PRESS = dismiss]

Agent: "First, from Mom at 2:15: 'Are you coming for dinner tonight?'
        Want to reply?"
User: [DOUBLE_PRESS = yes, starts recording]
User: [voice] "Tell her I'll be there at 6"
Agent: "Got it. I'll send: 'I'll be there at 6.' Sound good?"
User: [DOUBLE_PRESS = send] or [SHORT_PRESS = edit]
```

### 6.2 Push-Based TTS (P1-P2 Only)

For high-priority notifications, proactively read aloud:

```
[earcon plays]
Agent: "Message from Mom: Are you okay? I haven't heard from you."
[pause 2s for user to process]
Agent: "Want to reply?"
```

Only do this for:
- P1 Critical notifications (always)
- P2 High notifications when screen is off or user is idle >5 min
- Never during active interaction or recording

### 6.3 Summary-Then-Detail Drill-Down

For batch delivery (morning briefing, post-DND drain):

```
Agent: "Good morning. Here's your update:
        3 messages — 2 from Mom, 1 from Alex.
        5 emails — 1 from your boss marked urgent.
        2 tasks due today.
        Rain expected at 3pm.
        Want me to go through the details?"

User: [DOUBLE_PRESS]

Agent: "Starting with the urgent email from your boss:
        Subject: 'Q1 Review meeting moved to 2pm.'
        Want to reply or move to the next item?"
```

This pattern is more efficient than reading each notification individually. The agent acts as a news anchor, summarizing then drilling down on demand.

### 6.4 Quick Voice Replies

The existing notification system vision already describes this well. Implementation detail:

1. User hears notification, presses DOUBLE to reply
2. Device enters recording mode (hold-to-record from notification screen)
3. Audio sent to server for transcription (Lightning Whisper MLX on Mac mini or Groq cloud)
4. Agent drafts reply: "I'll send: 'I'll be there at 6.' Send it?"
5. DOUBLE_PRESS = send, SHORT_PRESS = re-record, LONG_PRESS = cancel
6. Agent sends via BlueBubbles API / Gmail API

Draft-first approach (save as draft, require confirmation to send) is safer for V1. Direct send can be a setting for trusted contacts.

---

## 7. Reference Implementations

### 7.1 Open-Source Notification Servers

**ntfy (ntfy.sh)**
- Self-hosted push notification server, dead simple HTTP PUT/POST API
- Supports priority levels (1-5), tags, action buttons, attachments
- No smart grouping or ML features — pure delivery pipe
- Useful as: delivery transport, not intelligence layer
- License: Apache 2.0

**Gotify**
- Self-hosted, WebSocket-based push notifications
- Simple app/token model, web UI, Android client
- No grouping or priority intelligence
- Useful as: reference for WebSocket notification delivery
- License: MIT

**Neither has notification intelligence.** They're delivery pipes. The intelligence must be built in the BITOS server layer.

### 7.2 Home Assistant Notification System

Most relevant reference implementation. Key patterns to adopt:

- **Actionable notifications:** Buttons in the notification that trigger automations. BITOS equivalent: `actions` array in event payload, mapped to button presses.
- **Critical notifications:** `critical: 1` flag bypasses DND on iOS. BITOS equivalent: P1 priority with breakthrough rules.
- **Notification tags:** Same tag replaces previous notification (dedup). BITOS: `coalesce_key` serves this purpose.
- **Notification groups:** Android grouping by app. BITOS: coalesce by `category:source_id`.
- **TTS notifications:** Home Assistant can announce via speakers with `tts_text` parameter. BITOS: TTS delivery for P1-P2.
- **Escalation patterns:** `wait_for_trigger` with timeout, then escalate. BITOS: if P2 notification ignored for 5 min, escalate to P1 (configurable per category).

### 7.3 ProactiveAgent (Python Library)

`github.com/leomariga/ProactiveAgent` — open-source framework for proactive AI agent behavior:
- Decision engine: should_respond() based on context, timing, engagement
- Sleep calculator: dynamic intervals between proactive checks
- Configurable min/max response intervals, probability weights
- Directly applicable to BITOS heartbeat + notification timing decisions
- License: MIT

### 7.4 ProactiveBench (Research Paper)

`arxiv.org/abs/2410.12361` — "Proactive Agent: Shifting LLM Agents from Reactive Responses to Active Assistance"
- Formal framework for proactive agent decisions: Pt = f(Et, At, St)
- 6,790 test events across Coding, Writing, Daily Life scenarios
- Fine-tuned model achieves 66% F1 on proactive task prediction
- Key insight: most LLMs over-help (too many false positives). Restraint is harder than initiative.
- Evaluation metrics: Precision (avoiding false alarms) > Recall (catching needs)
- **Takeaway for BITOS:** Start conservative (fewer proactive notifications), tune up based on feedback rather than starting aggressive and tuning down.

### 7.5 Alert Fatigue Research

Medical/security alert fatigue research is directly applicable:
- Hospital alarm systems reduced notifications by 99.3% using contextual reasoning (PMC article)
- Key metric: **Interruption Regret** — how often users negatively react to an alert
- IBM research: AI-driven triage reduced alert volume by 80-90% while maintaining critical detection
- **Takeaway for BITOS:** Measure dismiss rate per notification category. If >50% dismissed, that category needs filtering.

### 7.6 AI Notification System Architecture (zenvanriel.com)

Four-layer reference architecture:
1. Event Ingestion → processing queue
2. AI Processing → routing, content, timing decisions
3. Delivery → multi-channel dispatch
4. Feedback Loop → engagement data improves models

Maps directly to BITOS: BlueBubbles/Gmail webhooks → NotificationDispatcher → priority + coalesce → WebSocket delivery → track engage/dismiss.

---

## Architecture Recommendation

### Notification Intelligence Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│                        MAC MINI SERVER                          │
│                                                                 │
│  ┌──────────┐  ┌──────────────┐  ┌───────────┐  ┌───────────┐ │
│  │  Ingest   │→│  Classifier   │→│   Queue    │→│  Dispatch  │ │
│  │           │  │              │  │            │  │           │ │
│  │BlueBubbles│  │ Rule engine  │  │ SQLite     │  │ /ws/device│ │
│  │Gmail API  │  │ + Haiku LLM  │  │ Coalesce   │  │ Fallback  │ │
│  │Calendar   │  │ (ambiguous)  │  │ Dedup      │  │ polling   │ │
│  │Heartbeat  │  │ VIP boost    │  │ Batch      │  │           │ │
│  │Things MCP │  │ Focus mode   │  │ DND queue  │  │           │ │
│  └──────────┘  └──────────────┘  └───────────┘  └───────────┘ │
│                                                       │         │
│  ┌────────────────────────────────────────────────────┘         │
│  │  Feedback Store (SQLite)                                     │
│  │  - engage/dismiss/ignore per notification                    │
│  │  - running score per trigger category                        │
│  │  - daily aggregates for tuning                               │
│  └──────────────────────────────────────────────────────────────┘
└─────────────────────────────────────────────────────────────────┘
                              │ WebSocket
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     PI ZERO 2W DEVICE                           │
│                                                                 │
│  ┌──────────────┐  ┌───────────┐  ┌───────────────────────────┐│
│  │  WS Client   │→│  Router    │→│  Renderer                 ││
│  │              │  │           │  │                           ││
│  │ Receive evt  │  │ DND check │  │ P1: Full banner + TTS    ││
│  │ Send ACK     │  │ State chk │  │ P2: Banner + earcon      ││
│  │ Send action  │  │ Priority  │  │ P3: Toast                ││
│  │              │  │ Coalesce  │  │ P4: Badge dot            ││
│  │              │  │ local     │  │ P5: Queue only           ││
│  └──────────────┘  └───────────┘  │ Idle: Ambient blob glow  ││
│                                    └───────────────────────────┘│
│  ┌──────────────────────────────────────────────────────────────┘
│  │  Local State                                                 │
│  │  - DND mode (from schedule + context)                        │
│  │  - Unread counts per category                                │
│  │  - Feedback actions (sent back to server)                    │
│  └──────────────────────────────────────────────────────────────┘
└─────────────────────────────────────────────────────────────────┘
```

### Priority Classification System

**Two-tier classification:**

1. **Fast path (device-side or server-side rules, <1ms):**
   - Category → default priority mapping (from existing design table)
   - VIP sender boost (+1 tier)
   - Time-of-day adjustment (lower priorities at night)
   - Focus mode filtering

2. **Slow path (Mac mini Haiku, ~200ms, optional):**
   - Only for P3 notifications from unknown/new senders
   - Few-shot prompt with 4 examples
   - Classify as P2 (boost) or P4 (demote) or keep P3
   - Cache classification per sender for 24 hours

### DND / Quiet Hours Design

```python
class DNDManager:
    """Manages Do Not Disturb state from multiple signals."""

    def get_effective_mode(self) -> DNDMode:
        """Priority: manual override > calendar > schedule > device state."""
        if self.manual_override:
            return self.manual_override
        if self.calendar_busy():
            return DNDMode.FOCUS
        if self.in_sleep_hours():
            return DNDMode.DND
        if self.device_recording or self.device_speaking:
            return DNDMode.RECORDING  # Queue everything
        return DNDMode.NORMAL

    def can_deliver(self, event: NotificationEvent) -> bool:
        """Check if notification can break through current DND mode."""
        mode = self.get_effective_mode()
        rules = BREAKTHROUGH_RULES[mode]

        if event.priority in rules["allow"]:
            return True
        if rules["allow_vip"] and event.is_vip_sender:
            return True
        if rules.get("repeated_call") and self.is_repeated_contact(event):
            return True
        return False
```

### Delivery Strategy Summary

| Situation | Modality | Details |
|-----------|----------|---------|
| Idle, screen on (blob) | Ambient glow + optional earcon | Blob reacts to notification category |
| Idle, screen off | Wake screen + banner | Only for P1-P2 |
| Active browsing | Toast overlay | Non-destructive, auto-dismiss |
| In conversation | Queue, drain after | Never interrupt active chat |
| Recording | Queue, drain after | Never interrupt recording |
| DND (sleep) | Queue, breakthrough P1 only | Gradual drain on wake |
| Post-DND | Summary → individual drain | "3 messages, 2 emails while you slept" |
| Voice mode | TTS read-aloud | "Message from Mom: ..." |

---

## Recommended Implementation Order

### Phase 1: Foundation (Already Designed)
The `2026-03-16-notification-system-design.md` covers this phase. Implement as planned:
- WebSocket event bus (`/ws/device`)
- Server-side NotificationDispatcher with dedup and SQLite queue
- Device-side NotificationRouter with DND state machine
- Banner/Toast/Badge rendering with animations
- Priority tiers P1-P5 with rule-based assignment

### Phase 2: Coalescing & Batching
- Add `coalesce_key` to event schema
- Implement thread-based coalescing (same key = increment count, update body)
- Time-based batching for P3-P5 (30s and 5min windows)
- Burst detection and rate limiting (max 1 earcon per 10s, collapse after 4+ in same thread)
- Gradual DND drain with summary-first pattern

### Phase 3: Priority Intelligence
- VIP contacts list (companion app setting, synced to server)
- Focus modes (Normal, Priority Only, DND, Focus) with companion app control
- Calendar-aware DND (query Google Calendar for busy status)
- Schedule-based quiet hours
- Breakthrough rules (VIP, repeated contact)

### Phase 4: Voice-First Delivery
- TTS notification reading for P1-P2 when idle
- "What did I miss?" voice command → summary-then-detail drill-down
- Quick voice reply flow (record → transcribe → draft → confirm → send)
- Earcon sound set (synthesized, category-specific)

### Phase 5: Agent Intelligence
- Proactive notification decision gate (relevance, importance, user state, confidence)
- Feedback tracking (engage/dismiss/ignore per notification)
- Running score per trigger category with auto-throttle
- Haiku LLM classification for ambiguous priority (slow path)
- Consciousness layer integration (workspace signals for notification decisions)
- Daily/weekly feedback aggregation for tuning

### Phase 6: Ambient Intelligence
- Blob-aware notifications (color shift, gesture, glow for idle-screen notifications)
- Morning/evening briefing TTS with structured summary
- Pattern detection ("You usually check email by now")
- Adaptive timing (learn when user is most receptive to proactive messages)

---

## Key Metrics to Track

| Metric | Target | Measurement |
|--------|--------|-------------|
| Dismiss rate per category | <30% | dismissed / total delivered |
| Engage rate for agent proactive | >40% | tapped or replied / total agent notifications |
| Interruption regret (user backs out quickly) | <10% | dismissed within 1s / total |
| False positive rate (notification not useful) | <20% | (dismissed + ignored) / total |
| DND breakthrough appropriateness | >90% | breakthrough notifications engaged / total breakthroughs |
| Average notifications per day | 15-30 | Total delivered (excluding queued/suppressed) |
| Coalesce ratio | >2:1 | Raw events / delivered notifications |
| Voice reply completion rate | >70% | Replies sent / reply flows started |

---

## Sources

- [Apple watchOS Notification Grouping](https://developer.apple.com/documentation/watchos-apps/grouping-notifications)
- [Apple watchOS Notification Management](https://beebom.com/manage-notification-grouping-apple-watch/)
- [PebbleOS Open Source](https://opensource.googleblog.com/2025/01/see-code-that-powered-pebble-smartwatches.html)
- [ProactiveBench: Proactive Agent Research](https://arxiv.org/html/2410.12361v3)
- [ProactiveAgent Library](https://github.com/leomariga/ProactiveAgent)
- [Alert Deduplication Patterns](https://oneuptime.com/blog/post/2026-01-30-alert-deduplication/view)
- [AI Notification Systems Guide](https://zenvanriel.com/ai-engineer-blog/ai-notification-systems/)
- [ML-Based Notification Scoring](https://www.emergn.com/insights/smarter-approach-notifications-ml-ai/)
- [Home Assistant Critical Notifications](https://companion.home-assistant.io/docs/notifications/critical-notifications/)
- [Home Assistant Actionable Notifications](https://companion.home-assistant.io/docs/notifications/actionable-notifications/)
- [Alert Fatigue in Healthcare (PMC)](https://pmc.ncbi.nlm.nih.gov/articles/PMC6904899/)
- [IBM Alert Fatigue Reduction with AI](https://www.ibm.com/think/insights/alert-fatigue-reduction-with-ai-agents)
- [Earcon Design Research](https://en.wikipedia.org/wiki/Earcon)
- [BeepBank-500 Earcon Corpus](https://arxiv.org/html/2509.17277)
- [Google Assistant Message Reading](https://9to5google.com/2019/08/02/google-assistant-read-messages/)
- [Voice Assistants and Notifications (Fast Company)](https://www.fastcompany.com/40423049/on-amazon-echo-and-google-home-notifications-could-be-brilliant-or-brutal)
- [Apple Focus Modes Automation](https://www.macrumors.com/how-to/schedule-focus-modes/)
- [MoEngage DND/Quiet Hours](https://help.moengage.com/hc/en-us/articles/15919572705556-Do-Not-Disturb)
- [Notification System Design Guide](https://www.systemdesignhandbook.com/guides/design-a-notification-system/)
- [ntfy Push Notifications](https://ntfy.sh/)
- [Gotify Notification Server](https://gotify.net/)
- [Wearable UX Design Principles](https://www.protopie.io/blog/ultimate-guide-to-smartwatch-ux)
- [Toast Notification UX](https://blog.logrocket.com/ux-design/toast-notifications/)
- [Proactive AI Agent User Study (Springer)](https://link.springer.com/article/10.1007/s12599-024-00918-y)
