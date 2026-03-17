"""Bluetooth A2DP audio device management for BITOS.

Handles scanning, pairing, connecting Bluetooth audio devices (headphones,
speakers, AirPods) and routing audio output via PulseAudio sink switching.

Uses bluetoothctl subprocess calls for device management and pactl for
audio sink routing.  Falls back gracefully when not running on real hardware.
"""
from __future__ import annotations

import logging
import re
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# A2DP sink UUID — used to filter audio-capable devices during scan
_A2DP_SINK_UUID = "0000110b-0000-1000-8000-00805f9b34fb"

# How long to wait for bluetoothctl operations (seconds)
_CMD_TIMEOUT = 15
_SCAN_POLL_INTERVAL = 1.0


@dataclass
class BTAudioDevice:
    """Discovered or paired Bluetooth audio device."""
    name: str
    address: str
    paired: bool = False
    connected: bool = False
    device_type: str = "audio"  # audio, headphones, speaker, unknown

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "address": self.address,
            "paired": self.paired,
            "connected": self.connected,
            "type": self.device_type,
        }


class BluetoothAudioManager:
    """Manage Bluetooth audio devices and PulseAudio sink routing.

    Public API:
        scan(timeout) -> list[dict]         — discover nearby A2DP devices
        pair(address) -> bool               — pair with a device
        connect(address) -> bool            — connect to paired device
        disconnect(address) -> bool         — disconnect active device
        get_paired_devices() -> list[dict]  — list all paired audio devices
        get_connected_device() -> dict|None — currently connected audio device
        set_auto_connect(address, enabled)  — enable/disable auto-reconnect
        is_audio_routed_to_bt() -> bool     — True if BT is the active sink
        auto_reconnect_last()               — reconnect to last device on boot
    """

    def __init__(self, repository=None):
        self._repo = repository
        self._scanning = False
        self._scan_results: list[BTAudioDevice] = []
        self._scan_thread: threading.Thread | None = None
        self._connected_device: BTAudioDevice | None = None
        self._lock = threading.Lock()

        # Check if bluetoothctl is available
        self._bt_available = self._check_bluetoothctl()
        if not self._bt_available:
            logger.warning("[BT-AUDIO] bluetoothctl not available — Bluetooth audio disabled")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def scan(self, timeout: int = 10) -> list[dict]:
        """Scan for nearby Bluetooth audio devices.

        Returns list of dicts: [{name, address, type}, ...]
        Blocks for up to `timeout` seconds while scanning.
        """
        if not self._bt_available:
            logger.warning("[BT-AUDIO] scan: bluetoothctl not available")
            return []

        if self._scanning:
            logger.info("[BT-AUDIO] scan already in progress")
            return [d.to_dict() for d in self._scan_results]

        self._scanning = True
        self._scan_results = []

        try:
            # Power on adapter and set agent
            self._run_bluetoothctl(["power", "on"])
            self._run_bluetoothctl(["agent", "NoInputNoOutput"])
            self._run_bluetoothctl(["default-agent"])

            # Start scanning
            self._run_bluetoothctl(["scan", "on"], timeout=2, ignore_errors=True)

            # Poll for devices over the scan window
            deadline = time.monotonic() + timeout
            seen_addresses: set[str] = set()

            while time.monotonic() < deadline:
                time.sleep(_SCAN_POLL_INTERVAL)
                devices = self._parse_devices()
                for dev in devices:
                    if dev.address not in seen_addresses:
                        seen_addresses.add(dev.address)
                        self._scan_results.append(dev)
                        logger.info("[BT-AUDIO] found: %s (%s)", dev.name, dev.address)

            # Stop scanning
            self._run_bluetoothctl(["scan", "off"], timeout=3, ignore_errors=True)

        except Exception as exc:
            logger.error("[BT-AUDIO] scan error: %s", exc)
        finally:
            self._scanning = False

        results = [d.to_dict() for d in self._scan_results]
        logger.info("[BT-AUDIO] scan complete: %d devices found", len(results))
        return results

    def scan_async(self, timeout: int = 10, on_complete=None) -> None:
        """Start a non-blocking scan in a background thread.

        Call `get_scan_results()` to check progress, or pass `on_complete`
        callback which receives the results list.
        """
        def _scan_worker():
            results = self.scan(timeout=timeout)
            if on_complete:
                try:
                    on_complete(results)
                except Exception as exc:
                    logger.error("[BT-AUDIO] scan callback error: %s", exc)

        self._scan_thread = threading.Thread(
            target=_scan_worker, name="bt-audio-scan", daemon=True,
        )
        self._scan_thread.start()

    @property
    def is_scanning(self) -> bool:
        return self._scanning

    def get_scan_results(self) -> list[dict]:
        """Return current scan results (may be partial if scan is in progress)."""
        return [d.to_dict() for d in self._scan_results]

    def pair(self, address: str) -> bool:
        """Pair with a Bluetooth device by address.

        Returns True on success.
        """
        if not self._bt_available:
            return False

        logger.info("[BT-AUDIO] pairing with %s", address)
        try:
            # Trust the device first (required for auto-reconnect)
            self._run_bluetoothctl(["trust", address])
            time.sleep(0.5)

            # Pair
            result = self._run_bluetoothctl(["pair", address], timeout=_CMD_TIMEOUT)
            if result is None:
                logger.error("[BT-AUDIO] pair command failed for %s", address)
                return False

            # Check if pairing succeeded
            info = self._get_device_info(address)
            if info and info.get("Paired") == "yes":
                logger.info("[BT-AUDIO] paired successfully with %s", address)
                self._save_last_device(address)
                return True

            logger.warning("[BT-AUDIO] pairing may have failed for %s", address)
            return False

        except Exception as exc:
            logger.error("[BT-AUDIO] pair error: %s", exc)
            return False

    def connect(self, address: str) -> bool:
        """Connect to a paired Bluetooth audio device.

        Also switches PulseAudio output to the BT device.
        Returns True on success.
        """
        if not self._bt_available:
            return False

        logger.info("[BT-AUDIO] connecting to %s", address)
        try:
            result = self._run_bluetoothctl(["connect", address], timeout=_CMD_TIMEOUT)
            if result is None:
                logger.error("[BT-AUDIO] connect command failed for %s", address)
                return False

            # Wait for the audio sink to appear
            time.sleep(2.0)

            # Get device name for display
            info = self._get_device_info(address)
            name = "Unknown"
            if info:
                name = info.get("Name", info.get("Alias", "Unknown"))

            with self._lock:
                self._connected_device = BTAudioDevice(
                    name=name,
                    address=address,
                    paired=True,
                    connected=True,
                )

            # Route audio to BT device
            self._switch_audio_to_bt()
            self._save_last_device(address)

            logger.info("[BT-AUDIO] connected to %s (%s)", name, address)
            return True

        except Exception as exc:
            logger.error("[BT-AUDIO] connect error: %s", exc)
            return False

    def disconnect(self, address: str | None = None) -> bool:
        """Disconnect from a Bluetooth audio device.

        If address is None, disconnects the currently connected device.
        Switches audio back to built-in speaker.
        """
        if not self._bt_available:
            return False

        with self._lock:
            if address is None and self._connected_device:
                address = self._connected_device.address

        if not address:
            logger.info("[BT-AUDIO] no device to disconnect")
            return True

        logger.info("[BT-AUDIO] disconnecting from %s", address)
        try:
            self._run_bluetoothctl(["disconnect", address], timeout=_CMD_TIMEOUT)

            with self._lock:
                self._connected_device = None

            # Route audio back to built-in speaker
            self._switch_audio_to_speaker()

            logger.info("[BT-AUDIO] disconnected from %s", address)
            return True

        except Exception as exc:
            logger.error("[BT-AUDIO] disconnect error: %s", exc)
            return False

    def forget(self, address: str) -> bool:
        """Unpair (remove) a Bluetooth device."""
        if not self._bt_available:
            return False

        logger.info("[BT-AUDIO] forgetting device %s", address)
        try:
            # Disconnect first if connected
            with self._lock:
                if self._connected_device and self._connected_device.address == address:
                    self._connected_device = None

            self._run_bluetoothctl(["disconnect", address], timeout=5, ignore_errors=True)
            self._run_bluetoothctl(["untrust", address], timeout=5, ignore_errors=True)
            self._run_bluetoothctl(["remove", address], timeout=_CMD_TIMEOUT)

            # Switch audio back to speaker
            self._switch_audio_to_speaker()

            # Clear saved device if it matches
            if self._repo:
                saved = self._repo.get_setting("bt_audio_device")
                if saved == address:
                    self._repo.set_setting("bt_audio_device", "")

            logger.info("[BT-AUDIO] forgot device %s", address)
            return True

        except Exception as exc:
            logger.error("[BT-AUDIO] forget error: %s", exc)
            return False

    def get_paired_devices(self) -> list[dict]:
        """List all paired Bluetooth audio devices."""
        if not self._bt_available:
            return []

        try:
            result = self._run_bluetoothctl(["paired-devices"])
            if not result:
                return []

            devices = []
            for line in result.strip().splitlines():
                match = re.match(r"Device\s+([0-9A-Fa-f:]{17})\s+(.*)", line.strip())
                if match:
                    address = match.group(1)
                    name = match.group(2).strip()
                    info = self._get_device_info(address)
                    connected = False
                    if info and info.get("Connected") == "yes":
                        connected = True
                    devices.append({
                        "name": name,
                        "address": address,
                        "paired": True,
                        "connected": connected,
                        "type": "audio",
                    })

            return devices

        except Exception as exc:
            logger.error("[BT-AUDIO] get_paired_devices error: %s", exc)
            return []

    def get_connected_device(self) -> dict | None:
        """Return the currently connected BT audio device, or None."""
        with self._lock:
            if self._connected_device and self._connected_device.connected:
                return self._connected_device.to_dict()
        return None

    def set_auto_connect(self, address: str, enabled: bool) -> None:
        """Enable or disable auto-reconnect for a device address."""
        if enabled:
            self._save_last_device(address)
            # Trust ensures BlueZ will accept reconnections
            if self._bt_available:
                self._run_bluetoothctl(["trust", address], ignore_errors=True)
        else:
            if self._repo:
                saved = self._repo.get_setting("bt_audio_device")
                if saved == address:
                    self._repo.set_setting("bt_audio_device", "")
            if self._bt_available:
                self._run_bluetoothctl(["untrust", address], ignore_errors=True)

    def is_audio_routed_to_bt(self) -> bool:
        """Return True if audio is currently routed to a Bluetooth sink."""
        try:
            result = subprocess.run(
                ["pactl", "get-default-sink"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                sink = result.stdout.strip().lower()
                return "bluez" in sink or "bluetooth" in sink
        except Exception:
            pass
        return False

    def auto_reconnect_last(self) -> bool:
        """Try to reconnect to the last paired device (call at boot).

        Returns True if reconnection succeeded.
        """
        if not self._bt_available or not self._repo:
            return False

        address = self._repo.get_setting("bt_audio_device")
        if not address:
            logger.info("[BT-AUDIO] no saved device for auto-reconnect")
            return False

        logger.info("[BT-AUDIO] auto-reconnecting to %s", address)
        return self.connect(str(address))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _check_bluetoothctl() -> bool:
        """Return True if bluetoothctl is available on this system."""
        try:
            result = subprocess.run(
                ["bluetoothctl", "--version"],
                capture_output=True, text=True, timeout=5,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def _run_bluetoothctl(
        self,
        args: list[str],
        timeout: int = _CMD_TIMEOUT,
        ignore_errors: bool = False,
    ) -> str | None:
        """Run a bluetoothctl command and return stdout."""
        cmd = ["bluetoothctl"] + args
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            if result.returncode != 0 and not ignore_errors:
                logger.warning(
                    "[BT-AUDIO] bluetoothctl %s failed (rc=%d): %s",
                    " ".join(args), result.returncode,
                    result.stderr.strip()[:120],
                )
                return None
            return result.stdout
        except subprocess.TimeoutExpired:
            logger.warning("[BT-AUDIO] bluetoothctl %s timed out", " ".join(args))
            return None
        except FileNotFoundError:
            logger.error("[BT-AUDIO] bluetoothctl not found")
            self._bt_available = False
            return None
        except Exception as exc:
            logger.error("[BT-AUDIO] bluetoothctl error: %s", exc)
            return None

    def _parse_devices(self) -> list[BTAudioDevice]:
        """Parse bluetoothctl 'devices' output into BTAudioDevice list."""
        result = self._run_bluetoothctl(["devices"], timeout=5)
        if not result:
            return []

        devices = []
        for line in result.strip().splitlines():
            match = re.match(r"Device\s+([0-9A-Fa-f:]{17})\s+(.*)", line.strip())
            if match:
                address = match.group(1)
                name = match.group(2).strip()
                # Filter out unnamed or non-audio devices where possible
                if name and name != address:
                    devices.append(BTAudioDevice(
                        name=name,
                        address=address,
                        device_type="audio",
                    ))
        return devices

    def _get_device_info(self, address: str) -> dict[str, str] | None:
        """Get device info from bluetoothctl 'info <address>'."""
        result = self._run_bluetoothctl(["info", address], timeout=5)
        if not result:
            return None

        info: dict[str, str] = {}
        for line in result.strip().splitlines():
            line = line.strip()
            if ":" in line:
                key, _, value = line.partition(":")
                info[key.strip()] = value.strip()
        return info

    def _switch_audio_to_bt(self) -> None:
        """Switch PulseAudio default sink to the Bluetooth device."""
        try:
            # List sinks and find the bluez one
            result = subprocess.run(
                ["pactl", "list", "short", "sinks"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode != 0:
                logger.warning("[BT-AUDIO] pactl list sinks failed")
                return

            for line in result.stdout.strip().splitlines():
                parts = line.split("\t")
                if len(parts) >= 2:
                    sink_name = parts[1]
                    if "bluez" in sink_name.lower() or "bluetooth" in sink_name.lower():
                        subprocess.run(
                            ["pactl", "set-default-sink", sink_name],
                            capture_output=True, timeout=5,
                        )
                        logger.info("[BT-AUDIO] audio routed to BT sink: %s", sink_name)

                        # Move existing streams to the new sink
                        self._move_streams_to_sink(sink_name)
                        return

            logger.warning("[BT-AUDIO] no Bluetooth sink found in pactl")

        except Exception as exc:
            logger.error("[BT-AUDIO] switch_audio_to_bt error: %s", exc)

    def _switch_audio_to_speaker(self) -> None:
        """Switch PulseAudio default sink back to the built-in speaker."""
        try:
            result = subprocess.run(
                ["pactl", "list", "short", "sinks"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode != 0:
                return

            for line in result.stdout.strip().splitlines():
                parts = line.split("\t")
                if len(parts) >= 2:
                    sink_name = parts[1]
                    # Look for the non-BT sink (ALSA / built-in)
                    if "bluez" not in sink_name.lower() and "bluetooth" not in sink_name.lower():
                        subprocess.run(
                            ["pactl", "set-default-sink", sink_name],
                            capture_output=True, timeout=5,
                        )
                        logger.info("[BT-AUDIO] audio routed to speaker: %s", sink_name)

                        # Move existing streams to the speaker
                        self._move_streams_to_sink(sink_name)
                        return

            logger.warning("[BT-AUDIO] no built-in speaker sink found")

        except Exception as exc:
            logger.error("[BT-AUDIO] switch_audio_to_speaker error: %s", exc)

    @staticmethod
    def _move_streams_to_sink(sink_name: str) -> None:
        """Move all existing playback streams to the specified sink."""
        try:
            result = subprocess.run(
                ["pactl", "list", "short", "sink-inputs"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode != 0:
                return

            for line in result.stdout.strip().splitlines():
                parts = line.split("\t")
                if parts:
                    stream_id = parts[0]
                    subprocess.run(
                        ["pactl", "move-sink-input", stream_id, sink_name],
                        capture_output=True, timeout=5,
                    )
        except Exception:
            pass  # Best-effort stream migration

    def _save_last_device(self, address: str) -> None:
        """Persist the last connected device address for auto-reconnect."""
        if self._repo:
            self._repo.set_setting("bt_audio_device", address)
            logger.info("[BT-AUDIO] saved last device: %s", address)
