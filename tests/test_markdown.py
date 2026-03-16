"""Tests for the lightweight markdown parser."""
from device.display.markdown import (
    parse_line, strip_markdown, Segment,
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
