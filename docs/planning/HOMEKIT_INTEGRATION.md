# BITOS · HOMEKIT INTEGRATION PLAN
## docs/planning/HOMEKIT_INTEGRATION.md
## v1.0 · March 2026

---

## SUMMARY

Add HomeKit smart home control to BITOS via an MCP server running on
the Mac mini. The agent can then control lights, locks, thermostats,
scenes, and query device status through natural language on the device.

---

## REPO EVALUATION

### HomeClaw (github.com/omarshahine/HomeClaw) — RECOMMENDED

A native macOS app that bridges Apple HomeKit directly via `HMHomeManager`.
Exposes 8 MCP tools over stdio transport through a bundled Node.js server.

**Strengths:**
- Direct HomeKit API access — no Shortcuts intermediary, no manual setup per device
- Rich accessory control: lights (power/brightness/hue/color temp), thermostats
  (temp/HVAC mode), locks, doors, garage doors, fans, window coverings, switches,
  outlets, sensors (motion/contact/temp/humidity/light/battery)
- `homekit_device_map` tool returns LLM-optimized device landscape (semantic
  types, aliases, controllable characteristics) — perfect for agent reasoning
- `homekit_events` tool returns recent characteristic changes, scene triggers,
  accessory control actions — enables reactive notifications
- `homekit_webhook` tool can push events to an HTTP endpoint — enables
  real-time event-driven notifications without polling
- `homekit_config` tool supports device filtering (allowlist mode) — security
- 5 consolidated tools with clean action-based schemas (list/get/search/control)
- TestFlight distribution — no developer account needed for installation
- Active development, designed specifically for AI agent integration

**Constraints:**
- macOS only (Mac Catalyst + HomeKit entitlement) — fine, runs on Mac mini
- Requires the HomeClaw app to be running with Unix socket active
- Apple restricts HomeKit entitlement to development/App Store signing
- Needs Node.js 20+ for the MCP server process

### home-mcp (github.com/somethingwithproof/home-mcp) — NOT RECOMMENDED

A simpler MCP server that shells out to macOS Shortcuts and AppleScript.

**Why not:**
- Requires manually creating a Shortcut for every device/action — does not scale
- No direct HomeKit API access — limited to what Shortcuts exposes
- No device discovery, no event stream, no status queries
- No webhook support — no way to push events to BITOS
- Each tool is hardcoded to a specific shortcut name ("Lights On", "Lock Doors")
- Basically a Shortcuts runner, not a HomeKit integration

**Verdict:** HomeClaw is the clear winner. It provides native HomeKit access,
rich device control, event streaming, and was purpose-built for AI agents.

---

## MCP BRIDGE INTEGRATION

The ai-agent-env project has a working `MCPBridge` class (`src/tools/mcp_bridge.py`)
that connects to stdio MCP servers, namespaces their tools, and exposes them to
the agent. BITOS server does not yet have an equivalent — it uses domain-specific
adapters (Gmail, BlueBubbles, Vikunja) with a contracts/adapter pattern.

### Connection approach: MCP bridge on the Mac mini server

HomeClaw's MCP server is a Node.js stdio process. The BITOS server (FastAPI on
Mac mini) spawns it as a child process, same as the ai-agent-env pattern:

```python
# server/integrations/homekit_mcp.py

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def connect_homekit(bridge: MCPBridge):
    await bridge.connect(
        name="homekit",
        command="node",
        args=["/Applications/HomeClaw.app/Contents/Resources/mcp-server.js"],
    )
```

Tools get namespaced as `homekit__homekit_accessories`, `homekit__homekit_scenes`, etc.
The agent calls them through the standard tool-use loop.

### Alternative: direct adapter (no MCP bridge yet in BITOS)

If we don't want to add a full MCP bridge to the BITOS server yet, we can
write a `HomeKitAdapter` that spawns the MCP server process directly and
wraps the 8 tools as Python methods — matching the existing adapter pattern
(`GmailAdapter`, `BlueBubblesAdapter`, `VikunjaAdapter`).

```python
# server/integrations/homekit_adapter.py

class HomeKitAdapter:
    """HomeKit control via HomeClaw MCP server."""

    async def list_accessories(self, room: str = None) -> list[dict]: ...
    async def control_device(self, accessory_id: str, characteristic: str, value: str) -> dict: ...
    async def list_scenes(self) -> list[dict]: ...
    async def trigger_scene(self, scene_id: str) -> dict: ...
    async def get_device_map(self) -> dict: ...
    async def get_events(self, limit: int = 50, since: str = None) -> list[dict]: ...
    async def get_status(self) -> dict: ...
```

**Recommendation:** Start with the adapter approach to match BITOS patterns.
Introduce a proper MCP bridge when multi-agent services (Phase 10) arrive.

---

## AGENT TOOLS EXPOSED

These map to HomeClaw's 8 MCP tools, presented to the LLM as agent tools:

| Tool | Description | HomeClaw MCP tool |
|------|-------------|-------------------|
| `home_status` | Check HomeKit connectivity + home/accessory count | `homekit_status` |
| `home_devices` | List, search, get details, or control accessories | `homekit_accessories` |
| `home_rooms` | List rooms and their devices | `homekit_rooms` |
| `home_scenes` | List or trigger scenes | `homekit_scenes` |
| `home_map` | Get LLM-optimized device landscape | `homekit_device_map` |
| `home_config` | View/set default home, device filtering | `homekit_config` |
| `home_events` | Query recent HomeKit events | `homekit_events` |
| `home_webhook` | Configure webhook for event push | `homekit_webhook` |

