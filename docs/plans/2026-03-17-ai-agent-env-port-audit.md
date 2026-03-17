# AI Agent Environment -> BITOS Server Port Audit

**Date:** 2026-03-17
**Source:** `/Users/seb/Downloads/Manual Library/Seb's Mind/ai-agent-env/src/`
**Target:** `/Users/seb/bitos/server/`

---

## 1. Full Component Inventory of ai-agent-env

### src/server.py — Main FastAPI Application & Chat Orchestrator
**What it does:** The central entry point. Initializes 15+ subsystems on startup (DB, memory, vault, MCP, self-model, persistent state, tamagotchi needs, animation config, workspace, heartbeat, awareness loop, micro-behaviors, Antigravity bridge, Telegram). Houses the `/chat` endpoint which runs the full orchestration pipeline: perception -> enrichment -> system prompt assembly -> LLM call with tool loop -> post-processing (fact extraction, inner thoughts, memory consolidation, gesture annotation, idle director planning).

**Key classes/functions:**
- `lifespan()` — startup/shutdown lifecycle manager (~200 lines of initialization)
- `chat()` — main `/chat` endpoint (~400 lines, the core orchestration pipeline)
- `broadcast_blob_event()` — pushes events to all connected blob WebSocket clients
- `cancel_idle_timeline()` / `start_idle_timeline()` — manages idle blob choreography
- `create_background_task()` — lifecycle-managed async task launcher
- `calculate_cost()` / `serialize_content()` — utility helpers

**Dependencies:** Every other src module. External: anthropic, fastapi, pydantic, aiosqlite, websockets.

**Token/cost implications:**
- Perception call: Haiku, ~300 input / ~100 output tokens per message ($0.0006)
- Main LLM call: Sonnet, ~2000-8000 input / ~500-2000 output ($0.015-0.054)
- Tool loop: up to 5 additional Sonnet calls per turn
- Post-processing (all Haiku, all background):
  - Fact extraction: ~500 in / ~300 out ($0.0005)
  - Inner thoughts: ~3000 in / ~256 out ($0.003)
  - Gesture annotation: ~1500 in / ~1024 out ($0.005)
  - Memory consolidation: ~3000 in / ~1024 out (every 8 turns) ($0.003)
  - Idle director: ~2000 in / ~512 out (every 3rd response) ($0.003)

### src/perception.py — Intent/Entity Classifier
**What it does:** Fast Haiku pre-call to classify user messages into structured envelopes (intent, entities, topics, urgency, tool needs, memory needs, context needs). Returns JSON parsed from LLM response with fallback defaults.

**Key classes/functions:**
- `perceive(client, model, message)` — async classifier, returns dict
- `parse_json_response(text)` — robust JSON extraction (direct, code block, brace match)

**Dependencies:** anthropic (via passed client), json, re. No other src imports.

**Token/cost:** Haiku, ~200 input / ~100 output per call. ~$0.0006/call.

### src/consciousness.py — Global Workspace Theory (GWT) Blackboard
**What it does:** Implements a shared signal blackboard inspired by Global Workspace Theory. Sub-agents post WorkspaceSignals with salience (1-5). The workspace supports salience competition (exponential decay, 15s half-life), awareness state tracking (Attention Schema Theory hybrid), and listener pub/sub. Also defines all 10 agent body control tool schemas (perform_gesture, think_deeper, play_sequence, schedule_reminder, adjust_avatar, move_avatar, get_avatar_state, create_sequence, list_sequences, evolve_sequence).

**Key classes/functions:**
- `GlobalWorkspace` — signal store, pub/sub, salience competition, trace
- `WorkspaceSignal` — dataclass (source, type, salience, content, timestamp)
- `AwarenessState` — dataclass (focal_signal, attention_reason, peripheral, mood, idle_seconds)
- `SignalType` — enum of 12 signal types
- `CONSCIOUSNESS_PREAMBLE` — shared identity prompt for all sub-agents
- `get_gesture_tool_definitions()` — 10 avatar body control tool schemas

**Dependencies:** asyncio, math, time, dataclasses, enum. No external packages. No other src imports.

**Token/cost:** Zero — pure in-memory data structure. The tool definitions are passed to the main LLM call and add ~3000 tokens to every system prompt.

### src/self_model.py — Persistent Agent Identity
**What it does:** SQLite-backed self-model with 5 default blocks (identity, capabilities, about_seb, operating_principles, current_focus). Each block has character limits (500-2000). The agent can update its own identity via tool calls. Builds a system prompt section from all blocks.

**Key classes/functions:**
- `SelfModel` — init_schema, get_block, get_all_blocks, update_block, build_prompt_section
- `DEFAULT_BLOCKS` — 5 seed blocks with content
- `MAX_BLOCK_CHARS` — per-block character limits (Letta/MemGPT pattern)
- `get_tool_definition()` — update_self_model tool schema

**Dependencies:** json, logging, datetime, zoneinfo, aiosqlite (via passed db).

**Token/cost:** Zero direct LLM calls. Adds ~1500-3000 tokens to system prompt.

### src/live_context.py — Auto-Refreshing Ambient Context
**What it does:** Background loop (10-min refresh) that fetches current time, weather (wttr.in), calendar events (macOS Calendar via osascript), today's tasks (Things via MCP), and tech headlines (Hacker News API). Builds a formatted context block for the system prompt.

**Key classes/functions:**
- `LiveContext` — start, stop, refresh, get_prompt_block
- Providers: `_get_datetime`, `_get_weather`, `_get_calendar_events`, `_get_today_tasks`, `_get_headlines`

