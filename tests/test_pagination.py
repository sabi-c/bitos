"""Tests for shared pagination utilities."""
import os
import sys
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1] / "device"))

from display.pagination import split_into_pages, wrap_text


class SplitIntoPagesTests(unittest.TestCase):
    def test_empty_lines(self):
        pages = split_into_pages([], 9)
        self.assertEqual(pages, [[]])

    def test_single_page(self):
        lines = ["line one", "line two", "line three"]
        pages = split_into_pages(lines, lines_per_page=9)
        self.assertEqual(len(pages), 1)
        self.assertEqual(pages[0], lines)

    def test_multiple_pages(self):
        lines = [f"line {i}" for i in range(20)]
        pages = split_into_pages(lines, lines_per_page=9)
        self.assertEqual(len(pages), 3)
        self.assertEqual(len(pages[0]), 9)
        self.assertEqual(len(pages[1]), 9)
        self.assertEqual(len(pages[2]), 2)

    def test_max_four_pages(self):
        lines = [f"line {i}" for i in range(50)]
        pages = split_into_pages(lines, lines_per_page=9)
        self.assertEqual(len(pages), 4)
        self.assertTrue(pages[3][-1].endswith("..."))

    def test_paragraph_boundary(self):
        lines = [f"line {i}" for i in range(7)] + [""] + [f"para2 line {i}" for i in range(5)]
        pages = split_into_pages(lines, lines_per_page=9)
        self.assertEqual(len(pages), 2)
        self.assertEqual(pages[0][-1], "")

    def test_zero_lines_per_page(self):
        pages = split_into_pages(["a", "b"], lines_per_page=0)
        self.assertEqual(pages, [["a", "b"]])

    def test_custom_max_pages(self):
        lines = [f"line {i}" for i in range(30)]
        pages = split_into_pages(lines, lines_per_page=5, max_pages=2)
        self.assertEqual(len(pages), 2)
        self.assertTrue(pages[1][-1].endswith("..."))


class WrapTextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not pygame.get_init():
            pygame.init()
        if not pygame.font.get_init():
            pygame.font.init()
        cls.font = pygame.font.SysFont(None, 14)

    def test_short_text_single_line(self):
        lines = wrap_text("hello", self.font, 200)
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0], "hello")

    def test_newline_splits(self):
        lines = wrap_text("hello\nworld", self.font, 200)
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0], "hello")
        self.assertEqual(lines[1], "world")

    def test_empty_text(self):
        lines = wrap_text("", self.font, 200)
        self.assertEqual(lines, [""])

    def test_wraps_long_text(self):
        long_text = "a" * 200
        lines = wrap_text(long_text, self.font, 50)
        self.assertGreater(len(lines), 1)
        # All characters should be present
        self.assertEqual("".join(lines), long_text)


if __name__ == "__main__":
    unittest.main()
