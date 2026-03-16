"""Tests for SAFE_INSET constant and unified CORNER_RADIUS."""

from display.tokens import SAFE_INSET, CORNER_RADIUS as TOKENS_CORNER_RADIUS
from display.corner_mask import CORNER_RADIUS as MASK_CORNER_RADIUS


def test_safe_inset_exists_in_tokens():
    assert SAFE_INSET == 16


def test_corner_radius_matches_safe_inset():
    assert TOKENS_CORNER_RADIUS == SAFE_INSET


def test_corner_mask_uses_tokens_radius():
    assert MASK_CORNER_RADIUS == TOKENS_CORNER_RADIUS
