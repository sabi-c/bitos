# Submenu Navigation System — Design

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Two-level navigation where sidebar items open custom preview panels with submenu actions, before entering full-screen views.

**Architecture:** CompositeScreen gains a focus mode (sidebar vs submenu). DOUBLE on sidebar enters submenu; LONG goes back. Each sidebar item gets a custom PreviewPanel subclass with its own layout and submenu items.

**Tech Stack:** pygame, existing CompositeScreen/Sidebar components

---

## Layout (unchanged)

```
┌─────────────────────────────────┐ 0
│          (16px inset)           │
│         STATUS BAR (20px)       │ 16
├──────────┬──────────────────────┤ 36
│ SIDEBAR  │   RIGHT PANEL       │
│  84px    │    156x208px        │
│          │                     │
├──────────┴──────────────────────┤ 244
│     ACTION BAR (20px)          │
│          (16px inset)           │
└─────────────────────────────────┘ 280
```

Right panel: 156x208px — the preview panels render here.

## Navigation State Machine

```
SIDEBAR_MODE (default)
  SHORT  → next sidebar item
  DOUBLE → enter SUBMENU_MODE for selected item
  LONG   → no-op (or global back)

SUBMENU_MODE
  SHORT  → next submenu item
  DOUBLE → execute selected submenu action
  LONG   → back to SIDEBAR_MODE
```

## CompositeScreen Changes

Add `_focus` enum: `SIDEBAR` | `SUBMENU`. When focus is `SUBMENU`:
- Sidebar still renders but selected item is visually "locked" (highlight persists)
- Right panel's preview panel receives input
- SHORT/DOUBLE/LONG route to the preview panel instead of sidebar

## Preview Panel Base

```python
class PreviewPanel:
    """Base for custom sidebar preview panels with submenu navigation."""

    def __init__(self, items: list[dict], on_action: callable):
        self.items = items        # [{"label": "...", "description": "...", "action": "key"}]
        self.selected_index = 0
        self._on_action = on_action

    def handle_action(self, action: str):
        if action == "SHORT_PRESS":
            self.selected_index = (self.selected_index + 1) % len(self.items)
        elif action == "DOUBLE_PRESS":
            item = self.items[self.selected_index]
            self._on_action(item["action"])

    def render(self, surface): ...      # Override per panel
    def update(self, dt): ...           # Optional animation
```

## Custom Preview Panels

### ChatPreviewPanel (156x208px)

```
┌──────────────────────┐
│ [Last agent response  │  ← top ~80px, dimmed, truncated
│  or "Start talking"]  │
├──────────────────────┤
│ > START NEW CHAT      │  ← submenu items
│   RESUME CHAT         │
│   CHAT HISTORY        │
│   SETTINGS            │
│   BACK                │
└──────────────────────┘
```

- Top zone: last assistant message from repository (or prompt text)
- Bottom zone: scrollable submenu items with `>` indicator

### TasksPreviewPanel (156x208px)

```
┌──────────────────────┐
│ TODAY                 │  ← section header
│ □ Financial admin     │  ← top 3-4 tasks
│ ■ Anthony reimburse   │
│ □ Weekly doc rhythm   │
├──────────────────────┤
│ > VIEW ALL TASKS      │  ← submenu items
│   ADD TASK            │
│   BACK                │
└──────────────────────┘
```

- Top zone: live task items from provider (Things/Vikunja), checkbox style
- Bottom zone: action submenu

### Other panels (HOME, SETTINGS, FOCUS, MAIL, MSGS, MUSIC, HISTORY)

Start as simple list previews — can be upgraded individually later. Each gets its own class inheriting from PreviewPanel.

## Button Mapping (all contexts)

| Context | SHORT | DOUBLE | LONG |
|---------|-------|--------|------|
| Sidebar | Next item | Enter submenu | No-op |
| Submenu | Next item | Execute action | Back to sidebar |
| Chat | Scroll up | Actions menu | Record (hold) |

## Files to Create/Modify

- **Modify:** `device/ui/composite_screen.py` — add focus mode, route input
- **Modify:** `device/ui/panel_registry.py` — replace placeholders with custom panels
- **Create:** `device/ui/panels/base.py` — PreviewPanel base class
- **Create:** `device/ui/panels/chat_preview.py` — ChatPreviewPanel
- **Create:** `device/ui/panels/tasks_preview.py` — TasksPreviewPanel
- **Create:** `device/ui/panels/generic_preview.py` — GenericPreviewPanel for other items
- **Modify:** `device/main.py` — wire panel actions to screen_mgr.push()
