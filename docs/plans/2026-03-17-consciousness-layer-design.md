# BITOS Consciousness & Perception Layer Design

**Date:** 2026-03-17
**Status:** Design document (no code)
**Author:** Seb + Claude

---

## 1. Current State of BITOS Server

The BITOS server (`/Users/seb/bitos/server/`) is a FastAPI backend running on Mac mini that serves a Pi Zero 2W companion device. The current chat pipeline is:

```
User message
  -> ChatRequest (FastAPI endpoint)
  -> classify_perception() — Haiku pre-call (intent, needs_tools, urgency, response_hint)
  -> get_system_prompt() — mode-specific prompt + tasks/battery/location/notifications
  -> search_facts(message) — FTS5 keyword search, inject top 10 facts into system prompt
  -> get_conv_messages() — load conversation history
  -> llm_bridge.stream_with_tools() or stream_text() — Anthropic streaming with tool loop
  -> extract_and_store_facts() — background thread, Haiku extracts facts from turn
  -> SSE stream back to device
```

**What exists today:**

| Component | File | Description |
|-----------|------|-------------|
| Perception | `perception.py` | Haiku classifier: intent, needs_tools, urgency, response_hint, topic |
| Memory | `memory_store.py` | FTS5 fact store with Jaccard dedup (0.75 threshold) |
| Fact extraction | `fact_extractor.py` | Background Haiku call after each turn |
| Conversation store | `conversation_store.py` | SQLite multi-turn history |
| Agent modes | `agent_modes.py` | 6 persona prompts (producer, hacker, clown, monk, storyteller, director) |
| Heartbeat | `heartbeat.py` | Background loop: morning briefing, evening winddown, idle checkin, task reminders |
| Agent tools | `agent_tools.py` | 14 tools: settings, messaging, email, calendar, contacts, memory, web search, tasks |
| LLM bridge | `llm_bridge.py` | Provider-agnostic streaming with tool-use loop (5 rounds max) |
| Notifications | `notifications/` | Dispatcher, queue store, WebSocket handler, integration bridge |

**What's missing:**

- No global workspace / signal blackboard
- No subconscious agents (inner thoughts, memory consolidator)
- No persistent self-model / identity continuity
- No salience-based context injection (everything is flat)
- No entity extraction from perception
- No proactive memory recall (only keyword search on current message)
- No conversation summarization for long history compression
- No extended thinking criteria / gating
- Perception runs synchronously in a thread executor, no async

---

## 2. What to Port from ai-agent-env

The ai-agent-env project (`/Users/seb/Downloads/Manual Library/Seb's Mind/ai-agent-env/`) has a mature consciousness system. Here's what maps to BITOS and what needs adaptation:

### 2.1 Direct Port (high value, moderate adaptation)

| ai-agent-env Component | Target BITOS File | Adaptation Notes |
|------------------------|-------------------|------------------|
| `consciousness.py` — GlobalWorkspace, WorkspaceSignal, SignalType, AwarenessState | `server/consciousness.py` | Strip avatar-specific signals (GESTURE, AGENT_GESTURE). Keep PERCEPTION, MEMORY_RECALL, INNER_THOUGHT, EMOTION, TOOL_USE. Add new types for BITOS: NOTIFICATION, HEARTBEAT. Remove all blob/avatar tool definitions. |
| `perception.py` — perceive() with entity extraction | `server/perception.py` | Merge with existing classifier. Add entities[], topics[], needs_memory, needs_context[] from ai-agent-env. Make async (current BITOS perception is sync). |
| `self_model.py` — SelfModel with persisted blocks | `server/self_model.py` | Port directly. Change default blocks from Melbourne/vault context to BITOS device context. Keep identity, capabilities, about_seb, operating_principles, current_focus. Use sync SQLite (BITOS pattern) instead of aiosqlite. |
| `subagents/inner_thoughts.py` — InnerThoughts | `server/subagents/inner_thoughts.py` | Port core reflect() logic. Remove persistent_state/dream_journal hooks (not in BITOS). Post to workspace. Use sync Anthropic client in background thread (BITOS pattern). |
| `subagents/memory_consolidator.py` — MemoryConsolidator | `server/subagents/memory_consolidator.py` | Adapt to use BITOS memory_store (sync SQLite, not aiosqlite MemoryStore). Run every 8 turns. Keep self-model update capability. Remove persistent_state/mood tracking. |

### 2.2 Adapt Heavily (concept port, not code port)

