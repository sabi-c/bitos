"""NetworkManager wrapper used by BLE WiFi provisioning characteristic."""
from __future__ import annotations

import logging
import os
import subprocess



NMCLI_TIMEOUT_SECONDS = 8
STATUS_TIMEOUT_SECONDS = 3


class WiFiManager:
    """Wraps nmcli for WiFi operations."""

    def _connection_exists(self, ssid: str) -> bool:
        """Check if a NetworkManager connection profile exists for this SSID."""
        try:
            result = subprocess.run(
                ["nmcli", "-t", "-f", "NAME", "connection", "show"],
                capture_output=True, text=True, timeout=NMCLI_TIMEOUT_SECONDS,
            )
            if result.returncode != 0:
                return False
            return ssid in result.stdout.splitlines()
        except subprocess.TimeoutExpired:
            return False

    def _get_active_ssid(self) -> str:
        """Return the SSID of the currently active WiFi connection, or ''."""
        try:
            result = subprocess.run(
                ["nmcli", "-t", "-f", "ACTIVE,SSID", "dev", "wifi"],
                capture_output=True, text=True, timeout=STATUS_TIMEOUT_SECONDS,
            )
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    parts = line.split(":")
                    if parts and parts[0] == "yes" and len(parts) > 1:
                        return parts[1]
        except subprocess.TimeoutExpired:
            pass
        return ""

    def add_or_update_network(self, ssid: str, password: str, security: str, priority: int) -> bool:
        if os.environ.get("BITOS_WIFI") == "mock":
            logging.info("wifi_mock_add ssid=%s security=%s priority=%s", ssid, security, priority)
            return True

        exists = self._connection_exists(ssid)

        if exists:
            # Update existing connection profile
            cmd = [
                "nmcli", "connection", "modify", ssid,
                "connection.autoconnect-priority", str(priority),
                "connection.autoconnect", "yes",
            ]
            if security != "OPEN":
                cmd += ["wifi-sec.key-mgmt", "wpa-psk", "wifi-sec.psk", password]
        else:
            # Create new connection profile
            if security == "OPEN":
                cmd = [
                    "nmcli", "connection", "add",
                    "type", "wifi",
                    "ssid", ssid,
                    "connection.autoconnect-priority", str(priority),
                    "connection.autoconnect", "yes",
                ]
            else:
                cmd = [
                    "nmcli", "connection", "add",
                    "type", "wifi",
                    "ssid", ssid,
                    "wifi-sec.key-mgmt", "wpa-psk",
                    "wifi-sec.psk", password,
                    "connection.autoconnect-priority", str(priority),
                    "connection.autoconnect", "yes",
                ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=NMCLI_TIMEOUT_SECONDS)
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

    def list_networks(self) -> list[dict]:
        """Return saved WiFi connection profiles as a list of dicts."""
        if os.environ.get("BITOS_WIFI") == "mock":
            return [
                {"ssid": "MOCK_NET", "priority": 100, "autoconnect": True, "active": True},
                {"ssid": "MOCK_NET_2", "priority": 50, "autoconnect": True, "active": False},
            ]

        active_ssid = self._get_active_ssid()

        try:
            result = subprocess.run(
                ["nmcli", "-t", "-f", "NAME,TYPE,AUTOCONNECT,AUTOCONNECT-PRIORITY", "connection", "show"],
                capture_output=True, text=True, timeout=NMCLI_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            logging.warning("wifi_list_timeout")
            return []

        if result.returncode != 0:
            logging.warning("wifi_list_failed stderr=%s", result.stderr.strip())
            return []

        networks = []
        for line in result.stdout.splitlines():
            parts = line.split(":")
            if len(parts) < 4:
                continue
            name, conn_type, autoconnect, priority = parts[0], parts[1], parts[2], parts[3]
            # Filter to wifi connections only
            if "wireless" not in conn_type and "wifi" not in conn_type and "802-11" not in conn_type:
                continue
            networks.append({
                "ssid": name,
                "priority": int(priority) if priority.lstrip("-").isdigit() else 0,
                "autoconnect": autoconnect.lower() == "yes",
                "active": name == active_ssid,
            })

        return networks

    def remove_network(self, ssid: str) -> bool:
        """Remove a saved WiFi connection profile. Returns False if it's currently active."""
        if os.environ.get("BITOS_WIFI") == "mock":
            logging.info("wifi_mock_remove ssid=%s", ssid)
            return True

        # Don't allow removing the active connection
        active_ssid = self._get_active_ssid()
        if ssid == active_ssid:
            logging.warning("wifi_remove_blocked ssid=%s reason=currently_active", ssid)
            return False

        try:
            result = subprocess.run(
                ["nmcli", "connection", "delete", ssid],
                capture_output=True, text=True, timeout=NMCLI_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            logging.warning("wifi_remove_timeout ssid=%s", ssid)
            return False

        if result.returncode != 0:
            logging.warning("wifi_remove_failed ssid=%s stderr=%s", ssid, result.stderr.strip())
            return False

        logging.info("wifi_removed ssid=%s", ssid)
        return True

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
