import threading


class StatusState:
    """# WHY THIS EXISTS: shared state between poller thread and render."""

    def __init__(self):
        self._lock = threading.Lock()
        self.wifi_symbol = "▣"
        self.battery_pct = 84
        self.battery_text = "🔋84%"
        self.charging = False
        self.ai_online = True
        self.imessage_status = "unknown"
        self.imessage_unread = 0

    def update(self, **kwargs):
        with self._lock:
            for k, v in kwargs.items():
                setattr(self, k, v)

    def bar_left(self) -> str:
        with self._lock:
            if not self.ai_online and self.wifi_symbol != "✕":
                return "⊘ AI"
            return self.wifi_symbol

    def bar_right(self) -> str:
        with self._lock:
            if self.battery_text:
                return self.battery_text
            if self.battery_pct is None:
                return "--%"
            if self.battery_pct < 10:
                return f"⚡{self.battery_pct}%"
            arrow = "↑" if self.charging else ""
            return f"{self.battery_pct}%{arrow}"