**Dependencies:** httpx, asyncio, subprocess. src: MCP bridge (optional).

**Token/cost:** Zero LLM calls. HTTP calls every 10 min. Adds ~200-500 tokens to system prompt.

### src/heartbeat.py — Proactive Background Loop
**What it does:** 60-second tick loop that checks: (1) scheduled reminders from SQLite, (2) morning/evening time-of-day greetings, (3) idle check-ins after 30+ min silence. Delivers messages via WebSocket to connected clients, falls back to macOS notifications. Integrates with PersistentState for emotional context in greetings.

**Key classes/functions:**
- `AgentHeartbeat` — init_schema, start, stop, schedule_reminder, schedule_follow_up, schedule_custom, cancel_scheduled, list_scheduled, record_user_activity, get_status
- `_check_scheduled_actions`, `_check_time_triggers`, `_check_idle` — tick handlers

**Dependencies:** asyncio, json, subprocess, uuid, datetime, zoneinfo, aiosqlite. src: persistent_state (optional).

**Token/cost:** Zero LLM calls. The ai-agent-env version uses static messages (no Haiku generation for greetings).

### src/persistent_state.py — Experiential Substrate
**What it does:** SQLite-backed persistent state across 6 domains: emotional_trajectory (valence/arousal/momentum), relationship_model (trust/surprises/highlights), temporal_presence (absence tracking/streaks/daily patterns), dream_journal (idle synthesis/pending insights), expression_feedback (blob state cognition loop), tamagotchi_needs. In-memory cache for fast reads, async write-through to SQLite.

**Key classes/functions:**
- `PersistentState` — init_schema, get, update, get_all
- Domain helpers: record_mood, record_session_start/end, add_surprise, add_dream_entry, pop_pending_insights, record_expression, increment_trust, add_shared_highlight
- `build_prompt_section()` — builds system prompt block from emotional/temporal/relationship state

**Dependencies:** json, logging, datetime, zoneinfo, aiosqlite.

**Token/cost:** Zero LLM calls. Adds ~100-300 tokens to system prompt when state is notable.

### src/awareness_loop.py — Continuous Consciousness Heartbeat
**What it does:** Background loop ticking every 4 seconds. Runs GWT salience competition, detects focal signal changes and mood shifts, broadcasts to blob avatar, generates ambient micro-thoughts via Haiku during idle periods (>30s idle, 45s cooldown). Bridges "agent only exists when spoken to" to "continuously aware."

**Key classes/functions:**
- `AwarenessLoop` — start, stop, tick, get_status
- `_generate_ambient_thought()` — Haiku call for 1-line idle observations

**Dependencies:** asyncio, time. src: consciousness (GlobalWorkspace, signals), live_context (optional).

**Token/cost:** Ambient thoughts: Haiku, ~300 in / ~50 out, every 45s when idle. ~$0.0003/thought. Could accumulate to ~$0.02/hour if constantly idle.

### src/tamagotchi.py — Needs Engine
**What it does:** Four vital needs (hunger, energy, fun, affection) with time-based decay rates (2.5, 1.0, 3.0, 2.0 points/hour). Care actions replenish needs. Low needs affect blob expression and emotional trajectory. Builds system prompt sections when needs are low.

**Key classes/functions:**
- `NeedsEngine` — decay, care, get_needs, get_mood_influence, get_blob_emotion, build_prompt_section, get_idle_context

**Dependencies:** datetime, logging. src: persistent_state (for storage).

**Token/cost:** Zero LLM calls. Adds ~100-200 tokens to prompt when needs are low.

### src/memory/store.py — Memory Store with FTS5 + Semantic Dedup
**What it does:** Three-layer dedup memory: Layer 1 word-Jaccard (0.75 threshold), Layer 1.5 semantic cosine similarity via fastembed (0.85 threshold), Layer 2 LLM consolidation (every 8 turns). FTS5 full-text search with recency-weighted recall (30-day half-life, access-count modulated via FadeMem pattern).

**Key classes/functions:**
- `MemoryStore` — store, recall, forget, list_all
- `_find_similar()` — Jaccard + semantic dedup
- `_decay_factor()` — access-modulated exponential decay
- `_escape_fts_query()` — FTS5 query sanitizer

**Dependencies:** aiosqlite, numpy, fastembed (optional), math, uuid, datetime.

**Token/cost:** Zero direct LLM calls (dedup is algorithmic). The semantic layer uses fastembed (local CPU inference, ~5ms/embed).

### src/memory/post_process.py — Per-Turn Fact Extraction
**What it does:** Background task that calls Haiku to extract facts from each conversation turn. Stores extracted facts via MemoryStore (which handles dedup).

**Key classes/functions:**
- `extract_and_store_facts()` — async function

**Dependencies:** anthropic (via passed client). src: perception (parse_json_response), memory.store.

**Token/cost:** Haiku, ~500 in / ~300 out per turn. ~$0.0005/turn.

### src/memory/vault.py — Obsidian Vault Indexer
**What it does:** Indexes an Obsidian vault into FTS5-searchable chunks. Classifies files into 3 tiers. Parses YAML frontmatter. Chunks by heading (max 2000 chars). Loads core identity files (tier 1) for system prompt injection.

**Key classes/functions:**
- `VaultIndexer` — init_schema, index_vault, search, get_core_context, get_stats

**Dependencies:** aiosqlite, yaml, json, re, pathlib.

