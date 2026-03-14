## Summary
5 panels audited. 18 implementation gaps found.

## Per-panel gaps

### HOME PANEL
Reference: The UI reference shows a home panel with large centered time/date, weather card, and a “next task” row in the right panel shell (plus sidebar context and badges).  
Current: Python `HomePanel` renders a compact title and a vertical action list (`CHAT`, `FOCUS`, `NOTIFS`, `SETTINGS`) with status labels and startup health indicator.

Gaps:
- Missing large clock/date hero section.
- Missing weather module (temp/condition/high-low location block).
- Missing “next task” preview row and urgency dot treatment.
- Missing sidebar-style split shell treatment from the reference interaction model.

### CHAT PANEL
Reference: The UI reference shows chat with AI status row, richer conversation chrome, and explicit voice/stream states integrated into the panel shell.
Current: Python `ChatPanel` supports typed input, backend streaming, retry/degraded/offline status text, queue debug compact status, and optional voice capture via long-press.

Gaps:
- Missing explicit “new chat / prior chats” surface shown in reference flows.
- Missing fuller status widgets (network/AI context indicators) beyond compact text labels.
- Missing visual treatment for reference-style panel shell layout and row cards.
- No explicit context-limit recovery UI shown in ref error states (e.g., “new chat” CTA panel treatment).

### SETTINGS PANEL
Reference: Reference shows broader settings matrix (AI model, display, network, system) and richer row hierarchy.
Current: Python `SettingsPanel` provides toggles (`WEB SEARCH`, `MEMORY`), model picker, agent mode picker, sleep timer, about, companion app QR, and back.

Gaps:
- Missing dedicated network settings subpanel from reference IA.
- Missing display/theme tuning surface shown in reference architecture.
- Missing richer system diagnostics rows (battery/network/runtime summaries).
- Missing deeper nested settings shell visuals from HTML references.

### FOCUS PANEL
Reference: Reference includes pomodoro plus related productivity tools (world clocks/stopwatch) and break-mode visual states.
Current: Python `FocusPanel` provides a single countdown timer with start/pause/reset/back and state restore.

Gaps:
- Missing break-mode/invert visual state behavior from reference.
- Missing world clock and stopwatch utilities.
- Missing multi-block focus UX (session/break cycles) represented in references.

### NOTIFICATIONS PANEL
Reference: Reference includes notification toast system, full notification shade, app-specific row styling, and clear-all interactions.
Current: Python `NotificationsPanel` provides placeholder list rendering, local refresh action, back action, and empty/error copy.

Gaps:
- Missing full shade behaviors shown in reference (clear-all, grouped types, richer metadata rows).
- Missing interactive toast lifecycle controls reflected in design kit states.
- Missing per-notification CTA affordances (open action/source-specific behavior).
- Missing app-type visual differentiation (mail/task/AI iconography and badges).

## Priority order for fixes
For day-one hardware use, priority should be:
1. **Notifications reliability UX parity** (shade clarity + actionable rows) so missed events are obvious on device.
2. **Home information density parity** (time/date/weather/next task) since this is the primary idle screen.
3. **Chat error-state UI parity** (offline/context-limit recovery CTAs) to reduce dead-end interactions during network instability.
4. **Settings IA expansion** (network/display/system) to improve on-device configuration without SSH fallback.
5. **Focus feature parity** (break mode + secondary utilities) after core day-one use paths are stable.
