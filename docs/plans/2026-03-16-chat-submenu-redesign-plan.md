# Chat Submenu Redesign — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebuild the chat preview panel with an ambient agent greeting, voice-first response field, gesture cleanup (remove LONG_PRESS from chat), and a settings screen.

**Architecture:** Greeting stored as a special session type ("greeting") in SQLite. ChatPreviewPanel gets a slow typewriter banner + interactive response field as first submenu item. CompositeScreen updated so no submenu item is highlighted until DOUBLE_PRESS enters submenu. ChatPanel removes LONG_PRESS exit; exit moves to actions menu.

**Tech Stack:** pygame, SQLite (DeviceRepository), TypewriterRenderer, BackendClient, existing PreviewPanel/CompositeScreen

---

### Task 1: Add "slow" typewriter speed preset

**Files:**
- Modify: `device/display/typewriter.py:17-22`
- Test: `tests/test_typewriter.py`

**Step 1: Write the failing test**

Add to `tests/test_typewriter.py`:

```python
def test_slow_preset_uses_80ms_base(self):
    tw = TypewriterRenderer("hi", speed="slow")
    # "slow" preset = 80ms base, so 2 chars should take ~160ms minimum
    tw.update(0.05)  # 50ms — should reveal at most 1 char
    self.assertLess(len(tw.get_visible_text()), 2)
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_typewriter.py::TypewriterTests::test_slow_preset_uses_80ms_base -v`
Expected: FAIL — "slow" falls back to "normal" (30ms) so 2 chars may already be revealed.

**Step 3: Write minimal implementation**

In `device/display/typewriter.py`, change the `SPEED_PRESETS` dict:

```python
SPEED_PRESETS: dict[str, float] = {
    "slow": 80.0,
    "normal": 30.0,
    "fast": 15.0,
    "instant": 0.0,
}
```

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_typewriter.py -v`
Expected: All pass

**Step 5: Commit**

```bash
git add device/display/typewriter.py tests/test_typewriter.py
git commit -m "feat: add 'slow' typewriter speed preset (80ms base)"
```

---

### Task 2: Add session_type column + greeting session methods to repository

**Files:**
- Modify: `device/storage/repository.py`
- Test: `tests/test_repository.py` (create if not exists)

**Step 1: Write the failing tests**

Create or add to `tests/test_repository.py`:

```python
"""Tests for DeviceRepository greeting session support."""
import os
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

from storage.repository import DeviceRepository


class GreetingSessionTests(unittest.TestCase):
    def setUp(self):
        self.db_path = "/tmp/test_bitos_greeting.db"
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        self.repo = DeviceRepository(db_path=self.db_path)
        self.repo.initialize()

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_create_greeting_session(self):
        sid = self.repo.create_greeting_session("good morning")
        self.assertIsNotNone(sid)
        msgs = self.repo.list_messages(sid)
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0]["role"], "assistant")
        self.assertEqual(msgs[0]["text"], "good morning")

    def test_get_greeting_session_returns_recent(self):
        sid = self.repo.create_greeting_session("hello there")
        result = self.repo.get_greeting_session()
        self.assertIsNotNone(result)
        self.assertEqual(result["id"], sid)

    def test_get_greeting_session_returns_none_when_stale(self):
        # No greeting sessions exist
        result = self.repo.get_greeting_session()
        self.assertIsNone(result)

    def test_get_latest_chat_session_excludes_greeting(self):
        # Create a greeting and a regular chat
        self.repo.create_greeting_session("hi there")
        chat_id = self.repo.create_session(title="real chat")
        self.repo.add_message(chat_id, "user", "hello")
        result = self.repo.get_latest_chat_session()
        self.assertIsNotNone(result)
        self.assertEqual(result["id"], chat_id)

    def test_get_latest_chat_session_returns_none_when_only_greeting(self):
        self.repo.create_greeting_session("hi")
        result = self.repo.get_latest_chat_session()
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_repository.py -v`
Expected: FAIL — `create_greeting_session` and other methods don't exist yet.

**Step 3: Write minimal implementation**

In `device/storage/repository.py`:

1. Add migration 6 to `MIGRATIONS` dict and bump `LATEST_SCHEMA_VERSION` to 6:

```python
LATEST_SCHEMA_VERSION = 6
```

```python
    6: """
    ALTER TABLE sessions ADD COLUMN session_type TEXT DEFAULT 'chat';
    CREATE INDEX IF NOT EXISTS idx_sessions_type_created
      ON sessions(session_type, created_at);
    """,