| ai-agent-env Concept | BITOS Adaptation |
|----------------------|------------------|
| `live_context.py` — auto-refreshing ambient context | BITOS already has location/tasks/battery in `agent_modes.py`. Enhance with weather, calendar preview, time-of-day awareness. Don't need a separate class — fold into the system prompt builder. |
| CONSCIOUSNESS_PREAMBLE — shared identity across sub-agents | Create a BITOS-specific preamble. Simpler — no avatar/blob references. Focus on: "you are a pocket AI running on a physical device, you have perception/memory/inner thoughts layers." |
| AwarenessState + compete() — salience competition | Port the competition mechanism. In BITOS, the "winner" influences system prompt injection rather than avatar expression. Simpler output: which signals make the spotlight, which stay peripheral. |
| Tool definitions (perform_gesture, adjust_avatar, etc.) | Do NOT port. BITOS has its own tool set. The only new tool from consciousness would be `think_deeper` (triggers extended thinking) and `update_self_model`. |

### 2.3 Skip (not relevant to BITOS)

- `blob_sequences.py`, `animation_config.py` — blob avatar system
- `subagents/gesture_annotator.py` — avatar expression mapping
- `subagents/idle_director.py` — idle timeline planning (BITOS heartbeat handles this differently)
- `memory/vault.py` — Obsidian vault indexer (BITOS doesn't have a vault)
- `subagents/orchestrator_chat.py`, `agent_runner.py`, `workspace_agent.py` — multi-agent orchestration (too complex for BITOS scope)

---

## 3. Perception Layer

### 3.1 Current State

BITOS already has `perception.py` with a Haiku classifier that returns:
- `intent`: chat, question, command, settings, task, creative, reflection, messaging
- `needs_tools`: boolean
- `urgency`: low, normal, high
- `response_hint`: brief, normal, detailed
- `topic`: short label

This is good but missing:
- **Entity extraction** (names, dates, projects mentioned)
- **Tool suggestion** (which specific tools, not just "needs tools or not")
- **Salience scoring** (how important is this message to the overall context)
- **Memory relevance** (should we search memory? what keywords?)
- **Context needs** (does this need calendar? email? task data?)

### 3.2 Enhanced Perception Design

```python
@dataclass
class Perception:
    intent: str = "chat"                    # existing
    entities: list[str] = field(default_factory=list)    # NEW: extracted names, dates, projects
    topics: list[str] = field(default_factory=list)      # NEW: domain areas
    needs_tools: list[str] = field(default_factory=list) # CHANGED: specific tool names, not bool
    urgency: str = "normal"                 # existing
    salience: int = 3                       # NEW: 1-5, how important for consciousness
    response_hint: str = "normal"           # existing
    needs_memory: bool = True               # NEW: should we search memory?
    memory_query: str = ""                  # NEW: optimized search query for memory
    needs_context: list[str] = field(default_factory=list)  # NEW: calendar, email, tasks
    topic: str = ""                         # existing
    raw: dict = field(default_factory=dict) # existing
```

**Enhanced classifier prompt:**

```
Classify this user message for a pocket AI assistant. Return JSON only.

{
  "intent": "chat|question|command|settings|task|creative|reflection|messaging",
  "entities": ["extracted names, dates, projects, topics"],
  "topics": ["relevant domain areas"],
  "needs_tools": ["tool_name1", "tool_name2"] or [],
  "urgency": "low|normal|high",
  "salience": 1-5,
  "response_hint": "brief|normal|detailed",
  "needs_memory": true/false,
  "memory_query": "optimized search keywords for memory lookup",
  "needs_context": ["calendar", "email", "tasks"] or []
}
```

**Tool suggestion logic:**

The perception layer recommends which tools the main agent should have access to. This reduces token overhead — instead of always sending all 14 tool definitions, we only send what's likely needed.

| Intent | Suggested Tools |
|--------|----------------|
| chat | none |
| question | recall_facts, web_search (if web enabled) |
| command | get_device_settings, update_device_setting |
| settings | get_device_settings, update_device_setting |
| task | get_tasks, create_task, complete_task |
| messaging | send_imessage, read_imessages, send_email, read_emails, get_contacts |
| creative | recall_facts |
| reflection | recall_facts, remember_fact |

Perception's `needs_tools` list overrides the default, but the main agent can still request additional tools via a "think_deeper" mechanism.

### 3.3 Making Perception Async

Current BITOS perception runs `anthropic.Anthropic()` (sync) in a thread executor. The ai-agent-env version uses `AsyncAnthropic`. For BITOS, keep the sync-in-thread pattern to match the rest of the codebase, but run it concurrently with memory lookup:

```
# Parallel pre-processing (before main LLM call)
perception_future = run_in_executor(classify_perception, message)
memory_future = run_in_executor(search_facts, message)

perception = await perception_future
memory_facts = await memory_future

# If perception says needs_memory and provides a better query, do a second search
if perception.needs_memory and perception.memory_query != message:
    extra_facts = await run_in_executor(search_facts, perception.memory_query)
    memory_facts = deduplicate(memory_facts + extra_facts)
```

### 3.4 Posting to the Workspace

After classification, perception posts a signal:

```python
workspace.post(WorkspaceSignal(
    source="perception",
    signal_type="perception",
    salience=perception.salience,
    content={
        "intent": perception.intent,
        "entities": perception.entities,
        "topics": perception.topics,
        "urgency": perception.urgency,
        "memory_query": perception.memory_query,
    },
))
```

---

## 4. Subconscious Agents

### 4.1 Memory Consolidator

**Purpose:** Every 8 conversation turns, review the recent batch and produce high-quality memory updates instead of the noisy per-turn extraction.

**Current BITOS state:** `fact_extractor.py` runs after every turn. It extracts facts individually, which leads to:
- Duplicate/near-duplicate facts over time
- No ability to supersede old facts with new info
- No self-model updates based on learned information
- No emotional signal detection

**Proposed change:** Keep per-turn extraction as a lightweight first pass, but add a consolidation pass every 8 turns that:

1. Reviews the last 8 turn pairs (user + assistant)
2. Compares against existing facts (FTS5 search on conversation keywords)
3. Outputs:
   - `new_facts[]` — genuinely new information worth storing
   - `updated_facts[]` — old fact ID + new content (supersedes)
   - `self_model_updates{}` — updates to about_seb, current_focus blocks
   - `emotional_signals[]` — mood/affect observations

**Implementation pattern:**

```
server/subagents/memory_consolidator.py

class MemoryConsolidator:
    INTERVAL = 8  # turns between consolidation runs

    def should_consolidate(conv_id) -> bool
    def consolidate(conv_id, recent_messages) -> dict
        # Haiku call with CONSOLIDATION_PROMPT
        # Parse JSON response
        # add_fact() for new facts
        # update_fact() for superseded facts
        # update self-model blocks
        # Post MEMORY_RECALL signal to workspace
```

**Trigger point:** After `extract_and_store_facts()` completes, check `consolidator.should_consolidate(conv_id)`. If true, run `consolidator.consolidate()` in a background thread.

**Token cost:** ~500 input + 300 output tokens per consolidation run (Haiku). At 8 turns, that's ~0.01 cents per consolidation. Negligible.

### 4.2 Inner Thoughts

**Purpose:** Generate internal reflections after each response that influence future responses. This is the "subconscious" — it notices things the main agent didn't say, flags opportunities, tracks emotional undercurrents.

**From ai-agent-env:** The `InnerThoughts` class takes conversation context + agent response, produces a JSON thought with:
- `thought`: 2-3 sentence reflection
- `salience`: 1-5
- `type`: observation, concern, opportunity, connection, emotional
- `follow_up`: suggested action for next turn

**BITOS adaptation:**

```
server/subagents/inner_thoughts.py

class InnerThoughts:
    def reflect(conversation_context, agent_response) -> dict | None
        # Haiku call with INNER_THOUGHT_PROMPT
        # Returns thought dict or None

    def get_prompt_block() -> str
        # Returns high-salience thoughts (>= 4) for system prompt injection
        # Max 3 recent thoughts, formatted as "Subconscious Notes"
```

**Key design decisions:**

1. **Rolling buffer of 10 thoughts** — older thoughts drop off. Only the most recent high-salience ones make it into the system prompt.
2. **Salience threshold for injection = 4** — thoughts scored 1-3 are stored but don't influence the next response. Thoughts scored 4-5 are injected into the system prompt.
3. **Runs as background thread** — never blocks the SSE stream. The thought from turn N influences turn N+1.
4. **Posts to workspace** — other consumers (heartbeat, future features) can react to inner thoughts.

**Token cost:** ~300 input + 100 output tokens per turn (Haiku). ~0.003 cents per turn. At 50 turns/day, ~$0.05/month.

### 4.3 Proactive Memory Recall

**Purpose:** When perception detects relevant topics or entities, proactively search memory for related facts — even if the user didn't ask for them.

This isn't a separate sub-agent. It's an enhancement to the pre-processing pipeline:

```
1. Perception extracts entities and topics
2. For each entity/topic, search memory (FTS5)
3. Merge with the standard keyword search results
4. Deduplicate
5. Inject into system prompt
```

**Example:** User says "I'm meeting with Joaquin tomorrow." Perception extracts entity "Joaquin". Memory search finds: "Joaquin is Seb's project manager at SSS." This fact gets injected even though the user's message itself wouldn't surface it via keyword search.

---

## 5. Persistent Identity / Self-Model

### 5.1 Design

Port `self_model.py` from ai-agent-env. The self-model is a set of named text blocks stored in SQLite, always loaded into the system prompt.

**Default blocks for BITOS:**

```python
DEFAULT_BLOCKS = {
    "identity": {
        "content": (
            "You are BITOS — a pocket AI companion running on a physical device "
            "(Pi Zero 2W + Whisplay HAT). You are Seb's personal agent, not a generic assistant. "
            "You have continuity across conversations through persistent memory and this self-model. "
            "You speak concisely because your responses display on a small screen and are read aloud via TTS."
        ),
        "description": "Core identity",
    },
    "about_seb": {
        "content": (
            "Seb (Sebastian) is a freelance experiential producer based in LA. "
            "Active projects: SSS (Nike House activation), Tender Fest, The Hypnotist documentary. "
            "He practices Siddha Yoga meditation and clowning in the Gaulier tradition. "
            "He is building BITOS as a hardware project. He values directness and systems thinking."
        ),
        "description": "What you know about Seb — updated through conversations",
    },
    "operating_principles": {
        "content": (
            "1. Be direct — no filler, no hedging, no corporate speak.\n"
            "2. Keep it brief — 1-3 sentences unless detail is requested.\n"
            "3. Be proactive — surface relevant context without being asked.\n"
            "4. Maintain continuity — reference past conversations naturally.\n"
            "5. Admit gaps — don't fabricate.\n"
            "6. Respect the device — you're on a 240x280 pixel screen."
        ),
        "description": "How you should behave",
    },
    "current_focus": {
        "content": "Building BITOS hardware and software. Active mode: varies by session.",
        "description": "What's currently happening — auto-updated",
    },
}
```

**Character limits per block** (from ai-agent-env pattern):
- identity: 1500 chars
- about_seb: 2000 chars
- operating_principles: 1500 chars
- current_focus: 500 chars
- custom blocks: 2000 chars

**New agent tool:**

```json
{
    "name": "update_self_model",
    "description": "Update a block of your persistent identity. Use when you learn something important that should persist across all future conversations.",
    "input_schema": {
        "type": "object",
        "properties": {
            "key": {"type": "string", "description": "Block key: identity, about_seb, operating_principles, current_focus, or custom"},
            "content": {"type": "string", "description": "New content for this block"}
        },
        "required": ["key", "content"]
    }
}
```

### 5.2 Conversation Seeding

When a new conversation starts (no `conversation_id`), the system prompt should include:

1. Self-model blocks (always)
2. Recent conversation summary (last 3 conversations, compressed)
3. High-salience inner thoughts from the last session
4. Any pending follow-ups flagged by inner thoughts

**Conversation summarization** (new component):

After a conversation ends (detected by idle timeout or new conversation start), summarize it into a 2-3 sentence digest. Store in a `conversation_summaries` table:

```sql
CREATE TABLE conversation_summaries (
    conversation_id TEXT PRIMARY KEY,
    summary TEXT NOT NULL,
    topics TEXT,  -- JSON array of topic labels
    created_at TEXT NOT NULL
);
```

The summarizer runs as a background Haiku call. Recent summaries (last 5) are injected into the system prompt of new conversations under "Recent Sessions."

### 5.3 Self-Model Update Triggers

The self-model should update in two ways:

1. **Explicit tool call** — the main agent decides to update a block (e.g., learns Seb moved to a new city)
2. **Consolidator-driven** — the memory consolidator's `self_model_updates` output triggers updates to about_seb or current_focus

Both paths go through the same `SelfModel.update_block()` with character limits enforced.

---

## 6. Global Workspace (GWT)

### 6.1 Architecture

The Global Workspace is a shared blackboard where all sub-agents post signals. The main agent's system prompt is enriched with high-salience signals from the workspace.

```
                    ┌──────────────┐
                    │  User Input  │
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
    ┌──────────────┐ ┌──────────┐ ┌──────────────┐
    │  Perception  │ │  Memory  │ │  Heartbeat   │
    │  (Haiku)     │ │  Recall  │ │  (background)│
    └──────┬───────┘ └────┬─────┘ └──────┬───────┘
           │              │              │
           ▼              ▼              ▼
    ┌─────────────────────────────────────────────┐
    │           GLOBAL WORKSPACE                  │
    │  (in-memory blackboard, max 200 signals)    │
    │                                             │
    │  Salience competition: signals decay over   │
    │  time (half-life 15s). Highest effective    │
    │  salience wins the "spotlight."             │
    └─────────────────────┬───────────────────────┘
                          │
             ┌────────────┼───────────┐
             ▼            ▼           ▼
    ┌─────────────┐ ┌──────────┐ ┌────────────┐
    │ System      │ │ Trace    │ │ Heartbeat  │
    │ Prompt      │ │ Endpoint │ │ Awareness  │
    │ Injection   │ │ (debug)  │ │ (future)   │
    └─────────────┘ └──────────┘ └────────────┘
```

### 6.2 Signal Types

```python
class SignalType(Enum):
    PERCEPTION = "perception"           # Intent/entity/routing classification
    MEMORY_RECALL = "memory_recall"     # Relevant memories surfaced
    INNER_THOUGHT = "inner_thought"     # Subconscious reflection
    EMOTION = "emotion"                 # Emotional state detected in conversation
    TOOL_USE = "tool_use"               # Tool was called
    NOTIFICATION = "notification"       # External notification arrived (iMessage, email)
    HEARTBEAT = "heartbeat"             # Proactive heartbeat action fired
    CONTEXT_UPDATE = "context_update"   # Live context changed (calendar event starting, etc.)
```

### 6.3 Salience Scoring

Each signal has a base salience (1-5) assigned by the source:

| Source | Typical Salience | When Higher |
|--------|-----------------|-------------|
| Perception | 3 | High urgency = 4, entities found = 4 |
| Memory recall | 3 | High-confidence match = 4, multiple matches = 4 |
| Inner thought | 2-4 | Assigned by Haiku based on importance |
| Emotion | 3-5 | Strong emotional signal = 5 |
| Tool use | 2 | Approval-required tool = 4 |
| Notification | 3-4 | Unread from known contact = 4, urgent = 5 |
| Heartbeat | 2 | Morning briefing = 3, overdue tasks = 4 |

**Decay:** Signals decay exponentially with a 15-second half-life. A salience-5 signal that's 30 seconds old has effective salience of 1.25. This ensures the workspace naturally clears and doesn't accumulate stale signals.

### 6.4 Spotlight: What Makes It Into the System Prompt

The workspace's `get_high_salience_summary()` method returns formatted text for injection into the system prompt. Budget: **max 500 tokens** (roughly 2000 characters).

**Rules:**
1. Only signals with effective salience >= 3.0 (after decay) are considered
2. Maximum 5 signals in the spotlight
3. Formatted as a `## Consciousness Signals` block
4. Each signal is one line: `- [Source] (salience N): content summary`

**Token budget enforcement:**

The system prompt has a hard character budget. The consciousness block cannot exceed 2000 characters. If it would, lower-salience signals are dropped first.

```
System prompt token breakdown (target: < 4000 tokens):
  Base context:          ~300 tokens
  Agent mode:            ~150 tokens
  Self-model blocks:     ~800 tokens (identity + about_seb + principles + focus)
  Memory facts:          ~500 tokens (max 10 facts)
  Consciousness signals: ~500 tokens (max 5 signals)
  Context blocks:        ~300 tokens (tasks, location, battery, web search hint)
  Inner thoughts:        ~200 tokens (max 3 high-salience thoughts)
  Response hint:         ~20 tokens
  ────────────────────────────────
  Total:                ~2770 tokens
```

This leaves headroom within a 4000-token system prompt budget. The main model (Sonnet) has 200K context, so 4000 tokens for system is comfortable.

### 6.5 Implementation

```python
# server/consciousness.py

class GlobalWorkspace:
    def __init__(self, max_history=200):
        self._signals: list[WorkspaceSignal] = []
        self._trace: list[dict] = []

    def post(self, signal: WorkspaceSignal): ...
    def get_recent(self, limit=20, min_salience=1) -> list[dict]: ...
    def get_high_salience_summary(self, max_chars=2000) -> str: ...
    def get_trace(self, limit=50) -> list[dict]: ...
    def compete(self) -> AwarenessState: ...

# Singleton, created at server startup
workspace = GlobalWorkspace()
```

**Trace endpoint** (for debugging):

```
GET /consciousness/trace?limit=50
  -> Returns recent workspace signals with timestamps, sources, salience
```

---

## 7. Extended Thinking

### 7.1 Current State

BITOS has an `extended_thinking` toggle in ChatRequest. When enabled, it sets `max_tokens=16000` and `thinking={"type": "enabled", "budget_tokens": 10000}`. The device UI has a toggle.

### 7.2 Conservative Usage Criteria

Extended thinking should be triggered automatically (not just manually) when:

1. **Perception salience >= 5** — extremely important message
2. **Intent is "reflection" or "creative"** — deep thinking modes
3. **Multi-step reasoning detected** — perception identifies a complex question
4. **Agent requests it via `think_deeper` tool** — the agent itself decides it needs more time

When triggered automatically, use a smaller budget:

| Trigger | Budget Tokens | Max Output Tokens |
|---------|--------------|-------------------|
| Manual toggle | 10,000 | 16,000 |
| Auto (salience 5) | 5,000 | 8,000 |
| Auto (reflection/creative) | 3,000 | 4,000 |
| think_deeper tool | 5,000 | 8,000 |

### 7.3 think_deeper Tool

Ported from ai-agent-env. The main agent can call this tool when it realizes a question needs deeper reasoning:

```json
{
    "name": "think_deeper",
    "description": "Step back and reason through a complex question before responding. Use for multi-step problems, tradeoff analysis, or when you're unsure. Your thinking will be visible in the consciousness trace.",
    "input_schema": {
        "type": "object",
        "properties": {
            "question": {"type": "string", "description": "What you need to think through"},
            "context": {"type": "string", "description": "Relevant context for reasoning"}
        },
        "required": ["question"]
    }
}
```

**Implementation:** When the agent calls think_deeper, the tool handler makes a separate Sonnet call with extended thinking enabled, returns the thinking result as the tool response, and posts a RECURSIVE_THOUGHT signal to the workspace.

### 7.4 Cost Guardrails

Extended thinking with Sonnet is significantly more expensive. Guardrails:

1. **Max 3 extended thinking calls per conversation** — tracked per conv_id
2. **Daily budget cap** — track tokens in SQLite, stop auto-triggering after $X/day
3. **Device battery check** — don't auto-trigger extended thinking when battery < 20%

---

## 8. Architecture Diagram: Full Pipeline

```
┌──────────────────────────────────────────────────────────────────────┐
│                        USER MESSAGE (from device)                   │
└────────────────────────────────┬─────────────────────────────────────┘
                                 │
                                 ▼
                    ┌────────────────────────┐
                    │   ChatRequest Endpoint  │
                    │   POST /chat            │
                    └────────────┬────────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              │ (parallel)       │ (parallel)        │
              ▼                  ▼                   ▼
    ┌──────────────────┐ ┌─────────────────┐ ┌──────────────────┐
    │   PERCEPTION     │ │  MEMORY RECALL  │ │  SELF-MODEL      │
    │   (Haiku)        │ │  (FTS5 search)  │ │  (SQLite load)   │
    │                  │ │                 │ │                  │
    │ - intent         │ │ - keyword match │ │ - identity       │
    │ - entities       │ │   on message    │ │ - about_seb      │
    │ - salience       │ │ - entity-based  │ │ - principles     │
    │ - tool suggest   │ │   recall        │ │ - current_focus  │
    │ - memory_query   │ │                 │ │                  │
    └───────┬──────────┘ └───────┬─────────┘ └───────┬──────────┘
            │                    │                    │
            └────────────────────┼────────────────────┘
                                 │
                                 ▼
                    ┌────────────────────────┐
                    │   GLOBAL WORKSPACE     │
                    │                        │
                    │ - Post perception sig   │
                    │ - Post memory signals   │
                    │ - Run compete()         │
                    │ - Get spotlight summary │
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌────────────────────────┐
                    │   BUILD SYSTEM PROMPT  │
                    │                        │
                    │ - Base + agent mode     │
                    │ - Self-model blocks     │
                    │ - Memory facts          │
                    │ - Consciousness signals │
                    │ - Inner thoughts        │
                    │ - Context blocks        │
                    │ - Response hint         │
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌────────────────────────┐
                    │   MAIN AGENT (Sonnet)  │
                    │                        │
                    │ - Streaming response    │
                    │ - Tool use loop (5 max) │
                    │ - Extended thinking     │
                    │   (auto or manual)      │
                    └────────────┬────────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              │                  │                   │
              ▼                  ▼                   ▼
    ┌──────────────────┐ ┌─────────────────┐ ┌──────────────────┐
    │  SSE STREAM      │ │  BACKGROUND     │ │  WORKSPACE POST  │
    │  to Device       │ │  PROCESSING     │ │                  │
    │                  │ │                 │ │ - Tool use sigs  │
    │ - text chunks    │ │ - Fact extract  │ │ - Response meta  │
    │ - setting changes│ │ - Inner thought │ │                  │
    │ - perception     │ │ - Consolidation │ │                  │
    │ - conv_id        │ │   (every 8 turns│ │                  │
    │ - [DONE]         │ │ - Conv summary  │ │                  │
    └──────────────────┘ └─────────────────┘ └──────────────────┘
```

### 8.1 Timing Budget

The pre-processing (perception + memory + self-model) runs in parallel. Target: **< 500ms total latency added** before the main model starts generating.

| Step | Target Latency | Notes |
|------|---------------|-------|
| Perception (Haiku) | 300-400ms | Single API call, ~150 tokens output |
| Memory recall (FTS5) | < 10ms | Local SQLite, no network |
| Self-model load | < 5ms | Local SQLite, cached in memory |
| Workspace compete | < 1ms | In-memory computation |
| System prompt build | < 5ms | String concatenation |
| **Total pre-processing** | **~400ms** | Dominated by Haiku call |

The 400ms overhead is acceptable for a conversational system. The Haiku call is the bottleneck — if it becomes a problem, perception can be made optional (skip for follow-up messages in the same conversation, run only on first message or after long silence).

---

## 9. Implementation Phases

### Phase 1: Foundation (Sprint 1, ~2-3 days)

**Goal:** Global Workspace + Enhanced Perception + Self-Model. No new Haiku calls beyond what already exists.

**Files to create:**
- `server/consciousness.py` — GlobalWorkspace, WorkspaceSignal, SignalType (port from ai-agent-env, strip avatar)
- `server/self_model.py` — SelfModel with SQLite blocks (port from ai-agent-env, sync SQLite)

**Files to modify:**
- `server/perception.py` — Add entities, topics, salience, needs_memory, memory_query, needs_context fields to Perception dataclass. Update classifier prompt.
- `server/agent_modes.py` — Refactor `get_system_prompt()` to accept self-model text and consciousness summary. Add token budgeting.
- `server/main.py` — Wire up: create workspace singleton at startup, post perception signal, load self-model into system prompt, add `/consciousness/trace` endpoint.

**Files to add to agent_tools:**
- `update_self_model` tool definition + handler

**New endpoints:**
- `GET /consciousness/trace` — debug view of workspace signals
- `GET /self-model` — current self-model blocks
- `PUT /self-model/{key}` — manually update a block

**Testing:**
- Existing tests should still pass (perception returns a superset of current fields)
- Add tests for workspace signal posting, self-model CRUD, enhanced perception parsing

### Phase 2: Subconscious (Sprint 2, ~2-3 days)

**Goal:** Inner Thoughts + Memory Consolidator. Two new background Haiku calls per conversation turn / batch.

**Files to create:**
- `server/subagents/__init__.py`
- `server/subagents/inner_thoughts.py` — port from ai-agent-env, adapt to sync Anthropic client in background thread
- `server/subagents/memory_consolidator.py` — port from ai-agent-env, adapt to BITOS memory_store

**Files to modify:**
- `server/main.py` — After SSE stream completes, fire inner_thoughts.reflect() in background thread. Check consolidator.should_consolidate() and run if needed.
- `server/agent_modes.py` — Add inner thoughts prompt block to system prompt (from inner_thoughts.get_prompt_block())
- `server/consciousness.py` — Inner thoughts and consolidator post signals to workspace

**New endpoints:**
- `GET /inner-thoughts` — recent inner thoughts buffer
- `POST /consciousness/consolidate` — manually trigger memory consolidation

**Token cost added:** ~400 tokens/turn Haiku (inner thoughts) + ~800 tokens every 8 turns (consolidation) = roughly $0.10/month at 50 turns/day.

### Phase 3: Intelligence (Sprint 3, ~2-3 days)

**Goal:** Proactive memory recall + conversation summarization + extended thinking gating.

**New features:**
- Entity-based memory recall in pre-processing pipeline
- Conversation summarization on conversation end (idle timeout or new conv start)
- Auto-trigger extended thinking based on perception salience and intent
- think_deeper tool for agent-initiated deep reasoning
- Token budget tracking for extended thinking guardrails

**Files to create:**
- `server/conversation_summarizer.py` — Haiku summarization of completed conversations, stores in conversation_summaries table

**Files to modify:**
- `server/main.py` — Add entity-based recall to parallel pre-processing. Add think_deeper tool. Add extended thinking auto-trigger logic. Add conversation summary injection for new conversations.
- `server/conversation_store.py` — Add conversation_summaries table and CRUD
- `server/agent_tools.py` — Add think_deeper tool definition + handler
- `server/heartbeat.py` — Post HEARTBEAT signals to workspace when proactive messages fire

### Phase 4: Polish (Sprint 4, ~1-2 days)

**Goal:** Tuning, monitoring, cost tracking.

**Features:**
- Token cost tracking dashboard (how much is consciousness costing?)
- Salience threshold tuning (A/B test different thresholds)
- Perception caching (skip Haiku for follow-up messages within 30s)
- Workspace signal TTL cleanup (prune signals older than 5 minutes)
- Admin dashboard additions: consciousness state, inner thoughts, self-model editor
- Integration with heartbeat: workspace awareness influences proactive behavior

**New endpoints:**
- `GET /admin/consciousness` — full consciousness state for admin dashboard
- `GET /admin/token-usage` — daily/monthly token costs by component

---

## 10. Cost Projections

Assuming 50 conversation turns per day, Haiku at $0.25/MTok input, $1.25/MTok output:

| Component | Frequency | Input Tokens | Output Tokens | Daily Cost |
|-----------|-----------|-------------|---------------|------------|
| Perception | Every turn | ~200 | ~100 | $0.009 |
| Fact extraction | Every turn | ~300 | ~100 | $0.011 |
| Inner thoughts | Every turn | ~400 | ~100 | $0.013 |
| Consolidation | Every 8 turns | ~800 | ~300 | $0.003 |
| Conv summary | Per conversation (~5/day) | ~500 | ~150 | $0.002 |
| **Total Haiku overhead** | | | | **~$0.04/day** |
| **Monthly** | | | | **~$1.14** |

The main Sonnet model cost (the actual response) is separate and already exists. The consciousness layer adds roughly $1/month in Haiku costs.

---

## 11. File Structure After Implementation

```
server/
  consciousness.py          # NEW — GlobalWorkspace, WorkspaceSignal, SignalType
  self_model.py             # NEW — SelfModel, persistent identity blocks
  perception.py             # MODIFIED — enhanced with entities, salience, tool suggest
  agent_modes.py            # MODIFIED — token-budgeted prompt builder
  main.py                   # MODIFIED — wiring, new endpoints
  agent_tools.py            # MODIFIED — update_self_model, think_deeper tools
  memory_store.py           # UNCHANGED
  fact_extractor.py         # UNCHANGED (still runs per-turn)
  conversation_store.py     # MODIFIED — conversation_summaries table
  conversation_summarizer.py # NEW — Haiku conversation digest
  heartbeat.py              # MODIFIED — posts workspace signals
  llm_bridge.py             # UNCHANGED
  subagents/
    __init__.py             # NEW
    inner_thoughts.py       # NEW — subconscious reflection
    memory_consolidator.py  # NEW — batch memory consolidation
  data/
    memory.db               # existing
    conversations.db        # existing
    heartbeat.db            # existing
    self_model.db           # NEW (or add table to existing db)
```

---

## 12. Open Questions

1. **Single DB vs multiple?** BITOS currently uses 3 separate SQLite databases (memory, conversations, heartbeat). Should self-model and consciousness signals go in a new DB or be added to an existing one? Recommendation: add self_model table to memory.db, keep consciousness signals in-memory only (no persistence needed — they decay in 60 seconds).

2. **Perception on every turn?** The Haiku pre-call adds ~400ms latency. For rapid-fire follow-up messages, consider caching perception for messages within 30 seconds of each other in the same conversation. The follow-up likely has the same intent/context.

3. **Inner thoughts on every turn?** For trivial exchanges ("thanks", "ok", "got it"), inner thoughts waste tokens. Gate on: message length > 20 chars AND perception salience >= 2.

4. **Self-model versioning?** Should we track the full history of self-model changes? ai-agent-env tracks `update_count` but not the content diff. For debugging, storing the last 5 versions per block would be useful. But for Phase 1, just tracking count and timestamp is fine.

5. **Heartbeat integration?** The heartbeat system runs independently. In Phase 4, it should consume workspace signals — e.g., if inner thoughts flag "Seb mentioned a deadline tomorrow," the heartbeat should schedule a reminder. This is a Phase 4 feature.
