# Action Menu & Context Panel UX Patterns for Small Screens

**Date:** 2026-03-16
**Context:** BITOS pocket AI device, 240x280px display, single button (SHORT=scroll, DOUBLE=select, LONG=back)

---

## 1. Smartwatch Action Sheets & Context Menus

### Apple Watch Evolution

Apple Watch context menus went through a significant evolution. In early watchOS versions (1-6), **Force Touch** triggered a context menu overlay with up to 4 circular icon actions arranged in a grid. The user pressed firmly on the display and a translucent overlay appeared with labeled icons.

In **watchOS 7, Apple removed Force Touch menus entirely**, moving all contextual actions into visible inline buttons within the app UI. Apple's reasoning: gesture-based menus were too hidden -- users didn't discover them. The lesson is clear: **hidden gesture menus fail on constrained devices. Actions must be visually discoverable.**

Current watchOS 10+ uses:
- **Inline buttons** within scrollable content
- **EdgeButton** at the bottom of scrollable views for primary actions
- **Toolbar items** anchored to screen edges
- **Action sheets** that slide up from the bottom with a vertical list of labeled actions + a cancel button (max 4-5 items before scrolling)
- **Long-press context menus** (carried over from iOS) for secondary actions on specific elements

**Key takeaway for BITOS:** Apple abandoned hidden gestures in favor of always-visible action affordances. On a single-button device, this argues for a dedicated "actions available" indicator that's always visible when actions exist.

### Wear OS Quick Actions

Wear OS uses several patterns:
- **Chips** (rounded rectangles with icon + label) in vertical scrollable lists for navigation and actions
- **EdgeButton** at the bottom of tile layouts for primary actions
- **Swipe-to-reveal** on list items to expose secondary actions (delete, archive)
- **Bottom slot** in tiles for a single primary action button
- Minimum touch target: **48dp x 48dp**

**Key takeaway for BITOS:** The chip pattern (icon + short label in a rounded rectangle) works well for action lists. At 240px width, you could fit chips that are 200px wide with 20px padding on each side.

### Pebble OS (Most Relevant Precedent)

Pebble is the closest ancestor to BITOS -- a button-driven device with a small screen (144x168 on original, 144x180 on Time). Pebble used three right-side buttons (Up/Select/Down) plus a Back button.

**Three critical UI patterns:**

1. **MenuLayer** -- Vertical scrollable list. Up/Down to scroll, Select to choose. Each row has an icon (left) + title + optional subtitle. The currently highlighted row is visually distinct (inverted colors or highlight bar). This is the bread-and-butter navigation pattern.

2. **ActionBarLayer** -- A 30px-wide vertical bar on the right edge of the screen showing three icons aligned with the three right buttons. Each icon indicates what that button does. When the user needs more than 3 actions, pressing Select with an ellipsis icon opens a full ActionMenu.

3. **ActionMenu** -- A full-screen list of actions organized into sections. Breadcrumb dots on the left edge track navigation depth. Sections can have headers. Select confirms, Back retreats.

**Key takeaway for BITOS:** The ActionBarLayer concept is brilliant for button-driven devices. A persistent visual indicator showing what each button press will do at any moment. For a single-button device, this translates to a **status indicator** showing what SHORT/DOUBLE/LONG will do in the current context.

### Fitbit

