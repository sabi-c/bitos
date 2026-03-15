"""BITOS BLE service based on BlueZ/bluezero.

Implements Nordic UART Service (NUS) and baseline standard services.
"""

from __future__ import annotations

import datetime as dt
import logging
import threading
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# Nordic UART Service (NUS)
NUS_SERVICE_UUID = "6E400001-B5A3-F393-E0A9-E50E24DCCA9E"
NUS_TX_UUID = "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"  # Pi -> phone (notify)
NUS_RX_UUID = "6E400002-B5A3-F393-E0A9-E50E24DCCA9E"  # phone -> Pi (write)

# Current Time Service
CTS_SERVICE_UUID = "00001805-0000-1000-8000-00805F9B34FB"
CTS_CHAR_UUID = "00002A2B-0000-1000-8000-00805F9B34FB"

# Device Information Service
DIS_SERVICE_UUID = "0000180A-0000-1000-8000-00805F9B34FB"
DIS_MODEL_UUID = "00002A24-0000-1000-8000-00805F9B34FB"
DIS_MANUFACTURER_UUID = "00002A29-0000-1000-8000-00805F9B34FB"
DIS_FIRMWARE_UUID = "00002A26-0000-1000-8000-00805F9B34FB"


class BITOSBleService:
    """BLE peripheral service for phone<->device transport."""

    def __init__(self):
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._peripheral = None
        self._tx_char = None
        self._connected = False

        self._on_message_cb: Optional[Callable[[str], None]] = None
        self._on_connect_cb: Optional[Callable[[], None]] = None
        self._on_disconnect_cb: Optional[Callable[[], None]] = None

    def on_message(self, cb: Callable[[str], None]) -> None:
        self._on_message_cb = cb

    def on_connect(self, cb: Callable[[], None]) -> None:
        self._on_connect_cb = cb

    def on_disconnect(self, cb: Callable[[], None]) -> None:
        self._on_disconnect_cb = cb

    def send(self, text: str) -> bool:
        if not self._connected or self._tx_char is None:
            logger.warning("BLE send failed: no active NUS connection")
            return False

        try:
            self._tx_char.set_value(list(text.encode("utf-8")))
            return True
        except Exception as exc:
            logger.error("BLE send error: %s", exc)
            return False

    @property
    def is_connected(self) -> bool:
        return self._connected

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True, name="bitos-ble")
        self._thread.start()
        logger.info("BLE service start requested")

    def stop(self) -> None:
        self._running = False
        if self._peripheral:
            try:
                self._peripheral.stop_advertising()
            except Exception:
                pass

    def _run(self) -> None:
        try:
            from bluezero import adapter, peripheral
        except ImportError:
            logger.error("bluezero not installed; BLE disabled")
            self._running = False
            return

        try:
            adapters = adapter.list_adapters()
            if not adapters:
                logger.error("No BLE adapters detected")
                self._running = False
                return

            adapter_addr = adapters[0]
            dongle = adapter.Adapter(adapter_addr)
            dongle.powered = True

            self._peripheral = peripheral.Peripheral(adapter_address=adapter_addr, local_name="BITOS")

            self._peripheral.add_service(srv_id=1, uuid=NUS_SERVICE_UUID, primary=True)
            self._peripheral.add_characteristic(
                srv_id=1,
                chr_id=1,
                uuid=NUS_TX_UUID,
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
                uuid=NUS_RX_UUID,
                value=[],
                notifying=False,
                flags=["write", "write-without-response"],
                read_callback=None,
                write_callback=self._on_rx_write,
                notify_callback=None,
            )

            # Current Time Service: readable + writable to allow phone-initiated sync.
            self._peripheral.add_service(srv_id=2, uuid=CTS_SERVICE_UUID, primary=True)
            self._peripheral.add_characteristic(
                srv_id=2,
                chr_id=1,
                uuid=CTS_CHAR_UUID,
                value=self._current_time_bytes(),
                notifying=False,
                flags=["read", "write"],
                read_callback=self._on_time_read,
                write_callback=self._on_time_write,
                notify_callback=None,
            )

            # Device Information Service: lets scanners display BITOS metadata.
            self._peripheral.add_service(srv_id=3, uuid=DIS_SERVICE_UUID, primary=True)
            self._peripheral.add_characteristic(
                srv_id=3,
                chr_id=1,
                uuid=DIS_MODEL_UUID,
                value=list("BITOS".encode("utf-8")),
                notifying=False,
                flags=["read"],
                read_callback=self._read_dis_model,
                write_callback=None,
                notify_callback=None,
            )
            self._peripheral.add_characteristic(
                srv_id=3,
                chr_id=2,
                uuid=DIS_MANUFACTURER_UUID,
                value=list("BITOS".encode("utf-8")),
                notifying=False,
                flags=["read"],
                read_callback=self._read_dis_manufacturer,
                write_callback=None,
                notify_callback=None,
            )
            self._peripheral.add_characteristic(
                srv_id=3,
                chr_id=3,
                uuid=DIS_FIRMWARE_UUID,
                value=list("1.0.0".encode("utf-8")),
                notifying=False,
                flags=["read"],
                read_callback=self._read_dis_firmware,
                write_callback=None,
                notify_callback=None,
            )

            self._tx_char = self._peripheral.services[1].characteristics[1]
            self._peripheral.on_connect = self._on_phone_connect
            self._peripheral.on_disconnect = self._on_phone_disconnect
            self._peripheral.publish()

            logger.info("BLE advertising started: local_name=BITOS")
        except Exception as exc:
            logger.error("BLE startup error: %s", exc)
            self._running = False

    def _on_rx_write(self, value, options=None):
        del options
        try:
            text = bytes(value).decode("utf-8", errors="replace").strip()
            logger.info("BLE received NUS RX: %r", text)
            if self._on_message_cb:
                self._on_message_cb(text)
        except Exception as exc:
            logger.error("BLE RX parse error: %s", exc)

    def _on_tx_notify(self, notifying, characteristic):
        del characteristic
        logger.debug("BLE TX notify changed: %s", notifying)

    def _on_phone_connect(self, device):
        self._connected = True
        logger.info("BLE connected: %s", device)
        if self._on_connect_cb:
            self._on_connect_cb()

    def _on_phone_disconnect(self, device):
        self._connected = False
        logger.info("BLE disconnected: %s", device)
        if self._on_disconnect_cb:
            self._on_disconnect_cb()

    def _on_time_read(self):
        return self._current_time_bytes()

    def _on_time_write(self, value, options=None):
        del options
        logger.info("BLE current time write: %s", list(value))

    def _read_dis_model(self):
        return list("BITOS".encode("utf-8"))

    def _read_dis_manufacturer(self):
        return list("BITOS".encode("utf-8"))

    def _read_dis_firmware(self):
        return list("1.0.0".encode("utf-8"))

    @staticmethod
    def _current_time_bytes() -> list[int]:
        now = dt.datetime.now()
        weekday = now.isoweekday()
        fractions256 = int(now.microsecond / 3906.25)
        return [
            now.year & 0xFF,
            (now.year >> 8) & 0xFF,
            now.month,
            now.day,
            now.hour,
            now.minute,
            now.second,
            weekday,
            fractions256,
            0,
        ]
