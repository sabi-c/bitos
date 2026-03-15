"""BITOS App Registry."""

from __future__ import annotations

APP_REGISTRY: list = []


def register_app(cls):
    """Class decorator: register a Screen as a launchable app."""
    APP_REGISTRY.append(cls)
    return cls
