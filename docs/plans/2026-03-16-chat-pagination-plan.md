# Chat Response Pagination — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Paginate agent responses in ChatPanel into 1-4 pages with slow typewriter per page, triple-tap cycling, compact hint line, and overlay actions menu.

**Architecture:** Font sizes increased first (affects page budget). Client-side page splitting on paragraph boundaries. Each page gets its own TypewriterRenderer on first view, instant on revisit. Actions menu renders as overlay on top of page content. Hint line is a permanent compact one-liner at the bottom.

**Tech Stack:** pygame, TypewriterRenderer, ChatPanel, display/tokens.py

---

### Task 1: Increase font sizes + add bold support

**Files:**
- Modify: `device/display/tokens.py:48-55`
- Modify: `device/display/theme.py:59-70`
- Test: `tests/test_typewriter.py` (verify still passes)

**Step 1: Update font sizes**

In `device/display/tokens.py`, change `FONT_SIZES`:

```python
FONT_SIZES = {
    "time_large": 24,
    "timer": 20,
    "title": 18,
    "body": 14,
    "small": 11,
    "hint": 9,
}
```

**Step 2: Add bold font loader to theme.py**

In `device/display/theme.py`, add a bold variant loader after the existing `load_ui_font`:

```python
def load_ui_font_bold(role: str, ui_settings: dict) -> pygame.font.Font:
    """Load a bold variant of a UI font."""
    font = load_ui_font(role, ui_settings)
    font.set_bold(True)
    return font
```

**Step 3: Run tests to verify nothing breaks**