**Token/cost:** Zero LLM calls. Core context adds ~2000-8000 tokens to system prompt.

### src/subagents/memory_consolidator.py — Batch Memory Consolidation
**What it does:** Runs every 8 turns. Reviews recent conversation, existing memories, and self-model. Extracts new facts, updates superseded facts, updates self-model blocks, detects emotional signals. Feeds emotional signals into persistent state trajectory. Increments trust on successful consolidation.

**Key classes/functions:**
- `MemoryConsolidator` — should_consolidate, reset_counter, consolidate

**Dependencies:** anthropic (via passed client), json. src: memory.store, self_model, persistent_state.

**Token/cost:** Haiku, ~3000 in / ~1024 out, every 8 turns. ~$0.006/consolidation.

### src/subagents/inner_thoughts.py — Subconscious Reflection Layer
**What it does:** After each response, generates internal reflections (observations, concerns, opportunities, connections, emotional signals). Posts to GWT workspace. Feeds high-salience thoughts into dream journal and persistent state. High-salience thoughts (>=4) appear in system prompt.

**Key classes/functions:**
- `InnerThoughts` — reflect, get_prompt_block, get_all_thoughts

**Dependencies:** anthropic (via passed client), json. src: consciousness (PREAMBLE, workspace, signals), persistent_state.

**Token/cost:** Haiku, ~3000 in / ~256 out per turn. ~$0.003/turn.

### src/subagents/gesture_annotator.py — Response-to-Gesture Mapper
**What it does:** Takes agent response text, breaks into 1-2 sentence chunks, assigns expression + optional gesture to each chunk. Chunks are broadcast to blob avatar for real-time reaction as text streams. Falls back to rule-based annotation on failure.

**Key classes/functions:**
- `annotate_gestures()` — async function
- `_fallback_annotate()` — rule-based fallback

**Dependencies:** anthropic (via passed client), json. src: consciousness (PREAMBLE).

**Token/cost:** Haiku, ~1500 in / ~1024 out per response. ~$0.005/response. Only relevant if BITOS has blob avatar.

### src/subagents/idle_director.py — Between-Message Blob Choreographer
**What it does:** Plans 60-second idle timelines with 3-6 actions (expression changes, gestures, sequences, movements, verbal interjections). Uses LLM every 3rd call (cost control), falls back to 6 pre-built plans otherwise. Has needs-specific fallback plans (lonely, hungry, bored, tired).

**Key classes/functions:**
- `IdleDirector` — plan, _plan_with_llm, _fallback_plan

**Dependencies:** anthropic (via passed client), json, random. src: consciousness (PREAMBLE), persistent_state.

**Token/cost:** Haiku, ~2500 in / ~512 out, every 3rd response. ~$0.003/plan.

### src/subagents/orchestrator_chat.py — Project Management Agent
**What it does:** Long-lived "boss" agent with persistent conversation thread. Has access to workspace sub-agents (Scribe, Planner, Reviewer), Antigravity reader, Brave search. Separate from the main chat — this is for driving the project forward.

**Key classes/functions:**
- `OrchestratorChat` — send, get_history, clear, get_status

**Dependencies:** anthropic (AsyncAnthropic), json, uuid. src: tools (antigravity_reader, web_search), subagents (agent_runner).

**Token/cost:** Sonnet, variable. This is a separate chat interface, not part of the main pipeline.

### src/subagents/agent_runner.py — Workspace Agent Orchestrator
**What it does:** Dispatches role-based workspace agents (Scribe, Planner, Reviewer) and research sub-agents. Agents can write to a shared workspace (Obsidian docs folder).

**Dependencies:** anthropic. src: subagents (agent_roles, workspace_agent, research_agent).

**Token/cost:** Sonnet, variable per agent run.

### src/subagents/micro_behaviors.py — Subconscious Blob Animation Layer
**What it does:** Deterministic idle micro-behaviors every 3-14 seconds with zero LLM calls. Layer 1 of 3-layer animation model. Weighted random draws from a fixed behavior table (breath_sigh, curiosity_peek, micro_pulse, etc.).

**Dependencies:** asyncio, random. No LLM calls.

**Token/cost:** Zero.

### src/tools/mcp_bridge.py — MCP Server Connector
**What it does:** Connects to MCP servers via stdio transport. Registers tools with namespace prefixes. Routes tool calls to the correct session. Health checks via ping.

**Key classes/functions:**
- `MCPBridge` — connect, call_tool, get_tool_schemas, health_check, shutdown

**Dependencies:** mcp (ClientSession, StdioServerParameters, stdio_client), asyncio.

**Token/cost:** Zero direct LLM cost. Tool schemas add ~100-500 tokens per connected server to the system prompt.

### src/tools/file_tools.py — File Operations
**What it does:** Async-safe file read/write/search/list operations. Truncates reads at 10K chars. 4 tool schemas for Claude API.

**Dependencies:** asyncio, os.

**Token/cost:** Zero.

### src/tools/web_search.py — Brave Search API
**What it does:** Brave web search with structured results (title, URL, description, age). Country/language/freshness filtering.

**Dependencies:** httpx.

**Token/cost:** Zero LLM cost. Brave API: free tier 2K queries/month.

### src/tools/safety.py — Cost Guard & Loop Detector
**What it does:** CostGuard tracks per-conversation and hourly spending limits. LoopDetector prevents identical tool calls (max 3 identical, max 25 total per turn).

**Dependencies:** json, time.

**Token/cost:** Zero.