```

2. Add these methods to `DeviceRepository`:

```python
    def create_greeting_session(self, greeting_text: str) -> int:
        """Create a greeting session with the agent's greeting as first message."""
        now = time.time()
        with closing(self._connect()) as conn:
            cur = conn.execute(
                "INSERT INTO sessions(title, session_type, created_at, updated_at) VALUES (?, 'greeting', ?, ?)",
                ("greeting", now, now),
            )
            session_id = int(cur.lastrowid)
            conn.execute(
                "INSERT INTO messages(session_id, role, text, created_at) VALUES (?, 'assistant', ?, ?)",
                (session_id, greeting_text, now),
            )
            conn.commit()
            return session_id

    def get_greeting_session(self) -> dict | None:
        """Get the most recent greeting session if less than 1 hour old."""
        cutoff = time.time() - 3600
        with closing(self._connect()) as conn:
            row = conn.execute(
                """
                SELECT s.id, s.created_at, s.updated_at
                FROM sessions s
                WHERE s.session_type = 'greeting'
                  AND s.created_at > ?
                ORDER BY s.created_at DESC
                LIMIT 1
                """,
                (cutoff,),
            ).fetchone()
            if not row:
                return None
            return {"id": int(row[0]), "created_at": row[1], "updated_at": row[2]}

    def get_latest_chat_session(self) -> dict | None:
        """Get the most recent non-greeting session with messages."""
        with closing(self._connect()) as conn:
            row = conn.execute(
                """
                SELECT s.id, s.title, s.created_at, s.updated_at,
                       COUNT(m.id) as msg_count
                FROM sessions s
                LEFT JOIN messages m ON m.session_id = s.id
                WHERE COALESCE(s.session_type, 'chat') = 'chat'
                GROUP BY s.id
                HAVING msg_count > 0
                ORDER BY s.updated_at DESC
                LIMIT 1
                """
            ).fetchone()
            if not row:
                return None
            return {
                "id": int(row[0]),
                "title": row[1],
                "created_at": row[2],
                "updated_at": row[3],
                "msg_count": int(row[4]),
            }
```

**Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_repository.py -v`
Expected: All pass

**Step 5: Commit**

```bash
git add device/storage/repository.py tests/test_repository.py
git commit -m "feat: greeting session type + repository methods"
```

---

### Task 3: Update PreviewPanel base to support "no highlight" state

**Files:**
- Modify: `device/ui/panels/base.py`
- Test: `tests/test_composite_screen.py`

**Step 1: Write the failing test**

Add to `tests/test_composite_screen.py`:

```python
def test_submenu_no_highlight_in_sidebar_mode(self):
    """When sidebar is focused, preview panel should have selected_index = -1."""
    cs = self._make_cs()
    panel = cs._active_panel()
    self.assertEqual(panel.selected_index, -1)

def test_submenu_highlights_first_on_enter(self):
    """DOUBLE_PRESS from sidebar sets selected_index to 0."""
    cs = self._make_cs()
    cs.handle_action("DOUBLE_PRESS")
    panel = cs._active_panel()
    self.assertEqual(panel.selected_index, 0)
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_composite_screen.py::test_submenu_no_highlight_in_sidebar_mode -v`
Expected: FAIL — selected_index starts at 0, not -1.

**Step 3: Write minimal implementation**

In `device/ui/panels/base.py`:

1. Change `__init__` to start with `selected_index = -1`:

