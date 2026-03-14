"""NetworkManager wrapper used by BLE WiFi provisioning characteristic."""
from __future__ import annotations

import logging
import os
import subprocess

from bluetooth.network_manager import NetworkPriorityManager


NMCLI_TIMEOUT_SECONDS = 8
STATUS_TIMEOUT_SECONDS = 3


class WiFiManager:
    """Wraps nmcli for WiFi operations."""

    def add_or_update_network(self, ssid: str, password: str, security: str, priority: int) -> bool:
        if os.environ.get("BITOS_WIFI") == "mock":
            logging.info("wifi_mock_add ssid=%s security=%s priority=%s", ssid, security, priority)
            return True

        if security == "OPEN":
            cmd = [
                "nmcli",
                "connection",
                "add",
                "type",
                "wifi",
                "ssid",
                ssid,
                "connection.autoconnect-priority",
                str(priority),
                "connection.autoconnect",
                "yes",
            ]
        else:
            key_mgmt = "wpa-psk"
            cmd = [
                "nmcli",
                "connection",
                "add",
                "type",
                "wifi",
                "ssid",
                ssid,
                "wifi-sec.key-mgmt",
                key_mgmt,
                "wifi-sec.psk",
                password,
                "connection.autoconnect-priority",
                str(priority),
                "connection.autoconnect",
                "yes",
            ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        except subprocess.TimeoutExpired:
            logging.warning("wifi_add_timeout ssid=%s", ssid)
            return False

        if result.returncode != 0:
            logging.warning("wifi_add_failed stderr=%s", result.stderr.strip())
            return False

        try:
            up = subprocess.run(["nmcli", "connection", "up", ssid], capture_output=True, text=True, timeout=15)
        except subprocess.TimeoutExpired:
            logging.warning("wifi_up_timeout ssid=%s", ssid)
            return False

        return up.returncode == 0
        up = subprocess.run(["nmcli", "connection", "up", ssid], capture_output=True, text=True)
        ok = up.returncode == 0
        if ok:
            priority_manager = NetworkPriorityManager()
            priority_manager.set_priority(ssid, priority)
        return ok

    def get_status(self) -> dict:
        if os.environ.get("BITOS_WIFI") == "mock":
            return {
                "connected": True,
                "ssid": "MOCK_NET",
                "signal": "excellent",
                "ip": "192.168.0.10",
                "last_error": None,
            }

        try:
            active = subprocess.run(
                ["nmcli", "-t", "-f", "ACTIVE,SSID,SIGNAL", "dev", "wifi"],
                capture_output=True,
                text=True,
                timeout=5,
            )
        except subprocess.TimeoutExpired:
            logging.warning("wifi_status_timeout")
            return {"connected": False, "ssid": "", "signal": "weak", "ip": "", "last_error": None}

        ssid = ""
        signal = "weak"
        if active.returncode == 0:
            for line in active.stdout.splitlines():
                parts = line.split(":")
                if parts and parts[0] == "yes":
                    ssid = parts[1] if len(parts) > 1 else ""
                    sig = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
                    signal = "excellent" if sig >= 80 else "good" if sig >= 60 else "ok" if sig >= 40 else "weak"
                    break

        try:
            ip_cmd = subprocess.run(["hostname", "-I"], capture_output=True, text=True, timeout=3)
        except subprocess.TimeoutExpired:
            logging.warning("wifi_ip_timeout")
            return {"connected": bool(ssid), "ssid": ssid, "signal": signal, "ip": "", "last_error": "timeout"}

        ip = ip_cmd.stdout.strip().split()[0] if ip_cmd.returncode == 0 and ip_cmd.stdout.strip() else ""
        return {"connected": bool(ssid), "ssid": ssid, "signal": signal, "ip": ip, "last_error": None}
