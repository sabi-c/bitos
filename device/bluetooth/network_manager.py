"""NetworkManager priority helpers for WiFi/BT PAN connectivity."""
from __future__ import annotations

import logging
import os
import subprocess

logger = logging.getLogger(__name__)


class NetworkPriorityManager:
    """
    # WHY THIS EXISTS: wraps nmcli for WiFi priority management.
    # All Pi-specific nmcli calls mock-safe via BITOS_WIFI=mock.

    Priority order:
      100 — home/known networks (added via companion app)
       50 — phone hotspot (stored at setup)
       25 — BT PAN (added when phone tethers)
       10 — guest/open networks
    """

    def set_priority(self, ssid: str, priority: int) -> bool:
        if os.environ.get("BITOS_WIFI") == "mock":
            logger.info("wifi_priority_mock", extra={"ssid": ssid, "p": priority})
            return True
        result = subprocess.run(
            [
                "nmcli",
                "connection",
                "modify",
                ssid,
                "connection.autoconnect-priority",
                str(priority),
                "connection.autoconnect",
                "yes",
            ],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0

    def get_active_connection(self) -> dict | None:
        """Returns {ssid, type, signal} or None. Mock: returns None."""
        if os.environ.get("BITOS_WIFI") == "mock":
            return None
        result = subprocess.run(
            ["nmcli", "-t", "-f", "TYPE,NAME,SIGNAL", "connection", "show", "--active"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return None
        for line in result.stdout.splitlines():
            parts = line.split(":")
            if len(parts) < 2:
                continue
            conn_type = parts[0].strip()
            ssid = parts[1].strip()
            signal = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
            normalized = "bt-pan" if conn_type in {"bluetooth", "bt"} else conn_type
            return {"ssid": ssid, "type": normalized, "signal": signal}
        return None

    def get_connectivity_symbol(self) -> str:
        """Returns one of: ▣ (wifi) ◈ (bt-pan) ▦ (hotspot) ✕ (none)."""
        conn = self.get_active_connection()
        if conn is None:
            return "✕"
        if conn.get("type") == "bt-pan":
            return "◈"
        if "hotspot" in conn.get("ssid", "").lower():
            return "▦"
        return "▣"

    def setup_bt_pan_profile(self) -> bool:
        """Register BT PAN NetworkManager profile. Mock: logs + True."""
        if os.environ.get("BITOS_WIFI") == "mock":
            logger.info("bt_pan_profile_mock")
            return True
        result = subprocess.run(
            [
                "nmcli",
                "connection",
                "add",
                "type",
                "bluetooth",
                "ifname",
                "*",
                "con-name",
                "bitos-bt-pan",
                "autoconnect",
                "yes",
                "connection.autoconnect-priority",
                "25",
            ],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0