Run: `python3 -m pytest tests/test_typewriter.py tests/test_chat_panel.py tests/test_chat_preview.py -v`
Expected: All pass (font sizes don't affect test logic, only pixel rendering)

**Step 4: Commit**

```bash
git add device/display/tokens.py device/display/theme.py
git commit -m "feat: increase font sizes for readability + add bold font loader"
```

---

### Task 2: Page splitting utility

**Files:**
- Modify: `device/screens/panels/chat.py`
- Test: `tests/test_chat_panel.py`

**Step 1: Write the failing tests**

Add to `tests/test_chat_panel.py`:

```python
def test_split_into_pages_single_page(self):
    panel = self._make_panel()
    lines = ["line one", "line two", "line three"]
    pages = panel._split_into_pages(lines, lines_per_page=9)
    self.assertEqual(len(pages), 1)
    self.assertEqual(pages[0], lines)

def test_split_into_pages_multiple(self):
    panel = self._make_panel()
    lines = [f"line {i}" for i in range(20)]
    pages = panel._split_into_pages(lines, lines_per_page=9)
    self.assertEqual(len(pages), 3)
    self.assertEqual(len(pages[0]), 9)
    self.assertEqual(len(pages[1]), 9)
    self.assertEqual(len(pages[2]), 2)

def test_split_into_pages_max_four(self):
    panel = self._make_panel()
    lines = [f"line {i}" for i in range(50)]
    pages = panel._split_into_pages(lines, lines_per_page=9)
    self.assertEqual(len(pages), 4)
    # Last line of page 4 should end with "..."
    self.assertTrue(pages[3][-1].endswith("..."))

def test_split_into_pages_paragraph_boundary(self):
    panel = self._make_panel()
    # Lines with a paragraph break (empty line) near page boundary
    lines = [f"line {i}" for i in range(7)] + [""] + [f"para2 line {i}" for i in range(5)]
    pages = panel._split_into_pages(lines, lines_per_page=9)
    # Should split at the paragraph break (line 7-8) rather than at line 9
    self.assertEqual(len(pages), 2)
    self.assertEqual(pages[0][-1], "")  # empty line at end of page 1
```

**Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_chat_panel.py::ChatModeTests::test_split_into_pages_single_page -v`
Expected: FAIL — `_split_into_pages` doesn't exist.

**Step 3: Write minimal implementation**

Add to `ChatPanel` class in `device/screens/panels/chat.py`:

```python
    @staticmethod
    def _split_into_pages(lines: list[str], lines_per_page: int, max_pages: int = 4) -> list[list[str]]:
        """Split wrapped lines into pages, preferring paragraph boundaries."""
        if not lines or lines_per_page <= 0:
            return [lines] if lines else [[]]

        total = len(lines)
        if total <= lines_per_page:
            return [lines]

        pages: list[list[str]] = []
        pos = 0

        while pos < total and len(pages) < max_pages:
            if len(pages) == max_pages - 1:
                # Last allowed page — take remaining, truncate if needed
                remaining = lines[pos:]
                if len(remaining) > lines_per_page:
                    page = remaining[:lines_per_page]
                    page[-1] = page[-1].rstrip() + "..."
                else:
                    page = remaining
                pages.append(page)
                break

            end = min(pos + lines_per_page, total)

            # Look for paragraph break (empty line) within ±2 lines of boundary
            best_break = None
            for i in range(max(pos + 1, end - 2), min(end + 3, total)):
                if i < total and lines[i].strip() == "":
                    best_break = i + 1  # include the empty line
                    break

            if best_break and best_break > pos:
                page = lines[pos:best_break]
            else:
                page = lines[pos:end]

            pages.append(page)
            pos += len(page)

        return pages if pages else [[]]
```

**Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_chat_panel.py -v`
Expected: All pass

**Step 5: Commit**

```bash
git add device/screens/panels/chat.py tests/test_chat_panel.py
git commit -m "feat: page splitting utility with paragraph-aware boundaries"
```

---

### Task 3: Page state management + triple-tap navigation

**Files:**
- Modify: `device/screens/panels/chat.py:89-125` (init), `155-174` (update), `198-234` (handle_action)
- Test: `tests/test_chat_panel.py`

**Step 1: Write the failing tests**

Add to `tests/test_chat_panel.py`:

```python
def test_triple_press_advances_page(self):
    panel = self._make_panel()
    panel._pages = [["page1 line"], ["page2 line"], ["page3 line"]]
    panel._page_revealed = [True, False, False]
    panel._current_page = 0
    panel.handle_action("TRIPLE_PRESS")
    self.assertEqual(panel._current_page, 1)

def test_triple_press_cycles_around(self):
    panel = self._make_panel()
    panel._pages = [["p1"], ["p2"]]
    panel._page_revealed = [True, True]
    panel._current_page = 1
    panel.handle_action("TRIPLE_PRESS")
    self.assertEqual(panel._current_page, 0)

def test_triple_press_reveals_current_page(self):
    panel = self._make_panel()
    panel._pages = [["p1 line1", "p1 line2"], ["p2"]]
    panel._page_revealed = [False, False]
    panel._current_page = 0
    panel._page_typewriter = MagicMock()  # simulate active typewriter
    panel._page_typewriter.finished = False
    panel.handle_action("TRIPLE_PRESS")
    # Should mark page 0 as revealed and move to page 1
    self.assertTrue(panel._page_revealed[0])
    self.assertEqual(panel._current_page, 1)

def test_no_triple_press_without_pages(self):
    panel = self._make_panel()
    panel._pages = []
    panel._current_page = 0
    panel.handle_action("TRIPLE_PRESS")  # should not crash
    self.assertEqual(panel._current_page, 0)

def test_page_typewriter_created_on_first_view(self):
    panel = self._make_panel()
    panel._pages = [["hello world", "second line"]]
    panel._page_revealed = [False]
    panel._current_page = 0
    panel._start_page_typewriter()
    self.assertIsNotNone(panel._page_typewriter)

def test_page_typewriter_skipped_on_revisit(self):
    panel = self._make_panel()
    panel._pages = [["hello world"]]
    panel._page_revealed = [True]
    panel._current_page = 0
    panel._start_page_typewriter()
    self.assertIsNone(panel._page_typewriter)
```

**Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_chat_panel.py::ChatModeTests::test_triple_press_advances_page -v`
Expected: FAIL — `_pages` not initialized.

**Step 3: Write minimal implementation**

In `ChatPanel.__init__` (after line 124), add page state:

```python
        # Pagination state
        self._pages: list[list[str]] = []
        self._current_page: int = 0
        self._page_revealed: list[bool] = []
        self._page_typewriter: TypewriterRenderer | None = None
        self._context_header: str = ""
```

In `_handle_idle`, add TRIPLE_PRESS handler (after the DOUBLE_PRESS block, ~line 234):

```python
        elif action == "TRIPLE_PRESS":
            if len(self._pages) > 1:
                # Mark current page as revealed
                if self._current_page < len(self._page_revealed):
                    self._page_revealed[self._current_page] = True
                self._page_typewriter = None
                # Cycle to next page
                self._current_page = (self._current_page + 1) % len(self._pages)
                self._start_page_typewriter()
```

Add the `_start_page_typewriter` method:

```python
    def _start_page_typewriter(self) -> None:
        """Start typewriter for current page if not yet revealed."""
        if not self._pages or self._current_page >= len(self._pages):
            self._page_typewriter = None
            return
        if self._current_page < len(self._page_revealed) and self._page_revealed[self._current_page]:
            self._page_typewriter = None
            return
        page_text = "\n".join(self._pages[self._current_page])
        speed = "slow"
        if self._repository:
            saved_speed = self._repository.get_setting("text_speed", None)
            if saved_speed:
                speed = str(saved_speed)
        self._page_typewriter = TypewriterRenderer(page_text, speed=speed)
```

In `update()`, add page typewriter ticking (after the existing typewriter block, ~line 174):

```python
        # Tick page typewriter
        if self._page_typewriter and not self._page_typewriter.finished:
            self._page_typewriter.update(dt)
        elif self._page_typewriter and self._page_typewriter.finished:
            if self._current_page < len(self._page_revealed):
                self._page_revealed[self._current_page] = True
            self._page_typewriter = None
```

**Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_chat_panel.py -v`
Expected: All pass

**Step 5: Commit**

```bash
git add device/screens/panels/chat.py tests/test_chat_panel.py
git commit -m "feat: page state + triple-tap navigation with per-page typewriter"
```

---

### Task 4: Wire page splitting into _stream_response

**Files:**
- Modify: `device/screens/panels/chat.py:680-736` (_stream_response)
- Test: `tests/test_chat_panel.py`

**Step 1: Write the failing test**

Add to `tests/test_chat_panel.py`:

```python
def test_build_pages_from_response(self):
    panel = self._make_panel()
    panel._context_header = ""
    panel._build_pages("hello world. this is a test response.")
    self.assertGreaterEqual(len(panel._pages), 1)
    self.assertEqual(panel._current_page, 0)
    self.assertEqual(len(panel._page_revealed), len(panel._pages))
    self.assertFalse(panel._page_revealed[0])

def test_build_pages_sets_context_header(self):
    panel = self._make_panel()
    panel._build_pages("response text", user_message="what should I focus on today?")
    self.assertTrue(panel._context_header.startswith("> "))
    self.assertLessEqual(len(panel._context_header), 40)
```

**Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_chat_panel.py::ChatModeTests::test_build_pages_from_response -v`
Expected: FAIL — `_build_pages` doesn't exist.

**Step 3: Write minimal implementation**

Add `_build_pages` method to ChatPanel:

```python
    def _build_pages(self, response_text: str, user_message: str = "") -> None:
        """Split response into paginated pages and start typewriter on page 1."""
        # Context header: truncated user message
        if user_message:
            truncated = user_message[:35]
            if len(user_message) > 35:
                truncated += "..."
            self._context_header = f"> {truncated}"
        else:
            self._context_header = ""

        # Calculate available lines per page
        # Layout: status bar (SAFE_INSET + STATUS_BAR_H) + context header (1 line) + hint line (~12px)
        header_lines = 1 if self._context_header else 0
        hint_px = 14  # compact hint line
        available_h = PHYSICAL_H - (SAFE_INSET + STATUS_BAR_H + 2) - SAFE_INSET - hint_px
        lines_per_page = max(1, int(available_h / self._line_height) - header_lines - 1)  # -1 for page indicator

        # Word-wrap full response
        wrapped = self._wrap_text(response_text, PHYSICAL_W - SAFE_INSET * 2)

        # Split into pages
        self._pages = self._split_into_pages(wrapped, lines_per_page)
        self._current_page = 0
        self._page_revealed = [False] * len(self._pages)
        self._page_typewriter = None
        self._start_page_typewriter()
```

In `_stream_response` (~line 697-703), after typewriter creation, replace with page building:

Change:
```python
            self._typewriter = TypewriterRenderer(response_text, speed=speed)
```

To:
```python
            self._typewriter = TypewriterRenderer(response_text, speed=speed)
            # Build paginated view
            self._build_pages(response_text, user_message=message)
```

**Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_chat_panel.py -v`
Expected: All pass

**Step 5: Commit**

```bash
git add device/screens/panels/chat.py tests/test_chat_panel.py
git commit -m "feat: wire page splitting into stream response with context header"
```

---

### Task 5: Render paginated view + overlay actions

**Files:**
- Modify: `device/screens/panels/chat.py:297-415` (render method)

**Step 1: Rewrite the render method's message area + action area**

This is a rendering change — tested visually on device. The key changes:

1. **Message area calculation:** Remove the reserved `action_menu_h` from layout. The page content goes from `msg_area_top` to `PHYSICAL_H - SAFE_INSET - hint_px`.

2. **Paginated rendering:** When `self._pages` is non-empty, render the current page instead of the full message history.

3. **Context header:** Render truncated user message as first line, dimmed.

4. **Page indicator:** Centered "1/3" in hint font, DIM1, at bottom of response area (only if 2+ pages).

5. **Actions overlay:** When `self._mode == ChatMode.ACTIONS`, render the template menu as an opaque overlay on top of page content (not a reserved area).

6. **Hint line:** Compact one-liner at the very bottom (~12px). Replace the current multi-row action bar.

In `render()`, replace the layout calculations and message area (~lines 320-415) with:

```python
        # ── Layout calculations ──
        hint_px = 14
        msg_area_top = SAFE_INSET + STATUS_BAR_H + 2
        msg_area_bottom = PHYSICAL_H - SAFE_INSET - hint_px

        # ── Paginated response view ──
        if self._pages:
            self._render_paginated(surface, msg_area_top, msg_area_bottom)
        else:
            # Legacy: full conversation scroll view
            self._render_conversation(surface, msg_area_top, msg_area_bottom)

        # ── Streaming indicator ──
        if self._is_streaming:
            dots = "." * ((pygame.time.get_ticks() // 400) % 4)
            indicator = self._font_small.render(dots, False, DIM3)
            surface.blit(indicator, (SAFE_INSET, msg_area_bottom - 12))

        # ── Actions overlay (on top of page content) ──
        if self._mode == ChatMode.ACTIONS:
            overlay_h = self._ACTION_ROW_H * 3 + 4
            overlay_top = msg_area_bottom - overlay_h
            # Solid black background for overlay
            pygame.draw.rect(surface, BLACK, (0, overlay_top, PHYSICAL_W, overlay_h + hint_px + SAFE_INSET))
            pygame.draw.line(surface, HAIRLINE, (0, overlay_top), (PHYSICAL_W, overlay_top))
            self._render_actions_submenu(surface, overlay_top + 2)
        elif self._mode == ChatMode.RECORDING:
            # Recording elapsed in overlay area
            overlay_top = msg_area_bottom - self._ACTION_ROW_H
            pygame.draw.rect(surface, BLACK, (0, overlay_top, PHYSICAL_W, self._ACTION_ROW_H + hint_px + SAFE_INSET))
            elapsed = int(time.time() - self._recording_start_time)
            rec_surf = self._font.render(f"RECORDING  {elapsed}s", False, WHITE)
            surface.blit(rec_surf, (SAFE_INSET, overlay_top + 2))
        elif self._voice_step and self._voice_step not in ("", "SENDING"):
            overlay_h = self._ACTION_ROW_H * 3
            overlay_top = msg_area_bottom - overlay_h
            pygame.draw.rect(surface, BLACK, (0, overlay_top, PHYSICAL_W, overlay_h + hint_px + SAFE_INSET))
            self._render_voice_callout(surface, overlay_top)

        # ── Hint line (compact, always visible) ──
        hint_y = PHYSICAL_H - SAFE_INSET - hint_px
        bar_center_y = hint_y + hint_px // 2
        bar_content = self._get_action_bar_content()
        if bar_content:
            self._render_hint_line(surface, bar_center_y, bar_content)
        else:
            step_label = self._voice_step.lower() if self._voice_step else "listening"
            stream_text = self._font_small.render(f"{step_label}...", False, DIM3)
            surface.blit(stream_text, ((PHYSICAL_W - stream_text.get_width()) // 2, bar_center_y - stream_text.get_height() // 2))
```

Add `_render_paginated` method:

```python
    def _render_paginated(self, surface: pygame.Surface, top: int, bottom: int) -> None:
        """Render current page with context header and page indicator."""
        y = top

        # Context header (1 line, dimmed)
        if self._context_header:
            header_surf = self._font_small.render(self._context_header, False, DIM2)
            surface.blit(header_surf, (SAFE_INSET, y))
            y += self._line_height

        # Page text
        page = self._pages[self._current_page] if self._current_page < len(self._pages) else []

        if self._page_typewriter and not self._page_typewriter.finished:
            # Typewriter: show revealed portion
            visible = self._page_typewriter.get_visible_text()
            display_lines = self._wrap_text(visible, PHYSICAL_W - SAFE_INSET * 2)
        elif self._page_revealed[self._current_page] if self._current_page < len(self._page_revealed) else True:
            # Already revealed: show full page
            display_lines = page
        else:
            display_lines = page

        for line_text in display_lines:
            if y + self._line_height > bottom - self._line_height:  # leave room for indicator
                break
            text_surface = self._font.render(line_text, False, WHITE)
            surface.blit(text_surface, (SAFE_INSET, y))
            y += self._line_height

        # Page indicator (centered, hint font, DIM1) — only if 2+ pages
        if len(self._pages) > 1:
            indicator = f"{self._current_page + 1}/{len(self._pages)}"
            ind_surf = self._font_small.render(indicator, False, DIM1)
            ind_x = (PHYSICAL_W - ind_surf.get_width()) // 2
            surface.blit(ind_surf, (ind_x, bottom - self._line_height))
```

Add `_render_conversation` method (extract existing message rendering):

```python
    def _render_conversation(self, surface: pygame.Surface, top: int, bottom: int) -> None:
        """Render full conversation history (non-paginated fallback)."""
        with self._messages_lock:
            snapshot = list(self._messages)

        if self._typewriter and snapshot and snapshot[-1]["role"] == "assistant":
            snapshot = list(snapshot)
            snapshot[-1] = {"role": "assistant", "text": self._typewriter.get_visible_text()}

        visible_lines = []
        for msg in snapshot:
            prefix = "> " if msg["role"] == "user" else ""
            color = DIM2 if msg["role"] == "user" else WHITE
            lines = self._wrap_text(prefix + msg["text"], PHYSICAL_W - SAFE_INSET * 2)
            for line in lines:
                visible_lines.append((line, color))

        msg_y = top
        max_visible = int((bottom - top) / self._line_height)
        start = max(0, len(visible_lines) - max_visible - self._scroll_offset)
        for line_text, color in visible_lines[start:]:
            if msg_y > bottom:
                break
            text_surface = self._font.render(line_text, False, color)
            surface.blit(text_surface, (SAFE_INSET, msg_y))
            msg_y += self._line_height
```

Add `_render_hint_line` method:

```python
    def _render_hint_line(self, surface: pygame.Surface, center_y: int, items: list[tuple[str, str]]) -> None:
        """Render compact gesture hint line at bottom."""
        rendered = []
        for icon_type, label in items:
            label_surf = self._font_small.render(label.lower(), False, DIM1)
            rendered.append((icon_type, label_surf))

        total_w = sum(8 + 2 + s.get_width() for _, s in rendered)
        spacing = max(4, (PHYSICAL_W - total_w) // (len(rendered) + 1))
        bx = spacing
        for icon_type, label_surf in rendered:
            ic = (bx + 3, center_y)
            if icon_type == "tap":
                pygame.draw.circle(surface, DIM1, ic, 2, 1)
            elif icon_type == "double":
                pygame.draw.circle(surface, DIM1, ic, 2, 1)
                pygame.draw.circle(surface, DIM1, ic, 1, 1)
            elif icon_type == "hold":
                pygame.draw.circle(surface, DIM1, ic, 2, 0)
            elif icon_type == "triple":
                # Three interlocking circle outlines
                for offset in (-3, 0, 3):
                    pygame.draw.circle(surface, DIM1, (ic[0] + offset, ic[1]), 2, 1)
            surface.blit(label_surf, (bx + 8, center_y - label_surf.get_height() // 2))
            bx += 8 + label_surf.get_width() + spacing
```

**Step 2: Update `_get_action_bar_content` for triple-tap hint**

In `_get_action_bar_content`, update IDLE mode to include triple-tap when paginated:

```python
    def _get_action_bar_content(self) -> list[tuple[str, str]]:
        if self._mode == ChatMode.IDLE:
            items = [("tap", "rec"), ("hold", "talk"), ("double", "act")]
            if len(self._pages) > 1:
                items.append(("triple", "next"))
            return items
        # ... rest unchanged
```

**Step 3: Run all tests**

Run: `python3 -m pytest tests/test_chat_panel.py -v`
Expected: All pass

**Step 4: Commit**

```bash
git add device/screens/panels/chat.py
git commit -m "feat: paginated render with overlay actions, compact hint line, page indicator"
```

---

### Task 6: Add response format nudge to chat payload

**Files:**
- Modify: `device/client/api.py:135-142`
- Test: manual verification

**Step 1: Add format hint to chat payload**

In `device/client/api.py`, in `_stream_chat_sse`, add to the payload dict:

```python
        payload: dict = {
            "message": message,
            "agent_mode": mode,
            "tasks_today": tasks_today,
            "battery_pct": battery_pct,
            "web_search": web_search,
            "memory": memory,
            "response_format_hint": "Keep responses concise and structured. Use short paragraphs separated by blank lines. Aim for under 800 characters total — the device displays text in pages of ~250 characters each.",
        }
```

**Step 2: Commit**

```bash
git add device/client/api.py
git commit -m "feat: add response format hint to chat payload for page-aware responses"
```

---

### Task 7: Clear pagination on new message + final integration

**Files:**
- Modify: `device/screens/panels/chat.py:630-660` (_send_message)
- Test: `tests/test_chat_panel.py`

**Step 1: Write the failing test**

Add to `tests/test_chat_panel.py`:

```python
def test_send_message_clears_pages(self):
    panel = self._make_panel()
    panel._pages = [["old page"]]
    panel._page_revealed = [True]
    panel._current_page = 1
    panel._context_header = "old header"
    panel._input_text = "new message"
    panel._send_message()
    self.assertEqual(panel._pages, [])
    self.assertEqual(panel._current_page, 0)
    self.assertEqual(panel._context_header, "")
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_chat_panel.py::ChatModeTests::test_send_message_clears_pages -v`
Expected: FAIL — `_send_message` doesn't clear page state yet.

**Step 3: Write minimal implementation**

In `_send_message`, after `self._scroll_offset = 0` (~line 650), add:

```python
        # Clear pagination
        self._pages = []
        self._current_page = 0
        self._page_revealed = []
        self._page_typewriter = None
        self._context_header = ""
```

**Step 4: Run all tests**

Run: `python3 -m pytest tests/test_chat_panel.py -v`
Expected: All pass

**Step 5: Commit**

```bash
git add device/screens/panels/chat.py tests/test_chat_panel.py
git commit -m "feat: clear pagination state on new message send"
```

---

### Task 8: Run full test suite + push

**Step 1: Run all related tests**

Run: `python3 -m pytest tests/test_chat_panel.py tests/test_chat_preview.py tests/test_chat_settings.py tests/test_typewriter.py tests/test_device_repository.py -v`
Expected: All pass

**Step 2: Push**

```bash
git push origin main
```