```python
    def __init__(self, items: list[dict], on_action: callable):
        self.items = items
        self.selected_index = -1  # No highlight until submenu is entered
        self._on_action = on_action
```

2. Update `handle_action` to handle -1 → 0 on first SHORT_PRESS:

```python
    def handle_action(self, action: str) -> bool:
        """Handle button action. Returns True if consumed."""
        if action == "SHORT_PRESS":
            self.selected_index = (self.selected_index + 1) % len(self.items)
            return True
        elif action == "DOUBLE_PRESS":
            if self.selected_index < 0:
                return False  # Not focused yet
            item = self.items[self.selected_index]
            self._on_action(item["action"])
            return True
        return False
```

3. Update `_render_items` to skip highlight when `selected_index == -1`:

```python
    def _render_items(self, surface: pygame.Surface, y_offset: int = 0) -> None:
        font = get_font(FONT_SIZE)
        w = surface.get_width()

        for idx, item in enumerate(self.items):
            y = y_offset + idx * ITEM_H
            if y + ITEM_H > surface.get_height():
                break

            selected = idx == self.selected_index
            label = item["label"]

            if selected:
                text = INDICATOR + label
                color = WHITE
            else:
                text = "  " + label
                color = DIM3

            text_surf = font.render(text, False, color)
            surface.blit(text_surf, (PAD_X, y + PAD_Y))

            if not selected and y + ITEM_H - 1 < surface.get_height():
                pygame.draw.line(surface, HAIRLINE,
                                 (PAD_X, y + ITEM_H - 1),
                                 (w - PAD_X, y + ITEM_H - 1))
```

(No change to _render_items needed — when `selected_index == -1`, no item matches `idx == self.selected_index`, so all items render as DIM3. This is the desired "no highlight" behavior.)

4. In `device/ui/composite_screen.py`, update `_handle_sidebar_action` to set `selected_index = 0` on enter (already does this), and ensure panels start with -1. The init already happens in PreviewPanel base.

**Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_composite_screen.py -v`

Note: Some existing tests may need to be updated if they assume `selected_index` starts at 0. Fix any that break by setting `panel.selected_index = 0` explicitly before testing submenu behavior.

Expected: All pass

**Step 5: Commit**

```bash
git add device/ui/panels/base.py tests/test_composite_screen.py
git commit -m "feat: preview panels start with no highlight (selected_index=-1)"
```

---

### Task 4: Redesign ChatPreviewPanel with greeting banner + response field

**Files:**
- Modify: `device/ui/panels/chat_preview.py`
- Test: `tests/test_chat_preview.py` (create)

**Step 1: Write the failing tests**

Create `tests/test_chat_preview.py`:

```python
"""Tests for ChatPreviewPanel greeting + response field."""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

from ui.panels.chat_preview import ChatPreviewPanel, CHAT_ITEMS


class ChatPreviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.font.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_items_include_response_field(self):
        panel = ChatPreviewPanel(on_action=MagicMock())
        self.assertEqual(panel.items[0]["action"], "respond")
        self.assertEqual(panel.items[0]["label"], "RECORD")

    def test_items_include_back_to_main_menu(self):
        panel = ChatPreviewPanel(on_action=MagicMock())
        last = panel.items[-1]
        self.assertEqual(last["action"], "back")
        self.assertEqual(last["label"], "BACK TO MAIN MENU")

    def test_set_greeting_text(self):
        panel = ChatPreviewPanel(on_action=MagicMock())
        panel.set_greeting("good morning, 3 tasks today")
        self.assertEqual(panel._greeting_text, "good morning, 3 tasks today")

    def test_greeting_typewriter_uses_slow_speed(self):
        panel = ChatPreviewPanel(on_action=MagicMock())
        panel.set_greeting("hello there")
        self.assertIsNotNone(panel._greeting_typewriter)

    def test_set_resume_subtext(self):
        panel = ChatPreviewPanel(on_action=MagicMock())
        panel.set_resume_info("morning brief", "2h ago")
        resume_item = next(i for i in panel.items if i["action"] == "resume_chat")
        self.assertIn("morning brief", resume_item.get("subtext", ""))

    def test_respond_action_fires_callback(self):
        cb = MagicMock()
        panel = ChatPreviewPanel(on_action=cb)
        panel.selected_index = 0  # response field
        panel.handle_action("DOUBLE_PRESS")
        cb.assert_called_once_with("respond")


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_chat_preview.py -v`
Expected: FAIL — current ChatPreviewPanel doesn't have response field or greeting methods.

**Step 3: Write minimal implementation**

Rewrite `device/ui/panels/chat_preview.py`:

```python
"""ChatPreviewPanel — ambient greeting + voice-first response field.

Top area: slow typewriter greeting from agent (3-4 lines).
First submenu item: response field (record to reply to greeting).
Below: START NEW CHAT, RESUME CHAT, CHAT HISTORY, SETTINGS, BACK TO MAIN MENU.
"""

