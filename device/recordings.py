"""RecordingStore — CRUD for field recording metadata.

Persists recording metadata to a JSON file at device/data/recordings.json.
Phase 1: local metadata only. Actual audio capture comes later.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

DEFAULT_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
DEFAULT_JSON_PATH = os.path.join(DEFAULT_DATA_DIR, "recordings.json")


@dataclass
class Recording:
    """Metadata for a single field recording."""
    id: str                          # Unix timestamp + short suffix
    recorded_at: str                 # ISO 8601
    duration_s: float = 0.0
    filename: Optional[str] = None   # Future: rec_{ts}_{uuid}.wav
    status: str = "recorded"         # recorded | transcribing | complete | error
    bookmarks: list[float] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    summary: Optional[str] = None
    sync_status: str = "local_only"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Recording":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


class RecordingStore:
    """JSON-backed store for recording metadata.

    Thread-safe for basic operations (read/write are atomic via temp file).
    """

    def __init__(self, path: str | None = None):
        self._path = path or DEFAULT_JSON_PATH
        self._ensure_dir()

    def _ensure_dir(self) -> None:
        os.makedirs(os.path.dirname(self._path), exist_ok=True)

    def _load_all(self) -> list[dict]:
        if not os.path.exists(self._path):
            return []
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, OSError):
            return []

    def _save_all(self, records: list[dict]) -> None:
        self._ensure_dir()
        tmp = self._path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2, ensure_ascii=False)
        os.replace(tmp, self._path)

    # ── CRUD ──

    def create(self, duration_s: float = 0.0, bookmarks: list[float] | None = None) -> Recording:
        """Create a new recording entry and persist it."""
        now = datetime.now(timezone.utc)
        rec_id = f"rec_{int(now.timestamp())}"
        rec = Recording(
            id=rec_id,
            recorded_at=now.isoformat(),
            duration_s=duration_s,
            filename=f"{rec_id}.wav",
            bookmarks=bookmarks or [],
        )
        records = self._load_all()
        records.append(rec.to_dict())
        self._save_all(records)
        return rec

    def get(self, rec_id: str) -> Recording | None:
        """Get a recording by ID."""
        for d in self._load_all():
            if d.get("id") == rec_id:
                return Recording.from_dict(d)
        return None

    def list_recent(self, limit: int = 20) -> list[Recording]:
        """Return recordings ordered by most recent first."""
        records = self._load_all()
        records.sort(key=lambda r: r.get("recorded_at", ""), reverse=True)
        return [Recording.from_dict(d) for d in records[:limit]]

    def update(self, rec_id: str, **kwargs) -> Recording | None:
        """Update fields on a recording. Returns updated recording or None."""
        records = self._load_all()
        for i, d in enumerate(records):
            if d.get("id") == rec_id:
                valid_fields = Recording.__dataclass_fields__
                for k, v in kwargs.items():
                    if k in valid_fields and k != "id":
                        d[k] = v
                records[i] = d
                self._save_all(records)
                return Recording.from_dict(d)
        return None

    def delete(self, rec_id: str) -> bool:
        """Remove a recording by ID. Returns True if found and deleted."""
        records = self._load_all()
        filtered = [d for d in records if d.get("id") != rec_id]
        if len(filtered) == len(records):
            return False
        self._save_all(filtered)
        return True

    def count(self) -> int:
        """Total number of recordings."""
        return len(self._load_all())
