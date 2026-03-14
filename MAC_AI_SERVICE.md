# BITOS · MAC AI SERVICE + MULTI-AGENT ORCHESTRATION
## docs/planning/MAC_AI_SERVICE.md
## v1.0 · March 2026

---

## CONCEPT

The Mac mini is not just a backend — it's a personal AI workstation.
BITOS (the physical device) is the always-with-you interface into
that workstation. The Mac runs a persistent multi-agent service that
handles heavy computation, long-running tasks, and tool use. The
device just talks to it.

Think of it as: **Claude Code / Cursor-level capability on your own
hardware, with BITOS as the physical remote control.**

The "collab-electron" pattern — multiple Claude agents running in
parallel, each with a different specialization, auto-reviewing each
other's work, applying diffs, reading files, iterating — is the
inspiration for the Mac-side architecture.

---

## ARCHITECTURE OVERVIEW

```
┌─────────────────────────────────────────────────────────┐
│  MAC MINI — BITOS AI WORKSTATION                        │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │  BITOS Server (FastAPI, port 8000)              │   │
│  │  ├── Orchestrator Agent (Sonnet 4.6)            │   │
│  │  ├── Worker Pool (Haiku 4.5, parallel)          │   │
│  │  ├── Global Workspace (SQLite + memory)         │   │
│  │  └── MCP Bridge (Things, Calendar, Gmail, etc.) │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │  AGENT SERVICES (long-running, port 8001-8009)  │   │
│  │  ├── Code Agent (port 8001) — file ops, diffs   │   │
│  │  ├── Research Agent (port 8002) — web, docs     │   │
│  │  ├── Ops Agent (port 8003) — tasks, calendar    │   │
│  │  └── Creative Agent (port 8004) — writing, ideas│   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │  ELECTRON MONITOR (optional, port 8010)         │   │
│  │  Tiled terminal view of all agent activity      │   │
│  │  Visual diff viewer, file tree, log stream      │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
         │                              │
    Tailscale VPN                  BLE Companion
         │                              │
    ┌────┴────┐                   ┌─────┴────┐
    │  BITOS  │                   │  iPhone  │
    │ device  │                   │ companion│
    └─────────┘                   └──────────┘
```

---

## BITOS DEVICE INTEGRATION

The device doesn't need to know which agent is handling a request.
From the device's perspective, it sends a message to `/chat` and
gets a streamed response. The routing happens entirely on the server.

The device does need to be able to:
1. **Select active service** — Settings → Agent Mode → picks which
   service handles requests (Producer, Code, Research, etc.)
2. **See service status** — status bar shows active agent + load
3. **Trigger long-running tasks** — "run in background, notify me
   when done" pattern for things that take minutes

```
BITOS device settings:
  AGENT MODE: PRODUCER     ← routes to Ops Agent
  AGENT MODE: HACKER       ← routes to Code Agent
  AGENT MODE: STORYTELLER  ← routes to Creative Agent
  AGENT MODE: DIRECTOR     ← routes to Research Agent
  AGENT MODE: MONK         ← routes to base Orchestrator (reflective)
  AGENT MODE: CLOWN        ← routes to Creative Agent (generative)
```

This is already specced in the agent mode system — the new part is
that each mode can route to a *different specialized agent service*
rather than just changing the system prompt.

---

## AGENT SERVICE DESIGN

Each agent service is a long-running FastAPI process. They share
the same SQLite database but have their own specialization and tools.

### Code Agent (port 8001)

Inspired by collab-electron — handles file operations, code review,
diff application, and iterative coding tasks.

```python
# server/agents/services/code_agent.py

SYSTEM_PROMPT = """
You are Seb's code agent. You have access to his local filesystem,
can read and write files, run shell commands, apply diffs, and 
iterate on code. You work in the bitos/ repository by default.

When given a coding task:
1. Read relevant files first
2. Plan the change
3. Apply it
4. Run tests
5. Report result

You are conservative — you don't make changes outside the working
directory without explicit permission. You explain what you're 
doing before doing it.
"""

TOOLS = [
    read_file,          # read any file in allowed paths
    write_file,         # write with diff preview
    run_shell,          # run commands (sandboxed)
    apply_diff,         # apply a unified diff
    list_directory,     # list files
    search_code,        # grep/ripgrep
    run_tests,          # pytest / specific test file
]
```