from __future__ import annotations

import pygame

from device.display.theme import get_font
from device.display.tokens import DIM2, DIM3, HAIRLINE, WHITE
from device.display.animator import blink_cursor
from device.display.typewriter import TypewriterRenderer
from device.ui.panels.base import PreviewPanel


GREETING_H = 60  # Top greeting area height
GREETING_FONT_SIZE = 8
GREETING_PAD_X = 6
GREETING_PAD_Y = 4
MAX_GREETING_CHARS = 120

CHAT_ITEMS = [
    {"label": "RECORD", "description": "Reply to greeting", "action": "respond"},
    {"label": "START NEW CHAT", "description": "Begin a new conversation", "action": "new_chat"},
    {"label": "RESUME CHAT", "description": "Continue last conversation", "action": "resume_chat", "subtext": ""},
    {"label": "CHAT HISTORY", "description": "Browse past conversations", "action": "chat_history"},
    {"label": "SETTINGS", "description": "Chat settings", "action": "settings"},
    {"label": "BACK TO MAIN MENU", "description": "Return to sidebar", "action": "back"},
]


class ChatPreviewPanel(PreviewPanel):
    """Preview panel for CHAT sidebar item."""

    def __init__(self, on_action: callable, repository=None):
        # Deep copy items so subtext mutations don't leak across instances
        items = [dict(item) for item in CHAT_ITEMS]
        super().__init__(items=items, on_action=on_action)
        self._repository = repository
        self._greeting_text: str = ""
        self._greeting_typewriter: TypewriterRenderer | None = None
        self._greeting_revealed = False  # True after first full reveal
        self._cursor_anim = blink_cursor()
        self._greeting_session_id: int | None = None

    def set_greeting(self, text: str, session_id: int | None = None) -> None:
        """Set the agent greeting text and start slow typewriter."""
        self._greeting_text = text[:MAX_GREETING_CHARS] if text else ""
        self._greeting_session_id = session_id
        if self._greeting_text and not self._greeting_revealed:
            self._greeting_typewriter = TypewriterRenderer(self._greeting_text, speed="slow")
        else:
            self._greeting_revealed = True
            self._greeting_typewriter = None

    def set_resume_info(self, title: str, time_ago: str) -> None:
        """Update RESUME CHAT item with last chat info."""
        for item in self.items:
            if item["action"] == "resume_chat":
                item["subtext"] = f"{title} · {time_ago}"
                break

    def update(self, dt: float) -> None:
        self._cursor_anim.update(dt)
        if self._greeting_typewriter and not self._greeting_typewriter.finished:
            self._greeting_typewriter.update(dt)
        elif self._greeting_typewriter and self._greeting_typewriter.finished:
            self._greeting_revealed = True
            self._greeting_typewriter = None

    def render(self, surface: pygame.Surface) -> None:
        font = get_font(GREETING_FONT_SIZE)
        w = surface.get_width()

        # ── Greeting banner (top area) ──
        if self._greeting_text:
            if self._greeting_typewriter:
                visible = self._greeting_typewriter.get_visible_text()
            else:
                visible = self._greeting_text

            lines = _wrap_text(visible, font, w - GREETING_PAD_X * 2)
            y = GREETING_PAD_Y
            line_h = font.get_height() + 2
            for line in lines:
                if y + line_h > GREETING_H - 4:
                    break
                surf = font.render(line, False, DIM3)
                surface.blit(surf, (GREETING_PAD_X, y))
                y += line_h

            # Blinking cursor while typing
            if self._greeting_typewriter and not self._greeting_typewriter.finished:
                cursor_char = "_" if self._cursor_anim.visible else " "
                cursor_surf = font.render(cursor_char, False, DIM2)
                # Position after last character
                if lines:
                    last_line_w = font.size(lines[-1])[0]
                    cy = GREETING_PAD_Y + (len(lines) - 1) * line_h
                    surface.blit(cursor_surf, (GREETING_PAD_X + last_line_w, cy))

        # Separator
        pygame.draw.line(surface, HAIRLINE,
                         (GREETING_PAD_X, GREETING_H - 1),
                         (w - GREETING_PAD_X, GREETING_H - 1))

        # ── Submenu items below greeting ──
        self._render_items(surface, y_offset=GREETING_H)


