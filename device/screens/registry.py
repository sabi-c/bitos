"""Simple screen registry for app-style screens."""

from __future__ import annotations

REGISTRY: dict[str, type] = {}


def register_app(cls):
    REGISTRY[cls.__name__] = cls
    return cls
