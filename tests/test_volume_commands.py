"""Tests for inline command parsing (volume control)."""
import re

# Test the regex and parsing directly
CMD_RE = re.compile(r'\{\{(\w+):(\w+)\}\}')


class TestVolumeCommandParsing:
    def test_volume_command_found(self):
        text = "Sure, I've turned up the volume. {{volume:80}}"
        matches = list(CMD_RE.finditer(text))
        assert len(matches) == 1
        assert matches[0].group(1) == "volume"
        assert matches[0].group(2) == "80"

    def test_volume_command_stripped(self):
        text = "Volume raised. {{volume:80}} Enjoy!"
        result = CMD_RE.sub("", text).strip()
        assert "{{" not in result
        assert "volume" not in result.lower() or "Volume" in result

    def test_no_commands(self):
        text = "This is a normal response with no commands."
        matches = list(CMD_RE.finditer(text))
        assert len(matches) == 0

    def test_multiple_commands(self):
        text = "{{volume:50}} Here you go {{volume:75}}"
        matches = list(CMD_RE.finditer(text))
        assert len(matches) == 2

    def test_command_at_start(self):
        text = "{{volume:100}}Done!"
        result = CMD_RE.sub("", text).strip()
        assert result == "Done!"

    def test_command_value_zero(self):
        text = "Muted. {{volume:0}}"
        matches = list(CMD_RE.finditer(text))
        assert matches[0].group(2) == "0"