### src/tools/antigravity.py — Antigravity IDE Bridge
**What it does:** Bridges to Google Antigravity IDE via proxy or CDP. Not relevant to BITOS.

### src/tools/cdp_navigator.py — Chrome DevTools Protocol
**What it does:** CDP automation for Antigravity. Not relevant to BITOS.

### src/tools/telegram.py — Telegram Notifications
**What it does:** Sends outbound Telegram notifications when Antigravity tasks complete.

### src/subagents/antigravity_orchestrator.py — Antigravity Task Lifecycle
**What it does:** Manages async task lifecycle for Antigravity. Not relevant to BITOS.

### src/subagents/automation_loop.py — Self-Driving Antigravity Conversations
**What it does:** Multi-turn automation loop for Antigravity. Not relevant to BITOS.

### src/blob_sequences.py — Blob Animation Sequence Player
**What it does:** Loads animation sequences from JSON, maps pipeline moods to sequences, plays sequences over WebSocket to the blob emulator with step timing.

**Dependencies:** asyncio, json, websockets. Only relevant if BITOS has blob avatar.

### src/animation_config.py — Persistent Animation Configuration
**What it does:** SQLite-backed animation config (expression visuals, gesture impulses, speed, boot duration). Agent can read/update its own animation params via tools.

**Dependencies:** json, aiosqlite. Only relevant if BITOS has blob avatar.

### src/db/conversations.py — Conversation CRUD
**What it does:** SQLite conversation and message storage. Provides history formatted for Claude API. Trims to first 2 + last N messages when history is long.

**Dependencies:** aiosqlite, json, uuid, pathlib.

### src/voice/ws_handler.py — WebSocket Voice Streaming
**What it does:** WebSocket endpoint for hardware device audio streaming. Record-then-process flow with blob state management.

**Dependencies:** asyncio, fastapi (WebSocket). src: blob_sequences.

### src/workers/base.py — Worker Agent Loop
**What it does:** Reusable agentic loop for tool-using Haiku workers with loop detection.

**Dependencies:** src: server (calculate_cost, serialize_content), tools.safety.

### src/config.py — Settings
**What it does:** Pydantic settings from .env. Defines models (orchestrator=Sonnet, worker/perception=Haiku), cost limits ($1/conversation, $5/hour), paths, timezone, Antigravity/Telegram/workspace config.

---

## 2. What BITOS Server Already Has

| ai-agent-env Component | BITOS Equivalent | Status |
|------------------------|------------------|--------|
| `src/perception.py` | `server/perception.py` | **Ported** — same pattern (Haiku classifier), BITOS adds response_hint field, uses sync client |
| `src/memory/post_process.py` | `server/fact_extractor.py` | **Ported** — same pattern, BITOS version is sync (runs in thread), adds confidence + category per fact |
| `src/memory/store.py` | `server/memory_store.py` | **Partial** — BITOS has Jaccard dedup (Layer 1) but missing semantic dedup (Layer 1.5), missing recency decay, missing access-count modulation |
| `src/heartbeat.py` | `server/heartbeat.py` | **Ported and improved** — BITOS version adds LLM-generated messages (Haiku), task reminders, macOS calendar/task context gathering, activity feed integration |
| `src/db/conversations.py` | `server/conversation_store.py` | **Ported** — BITOS version is sync (sqlite3), simpler schema (no cost/token tracking per message) |
| `src/tools/web_search.py` | `server/web_search.py` | **Ported** — BITOS has its own Brave search implementation |
| `src/config.py` | `server/config.py` | **Ported** — BITOS version is simpler (env vars, no pydantic_settings) |
| Agent modes (N/A) | `server/agent_modes.py` | **BITOS-original** — 6 personality modes (producer/hacker/clown/monk/storyteller/director). No equivalent in ai-agent-env |
| LLM bridge (N/A) | `server/llm_bridge.py` | **BITOS-original** — Multi-provider bridge (Anthropic, OpenAI-compatible, OpenClaw, NanoClaw, Echo). ai-agent-env only uses Anthropic directly |
| Agent tools (N/A) | `server/agent_tools.py` | **BITOS-original** — Device settings, approval flow, iMessage/email/calendar/contacts/tasks tools. Much broader tool set than ai-agent-env's file tools |
| Activity feed (N/A) | `server/activity_feed.py` | **BITOS-original** |
| Notifications (N/A) | `server/notifications/` | **BITOS-original** |
| Voice catalog (N/A) | `server/voice_catalog.py` | **BITOS-original** |
| UI settings (N/A) | `server/ui_settings.py` | **BITOS-original** |

### What's Missing from BITOS

| ai-agent-env Component | Relevance | Notes |
|------------------------|-----------|-------|
| `consciousness.py` (GWT) | High | The core intelligence multiplier — blackboard, salience competition, awareness |
| `self_model.py` | High | Persistent evolving identity blocks (about_seb, operating_principles, current_focus) |
| `persistent_state.py` | High | Emotional trajectory, relationship model, temporal presence, dream journal |
| `live_context.py` | Medium | BITOS already gets tasks/calendar via tools; weather/time could be useful in system prompt |
| `inner_thoughts.py` | Medium | Subconscious reflection — makes agent more insightful but adds cost |
| `memory_consolidator.py` | High | BITOS extracts facts per-turn but never consolidates, deduplicates, or resolves contradictions |
| `awareness_loop.py` | Low | Only relevant if BITOS has continuous display/avatar. Generates ambient thoughts during idle |
| `tamagotchi.py` | Low | Cute but not core intelligence. Only matters for blob avatar personality |
| MCP bridge | Medium | BITOS uses direct integration adapters instead. MCP would enable pluggable tools |
| Vault indexer | Low | BITOS doesn't have an Obsidian vault to index. Would need a different knowledge source |
| Safety (CostGuard) | Medium | BITOS has no per-conversation or hourly cost limits |
| Safety (LoopDetector) | High | BITOS tool loop has no loop detection — could infinite-loop |
| Blob/animation components | Skip | BITOS has its own display system (OLED, not blob) |