### Research Agent (port 8002)

Web search, documentation lookup, summarization.

```python
SYSTEM_PROMPT = """
You are Seb's research agent. You search the web, read documentation,
synthesize information, and save findings to Obsidian.

When researching:
1. Search multiple sources
2. Cross-reference findings
3. Save summary to /Research/ in Obsidian
4. Return key points to device
"""

TOOLS = [
    web_search,
    web_fetch,
    save_to_obsidian,
    search_obsidian,
]
```

### Ops Agent (port 8003)

Tasks, calendar, email, project coordination.

```python
SYSTEM_PROMPT = """
You are Seb's operations agent. You manage tasks, calendar,
email, and project coordination. You are conservative about
sending anything — you always draft first and confirm.

Current projects: SSS, Tender Fest, Hypnotist Doc.
"""

TOOLS = [
    things_mcp,         # tasks
    gcal_mcp,           # calendar
    gmail_mcp,          # email (read + draft)
    draft_action,       # creates tier-2 confirmation items
]
```

### Creative Agent (port 8004)

Writing, brainstorming, storytelling, bit development.

```python
SYSTEM_PROMPT = """
You are Seb's creative partner. You help with physical performance
work (Gaulier clowning tradition), writing, Tender Fest development,
and any creative project. You are generative and lateral.
"""

TOOLS = [
    save_to_obsidian,
    search_obsidian,
    web_search,         # research for creative projects
]
```

---

## MULTI-AGENT COORDINATION

For complex tasks, the Orchestrator can spin up multiple workers
in parallel. This is the "collab-electron" pattern applied to BITOS.

```python
# server/agents/orchestrator.py

class Orchestrator:
    """
    Routes requests to appropriate agent service.
    For complex tasks, coordinates multiple agents in parallel.
    """
    
    async def handle(self, message: str, 
                     agent_mode: str,
                     session_id: str) -> AsyncGenerator[str, None]:
        
        # Simple routing: single agent
        if self._is_simple_request(message):
            agent = self._get_agent_for_mode(agent_mode)
            async for chunk in agent.stream(message):
                yield chunk
            return
        
        # Complex routing: parallel workers
        # e.g. "review my code, check my tasks, and brief me"
        tasks = self._decompose(message)
        results = await asyncio.gather(*[
            self._dispatch(task) for task in tasks
        ])
        
        # Synthesize results
        async for chunk in self._synthesize(results, message):
            yield chunk
    
    def _get_agent_for_mode(self, mode: str) -> AgentService:
        mapping = {
            "producer": self.ops_agent,
            "hacker": self.code_agent,
            "storyteller": self.creative_agent,
            "director": self.research_agent,
            "monk": self.orchestrator_direct,
            "clown": self.creative_agent,
        }
        return mapping.get(mode, self.orchestrator_direct)
```

---

## BACKGROUND TASK PATTERN

Some tasks take minutes, not seconds. The device needs a way to
trigger them and be notified when done.

```
User on device: "Review my codebase and suggest improvements"
                                  ↓
Device: POST /tasks/background
        {"task": "code_review", "message": "...", "notify_on_done": true}
                                  ↓
Server: {"task_id": "uuid", "estimated_minutes": 3, "status": "running"}
                                  ↓
Device shows: "RUNNING IN BACKGROUND · CODE REVIEW" (toast)
                                  ↓
[3 minutes later]
                                  ↓
Server: pushes notification → device
        "CODE REVIEW COMPLETE · 12 suggestions found"
                                  ↓
User opens chat → sees full report
```

New endpoints needed:
```
POST /tasks/background    → queue a long-running task
GET  /tasks/{id}/status   → check status
GET  /tasks/{id}/result   → get result when done
GET  /tasks/              → list all background tasks
```