def _wrap_text(text: str, font: pygame.font.Font, max_width: int) -> list[str]:
    """Simple word-wrap."""
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        test = (current + " " + word).strip()
        if font.size(test)[0] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [""]
```

**Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_chat_preview.py -v`
Expected: All pass

**Step 5: Commit**

```bash
git add device/ui/panels/chat_preview.py tests/test_chat_preview.py
git commit -m "feat: ChatPreviewPanel with greeting banner + response field"
```

---

### Task 5: Remove LONG_PRESS exit from ChatPanel, add BACK to actions menu

**Files:**
- Modify: `device/screens/panels/chat.py:220-270`
- Test: `tests/test_chat_panel.py`

**Step 1: Write the failing tests**

Add/update in `tests/test_chat_panel.py`:

```python
def test_long_press_in_idle_does_not_exit(self):
    """LONG_PRESS should NOT call on_back anymore."""
    called = []
    panel = self._make_panel(on_back=lambda: called.append(True))
    panel.handle_action("LONG_PRESS")
    self.assertFalse(called)

def test_actions_menu_includes_back(self):
    panel = self._make_panel()
    items = list(panel._templates) + [{"label": "BACK TO MAIN MENU", "message": ""}]
    back_labels = [i["label"] for i in items]
    self.assertIn("BACK TO MAIN MENU", back_labels)

def test_selecting_back_in_actions_calls_on_back(self):
    called = []
    panel = self._make_panel(on_back=lambda: called.append(True))
    panel._mode = ChatMode.ACTIONS
    # Navigate to BACK TO MAIN MENU (last item)
    items = list(panel._templates) + [{"label": "BACK TO MAIN MENU", "message": ""}]
    panel._action_template_index = len(items) - 1
    panel.handle_action("DOUBLE_PRESS")
    self.assertTrue(called)
```

**Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_chat_panel.py -v`
Expected: `test_long_press_in_idle_does_not_exit` FAILS (currently LONG_PRESS calls on_back).

**Step 3: Write minimal implementation**

In `device/screens/panels/chat.py`:

1. Update `_handle_idle` — remove LONG_PRESS exit:

```python
    def _handle_idle(self, action: str):
        if action == "SHORT_PRESS":
            if self._hold_timer is not None:
                self._hold_timer = None
                return
            self._quick_talk = False
            self._start_recording()
        elif action == "DOUBLE_PRESS":
            self._mode = ChatMode.ACTIONS
            self._action_template_index = 0
        # LONG_PRESS: no-op (removed — conflicts with hold gesture)