---

## 3. Orchestrator Analysis

### Pipeline Stages (ai-agent-env /chat endpoint)

```
1. CANCEL idle timeline (user is talking)
2. Set _agent_busy = True
3. Record user activity (heartbeat idle tracking)
4. Record session start + increment trust (persistent state)
5. Tamagotchi care("talk")
6. Validate input + check cost budget
7. Ensure conversation exists in DB

8. PERCEPTION (Haiku, 4s timeout)
   -> Returns: intent, entities, topics, urgency, needs_tools, needs_memory, needs_context
   -> Posts WorkspaceSignal(PERCEPTION, salience=3)

9. PARALLEL ENRICHMENT
   -> Memory recall (FTS5 search from perception entities+topics)
   -> Vault search (FTS5 search from perception entities+topics)
   -> Posts WorkspaceSignal(MEMORY_RECALL) and WorkspaceSignal(VAULT_CONTEXT)

10. Store user message in DB

11. GET conversation history (last 40 messages, keeps first 2 + last N)

12. BUILD SYSTEM PROMPT (structured, with cache_control):
    a. Static (cached): self-model blocks + vault core knowledge
    b. Dynamic (per-request):
       - Live context (time, weather, calendar, tasks, headlines)
       - Inner thoughts (high-salience only, max 3)
       - Recalled memories
       - Vault search results (truncated to 500 chars each)
       - Message analysis (intent, topics, urgency)
       - Workspace consciousness signals (high-salience summary)
       - Persistent awareness (emotional trajectory, temporal, relationship)
       - Tamagotchi needs (only when low)
       - Dream insights (pending, from idle reflection)
       - Body awareness prompt (~200 tokens of avatar context)

13. GATHER TOOLS:
    - MCP tools (Things, etc.)
    - File tools (read, write, search, list)
    - Self-model update tool
    - Animation tools (update_animation, test_animation)
    - Consciousness tools (10 body control tools)

14. MAIN LLM CALL (Sonnet, max_tokens=2048)

15. TOOL USE LOOP (max 5 rounds):
    - Route to MCP, local handler, or consciousness handler
    - Post WorkspaceSignal(TOOL_USE) for each call
    - Continue conversation with tool results

16. Store assistant message in DB + update conversation cost

17. BACKGROUND POST-PROCESSING (all parallel, non-blocking):
    a. Fact extraction (Haiku, per-turn)
    b. Inner thoughts reflection (Haiku, per-turn) -> workspace signal
    c. Memory consolidation (Haiku, every 8 turns) -> updates self-model
    d. Gesture annotation (Haiku, per-turn) -> blob broadcast
    e. Idle director planning (Haiku, every ~3rd turn) -> blob timeline

18. RETURN ChatResponse
```

### How it handles tool-use loops

Simple for loop, max 5 rounds. On each round:
1. Collect all tool_use blocks from response
2. Execute each tool (MCP routing or local handler)
3. Append assistant content + tool results to messages
4. Call LLM again with full message history
5. If stop_reason != "tool_use", break

**No loop detection inside the tool loop.** The LoopDetector exists in src/tools/safety.py but is only used in the worker base (src/workers/base.py), NOT in the main chat endpoint. This is a gap.

### Turn limits and token budget management

- `max_tokens=2048` for all LLM calls (main and tool continuations)
- 5 tool-use rounds max (hardcoded)
- CostGuard checks $1/conversation and $5/hour BEFORE the call, not during
- No token budget tracking within a single turn
- History trimmed to first 2 + last 40 messages
- No extended thinking in the main /chat endpoint (only used in OrchestratorChat)

**Issues identified:**
- No protection against system prompt bloat — if vault core context (up to 8K tokens) + live context + memories + vault results + body awareness all fire, the system prompt could easily hit 10K+ tokens
- max_tokens=2048 is quite low for complex responses — tool calls that return large results can consume most of this
- No streaming in /chat — the response is synchronous, which means long tool loops block

### Extended thinking usage

ai-agent-env does NOT use extended thinking in the main /chat pipeline. It's only available in:
- `OrchestratorChat` (the project management chat, separate endpoint)
- Not the primary conversation flow

BITOS already has extended thinking support in its `llm_bridge.py` (budget_tokens=10000, max_tokens=16000), toggled via a device setting.

### Where it ran into problems

1. **Token overflow:** System prompt can grow unbounded with vault context + memories + live context + consciousness signals + body awareness
2. **Tool loop cost:** 5 rounds x Sonnet = up to ~$0.30 per turn if all rounds fire
3. **No streaming in /chat:** Synchronous response means ~5-15 second latency for complex responses
4. **Gesture annotation cost:** Running Haiku on every response purely for blob animation is expensive if there's no blob
5. **Awareness loop ambient thoughts:** Haiku calls every 45 seconds during idle accumulate ($0.02/hour idle)

### How the orchestrator could become a BITOS "mode"

