# BITOS UI Overhaul — Design

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Upgrade BITOS device UI with multi-font support (Monocraft + hot-swap), 1-bit design system visual polish, and a reworked voice-first chat panel.

**Architecture:** Three independent pillars that can be built in sequence: font system → visual polish → chat rework. Each builds on the prior but is independently shippable.

**Constraints:** 240×280 ST7789 display, single-button navigation (SHORT=next, DOUBLE=select, LONG=back, TRIPLE=prev), 15 FPS pygame, Pi Zero 2W.

---

## Pillar 1: Font System

### Fonts
- **Press Start 2P** (current) — pixel bitmap, 8px base grid
- **Monocraft** — Minecraft-inspired monospace, 1500+ glyphs, OFL-1.1 license
- Download: `https://cdn.jsdelivr.net/gh/IdreesInc/Monocraft@main/dist/Monocraft-ttf/Monocraft.ttf`

### Architecture
- Add `Monocraft.ttf` to `device/assets/fonts/`
- Font registry in `display/tokens.py`: map family name → file path
- Hot-swap: flush `_FONT_CACHE` dict in `theme.py` when `font_family` changes
- Panels that cache fonts at `__init__` time call `_reload_fonts()` on font change
- Anti-aliasing always off: `render(text, False, color)`
- Existing `font_scale` multiplier still applies on top

### Settings
- `font_family` stored in repository (values: `"press_start_2p"`, `"monocraft"`)
- `FontPickerPanel` in settings: show font name + live preview, cycle through options, save

---

## Pillar 2: Visual Polish (Selective 1-Bit Adoption)

### Changes
- **Row indicators**: `▸` on focused items, `○` on default items
- **Border weights**: 2px component borders, 1px hairline separators (verify consistency)
- **Focus state**: Keep inverted (white bg, black text) — already matches 1-bit spec
- **Loading states**: Skeleton shimmer for async panels (tasks, messages, mail)

### No changes
- Sidebar + right panel layout (CompositeScreen) stays
- Current color tokens stay (already align with 1-bit ramp)
- Hint bar format stays

---

## Pillar 3: Chat Panel Rework

### Voice-first flow
1. Enter chat → see last conversation + action menu at bottom
2. SHORT scrolls through: `SPEAK` | `ACTIONS` | `BACK`
3. DOUBLE on SPEAK → recording indicator (volume meter, pulsing dot)
4. Recording continues until SHORT to send
5. Response streams in
6. Agent can present multiple-choice actions as selectable rows
7. ACTIONS shows 3 agent-suggested or template actions (infrastructure for now, full wiring later)
8. BACK exits chat panel

### Bug fixes
- Fix back-out bug (LONG_PRESS not routing correctly)
- Add BACK as explicit menu item (safety net)
- Better message rendering: user/assistant visual distinction, word wrap, scroll

### Layout (240×280)
```
┌─────────────────────┐
│ CHAT          ●REC  │  ← status bar (20px)
├─────────────────────┤
│                     │
│ You: what's next?   │  ← message area (scrollable)
│                     │
│ AI: Here are your   │
│ top 3 tasks...      │
│                     │
├─────────────────────┤
│ ▸ SPEAK             │  ← action menu (selectable rows)
│ ○ ACTIONS           │
│ ○ BACK              │
├─────────────────────┤
│ SHORT:NEXT·DBL:SEL  │  ← hint bar
└─────────────────────┘
```

---

## Out of scope (next sprint)
- Backend API key integration
- MCP/tool-use wiring for smart actions
- Live transcription during recording
- Widget system
- Second button support