```

2. Update `_handle_actions` — add BACK TO MAIN MENU:

```python
    def _handle_actions(self, action: str):
        items = list(self._templates) + [{"label": "BACK", "message": ""}, {"label": "BACK TO MAIN MENU", "message": ""}]
        if action == "SHORT_PRESS":
            self._action_template_index = (self._action_template_index + 1) % len(items)
        elif action == "TRIPLE_PRESS":
            self._action_template_index = (self._action_template_index - 1) % len(items)
        elif action == "DOUBLE_PRESS":
            selected = items[self._action_template_index]
            if selected["label"] == "BACK":
                self._mode = ChatMode.IDLE
            elif selected["label"] == "BACK TO MAIN MENU":
                self._mode = ChatMode.IDLE
                if self._on_back:
                    self._on_back()
            else:
                self._send_template_message(selected)
                self._mode = ChatMode.IDLE
        elif action == "LONG_PRESS":
            self._mode = ChatMode.IDLE
```

3. Update `_get_action_bar_content` for IDLE — remove hold reference:

```python
    def _get_action_bar_content(self) -> list[tuple[str, str]]:
        if self._mode == ChatMode.IDLE:
            return [("tap", "RECORD"), ("hold", "TALK"), ("double", "ACTIONS")]
```

(Already correct from earlier changes.)

**Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_chat_panel.py -v`

Note: The existing `test_long_press_in_idle_exits_chat` test will need to be removed or inverted. Update it to assert LONG_PRESS does NOT call on_back.

Expected: All pass

**Step 5: Commit**

```bash
git add device/screens/panels/chat.py tests/test_chat_panel.py
git commit -m "feat: remove LONG_PRESS exit from chat, add BACK TO MAIN MENU in actions"
```

---

### Task 6: Wire greeting fetch on boot + panel registry updates

**Files:**
- Modify: `device/main.py:374-404`
- Modify: `device/ui/panel_registry.py`

**Step 1: Update panel_registry to pass context to ChatPreviewPanel**

In `device/ui/panel_registry.py`, update `create_right_panels` to accept and pass `repository`:

```python
def create_right_panels(panel_openers: dict | None = None, repository=None) -> dict:
    openers = panel_openers or {}
    panels = {}

    def chat_action(action_key):
        if action_key == "back":
            return
        if action_key == "respond":
            # Open chat with greeting session context
            opener = openers.get("CHAT")
            if opener is not None:
                opener()
            return
        opener = openers.get("CHAT")
        if opener is not None:
            opener()

    panels["CHAT"] = ChatPreviewPanel(on_action=chat_action, repository=repository)
    # ... rest unchanged
```

**Step 2: Update main.py to fetch greeting on boot**

In `device/main.py`, inside `on_home()`:

```python
    def on_home():
        panel_openers = { ... }  # unchanged
        right_panels = create_right_panels(panel_openers=panel_openers, repository=repository)

        # Fetch greeting for chat preview
        import threading
        def _fetch_greeting():
            try:
                existing = repository.get_greeting_session()
                if existing:
                    msgs = repository.get_session_messages(str(existing["id"]), limit=1)
                    if msgs:
                        chat_panel = right_panels.get("CHAT")
                        if chat_panel and hasattr(chat_panel, "set_greeting"):
                            chat_panel.set_greeting(msgs[0]["text"], session_id=existing["id"])
                    return

                # No recent greeting — request one from backend
                result = client.chat(
                    "Give a brief contextual greeting in under 100 characters. "
                    "Lowercase, casual, no emojis. Mention time of day and any "
                    "relevant tasks or context.",
                    system_prompt="You are a pocket AI companion. Respond with ONLY the greeting text, nothing else."
                )
                greeting_text = ""
                for chunk in result:
                    greeting_text += chunk
                greeting_text = greeting_text.strip()[:120]

                if greeting_text:
                    sid = repository.create_greeting_session(greeting_text)
                    chat_panel = right_panels.get("CHAT")
                    if chat_panel and hasattr(chat_panel, "set_greeting"):
                        chat_panel.set_greeting(greeting_text, session_id=sid)
            except Exception as exc:
                logger.warning("greeting_fetch_failed: %s", exc)

        threading.Thread(target=_fetch_greeting, daemon=True).start()

        # Set resume info
        latest_chat = repository.get_latest_chat_session()
        if latest_chat:
            import time as _time
            age_s = _time.time() - float(latest_chat.get("updated_at", 0))
            if age_s < 3600:
                time_ago = f"{int(age_s / 60)}m ago"
            elif age_s < 86400:
                time_ago = f"{int(age_s / 3600)}h ago"
            else:
                time_ago = f"{int(age_s / 86400)}d ago"
            title = str(latest_chat.get("title", ""))[:16] or "untitled"
            chat_panel = right_panels.get("CHAT")
            if chat_panel and hasattr(chat_panel, "set_resume_info"):
                chat_panel.set_resume_info(title, time_ago)

        home = CompositeScreen(...)  # unchanged
        screen_mgr.replace(home)
```

