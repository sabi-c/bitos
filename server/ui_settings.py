"""UI settings catalog + persistence for backend-driven theming/layout controls."""
from __future__ import annotations

import json
import threading
from copy import deepcopy
from pathlib import Path
from typing import Any

DEFAULT_UI_SETTINGS: dict[str, Any] = {
    "font_family": "press_start_2p",
    "font_scale": 1.0,
    "font_size_overrides": {
        "title": 10,
        "body": 8,
        "small": 6,
    },
    "layout_density": "comfy",
    "sidebar_width": 84,
}

UI_SETTINGS_CATALOG: dict[str, Any] = {
    "font_family": {
        "type": "enum",
        "values": ["press_start_2p", "monospace"],
    },
    "font_scale": {
        "type": "float",
        "min": 0.75,
        "max": 2.0,
        "step": 0.05,
    },
    "font_size_overrides": {
        "type": "object",
        "keys": {
            "title": {"type": "int", "min": 8, "max": 22},
            "body": {"type": "int", "min": 6, "max": 18},
            "small": {"type": "int", "min": 5, "max": 14},
        },
    },
    "layout_density": {
        "type": "enum",
        "values": ["compact", "comfy"],
    },
    "sidebar_width": {
        "type": "int",
        "min": 72,
        "max": 110,
    },
}


class UISettingsValidationError(ValueError):
    """Raised when incoming settings are invalid."""


class UISettingsStore:
    """JSON-backed UI settings store with runtime validation."""

    def __init__(self, file_path: str):
        self._path = Path(file_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        if not self._path.exists():
            self._write(DEFAULT_UI_SETTINGS)

    def catalog(self) -> dict[str, Any]:
        return deepcopy(UI_SETTINGS_CATALOG)

    def get(self) -> dict[str, Any]:
        with self._lock:
            data = self._read()
        return self._merge_defaults(data)

    def update(self, patch: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            current = self._merge_defaults(self._read())
            candidate = self._merge_defaults(current | patch)
            self._validate(candidate)
            self._write(candidate)
            return candidate

    def _read(self) -> dict[str, Any]:
        try:
            return json.loads(self._path.read_text())
        except Exception:
            return deepcopy(DEFAULT_UI_SETTINGS)

    def _write(self, data: dict[str, Any]):
        self._path.write_text(json.dumps(data, indent=2, sort_keys=True))

    def _merge_defaults(self, incoming: dict[str, Any]) -> dict[str, Any]:
        merged = deepcopy(DEFAULT_UI_SETTINGS)
        merged.update({k: v for k, v in incoming.items() if k != "font_size_overrides"})
        if isinstance(incoming.get("font_size_overrides"), dict):
            merged["font_size_overrides"].update(incoming["font_size_overrides"])
        return merged

    def _validate(self, data: dict[str, Any]):
        unknown = [k for k in data.keys() if k not in UI_SETTINGS_CATALOG]
        if unknown:
            raise UISettingsValidationError(f"Unknown settings keys: {unknown}")

        if data["font_family"] not in UI_SETTINGS_CATALOG["font_family"]["values"]:
            raise UISettingsValidationError("font_family must be one of catalog values")

        scale = data["font_scale"]
        spec = UI_SETTINGS_CATALOG["font_scale"]
        if not isinstance(scale, (float, int)) or not (spec["min"] <= float(scale) <= spec["max"]):
            raise UISettingsValidationError("font_scale out of range")

        density = data["layout_density"]
        if density not in UI_SETTINGS_CATALOG["layout_density"]["values"]:
            raise UISettingsValidationError("layout_density must be compact/comfy")

        sidebar_width = data["sidebar_width"]
        sidebar_spec = UI_SETTINGS_CATALOG["sidebar_width"]
        if not isinstance(sidebar_width, int) or not (sidebar_spec["min"] <= sidebar_width <= sidebar_spec["max"]):
            raise UISettingsValidationError("sidebar_width out of range")

        overrides = data.get("font_size_overrides", {})
        if not isinstance(overrides, dict):
            raise UISettingsValidationError("font_size_overrides must be an object")

        for key, key_spec in UI_SETTINGS_CATALOG["font_size_overrides"]["keys"].items():
            value = overrides.get(key)
            if not isinstance(value, int) or not (key_spec["min"] <= value <= key_spec["max"]):
                raise UISettingsValidationError(f"font_size_overrides.{key} out of range")
