"""Tests for HomePanel live context polling."""
import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

import pygame
import pytest

pygame.init()
pygame.font.init()

from screens.panels.home import HomePanel


def test_home_has_context_polling_state():
    hp = HomePanel()
    assert hasattr(hp, "_context_fetching")
    assert hp._context_fetching is False


def test_home_has_context_elapsed():
    hp = HomePanel()
    assert hasattr(hp, "_context_elapsed")
    assert hp._context_elapsed == 0.0


def test_home_has_context_interval():
    hp = HomePanel()
    assert hasattr(hp, "_context_interval")
    assert hp._context_interval == 60.0


def test_home_poll_context_no_client():
    """Polling with no client should be a no-op."""
    hp = HomePanel(client=None)
    hp._poll_context()
    assert hp._context_fetching is False


def test_home_update_increments_context_elapsed():
    hp = HomePanel()
    hp.update(1.0)
    assert hp._context_elapsed == 1.0