### Example agent interactions

```
User: "Turn off the living room lights"
Agent: home_devices(action="search", query="lights", room="living room")
       → finds matching accessories
       home_devices(action="control", accessory_id="uuid", characteristic="power", value="false")
       → "Done — living room lights are off."

User: "Set the house to movie mode"
Agent: home_scenes(action="trigger", scene_id="Movie Time")
       → "Movie Time scene activated."

User: "What's the temperature in the bedroom?"
Agent: home_devices(action="search", query="temperature", room="bedroom")
       → "Bedroom sensor reads 21.5C."
```

---

## HOMEKIT EVENTS → NOTIFICATION SYSTEM

BITOS already has a `NotificationPoller` that polls various sources on
intervals and pushes `NotificationRecord` items to the device overlay.
HomeKit events fit this pattern perfectly.

### Option A: Polling (simple, immediate)

Add a `_poll_homekit_events` method to `NotificationPoller` that calls
`homekit_events(since=last_check)` every 30-60 seconds. Filter for
interesting events (motion detected, door opened, temperature threshold
exceeded) and push notifications.

```python
def _poll_homekit_events(self) -> None:
    events = self._homekit_adapter.get_events(since=self._last_homekit_check)
    for event in events:
        if self._is_notable(event):
            record = NotificationRecord(
                id=f"homekit:{event['id']}",
                type="HOME",
                app_name="HOME",
                message=self._format_event(event),
                time_str=time.strftime("%H:%M"),
                source_id=event.get("accessory_id", ""),
            )
            self._queue.push_record(record)
```

### Option B: Webhook push (real-time, better)

HomeClaw supports webhooks — configure it to POST events to the BITOS
server. Add a `/webhooks/homekit` endpoint that receives events and
pushes them directly into the notification queue.

```python
@app.post("/webhooks/homekit")
async def homekit_webhook(event: dict):
    # Push to notification queue
    # Push to WebSocket for real-time device update
    # Optionally feed into agent consciousness workspace
```

**Recommendation:** Implement Option A first (polling, ~30 lines of code),
then add Option B (webhook) when real-time response matters.

### Notable events to surface as notifications

- Motion detected (security)
- Door/window opened or closed
- Lock state changed
- Temperature outside comfort range (e.g. below 18C or above 26C)
- Scene triggered by another household member
- Device went unreachable / came back online

---

## DEVICE UI INTEGRATION

### Home preview panel

Add a `home_preview` widget to the BITOS device home screen showing:
- Active scene name
- Room temperature (primary sensor)
- Number of lights on
- Lock status icon

### Quick actions from device

The 5-way nav or action menu could expose:
- Toggle scene (e.g., "Good Night" / "Good Morning")
- Lights on/off for current room
- Lock all doors

These map to `home_scenes(action="trigger")` and
`home_devices(action="control")` calls through the server.

---

## DEPENDENCIES AND SETUP

### Required

1. **HomeClaw app** — Install via TestFlight on Mac mini
   - Grant HomeKit access when prompted
   - Select home in HomeClaw settings
   - Verify devices appear in HomeClaw device list

2. **Node.js 20+** on Mac mini — `brew install node`

3. **HomeKit-compatible devices** — must be set up in Apple Home app first

4. **Python MCP SDK** — `pip install mcp` (already a dependency in ai-agent-env)

### Optional

- **HomeBridge** — NOT required if devices are already HomeKit-native.
  Only needed to bring non-HomeKit devices (e.g., cheap Tuya bulbs,
  older Z-Wave gear) into the HomeKit ecosystem. HomeBridge runs as a
  separate service and makes devices appear as native HomeKit accessories.
  HomeClaw sees them like any other device.

### Environment variables

```bash
# .env
HOMEKIT_ENABLED=true
HOMECLAW_MCP_PATH=/Applications/HomeClaw.app/Contents/Resources/mcp-server.js
```

---

## IMPLEMENTATION PHASES

### Phase 1: Basic control (1-2 hours)

- [ ] Install HomeClaw on Mac mini via TestFlight
- [ ] Write `server/integrations/homekit_adapter.py` wrapping HomeClaw MCP
- [ ] Add `home_devices`, `home_scenes`, `home_map` to agent tool list
- [ ] Test: "turn on living room lights" end-to-end

### Phase 2: Notifications (1 hour)

- [ ] Add `_poll_homekit_events` to `NotificationPoller`
- [ ] Add `HOME` notification type to device overlay
- [ ] Configure notable event filters

### Phase 3: Device UI (2-3 hours)

- [ ] Home preview panel on device home screen
- [ ] Quick action shortcuts in action menu
- [ ] Home status in settings/integrations view

### Phase 4: Webhook + real-time (1-2 hours)

- [ ] Add `/webhooks/homekit` endpoint to server
- [ ] Configure HomeClaw webhook to point at BITOS server
- [ ] Push real-time events to device via existing notification WebSocket

---

## SECURITY CONSIDERATIONS

- HomeClaw runs locally on Mac mini — no cloud dependency, no API keys
- Device filtering (allowlist mode) limits which accessories the agent can see/control
- Lock/unlock and door operations should require device confirmation
  (tier-2 action in the existing permission gate system)
- Webhook endpoint should validate bearer token from HomeClaw config
- HomeKit events may contain sensitive data (who's home, door states) —
  don't log event payloads in production

---

*Reference: HomeClaw v0.0.2, home-mcp v1.0.0 · Evaluated March 2026*
