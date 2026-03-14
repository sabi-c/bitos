"""Runtime UI theme helpers (fed by backend settings)."""
from __future__ import annotations

import pygame

from display.tokens import FONT_PATH, FONT_SIZES, PAD_ROW

DEFAULT_RUNTIME_UI_SETTINGS = {
    "font_family": "press_start_2p",
    "font_scale": 1.0,
    "font_size_overrides": {
        "title": FONT_SIZES["title"],
        "body": FONT_SIZES["body"],
        "small": FONT_SIZES["small"],
    },
    "layout_density": "comfy",
    "sidebar_width": 84,
}


def merge_runtime_ui_settings(incoming: dict | None) -> dict:
    merged = {
        "font_family": DEFAULT_RUNTIME_UI_SETTINGS["font_family"],
        "font_scale": DEFAULT_RUNTIME_UI_SETTINGS["font_scale"],
        "font_size_overrides": dict(DEFAULT_RUNTIME_UI_SETTINGS["font_size_overrides"]),
        "layout_density": DEFAULT_RUNTIME_UI_SETTINGS["layout_density"],
        "sidebar_width": DEFAULT_RUNTIME_UI_SETTINGS["sidebar_width"],
    }

    if not isinstance(incoming, dict):
        return merged

    for key in ["font_family", "font_scale", "layout_density", "sidebar_width"]:
        if key in incoming:
            merged[key] = incoming[key]

    if isinstance(incoming.get("font_size_overrides"), dict):
        merged["font_size_overrides"].update(incoming["font_size_overrides"])

    return merged


def ui_font_size(role: str, ui_settings: dict) -> int:
    base = ui_settings.get("font_size_overrides", {}).get(role, FONT_SIZES[role])
    scale = ui_settings.get("font_scale", 1.0)
    return max(5, int(round(base * float(scale))))


def load_ui_font(role: str, ui_settings: dict) -> pygame.font.Font:
    size = ui_font_size(role, ui_settings)
    if ui_settings.get("font_family") == "monospace":
        return pygame.font.SysFont("monospace", size)

    try:
        return pygame.font.Font(FONT_PATH, size)
    except FileNotFoundError:
        return pygame.font.SysFont("monospace", size)


def ui_line_height(font: pygame.font.Font, ui_settings: dict) -> int:
    extra = 2 if ui_settings.get("layout_density") == "compact" else PAD_ROW
    return font.get_height() + extra