New device screen: a "Background Tasks" view (accessible from
status bar or Settings → Queue) showing running, completed, and
failed tasks with their results.

---

## ELECTRON MONITOR (OPTIONAL, MAC-ONLY)

For development and transparency — a window on the Mac showing
all agent activity in real time.

```
┌─────────────────────────────────────────────────────────────┐
│  BITOS AGENT MONITOR                          [minimize]    │
├───────────────┬───────────────┬───────────────┬─────────────┤
│ ORCHESTRATOR  │ CODE AGENT    │ OPS AGENT     │ CREATIVE    │
│               │               │               │             │
│ routing →     │ reading:      │ checking      │ idle        │
│ ops_agent     │ main.py       │ Things MCP    │             │
│               │               │ 3 tasks found │             │
│               │ applying      │               │             │
│               │ diff +14/-3   │               │             │
│               │               │ calendar:     │             │
│               │ running tests │ 2 events      │             │
│               │ ✓ 47 passed   │ today         │             │
├───────────────┴───────────────┴───────────────┴─────────────┤
│ [log stream of all agent activity]                          │
└─────────────────────────────────────────────────────────────┘
```

Built with Electron + React. Reads from a WebSocket endpoint on
the BITOS server (`ws://localhost:8000/ws/monitor`). Shows:
- Which agent is active
- What files are being read/written
- Current tool calls in flight
- Cost per session
- Request/response latency

This is purely a developer/observer tool — doesn't change device
behavior. Useful during development and for demos.

Implementation: separate package at `monitor/` in the repo.
Not required for device functionality.

---

## ROADMAP INTEGRATION

```
Phase 8 (already planned):
  P8-001  Global workspace class
  P8-002  Morning brief worker
  P8-003  Session distiller
  P8-004  Agent mode system prompt injection  ← starts this
  P8-005  Proactive notifications

Phase 10 (new — multi-agent services):
  P10-001  Code Agent service (port 8001) + file tools
  P10-002  Ops Agent service (port 8003) — separates from orchestrator
  P10-003  Research Agent service (port 8002) + web tools
  P10-004  Creative Agent service (port 8004)
  P10-005  Background task queue + device notification on complete
  P10-006  Background tasks screen on device
  P10-007  Orchestrator multi-agent routing (decompose + parallel)
  P10-008  Electron monitor app (optional, mac-only)
```

---

## DEPENDENCIES ON EXISTING WORK

Everything in Phase 10 builds on:
- ✓ FastAPI server (Phase 1)
- ✓ LLM bridge with provider abstraction (P3-003)
- ✓ Permission gate + outbound queue (P3-004)
- ✓ Notification system + poller (P4-004)
- ✓ Agent mode settings (P4-003)
- → Global workspace (P8-001) — needed before Phase 10

Phase 10 should not start until Phase 8 is complete.
The global workspace is what makes multi-agent coordination
coherent — without it, agents don't share context.

---

## SECURITY CONSIDERATIONS

Multi-agent systems need additional safeguards:

1. **Tool sandboxing** — Code Agent can only write to whitelisted
   paths (~/bitos/, ~/Desktop/BITOS-work/). Never /, ~/Documents
   without explicit per-session permission grant.

2. **Agent budget limits** — each agent session has a max token
   budget (configurable, default 50K tokens / $0.50). Agent stops
   and notifies device when budget is reached.

3. **Diff preview before apply** — Code Agent never applies a diff
   without showing it first. Even in "auto" mode, the diff is logged
   to the audit file (SD-006).

4. **Inter-agent trust** — agents don't trust each other's outputs
   directly. Orchestrator re-validates before acting on worker results.

5. **Human in the loop for irreversible actions** — even in background
   tasks, any action that can't be undone (send email, delete file,
   push to git remote) requires device confirmation via notification.

---

*Reference: "collab-electron" multi-agent pattern · March 2026*
*BITOS device is the physical interface to this system.*
*Mac mini is the compute layer. Pi Zero 2W is the interaction layer.*