The ai-agent-env orchestration pipeline could map to a new BITOS agent mode (e.g., "deep" or "conscious") that:
1. Runs perception before the main call (already exists in BITOS)
2. Adds memory enrichment to the system prompt (new)
3. Includes inner thoughts from previous turns (new)
4. Includes self-model blocks in the system prompt (new)
5. Runs memory consolidation every N turns (new)
6. Tracks persistent state (emotional, temporal, relationship) (new)

This would be an opt-in mode because it adds ~$0.01-0.02 per turn in sub-agent costs.

---

## 4. Portable Components (Priority Ranked)

### Port Directly (copy + adapt, <1 day each)

| Component | Effort | Value | Risk | Dependencies | Notes |
|-----------|--------|-------|------|-------------|-------|
| **CostGuard** (safety.py) | Low | High | None | None | BITOS has no cost limits. Copy CostGuard + adapt to BITOS sync model |
| **LoopDetector** (safety.py) | Low | High | None | None | BITOS tool loop has no loop detection — critical safety gap |
| **Self-model blocks** (self_model.py) | Low | High | Low | SQLite | Add identity/about_seb/principles blocks to system prompt. Adapt to sync SQLite |
| **parse_json_response** (perception.py) | Low | Medium | None | None | BITOS fact_extractor has its own `_parse_json` but ai-agent-env version is cleaner |

### Adapt (same concept, needs BITOS-specific implementation, 1-3 days each)

| Component | Effort | Value | Risk | Dependencies | Notes |
|-----------|--------|-------|------|-------------|-------|
| **Memory consolidation** | Medium | High | Medium (token cost) | Memory store upgrade | Biggest intelligence gap. BITOS extracts per-turn but never consolidates. Port the 8-turn consolidation cycle, adapt to sync Haiku client |
| **Memory store upgrade** | Medium | High | Low | fastembed (optional) | Add semantic dedup (Layer 1.5), recency decay, access-count modulation. Major recall quality improvement |
| **Persistent state** | Medium | High | Low | SQLite | Emotional trajectory + relationship model + temporal presence. Skip dream_journal and expression_feedback (blob-specific). Adapt to sync SQLite |
| **Live context (system prompt)** | Medium | Medium | Low | None | BITOS already fetches calendar/tasks via tools. Port weather + time as auto-injected system prompt context instead of requiring tool calls |
| **Inner thoughts** | Medium | Medium | Medium (token cost) | Persistent state | Powerful but adds ~$0.003/turn. Port as opt-in feature behind a setting |
| **System prompt assembly** | Medium | High | Low | Self-model, persistent state, memory | The multi-layer prompt assembly (static cached + dynamic per-request) is a major architecture pattern to port |
| **Cost tracking** | Low | Medium | None | None | Track tokens + cost per message and per conversation in conversation_store |

### Skip (not relevant to BITOS or superseded)

| Component | Reason |
|-----------|--------|
| Blob/animation (gesture_annotator, idle_director, micro_behaviors, animation_config, blob_sequences) | BITOS has OLED UI, not blob avatar. The gesture/expression paradigm doesn't map to 240x280 text display |
| Consciousness GWT (consciousness.py) | Interesting architecture but overkill for a pocket device. The signal/salience/competition model adds complexity without clear benefit when there's no blob to animate. The useful parts (workspace trace, consciousness preamble) can be adapted without the full GWT |
| Awareness loop | Continuous Haiku calls during idle are too expensive for a pocket device. The useful output (ambient thoughts, mood tracking) can be achieved more cheaply via periodic heartbeat tasks |
| Tamagotchi needs | Cute but not intelligence. Skip unless you want personality on the device |
| MCP bridge | BITOS uses direct integration adapters (BlueBubbles, Gmail, Vikunja) which is simpler and more reliable for a hardware device |
| Vault indexer | BITOS doesn't have an Obsidian vault. The FTS5 pattern is already used in memory_store |
| Antigravity tools | Not relevant |
| Orchestrator chat / Agent runner | Project management tooling for the web UI, not for pocket device |
| Telegram notifications | BITOS has its own notification system |

### Research More

| Component | Question |
|-----------|---------|
| **MCP bridge** | Would MCP be worth it for BITOS? It would allow pluggable tools without custom adapter code. But MCP stdio transport has process overhead on Pi Zero |
| **Consciousness preamble** | The shared identity preamble for sub-agents is a good pattern. Worth adapting for BITOS perception/fact extraction prompts even without full GWT |
| **Worker base** | The reusable tool-using agent loop (workers/base.py) is a good pattern if BITOS ever needs multi-step agent workflows |

---

## 5. Extended Thinking Integration

### How ai-agent-env uses it
- NOT used in the main /chat endpoint
- Only available in OrchestratorChat (project management) with:
  - `max_tokens=16000`
  - `thinking.budget_tokens=10000`
  - `thinking.type="enabled"`

### How BITOS currently uses it
- Toggled via `extended_thinking` device setting (true/false)
- In `llm_bridge.py`: `max_tokens=16000`, `budget_tokens=10000`
- Applied to the main chat call — always-on when enabled
- No visual indication on device during thinking

### How to show on 240x280 OLED device
1. **Thinking indicator:** Show a pulsing "..." or thinking icon in the chat area while the model thinks
2. **Thinking summary:** After response, optionally show "[thought for Xs]" as a subtle prefix
3. **Do NOT show the thinking content** — it's internal reasoning, not useful on a tiny screen
4. **State management:** The SSE stream should emit a `{"thinking": true}` event before text starts, so the device can show the indicator

