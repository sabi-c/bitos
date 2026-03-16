# Chat Response Pagination — Design

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Paginate agent responses in the full ChatPanel into 1-4 pages with slow typewriter per page, triple-tap cycling, and a subtle centered page indicator.

**Architecture:** Client-side page splitting on paragraph boundaries with line-based fallback. Agent gets a soft prompt nudge to keep responses structured. TypewriterRenderer animates each page on first view, instant on revisit.

**Tech Stack:** pygame, TypewriterRenderer, ChatPanel, BackendClient system context

---

## 1. Layout (Full ChatPanel — paginated response)

```
┌──────────────────────────────┐
│ CHAT              connected  │  status bar (20px)
├──────────────────────────────┤
│ > what should I focus on...  │  context header (1 line, dimmed)
│                              │
│ good question. your top      │
│ priority today is the api    │
│ integration deadline.        │  response page area
│                              │  ~8-9 lines body text
│ anthony flagged the auth     │  slow typewriter on first view
│ module needs review before   │
│ merge — that's blocking      │
│ two other tasks.             │
│                              │
│             1/3              │  ← centered, hint font, DIM1
│ ○rec  ◉talk  ◎act  ⊙⊙⊙next │  hint line (1 line, compact, always visible)
└──────────────────────────────┘
```

- **Context header:** User's last message, truncated to 1 line with "...". Color: DIM2. Stays visible on all pages.
- **Response area:** Body text, word-wrapped. Typewriter animation on first view per page.
- **Page indicator:** Centered, hint font (8px), DIM1. Only visible when 2+ pages. Reads "1/3", "2/3", etc. No separator lines — it's part of the page, like a book page number.
- **Hint line:** Single line at the very bottom. Compact gesture icons + labels in hint font, DIM1. Always visible. Takes ~12px.
- **Actions overlay:** When user double-taps, the template menu (MORNING BRIEF, etc.) overlays on top of the page content. Exiting actions returns to full page view. The overlay does NOT resize the page — text stays in place underneath.
- **Non-paginated mode:** When response fits on one page, no indicator shown. Behaves exactly as current.

## 2. Page Splitting

After the full response text arrives and streaming completes:

1. Word-wrap the entire response into display lines (existing `_wrap_text`).
2. Calculate `lines_per_page`: available height for response area ÷ line_height. Subtract 1 line for context header, 1 line for page indicator.
3. Split into pages, preferring paragraph boundaries:
   - Scan for `\n\n` (paragraph breaks) in the wrapped lines.
   - If a paragraph break falls within ±2 lines of a page boundary, use it as the split point.
   - Otherwise, split at the last full line that fits.
4. Max 4 pages. If response exceeds 4 pages, page 4 ends with "..." appended to last line.
5. Store pages as `list[list[tuple[str, color]]]` — one list of colored lines per page.

## 3. Typewriter Animation Per Page

- Each page has a `revealed: bool` flag, initially `False`.
- **First view:** Create a new TypewriterRenderer with the page's text, speed "slow". Animate until complete, then mark `revealed = True`.
- **Revisit:** Text displays instantly (no animation). `revealed` flag persists.
- **Skip (triple-tap during animation):** Mark current page as `revealed`, advance to next page.
- Typewriter only runs for the currently visible page.

## 4. Page Navigation

- **Triple-tap:** Cycles through pages: 1→2→3→4→1→...
- Only active when response has 2+ pages.
- If typewriter is animating on current page, triple-tap:
  1. Marks current page revealed (shows full text)
  2. Advances to next page
  3. Starts typewriter on next page (if not yet revealed)

## 5. Gesture Map (ChatPanel with pagination)

| Gesture | IDLE (no pages) | IDLE (paginated) | During typewriter | RECORDING | ACTIONS |
|---------|----------------|------------------|-------------------|-----------|---------|
| Tap | Record | Record | Record | Stop & send / — | Next item |
| Hold | Quick talk | Quick talk | Quick talk | — | — |
| Double | Actions | Actions | Actions | — | Select |
| Triple | (unused) | Next page | Skip + next page | — | Prev item |
| Long | (no-op) | (no-op) | (no-op) | Cancel | Back to idle |

No gesture conflicts. Triple-tap was previously unused in IDLE mode. In ACTIONS mode it already means "prev item" — that's fine since pagination is only active in IDLE.

## 6. Hint Line + Actions Overlay

**Hint line** (always visible, 1 line, ~12px at very bottom):
- Paginated (2+ pages): `○rec  ◉talk  ◎act  ⊙⊙⊙next`
- Single page / no response: `○rec  ◉talk  ◎act`
- Hint font (8px), DIM1 color. Icons same as current but more compact.
- Triple-tap icon: three small interlocking circle outlines. Drawn with 3 overlapping `pygame.draw.circle(surface, DIM2, (x+offset, y), 3, 1)` calls, offset by ~4px each.

**Actions overlay** (on double-tap):
- Template menu renders as an opaque overlay on top of page content (solid BLACK background).
- Occupies the bottom ~60-80px of the screen (3 visible rows + its own hint line).
- Page text stays rendered underneath — no reflow or resize.
- Exiting actions (LONG_PRESS or selecting BACK) removes overlay, page is fully visible again.

## 7. Agent Prompt Nudge

Add to the system context / meta prompt sent with each chat request:

```
Keep responses concise and structured. Use short paragraphs separated by blank lines.
Aim for under 800 characters total when possible — the device displays text in pages
of ~250 characters each.
```

This is a soft guideline. The client-side splitting handles any response length gracefully.

## 8. State Management

New state on ChatPanel:
```python
self._pages: list[list[str]] = []       # wrapped lines per page
self._current_page: int = 0             # 0-indexed
self._page_revealed: list[bool] = []    # per-page reveal flag
self._page_typewriter: TypewriterRenderer | None = None  # current page animator
self._context_header: str = ""          # truncated user message
```

Page state is reset when:
- New user message is sent (clears pages, starts streaming)
- New response arrives (pages recomputed)

## 9. Font Size Increase (prerequisite)

Must be done before pagination so page character budgets are accurate.

Current sizes → proposed (needs device testing):
```python
FONT_SIZES = {
    "time_large": 24,    # keep
    "timer": 20,         # keep
    "title": 16 → 18,    # slightly larger
    "body": 12 → 14,     # main readability improvement
    "small": 10 → 11,    # slight bump
    "hint": 8 → 9,       # slight bump
}
```

Add bold support: `font.set_bold(True)` for body text in chat responses and menu labels. This is a display-wide change in `display/tokens.py` and `display/theme.py`.

After font change, recalculate lines_per_page for pagination.

## 10. Files to Modify

- **Modify:** `device/display/tokens.py` — font size increase
- **Modify:** `device/display/theme.py` — bold font support
- **Modify:** `device/screens/panels/chat.py` — page splitting, page state, triple-tap handler, render with pagination, context header, page indicator, actions as overlay, hint line (compact 1-liner)
- **Modify:** `device/display/typewriter.py` — no changes needed (reuse existing)
- **Modify:** `device/client/api.py` — add response format nudge to system context
- **Test:** `tests/test_chat_panel.py` — page splitting tests, triple-tap navigation, typewriter per page
- **Test:** `tests/test_typewriter.py` — verify existing tests still pass with new font sizes
