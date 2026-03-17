from __future__ import annotations
import hashlib, time, uuid
from dataclasses import dataclass, field
from enum import IntEnum


class Priority(IntEnum):
    CRITICAL = 1  # P1: full banner, wake, chime
    HIGH = 2      # P2: banner, wake if sleeping
    NORMAL = 3    # P3: toast strip
    LOW = 4       # P4: badge only
    SILENT = 5    # P5: queue only


CATEGORY_DEFAULTS = {
    "sms": Priority.HIGH, "mail": Priority.NORMAL, "calendar": Priority.HIGH,
    "task": Priority.HIGH, "agent": Priority.HIGH, "reminder": Priority.CRITICAL,
    "tool": Priority.NORMAL, "system": Priority.LOW,
}

CATEGORY_COLORS = {
    "sms": (60, 130, 220), "mail": (180, 140, 60), "calendar": (80, 180, 120),
    "task": (160, 100, 220), "agent": (100, 200, 200), "reminder": (220, 80, 80),
    "tool": (100, 200, 200), "system": (120, 120, 120),
}


@dataclass
class NotificationEvent:
    type: str
    priority: Priority
    category: str
    payload: dict
    id: str = field(default_factory=lambda: f"evt_{uuid.uuid4().hex[:12]}")
    timestamp: float = field(default_factory=time.time)

    @property
    def dedup_key(self) -> str:
        source_id = self.payload.get("source_id", "")
        body = self.payload.get("body", "")
        body_hash = hashlib.md5(body.encode()).hexdigest()[:8]
        return f"{self.category}:{source_id}:{body_hash}"

    def to_dict(self) -> dict:
        return {"type": self.type, "id": self.id, "priority": int(self.priority),
                "category": self.category, "payload": self.payload, "timestamp": self.timestamp}
