"""BITOS BLE Service — Nordic UART Service (NUS) peripheral.

Two implementations:
- BITOSBleService: real BlueZ/bluezero peripheral (Pi with BT adapter)
- MockBleService: no-op fallback for dev machines or missing hardware
- get_ble_service(): factory that picks the right one automatically
"""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import Callable, Optional

from .protocol import BITOSProtocol, ChunkAssembler

logger = logging.getLogger(__name__)

NUS_SERVICE = "6E400001-B5A3-F393-E0A9-E50E24DCCA9E"
NUS_TX = "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"
NUS_RX = "6E400002-B5A3-F393-E0A9-E50E24DCCA9E"

# Retry configuration for BLE peripheral setup
_MAX_RETRIES = 3
_RETRY_DELAY_SECONDS = 5


class BITOSBleService:
    """BLE peripheral for BITOS using BlueZ/bluezero."""

    def __init__(self):
        self._running = False
        self._connected = False
        self._thread: Optional[threading.Thread] = None
        self._peripheral = None
        self._tx_char = None
        self._assembler = ChunkAssembler()
        self._healthy = False

        self._on_message_cb: Optional[Callable[[dict], None]] = None
        self._on_connect_cb: Optional[Callable[[], None]] = None
        self._on_disconnect_cb: Optional[Callable[[], None]] = None

    def on_message(self, cb: Callable[[dict], None]) -> None:
        self._on_message_cb = cb

    def on_connect(self, cb: Callable[[], None]) -> None:
        self._on_connect_cb = cb

    def on_disconnect(self, cb: Callable[[], None]) -> None:
        self._on_disconnect_cb = cb

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def is_healthy(self) -> bool:
        """True if the BLE peripheral is running and advertising."""
        return self._healthy

    def send(self, msg: dict) -> bool:
        """Send a dict to phone via NUS TX; handles chunking automatically."""
        if not self._connected or self._tx_char is None:
            logger.debug("BLE send skipped: not connected")
            return False

        try:
            for payload in BITOSProtocol.encode(msg):
                self._tx_char.set_value(list(payload))
            return True
        except Exception as exc:
            logger.error("BLE send error: %s", exc)
            return False

    def start(self) -> None:
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True, name="bitos-ble")
        self._thread.start()
        logger.info("[BLE] NUS service starting")

    def stop(self) -> None:
        self._running = False
        self._healthy = False
        if self._peripheral:
            try:
                self._peripheral.stop_advertising()
            except Exception:
                pass
        logger.info("[BLE] NUS service stopped")

    def _run(self) -> None:
        try:
            from bluezero import adapter, peripheral
        except ImportError:
            logger.warning("[BLE] bluezero not installed — NUS service disabled")
            self._running = False
            return

        retries = 0
        while self._running and retries < _MAX_RETRIES:
            try:
                self._setup_peripheral(adapter, peripheral)
                self._healthy = True
                logger.info("[BLE] NUS peripheral published and advertising")
                return  # publish() blocks; returns when stopped
            except Exception as exc:
                retries += 1
                self._healthy = False
                self._connected = False
                logger.error("[BLE] NUS setup failed (attempt %d/%d): %s", retries, _MAX_RETRIES, exc)
                if retries < _MAX_RETRIES and self._running:
                    time.sleep(_RETRY_DELAY_SECONDS)

        if self._running:
            logger.error("[BLE] NUS service gave up after %d retries — running degraded", _MAX_RETRIES)
        self._running = False

    def _setup_peripheral(self, adapter, peripheral) -> None:
        """Create and publish the NUS peripheral. Raises on failure."""
        adapters = adapter.list_adapters()
        if not adapters:
            raise RuntimeError("No Bluetooth adapter found")

        addr = adapters[0]
        dongle = adapter.Adapter(addr)
        dongle.powered = True

        self._peripheral = peripheral.Peripheral(addr, local_name="BITOS")
        self._peripheral.add_service(srv_id=1, uuid=NUS_SERVICE, primary=True)
        self._peripheral.add_characteristic(
            srv_id=1,
            chr_id=1,
            uuid=NUS_TX,
            value=[],
            notifying=False,
            flags=["notify"],
            read_callback=None,
            write_callback=None,
            notify_callback=self._on_tx_notify,
        )
        self._peripheral.add_characteristic(
            srv_id=1,
            chr_id=2,
            uuid=NUS_RX,
            value=[],
            notifying=False,
            flags=["write", "write-without-response"],
            read_callback=None,
            write_callback=self._on_rx_write,
            notify_callback=None,
        )

        self._tx_char = self._peripheral.services[1].characteristics[1]
        self._peripheral.on_connect = self._on_phone_connect
        self._peripheral.on_disconnect = self._on_phone_disconnect
        self._peripheral.publish()

    def _on_rx_write(self, value, options=None):
        del options
        try:
            msg = BITOSProtocol.decode(bytes(value))
            if msg is None:
                return

            complete = self._assembler.feed(msg)
            if complete is None:
                return

            message_type = complete.get("t", "")
            logger.info("[BLE] rx: t=%s", message_type)

            if message_type == "ping":
                self.send({"t": "pong"})
                return

            if self._on_message_cb:
                self._on_message_cb(complete)
        except Exception as exc:
            logger.error("[BLE] rx handler error: %s", exc)

    def _on_tx_notify(self, notifying, characteristic):
        del characteristic
        logger.debug("[BLE] TX notify: %s", notifying)

    def _on_phone_connect(self, device):
        self._connected = True
        logger.info("[BLE] phone connected: %s", device)
        self.send({"t": "status", "screen": "LOCK", "ble": True})
        if self._on_connect_cb:
            try:
                self._on_connect_cb()
            except Exception as exc:
                logger.error("[BLE] on_connect callback error: %s", exc)

    def _on_phone_disconnect(self, device):
        self._connected = False
        logger.info("[BLE] phone disconnected: %s", device)
        if self._on_disconnect_cb:
            try:
                self._on_disconnect_cb()
            except Exception as exc:
                logger.error("[BLE] on_disconnect callback error: %s", exc)


class MockBleService:
    """No-op BLE service for development without Bluetooth hardware."""

    def __init__(self):
        self._connected = False
        self._on_message_cb: Optional[Callable[[dict], None]] = None
        self._on_connect_cb: Optional[Callable[[], None]] = None
        self._on_disconnect_cb: Optional[Callable[[], None]] = None

    def on_message(self, cb: Callable[[dict], None]) -> None:
        self._on_message_cb = cb

    def on_connect(self, cb: Callable[[], None]) -> None:
        self._on_connect_cb = cb

    def on_disconnect(self, cb: Callable[[], None]) -> None:
        self._on_disconnect_cb = cb

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def is_healthy(self) -> bool:
        return True  # Mock is always "healthy"

    def send(self, msg: dict) -> bool:
        logger.debug("[BLE][MOCK] send: %s", msg.get("t", "?"))
        return False

    def start(self) -> None:
        logger.info("[BLE][MOCK] NUS service start (no-op)")

    def stop(self) -> None:
        logger.info("[BLE][MOCK] NUS service stop (no-op)")


def get_ble_service() -> BITOSBleService | MockBleService:
    """Factory: returns MockBleService on dev machines or when BITOS_BLE=mock."""
    if os.environ.get("BITOS_BLE") == "mock":
        logger.info("[BLE] Using mock NUS service (BITOS_BLE=mock)")
        return MockBleService()
    try:
        import bluezero  # noqa: F401
        return BITOSBleService()
    except ImportError:
        logger.info("[BLE] bluezero not available — using mock NUS service")
        return MockBleService()