### Token budget recommendations
- **Conservative (current):** 10K budget is fine for most questions. Total cost: ~$0.08-0.15 per extended thinking turn with Sonnet
- **Aggressive:** 5K budget for quick reasoning, 20K for explicitly complex questions
- **Device constraint:** Extended thinking adds 3-10 seconds of latency. On a pocket device, this should be opt-in or auto-triggered only for complex questions

### When to trigger vs skip
Auto-trigger when:
- Perception classifies intent as "reflection" or urgency as "high"
- Message contains question words + complexity signals ("how should I...", "compare...", "analyze...")
- Agent mode is "monk" or "director" (both benefit from deeper reasoning)

Skip when:
- Simple chat/greetings
- Settings commands
- Messaging commands
- Battery < 20% (conserve power by reducing latency)

---

## 6. Token/Cost Budget Analysis

### ai-agent-env per-conversation cost (full pipeline)

| Stage | Model | Input | Output | Cost/Turn |
|-------|-------|-------|--------|-----------|
| Perception | Haiku | 300 | 100 | $0.0006 |
| Main LLM | Sonnet | 5000 | 1000 | $0.030 |
| Tool round (if any) | Sonnet | 6000 | 500 | $0.026 |
| Fact extraction | Haiku | 500 | 300 | $0.0005 |
| Inner thoughts | Haiku | 3000 | 256 | $0.003 |
| Gesture annotation | Haiku | 1500 | 1024 | $0.005 |
| Memory consolidation (1/8) | Haiku | 3000 | 1024 | $0.0008 |
| Idle director (1/3) | Haiku | 2500 | 512 | $0.001 |
| **Total per turn (no tools)** | | | | **$0.040** |
| **Total per turn (1 tool round)** | | | | **$0.066** |
| **10-turn conversation** | | | | **$0.40-0.66** |

### BITOS current per-conversation cost

| Stage | Model | Input | Output | Cost/Turn |
|-------|-------|-------|--------|-----------|
| Perception | Haiku | 200 | 150 | $0.0008 |
| Main LLM | Sonnet | 2000 | 500 | $0.014 |
| Tool round (if any) | Sonnet | 3000 | 500 | $0.017 |
| Fact extraction | Haiku | 500 | 300 | $0.0005 |
| **Total per turn (no tools)** | | | | **$0.015** |
| **Total per turn (1 tool round)** | | | | **$0.032** |
| **10-turn conversation** | | | | **$0.15-0.32** |

### BITOS with ported components (estimated)

| Stage | Model | Input | Output | Cost/Turn |
|-------|-------|-------|--------|-----------|
| Perception | Haiku | 200 | 150 | $0.0008 |
| Main LLM (richer prompt) | Sonnet | 4000 | 800 | $0.024 |
| Tool round (if any) | Sonnet | 5000 | 500 | $0.023 |
| Fact extraction | Haiku | 500 | 300 | $0.0005 |
| Memory consolidation (1/8) | Haiku | 3000 | 1024 | $0.0008 |
| Inner thoughts (opt-in) | Haiku | 3000 | 256 | $0.003 |
| **Total per turn (no tools, no inner thoughts)** | | | | **$0.026** |
| **Total per turn (full pipeline)** | | | | **$0.052** |
| **10-turn conversation** | | | | **$0.26-0.52** |

### Recommendations
1. Memory consolidation is almost free (1/8 turns, Haiku) — always enable
2. Inner thoughts add $0.003/turn — make this a device setting ("deep mode" or similar)
3. Self-model in system prompt is free (no LLM cost, ~1500 tokens) — always include
4. Persistent state in system prompt is free — always include
5. Live context is free (HTTP calls, no LLM) — always include
6. Skip gesture annotation entirely (no blob on BITOS)
7. Skip idle director entirely (no blob on BITOS)
8. Skip awareness loop (too expensive for idle device)

---

## 7. Recommended Port Order

### Phase 1: Quick Wins (1-2 days, high value, low effort)

**Goal:** Safety + identity + better memory

1. **Port LoopDetector** to BITOS tool loop in `llm_bridge.py`
   - Prevents infinite tool loops (critical safety gap)
   - Copy `LoopDetector` class from `tools/safety.py`
   - Add to `stream_with_tools` in `llm_bridge.py`

2. **Port CostGuard** to BITOS
   - Add per-conversation ($1) and hourly ($5) spending limits
   - Track in main.py chat endpoint

3. **Port Self-Model blocks** to BITOS system prompt
   - Create `server/self_model.py` with SQLite-backed blocks
   - Seed with identity, about_seb, operating_principles, current_focus
   - Inject into system prompt via `agent_modes.py`
   - No LLM cost — just prompt engineering

4. **Add cost tracking** to conversation_store
   - Track input_tokens, output_tokens, cost per message
   - Display in admin/debug views

### Phase 2: Core Intelligence (3-5 days, high value, medium effort)

**Goal:** Memory that actually works + persistent personality

5. **Upgrade memory_store.py**
   - Add recency decay (30-day half-life, FadeMem access-count modulation)
   - Add access_count + last_accessed columns
   - This alone will dramatically improve recall quality

6. **Port memory consolidation**
   - Create `server/memory_consolidator.py`
   - Every 8 turns: review conversation, extract/update/deduplicate facts
   - Run as background task (asyncio.to_thread with sync Haiku client)
   - Update self-model blocks when significant new info learned

