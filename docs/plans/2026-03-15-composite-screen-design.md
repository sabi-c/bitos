# CompositeScreen: Wire New UI Panels Into Device

**Date**: 2026-03-15
**Approach**: Option C — Coordinator wrapper, incremental migration

## Problem

New render-only panels exist (`device/ui/panels/`) matching the HTML reference design but are never used. Old panels (`device/screens/panels/`) render full 240x280 with embedded nav logic and work fine. We need to bridge these without breaking the working system.

## Architecture

### CompositeScreen (extends BaseScreen)

A new `CompositeScreen` class that the existing `ScreenManager` accepts (it extends `BaseScreen`). It composes the full 240x280 layout from the new components:

```
┌─────────────────────────────────┐ 0
│         STATUS BAR (18px)       │
│  time    BITOS    AI·RDY        │
├──────────┬──────────────────────┤ 18
│ SIDEBAR  │   RIGHT PANEL       │
│  84px    │    156x250px        │
│          │                      │
│ ▶HOME    │  [new panel.render()]│
│  CHAT    │                      │
│  TASKS   │                      │
│  SETTINGS│                      │
│  FOCUS   │                      │
│  MAIL    │                      │
│  MSGS    │                      │
│  MUSIC   │                      │
│  HISTORY │                      │
│          │                      │
├──────────┴──────────────────────┤ 268
│  SHORT:NEXT · LONG:SEL · DBL:BACK │
└─────────────────────────────────┘ 280
```

### Two Modes

1. **SIDEBAR mode** (default): Sidebar is active. SHORT cycles items, LONG enters the selected panel. Right panel shows a preview render of the selected new panel.
2. **PANEL mode**: Input routes to the active old panel's `handle_action()`. Sidebar shows current selection but is dimmed. DOUBLE_PRESS returns to SIDEBAR mode.

### How It Replaces HomePanel

Currently `main.py` pushes `HomePanel` as the root screen. HomePanel IS the sidebar (renders a full-width menu list). We replace it with `CompositeScreen` which:
- Takes the same constructor args HomePanel takes (callbacks, client, repository, etc.)
- Uses the new `Sidebar` component for the left 84px
- Uses the new `StatusBar` for the top 18px
- Uses the new `HintBar` for the bottom 12px
- In SIDEBAR mode, renders the new HomePanel (render-only) in the right panel
- On LONG_PRESS, switches to PANEL mode and instantiates the selected old panel

### Panel Integration (Incremental)

Old panels still handle all logic. The CompositeScreen wraps them:
- Old panel renders into a 156x250 subsurface (clipped from 240x280)
- Old panel's `handle_action()` receives input in PANEL mode
- Old panel's `update(dt)` still ticks
- Old panel's `_owns_status_bar = True` is overridden (CompositeScreen owns it)

Over time, old panel renders get replaced with new panel renders while keeping old panel logic.

## Files to Create/Modify

### Create
- `device/ui/composite_screen.py` — CompositeScreen class
- `device/ui/panel_registry.py` — Maps sidebar items to panel classes

### Modify
- `device/main.py` — Replace HomePanel with CompositeScreen
- `device/ui/panels/home.py` — Wire to live data (weather, tasks from repository)
- `device/ui/panels/*.py` — Add `set_data()` methods for live data injection
- `device/ui/components/sidebar.py` — Add dim/active visual states

### Low-Effort Additions
- Add `pyaudio` to `requirements-device.txt`
- Fix `/dashboard` and `/brief` stub endpoints in `server/main.py`

## Key Constraints

- Old ScreenManager is NOT modified — CompositeScreen adapts to its interface
- All old panel logic (streaming, voice, BLE, callbacks) stays intact
- New panels remain render-only — no logic migration yet
- Device must boot and work identically after the change (just looks different)
