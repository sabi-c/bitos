"""Tests for MarkdownViewerPanel."""
import os
import sys
import unittest
from unittest.mock import MagicMock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1] / "device"))
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1] / "server"))
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1] / "server" / "integrations"))

from screens.panels.markdown_viewer import MarkdownViewerPanel


SAMPLE_PAGES = [
    "Welcome to BITOS. This is page one of the document.",
    "Page two covers navigation and basic controls.",
    "Page three has advanced features and settings.",
]


class MarkdownViewerPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not pygame.get_init():
            pygame.init()
        if not pygame.font.get_init():
            pygame.font.init()

    def _make_panel(self, pages=None, content=None, on_back=None):
        file_data = {"name": "test-file", "id": "abc123"}
        if pages is not None:
            file_data["pages"] = pages
        elif content is not None:
            file_data["content"] = content
        else:
            file_data["pages"] = list(SAMPLE_PAGES)
        return MarkdownViewerPanel(
            file_data=file_data,
            on_back=on_back,
        )

    def test_creation_with_pages(self):
        panel = self._make_panel()
        self.assertEqual(len(panel._pages), 3)
        self.assertEqual(panel._current_page, 0)
        self.assertEqual(len(panel._page_revealed), 3)
        self.assertFalse(panel._page_revealed[0])

    @unittest.skipIf(
        os.environ.get("SDL_VIDEODRIVER") == "dummy",
        "font.size() segfaults with dummy SDL driver + custom fonts"
    )
    def test_creation_with_content(self):
        long_content = "This is a test. " * 50
        panel = self._make_panel(content=long_content)
        self.assertGreaterEqual(len(panel._pages), 1)

    def test_short_press_advances_page(self):
        panel = self._make_panel()
        # Mark page 0 typewriter as done
        panel._page_typewriter = None
        panel._page_revealed[0] = True
        panel.handle_action("SHORT_PRESS")
        self.assertEqual(panel._current_page, 1)

    def test_short_press_cycles(self):
        panel = self._make_panel()
        panel._page_revealed = [True, True, True]
        panel._page_typewriter = None
        panel._current_page = 2
        panel.handle_action("SHORT_PRESS")
        self.assertEqual(panel._current_page, 0)

    def test_short_press_marks_current_revealed(self):
        panel = self._make_panel()
        panel._page_revealed = [False, False, False]
        panel._current_page = 0
        panel._page_typewriter = MagicMock()
        panel._page_typewriter.finished = False
        panel.handle_action("SHORT_PRESS")
        self.assertTrue(panel._page_revealed[0])
        self.assertEqual(panel._current_page, 1)

    def test_triple_press_goes_back_page(self):
        panel = self._make_panel()
        panel._page_revealed = [True, True, True]
        panel._page_typewriter = None
        panel._current_page = 1
        panel.handle_action("TRIPLE_PRESS")
        self.assertEqual(panel._current_page, 0)

    def test_long_press_calls_on_back(self):
        called = []
        panel = self._make_panel(on_back=lambda: called.append(True))
        panel.handle_action("LONG_PRESS")
        self.assertTrue(called)

    def test_typewriter_starts_on_first_page(self):
        panel = self._make_panel()
        self.assertIsNotNone(panel._page_typewriter)

    def test_typewriter_skipped_on_revealed_page(self):
        panel = self._make_panel()
        panel._page_revealed[0] = True
        panel._start_page_typewriter()
        self.assertIsNone(panel._page_typewriter)

    def test_renders_without_crash(self):
        panel = self._make_panel()
        surface = pygame.Surface((240, 280))
        panel.render(surface)

    def test_single_page_no_short_advance(self):
        panel = self._make_panel(pages=["Only one page."])
        panel._page_revealed = [True]
        panel._page_typewriter = None
        panel.handle_action("SHORT_PRESS")
        self.assertEqual(panel._current_page, 0)

    def test_single_page_no_triple_back(self):
        panel = self._make_panel(pages=["Only one page."])
        panel._page_revealed = [True]
        panel._page_typewriter = None
        panel.handle_action("TRIPLE_PRESS")
        self.assertEqual(panel._current_page, 0)

    def test_update_ticks_typewriter(self):
        panel = self._make_panel()
        self.assertIsNotNone(panel._page_typewriter)
        self.assertFalse(panel._page_typewriter.finished)
        # Tick enough to finish
        for _ in range(500):
            panel.update(0.1)
        self.assertTrue(panel._page_revealed[0])

    def test_no_content_fallback(self):
        panel = MarkdownViewerPanel(file_data={"name": "empty", "id": "x"})
        self.assertEqual(len(panel._pages), 1)
        self.assertEqual(panel._pages[0], ["(no content)"])


if __name__ == "__main__":
    unittest.main()