7. **Port persistent state** (core domains only)
   - Create `server/persistent_state.py`
   - Emotional trajectory (valence/arousal/momentum from consolidator emotional signals)
   - Temporal presence (session tracking, streaks, absence awareness)
   - Relationship model (trust level, interaction patterns)
   - Skip: dream_journal, expression_feedback, tamagotchi_needs
   - Inject into system prompt as "Persistent Awareness" block

8. **Enrich system prompt assembly**
   - Move from flat string to structured multi-block prompt:
     - Static: self-model blocks (can use prompt caching)
     - Dynamic: live context, memory context, persistent awareness, perception analysis
   - Add memory recall results to prompt (from perception entities/topics)

### Phase 3: Full Intelligence Loop (3-5 days, medium value, medium effort)

**Goal:** Agent that reflects, learns, and improves over time

9. **Port inner thoughts** (opt-in)
   - Create `server/inner_thoughts.py`
   - After each response, Haiku generates reflection
   - High-salience thoughts injected into next system prompt
   - Toggled via device setting (default: off for cost savings)

10. **Port live context** (auto-injected)
    - Weather, time-of-day awareness without tool calls
    - Lightweight HTTP fetches, no LLM cost
    - Inject into system prompt as "Current Context" block

11. **Add semantic dedup** to memory store (optional)
    - fastembed for local embeddings (requires pip install)
    - Cosine similarity threshold 0.85
    - May be too heavy for Pi Zero — evaluate CPU impact

12. **Port consciousness preamble** pattern
    - Shared identity prompt for perception, fact extraction, inner thoughts
    - Makes all sub-agents feel like aspects of one mind
    - Purely prompt engineering, zero cost

### Phase 4: Orchestrator Mode (5+ days, experimental)

**Goal:** Multi-stage orchestration as a BITOS mode

13. **Create "deep" agent mode**
    - Full pipeline: perception -> enrichment -> main LLM -> subagent post-processing
    - Auto-enables: memory consolidation, inner thoughts, persistent state
    - Auto-triggers extended thinking for complex questions
    - Higher cost (~$0.05/turn vs $0.015/turn normal)

14. **Add consciousness workspace** (simplified)
    - Signal posting from perception, memory, inner thoughts
    - High-salience summary injected into main prompt
    - Skip: salience competition, awareness loop, ambient thoughts
    - Just use it as a tracing/transparency mechanism

15. **Port scheduled reminders** (agent tool)
    - Let the agent schedule future proactive messages via heartbeat
    - Already partially exists in BITOS heartbeat, just needs the tool bridge

---

## Appendix: File-by-File Mapping

```
ai-agent-env                     BITOS Server
─────────────                    ────────────
src/server.py                 -> server/main.py (heavily adapted)
src/perception.py             -> server/perception.py (already ported)
src/config.py                 -> server/config.py (already ported)
src/db/conversations.py       -> server/conversation_store.py (already ported)
src/memory/post_process.py    -> server/fact_extractor.py (already ported)
src/memory/store.py           -> server/memory_store.py (partial — needs upgrade)
src/tools/web_search.py       -> server/web_search.py (already ported)
src/heartbeat.py              -> server/heartbeat.py (already ported, improved)
src/tools/safety.py           -> [MISSING — port CostGuard + LoopDetector]
src/self_model.py             -> [MISSING — port as server/self_model.py]
src/persistent_state.py       -> [MISSING — port as server/persistent_state.py]
src/live_context.py           -> [MISSING — port as server/live_context.py]
src/subagents/memory_consolidator.py -> [MISSING — port as server/memory_consolidator.py]
src/subagents/inner_thoughts.py      -> [MISSING — port as server/inner_thoughts.py]
src/consciousness.py          -> [SKIP full GWT — extract preamble pattern only]
src/awareness_loop.py         -> [SKIP — too expensive for idle device]
src/tamagotchi.py             -> [SKIP — blob personality, not relevant]
src/subagents/gesture_annotator.py   -> [SKIP — no blob avatar]
src/subagents/idle_director.py       -> [SKIP — no blob avatar]
src/subagents/micro_behaviors.py     -> [SKIP — no blob avatar]
src/blob_sequences.py         -> [SKIP — no blob avatar]
src/animation_config.py       -> [SKIP — no blob avatar]
src/voice/ws_handler.py       -> [SKIP — BITOS has its own voice handling]
src/tools/mcp_bridge.py       -> [SKIP — BITOS uses direct adapters]
src/tools/file_tools.py       -> [SKIP — not needed on device]
src/tools/antigravity.py      -> [SKIP — not relevant]
src/tools/cdp_navigator.py    -> [SKIP — not relevant]
src/tools/telegram.py         -> [SKIP — not relevant]
src/subagents/orchestrator_chat.py   -> [SKIP — web UI feature]
src/subagents/agent_runner.py        -> [SKIP — workspace agents]
src/subagents/automation_loop.py     -> [SKIP — Antigravity]
src/subagents/antigravity_orchestrator.py -> [SKIP — Antigravity]
src/workers/base.py           -> [RESEARCH — useful pattern for future workflows]
N/A                           -> server/agent_modes.py (BITOS-original, keep)
N/A                           -> server/agent_tools.py (BITOS-original, keep)
N/A                           -> server/llm_bridge.py (BITOS-original, keep)
N/A                           -> server/activity_feed.py (BITOS-original, keep)
N/A                           -> server/voice_catalog.py (BITOS-original, keep)
N/A                           -> server/ui_settings.py (BITOS-original, keep)
```