Fitbit uses a simplified pattern:
- **Notification actions** appear as a vertical list of pre-defined quick replies (Yes, No, Sounds good!, Can't talk now)
- Limited to **5-6 pre-set options** maximum
- Text icon (three lines) opens quick replies, emoji icon opens emoji picker
- Voice reply available on devices with microphones

**Key takeaway for BITOS:** Pre-defined quick reply sets are effective for common interactions. The AI agent could pre-populate contextual quick replies.

---

## 2. Layout Patterns for Sub-300px Screens

### Why Split-Panel Fails at 240px

A sidebar (84px) + detail pane (156px) at 240px width is **not viable**. Here's why:
- At 16-18px font size (minimum for readability on small screens), 84px sidebar fits ~5 characters per line
- 156px detail pane fits ~9-10 characters per line
- Neither pane has enough room for meaningful content
- No smartwatch platform attempts side-by-side panels

Even Pebble (144px wide) never used split panels. The ActionBarLayer was only 30px wide and contained only icons, never text.

### Viable Alternatives (Ranked)

**Pattern A: Full-Screen Action List with Description Footer (RECOMMENDED)**
```
+------------------------+
| [icon] Action Name  >  |  <- highlighted (inverted)
| [icon] Action Name     |
| [icon] Action Name     |
| [icon] Action Name     |
+------------------------+
| Brief description of   |
| highlighted action...  |
+------------------------+
```
- Top 70% = scrollable action list (4-5 visible items)
- Bottom 30% = description/preview area for the currently highlighted item
- Separator line between zones
- As user scrolls (SHORT press), description updates for each highlighted item
- DOUBLE press to execute highlighted action
- LONG press to go back

This is essentially the pattern used by Garmin's glance system (1/3 screen for preview, 2/3 for navigation) and Flipper Zero's menu system.

**Pattern B: Card Carousel (Vertical)**
```
+------------------------+
|                        |
|     [Large Icon]       |
|                        |
|     Action Name        |
|   Brief description    |
|                        |
|      * * o * *         |  <- dot indicator (position in list)
+------------------------+
```
- One action per screen, full-width
- SHORT press = next card
- DOUBLE press = execute
- LONG press = back
- Dot indicator shows position in list
- Good for 3-5 actions, poor for 8+
- Used by Rabbit R1's card-based OS and watchOS notification actions

**Pattern C: Stacked List + Expandable Detail**
```
+------------------------+
| > Action Name          |  <- collapsed
| v Action Name          |  <- expanded
|   Description text     |
|   [Execute] button     |
| > Action Name          |
| > Action Name          |
+------------------------+
```
- SHORT to scroll between items
- DOUBLE to expand/collapse the highlighted item
- When expanded, DOUBLE again to execute
- Two-step confirmation prevents accidental execution
- Risk: two DOUBLE presses feels slow

**Pattern D: Overlay Bottom Sheet**
```
+------------------------+
| [dimmed chat content]  |
| [dimmed chat content]  |
+========================+
| Actions           [x]  |
| [icon] Do this         |
| [icon] Do that         |
| [icon] See more        |
+------------------------+
```
- Chat content visible but dimmed above
- Action panel slides up from bottom, occupying ~60% of screen
- Maintains conversational context
- LONG press to dismiss (back)
- Works best with 3-4 actions visible

### Recommendation for BITOS

**Use Pattern A (list + description footer) as the primary action menu**, with Pattern D (bottom sheet overlay) for in-chat contextual actions. Pattern B (card carousel) is good for agent-suggested actions where each option needs more explanation.

---

## 3. Action Categorization & Iconography

### Icon Strategies at 8-12px

At 240x280px, icons need to be **12-16px** to be recognizable. Below 12px, only the simplest shapes work.

**What works at 12px (monochrome):**
- Filled geometric shapes: circle, square, triangle, star, heart
- Simple glyphs: arrow, checkmark, X, plus, minus, gear, bell
- Single-stroke symbols: play, pause, stop, skip, home, search

**What fails at 12px:**
- Multi-detail icons (a person with a briefcase)
- Thin outlines (stroke gets lost)
- Icons that rely on internal detail (a document with lines)

**Unicode/ASCII approach (viable for BITOS):**
```
Navigation:    > < ^ v
Actions:       + - x = ~
Status:        * . o O @
Communication: ! ? #
Media:         |> || [] >>
Objects:       (simple geometric only)
```

At 240px width with 16px font, you can display meaningful icon+label combos:
```
[>] Play message        (3 + 13 chars = fits in 240px at 14px font)
[*] Mark important
[#] Add to tasks
[~] Summarize
```

### Color-Coding on Limited Displays

If the BITOS display supports color (even limited):
- **Green** = positive/confirm/go actions
- **Red** = destructive/stop/urgent actions
- **Blue/Cyan** = informational/navigation
- **Yellow/Amber** = caution/pending/starred
- **White** = neutral/default

On monochrome displays, use these alternatives:
- **Inverted text** (white on black) = highlighted/selected
- **Bold vs regular weight** = primary vs secondary
- **Filled vs outline shapes** = active vs inactive
- **Underline or border** = interactive/tappable
- **Dithering/stipple** = disabled/unavailable

### Category Grouping

Group actions by type with visual separators:
```
--- Reply ---
[>] Quick reply
[>] Voice reply
--- Manage ---
[*] Save to memory
[#] Create task
--- Info ---
[?] Explain more
[~] Summarize
```

Section headers in a smaller or dimmer font provide scannable structure without consuming much vertical space.

---

## 4. Voice-First Action Patterns

### How Voice Assistants Surface Options

Voice assistants on wearables use these patterns to present actionable options:

**Verbal enumeration with visual cards:**
The assistant speaks "I found three options" and displays numbered cards. The user can say "number two" or tap. On BITOS, the equivalent: the AI response includes suggested actions, displayed as a numbered list the user can scroll through.

**Smart suggestions / Quick replies:**
Contextual buttons that appear after specific messages. In chat interfaces, these are typically:
- 2-4 pill-shaped buttons below the last message
- Labeled with short action text ("Yes", "Tell me more", "Add to tasks")
- Disappear after selection or after the next message

**Agent-suggested actions:**
The AI proactively suggests next steps based on context:
```
+------------------------+
| "Your meeting with     |
| Alex is in 30 min."    |
|                        |
| [Navigate] [Message]   |
| [Snooze]  [Dismiss]    |
+------------------------+
```

### BITOS Voice-Action Integration

Since BITOS has voice capability, the pattern should be:
1. AI speaks response
2. Display shows 2-4 contextual action chips below the response text
3. User can SHORT-scroll through chips, DOUBLE to select
4. Or user can speak a command instead
5. Actions timeout after ~10 seconds if no interaction, falling back to idle

---

## 5. Single-Button Navigation of Action Menus

### The SHORT/DOUBLE/LONG Mapping

This is the core interaction challenge. With only three distinct inputs, here is the recommended mapping:

| Input | Action | Rationale |
|-------|--------|-----------|
| SHORT | Scroll/Next | Most frequent action, lowest effort |
| DOUBLE | Select/Confirm | Intentional action, requires deliberate input |
| LONG | Back/Cancel/Dismiss | Escape hatch, always available |

This mapping is consistent with Pebble's philosophy (scroll is the most common action) and iPod's (scroll is continuous, select is deliberate).

### Navigating a Multi-Action Menu

**Linear scroll with wrap-around:**
```
State: Menu with 5 items, item 2 highlighted

SHORT -> highlight moves to item 3
SHORT -> highlight moves to item 4
SHORT -> highlight moves to item 5
SHORT -> highlight wraps to item 1
DOUBLE -> execute highlighted item
LONG  -> dismiss menu, return to chat
```

**Visual feedback requirements:**
- **Currently highlighted:** Inverted colors (white text on black background) or a visible selection bar
- **Will be executed on DOUBLE:** The highlight itself is the indicator. No separate "armed" state needed -- DOUBLE is intentional enough
- **Scroll position:** Dot indicators or a scrollbar on the right edge showing position in the list

### Timeout-Based Patterns

**Auto-dismiss timeout:**
- If no input for 8-10 seconds, action menu fades/slides away
- Prevents the device from getting "stuck" on a menu screen
- The chat view underneath remains accessible

**NOT recommended: timeout-based selection** (where hovering on an item for N seconds selects it). This is error-prone and anxiety-inducing on small devices. Explicit DOUBLE-press selection is safer.

### Acceleration for Long Lists

If the list has more than 6-7 items:
- Rapid SHORT presses (within 200ms of each other) could scroll faster (skip every other item)
- Or: hold SHORT (if hardware supports press-and-hold distinct from LONG) to auto-scroll
- Group items into sections; SHORT at section boundary pauses briefly (haptic tick)

---

## 6. Chat Overlay / Modal Patterns

### Bottom Sheet on 240x280px

The bottom sheet is the strongest pattern for showing actions while maintaining chat context.

**Sizing recommendations:**
```
Full screen: 240 x 280px

Bottom sheet (60% height):
+------------------------+  y=0
| [Chat content, dimmed] |
| [Last message visible] |  y=112
+========================+  <- drag handle or separator
| Action Panel Title     |
| [>] Action one         |
| [>] Action two         |
| [>] Action three       |
| [SHORT=scroll DOUBLE=go|  y=280
+------------------------+
```

- Chat area: 112px tall (enough for 2-3 lines of chat at 16px + padding)
- Action panel: 168px tall (title + 3-4 action items + hint bar)
- Separator: 2px line or a small notch indicator

**Alternative sizes:**
- **Compact (40%):** 168px chat + 112px actions. Shows more chat context, fits 2-3 actions.
- **Expanded (80%):** 56px chat peek + 224px actions. Shows the last message snippet above, room for 5-6 actions + description area.

### Transparency and Dimming

On a color display:
- Chat content above the sheet at 30-40% opacity
- Action panel at full opacity with a subtle background color difference
- Sharp separator line between zones

On monochrome:
- Chat content above uses lighter/thinner font weight
- Action panel uses bold/inverted styling
- Dotted or dashed separator line

### Slide-In Animation

If the display supports smooth rendering:
- Action panel slides up from the bottom over 200-300ms
- Chat content simultaneously scrolls up and dims
- On dismiss (LONG press), reverse animation

If no animation capability:
- Instant cut to action panel view
- A brief flash or invert of the screen edge as transition indicator

### Alternative: Full-Screen Takeover with Breadcrumb

```
+------------------------+
| < Back to chat         |  <- header with context
|                        |
| [>] Action one         |
| [>] Action two         |
| [>] Action three       |
| [>] Action four        |
|                        |
| Description of         |
| highlighted action     |
+------------------------+
```

Simpler to implement. The "< Back to chat" header reminds the user where they came from. LONG press returns to chat. No transparency/dimming needed.

---

## 7. Precedent Device Summary

| Device | Screen | Input | Menu Pattern | Key Lesson |
|--------|--------|-------|-------------|------------|
| Pebble | 144x168/180 | 4 buttons | MenuLayer + ActionBar | Visual button mapping, breadcrumb dots |
| Apple Watch | 272x340+ | Touch + crown + side button | Inline buttons, action sheets | Hidden gestures fail, be explicit |
| Flipper Zero | 128x64 | D-pad + back | 13 GUI modules, vertical/horizontal menus | Composable UI components, d-pad optimized |
| Rabbit R1 | 2.88" touch | Touch + scroll wheel + button | Card carousel | One function per card, swipe/scroll navigation |
| Garmin | ~240x240 | Touch + 5 buttons | Glance (1/3 preview) + full widget | Glanceable preview before commitment |
| iPod | Various | Click wheel + center | Hierarchical list menus | Scroll is continuous, select is center |
| Fitbit | ~300x300 | Touch + 1-3 buttons | Quick replies, vertical lists | Pre-defined action sets, ~5 max |

---

## 8. Concrete Recommendations for BITOS (240x280px)

### Primary Action Menu Layout

Use **Pattern A: List with Description Footer**.

```
+----[240px]-------------+
| Actions            3/7 |  16px header + count    (y: 0-24)
+------------------------+
|  > Quick reply         |  20px row               (y: 24-44)
|  * Save to memory      |  20px row (HIGHLIGHTED) (y: 44-68)
|  # Create task         |  20px row               (y: 68-88)
|  ~ Summarize           |  20px row               (y: 88-108)
|  ? Explain more        |  20px row               (y: 108-128)
+------------------------+
| Saves this exchange to |  14px description        (y: 132-168)
| long-term memory for   |
| future reference.      |
+------------------------+
| SHORT=next  DBL=select |  12px hint bar          (y: 172-184)
+------------------------+
```

Dimensions: Header 24px + 5 rows at 24px each (120px) + separator 4px + description 52px + hint bar 16px = 216px. Leaves 64px margin. Adjust row count to 4-6 depending on font choice.

### In-Chat Quick Actions (Bottom Sheet)

When the AI suggests actions within conversation:

```
+------------------------+
| AI: "Your meeting is   |  Chat area (dimmed)
| at 3pm. Want me to..." |
+========================+
|  [>] Set reminder      |  Action chips
|  [>] Get directions    |
|  [>] Message Alex      |
+------------------------+
| SHORT=next  DBL=select |
+------------------------+
```

### Agent-Suggested Actions (Card Style)

For rich suggestions where each option needs context:

```
+------------------------+
|                        |
|     [ * ]              |  Large icon (24-32px)
|                        |
|   Save to Memory       |  18px title, centered
|                        |
|  Stores this chat for  |  14px description
|  future conversations  |
|  and fact extraction.  |
|                        |
|     o o * o o          |  Dot position indicator
+------------------------+
| SHORT=next  DBL=select |
+------------------------+
```

### Button Hint Bar

**Always show what each button does at the bottom of the screen.** This is the single most important UX decision for a single-button device. The hint bar should update dynamically based on context:

- In chat: `SHORT=scroll  DBL=actions  LONG=menu`
- In action list: `SHORT=next  DBL=select  LONG=back`
- On confirmation: `DBL=confirm  LONG=cancel`
- During playback: `SHORT=pause  DBL=skip  LONG=stop`

This is directly inspired by Pebble's ActionBarLayer philosophy: never leave the user guessing what a button press will do.

### Icon Recommendations

Use simple single-character symbols at 14-16px:
```
>  reply/forward       ?  help/explain
*  star/save           !  alert/urgent
#  task/tag            ~  summarize/wave
+  add/create          -  remove/dismiss
@  mention/contact     =  settings/config
```

These render clearly at small sizes, are language-neutral, and don't require custom pixel art. If you later want richer icons, design a custom 12x12 bitmap set -- but ASCII symbols are a strong starting point.

### Navigation State Machine

```
IDLE (chat view)
  SHORT -> scroll chat history
  DOUBLE -> open action menu (for last AI message)
  LONG -> open main menu

ACTION_MENU (list view)
  SHORT -> highlight next item (wrap at end)
  DOUBLE -> execute highlighted item
  LONG -> dismiss, return to chat
  TIMEOUT (10s) -> auto-dismiss, return to chat

CONFIRMATION (for destructive actions)
  DOUBLE -> confirm execution
  LONG -> cancel, return to action menu
  TIMEOUT (5s) -> cancel, return to action menu

MAIN_MENU (settings, history, etc.)
  SHORT -> highlight next item
  DOUBLE -> enter submenu / toggle setting
  LONG -> back one level (or dismiss if at top)
```

### Critical Design Rules

1. **Never more than 7 items in an action list.** If the AI generates more, group into categories or paginate.
2. **Always show a hint bar.** The user must know what their button presses will do at every moment.
3. **Highlight must be unambiguous.** Full-width inverted bar (white on black) for the selected item. No subtle underlines.
4. **Description area updates instantly** on scroll -- no delay, no animation.
5. **Timeout on menus.** 10 seconds of inactivity returns to chat. The device should never get stuck.
6. **LONG press always means "go back/escape."** This must be 100% consistent across every screen.
7. **Confirmation for destructive actions only.** "Send message" = direct execute. "Delete conversation" = confirmation step.
8. **Sound/haptic on each SHORT press.** A subtle tick confirms the scroll registered, critical when there's no touch feedback.

---

## Sources

- [Apple Watch Action Sheets - HIG](https://developer.apple.com/design/human-interface-guidelines/action-sheets)
- [Apple Watch Menus and Actions - HIG](https://developer.apple.com/design/human-interface-guidelines/menus-and-actions)
- [Creating Intuitive UI in watchOS 10](https://developer.apple.com/documentation/watchos-apps/creating-an-intuitive-and-effective-ui-in-watchos-10)
- [Wear OS Design Getting Started](https://developer.android.com/design/ui/wear/guides/m2-5/foundations/getting-started)
- [Wear OS Buttons](https://developer.android.com/design/ui/wear/guides/m2-5/components/buttons)
- [Wear OS Swipe to Reveal](https://developer.android.com/design/ui/wear/guides/m2-5/components/swipe-to-reveal)
- [Pebble Design Guidelines](https://developer.repebble.com/guides/design-and-interaction/recommended/)
- [Pebble ActionMenu API](https://d2r0ymlem3140p.cloudfront.net/developer.pebble.com/docs/c/User_Interface/Window/ActionMenu/index.html)
- [PebbleActionList (GitHub)](https://github.com/CocoaBob/PebbleActionList)
- [How to Design for Small Smartwatch Screens](https://thisisglance.com/learning-centre/how-do-i-design-for-such-a-small-smartwatch-screen)
- [UX Design for Smartwatches - Hapy Design](https://hapy.design/journal/ux-design-for-smartwatches/)
- [Designing for Smartwatches - Smashing Magazine](https://www.smashingmagazine.com/2015/02/designing-for-smartwatches-wearables/)
- [Smartwatch UX Guide - Protopie](https://www.protopie.io/blog/ultimate-guide-to-smartwatch-ux)
- [Bottom Sheets - NN/g](https://www.nngroup.com/articles/bottom-sheet/)
- [Bottom Sheets - Material Design 3](https://m3.material.io/components/bottom-sheets/guidelines)
- [Visual Guide to Flipper Zero GUI Components](https://brodan.biz/blog/a-visual-guide-to-flipper-zero-gui-components/)
- [Flipper Zero UI Tutorials (GitHub)](https://github.com/jamisonderek/flipper-zero-tutorials/wiki/User-Interface)
- [LVGL Embedded UI Framework](https://lvgl.io/)
- [LVGL Menu Widget](https://docs.lvgl.io/master/widgets/menu.html)
- [Rabbit R1 - rabbit.tech](https://www.rabbit.tech/rabbit-r1)
- [rabbitOS 2 Card-Based Design](https://www.humai.blog/rabbit-r1-rabbitos-2-complete-overhaul-vibe-coding-2025/)
- [Garmin Widget Glances](https://forums.garmin.com/developer/connect-iq/b/news-announcements/posts/widget-glances---a-new-way-to-present-your-data)
- [Garmin WatchUi API](https://developer.garmin.com/connect-iq/api-docs/Toybox/WatchUi.html)
- [iPod Click Wheel - Wikipedia](https://en.wikipedia.org/wiki/IPod_click_wheel)
- [PinchWatch: One-Handed Microinteractions](https://www.semanticscholar.org/paper/PinchWatch:-A-Wearable-Device-for-One-Handed-Loclair-Gustafson/a13ff458d5e7461eaccec0bee2e856b93c6be172)
- [Microinteraction Taxonomy](https://link.springer.com/chapter/10.1007/978-3-642-23774-4_45)
- [VUI Design Principles](https://www.parallelhq.com/blog/voice-user-interface-vui-design-principles)
- [AI UI Patterns](https://www.patterns.dev/react/ai-ui-patterns/)
- [8px Icons - Iconfinder](https://www.iconfinder.com/search/icons?family=8px)
- [Mobbin - Action Sheet Design](https://mobbin.com/glossary/action-sheet)
