"""Tests for the lightweight markdown parser."""
import pygame
from device.display.markdown import (
    parse_line, strip_markdown, wrap_markdown_text, Segment,
    STYLE_NORMAL, STYLE_BOLD, STYLE_ITALIC, STYLE_CODE,
    STYLE_HEADER, STYLE_BULLET,
)


class TestParseLine:
    def test_plain_text(self):
        segs = parse_line("hello world")
        assert len(segs) == 1
        assert segs[0].text == "hello world"
        assert segs[0].style == STYLE_NORMAL

    def test_bold(self):
        segs = parse_line("this is **bold** text")
        assert len(segs) == 3
        assert segs[0] == Segment("this is ", STYLE_NORMAL)
        assert segs[1] == Segment("bold", STYLE_BOLD)
        assert segs[2] == Segment(" text", STYLE_NORMAL)

    def test_italic(self):
        segs = parse_line("this is *italic* text")
        assert len(segs) == 3
        assert segs[1] == Segment("italic", STYLE_ITALIC)

    def test_code(self):
        segs = parse_line("run `pip install` now")
        assert len(segs) == 3
        assert segs[1] == Segment("pip install", STYLE_CODE)

    def test_header_h1(self):
        segs = parse_line("# Big Header")
        assert len(segs) == 1
        assert segs[0] == Segment("Big Header", STYLE_HEADER)

    def test_header_h2(self):
        segs = parse_line("## Sub Header")
        assert segs[0] == Segment("Sub Header", STYLE_HEADER)

    def test_header_h3(self):
        segs = parse_line("### Sub Sub")
        assert segs[0] == Segment("Sub Sub", STYLE_HEADER)

    def test_bullet_dash(self):
        segs = parse_line("- item one")
        assert segs[0] == Segment("\u2022 ", STYLE_BULLET)
        assert segs[1] == Segment("item one", STYLE_NORMAL)

    def test_bullet_star(self):
        segs = parse_line("* item two")
        assert segs[0] == Segment("\u2022 ", STYLE_BULLET)
        assert segs[1] == Segment("item two", STYLE_NORMAL)

    def test_numbered_list(self):
        segs = parse_line("1. first item")
        assert segs[0] == Segment("1. ", STYLE_BULLET)
        assert segs[1] == Segment("first item", STYLE_NORMAL)

    def test_mixed_inline(self):
        segs = parse_line("**bold** and *italic*")
        assert segs[0] == Segment("bold", STYLE_BOLD)
        assert segs[1] == Segment(" and ", STYLE_NORMAL)
        assert segs[2] == Segment("italic", STYLE_ITALIC)

    def test_empty_line(self):
        segs = parse_line("")
        assert len(segs) == 1
        assert segs[0].text == ""

    def test_bullet_with_bold(self):
        segs = parse_line("- **important** task")
        assert segs[0] == Segment("\u2022 ", STYLE_BULLET)
        assert segs[1] == Segment("important", STYLE_BOLD)
        assert segs[2] == Segment(" task", STYLE_NORMAL)


class TestStripMarkdown:
    def test_strip_bold(self):
        assert strip_markdown("**bold**") == "bold"

    def test_strip_italic(self):
        assert strip_markdown("*italic*") == "italic"

    def test_strip_code(self):
        assert strip_markdown("`code`") == "code"

    def test_strip_header(self):
        assert strip_markdown("# Header") == "Header"

    def test_strip_bullet(self):
        assert strip_markdown("- item") == "\u2022 item"

    def test_strip_mixed(self):
        assert strip_markdown("**bold** and *italic*") == "bold and italic"

    def test_plain_unchanged(self):
        assert strip_markdown("hello world") == "hello world"


class TestWrapMarkdownText:
    """Tests for markdown-aware word wrapping."""

    @classmethod
    def setup_class(cls):
        pygame.init()
        cls.font = pygame.font.Font(None, 16)

    @classmethod
    def teardown_class(cls):
        pygame.quit()

    def test_short_text_no_wrap(self):
        lines = wrap_markdown_text("hello", self.font, 300)
        assert lines == ["hello"]

    def test_preserves_bold_markers(self):
        lines = wrap_markdown_text("**bold**", self.font, 300)
        assert lines == ["**bold**"]
        # parse_line should still detect the bold
        segs = parse_line(lines[0])
        assert segs[0].style == STYLE_BOLD

    def test_empty_line_paragraph_break(self):
        lines = wrap_markdown_text("hello\n\nworld", self.font, 300)
        assert "" in lines  # paragraph break preserved

    def test_bullet_preserved(self):
        lines = wrap_markdown_text("- item one", self.font, 300)
        assert lines[0] == "- item one"
        segs = parse_line(lines[0])
        assert segs[0].style == STYLE_BULLET

    def test_wrap_excludes_marker_width(self):
        """Markdown markers should not count toward visible width."""
        # Create text with bold markers that fits without markers but not with
        plain = "a " * 20  # roughly 40 chars
        bold_text = "**" + plain.strip() + "**"
        # Wrap at a width that fits the plain text
        plain_w = self.font.size(plain.strip())[0]
        lines_md = wrap_markdown_text(bold_text, self.font, plain_w + 10)
        lines_plain = wrap_markdown_text(plain.strip(), self.font, plain_w + 10)
        # Both should produce the same number of lines (markers don't add width)
        assert len(lines_md) == len(lines_plain)

    def test_numbered_list(self):
        lines = wrap_markdown_text("1. first item", self.font, 300)
        assert lines[0] == "1. first item"

    def test_multiline_with_markdown(self):
        text = "**Title**\n- item one\n- item two"
        lines = wrap_markdown_text(text, self.font, 300)
        assert "**Title**" in lines
        assert "- item one" in lines
        assert "- item two" in lines