**Step 3: No new tests for this task** — integration wiring. Verified by manual testing on device.

**Step 4: Commit**

```bash
git add device/main.py device/ui/panel_registry.py
git commit -m "feat: wire greeting fetch on boot + resume info in chat preview"
```

---

### Task 7: Chat settings screen (v1)

**Files:**
- Create: `device/screens/panels/chat_settings.py`
- Modify: `device/main.py` — add `open_chat_settings` opener
- Test: `tests/test_chat_settings.py`

**Step 1: Write the failing test**

Create `tests/test_chat_settings.py`:

```python
"""Tests for ChatSettingsPanel."""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

from screens.panels.chat_settings import ChatSettingsPanel


class ChatSettingsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.font.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_has_meta_prompt_setting(self):
        repo = MagicMock()
        repo.get_setting = MagicMock(return_value=None)
        panel = ChatSettingsPanel(repository=repo, on_back=MagicMock())
        labels = [s["label"] for s in panel._settings]
        self.assertIn("META PROMPT", labels)

    def test_has_text_speed_setting(self):
        repo = MagicMock()
        repo.get_setting = MagicMock(return_value=None)
        panel = ChatSettingsPanel(repository=repo, on_back=MagicMock())
        labels = [s["label"] for s in panel._settings]
        self.assertIn("TEXT SPEED", labels)

    def test_short_press_cycles_settings(self):
        repo = MagicMock()
        repo.get_setting = MagicMock(return_value=None)
        panel = ChatSettingsPanel(repository=repo, on_back=MagicMock())
        panel.handle_action("SHORT_PRESS")
        self.assertEqual(panel._selected, 1)

    def test_long_press_calls_on_back(self):
        called = []
        repo = MagicMock()
        repo.get_setting = MagicMock(return_value=None)
        panel = ChatSettingsPanel(repository=repo, on_back=lambda: called.append(True))
        panel.handle_action("LONG_PRESS")
        self.assertTrue(called)


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_chat_settings.py -v`
Expected: FAIL — module doesn't exist.

**Step 3: Write minimal implementation**

Create `device/screens/panels/chat_settings.py`:

```python
"""ChatSettingsPanel — voice-configurable chat settings."""

from __future__ import annotations

import pygame

from screens.base import BaseScreen
from display.tokens import BLACK, WHITE, DIM1, DIM2, DIM3, HAIRLINE, PHYSICAL_W, PHYSICAL_H, SAFE_INSET, STATUS_BAR_H
from display.theme import load_ui_font, merge_runtime_ui_settings, ui_line_height


class ChatSettingsPanel(BaseScreen):
    """Full-screen chat settings with voice-driven editing."""

    _owns_status_bar = True

    def __init__(self, repository, on_back, ui_settings=None):
        self._repository = repository
        self._on_back = on_back
        self._ui_settings = merge_runtime_ui_settings(ui_settings)
        self._font = load_ui_font("body", self._ui_settings)
        self._font_small = load_ui_font("small", self._ui_settings)
        self._line_height = ui_line_height(self._font, self._ui_settings)
        self._selected = 0

        # Load current values
        meta = self._repository.get_setting("meta_prompt", "default assistant")
        text_speed = self._repository.get_setting("text_speed", "normal")
        voice_speed = self._repository.get_setting("voice_speed", "normal")

        self._settings = [
            {"label": "META PROMPT", "key": "meta_prompt", "value": str(meta)},
            {"label": "TEXT SPEED", "key": "text_speed", "value": str(text_speed)},
            {"label": "VOICE SPEED", "key": "voice_speed", "value": str(voice_speed)},
        ]

    def handle_action(self, action: str):
        if action == "SHORT_PRESS":
            self._selected = (self._selected + 1) % len(self._settings)
        elif action == "TRIPLE_PRESS":
            self._selected = (self._selected - 1) % len(self._settings)
        elif action == "LONG_PRESS":
            if self._on_back:
                self._on_back()

    def render(self, surface: pygame.Surface):
        surface.fill(BLACK)

        # Status bar
        header = self._font_small.render("CHAT SETTINGS", False, WHITE)
        surface.blit(header, (SAFE_INSET, SAFE_INSET + (STATUS_BAR_H - header.get_height()) // 2))
        pygame.draw.line(surface, HAIRLINE, (0, SAFE_INSET + STATUS_BAR_H - 1), (PHYSICAL_W, SAFE_INSET + STATUS_BAR_H - 1))

        # Settings list
        y = SAFE_INSET + STATUS_BAR_H + 8
        for idx, setting in enumerate(self._settings):
            selected = idx == self._selected
            label_color = WHITE if selected else DIM3
            value_color = DIM2

            prefix = "> " if selected else "  "
            label_surf = self._font.render(prefix + setting["label"], False, label_color)
            surface.blit(label_surf, (SAFE_INSET, y))
            y += self._line_height

            # Truncated value
            val_text = setting["value"]
            if len(val_text) > 28:
                val_text = val_text[:25] + "..."
            val_surf = self._font_small.render(f'  "{val_text}"', False, value_color)
            surface.blit(val_surf, (SAFE_INSET, y))
            y += self._line_height + 4

        # Hint bar
        hint_y = PHYSICAL_H - SAFE_INSET - 20
        pygame.draw.line(surface, HAIRLINE, (0, hint_y), (PHYSICAL_W, hint_y))
        hint = self._font_small.render("tap: select · hold: speak to edit", False, DIM1)
        surface.blit(hint, ((PHYSICAL_W - hint.get_width()) // 2, hint_y + 4))

    def update(self, dt: float):
        pass
```

**Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_chat_settings.py -v`
Expected: All pass

**Step 5: Wire into main.py**

In `device/main.py`, add:

```python
from screens.panels.chat_settings import ChatSettingsPanel

def open_chat_settings():
    screen_mgr.push(
        ChatSettingsPanel(
            repository=repository,
            on_back=lambda: screen_mgr.pop(),
            ui_settings=ui_settings,
        )
    )
```

And in the panel_registry chat_action handler, add:

```python
if action_key == "settings":
    opener = openers.get("CHAT_SETTINGS")
    if opener is not None:
        opener()
    return
```

Add `"CHAT_SETTINGS": open_chat_settings` to `panel_openers` in `on_home()`.

**Step 6: Commit**

```bash
git add device/screens/panels/chat_settings.py tests/test_chat_settings.py device/main.py device/ui/panel_registry.py
git commit -m "feat: chat settings screen (v1) — meta prompt, text speed, voice speed"
```

---

## Summary

| Task | What | Files |
|------|------|-------|
| 1 | Slow typewriter preset | typewriter.py |
| 2 | Greeting session DB + methods | repository.py |
| 3 | No-highlight state for preview panels | base.py, composite_screen.py |
| 4 | ChatPreviewPanel redesign | chat_preview.py |
| 5 | Remove LONG_PRESS from chat, add BACK in actions | chat.py |
| 6 | Wire greeting fetch + resume info | main.py, panel_registry.py |
| 7 | Chat settings screen | chat_settings.py, main.py |

Tasks 1-5 are independent and can be parallelized. Task 6 depends on 2 + 4. Task 7 depends on 6.
