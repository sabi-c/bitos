"""BITOS ANCS client for forwarding iOS notifications to BITOS runtime."""

from __future__ import annotations

import asyncio
import logging
import struct
import threading
from typing import Callable, Optional

logger = logging.getLogger(__name__)

ANCS_SERVICE = "7905F431-B5CE-4E99-A40F-4B1E122D00D0"
ANCS_NOTIF_SOURCE_UUID = "9FBF120D-6301-42D9-8C58-25E699A21DBD"
ANCS_CONTROL_POINT_UUID = "69D1D8F3-45E1-49A8-9821-9BBDFDAAD9D9"
ANCS_DATA_SOURCE_UUID = "22EAC6E9-24D6-4BB5-BE44-B36ACE7C7BFB"

CATEGORY_NAMES = {
    0: "Other",
    1: "IncomingCall",
    2: "MissedCall",
    3: "Voicemail",
    4: "Social",
    5: "Schedule",
    6: "Email",
    7: "News",
    8: "HealthFitness",
    9: "BusinessFinance",
    10: "Location",
    11: "Entertainment",
}

EVENT_ADDED = 0
EVENT_MODIFIED = 1
EVENT_REMOVED = 2

ATTR_APP_ID = 0
ATTR_TITLE = 1
ATTR_SUBTITLE = 2
ATTR_MESSAGE = 3


class ANCSClient:
    """Connect to paired iPhone and subscribe to ANCS notifications."""

    def __init__(self):
        self._on_notif_cb: Optional[Callable[[dict], None]] = None
        self._running = False
        self._iphone_address: Optional[str] = None
        self._thread: Optional[threading.Thread] = None

    def on_notification(self, cb: Callable[[dict], None]) -> None:
        self._on_notif_cb = cb

    def connect(self, iphone_address: str) -> None:
        self._iphone_address = iphone_address
        self._running = True
        self._thread = threading.Thread(target=self._run_async, daemon=True, name="ancs-client")
        self._thread.start()
        logger.info("ANCS client starting for %s", iphone_address)

    def stop(self) -> None:
        self._running = False

    def _run_async(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._connect_and_subscribe())
        except Exception as exc:
            logger.error("ANCS error: %s", exc)
        finally:
            loop.close()

    async def _connect_and_subscribe(self) -> None:
        try:
            from bleak import BleakClient
        except ImportError:
            logger.error("bleak not installed. Run: pip install bleak")
            return

        if not self._iphone_address:
            logger.error("ANCS missing iPhone address")
            return

        logger.info("Connecting to iPhone at %s", self._iphone_address)
        async with BleakClient(self._iphone_address) as client:
            logger.info("Connected to iPhone. Discovering ANCS...")
            services = await client.get_services()

            notif_source_uuid = None
            control_point_uuid = None
            data_source_uuid = None

            for service in services:
                if service.uuid.lower() == ANCS_SERVICE.lower():
                    for char in service.characteristics:
                        uuid = char.uuid.lower()
                        if uuid == ANCS_NOTIF_SOURCE_UUID.lower():
                            notif_source_uuid = char.uuid
                        elif uuid == ANCS_CONTROL_POINT_UUID.lower():
                            control_point_uuid = char.uuid
                        elif uuid == ANCS_DATA_SOURCE_UUID.lower():
                            data_source_uuid = char.uuid

            if not notif_source_uuid or not control_point_uuid or not data_source_uuid:
                logger.error("ANCS characteristics not found. Is this a paired iPhone?")
                return

            pending: dict[int, dict] = {}
            data_buffer = bytearray()

            def _try_parse_data_source(payload: bytearray) -> tuple[Optional[dict], int]:
                if len(payload) < 5:
                    return None, 0
                if payload[0] != 0:
                    return None, 1

                uid = struct.unpack_from("<I", payload, 1)[0]
                offset = 5
                notif = pending.pop(uid, {"uid": uid})

                while offset < len(payload):
                    if offset + 3 > len(payload):
                        pending[uid] = notif
                        return None, 0
                    attr_id = payload[offset]
                    attr_len = struct.unpack_from("<H", payload, offset + 1)[0]
                    offset += 3
                    if offset + attr_len > len(payload):
                        pending[uid] = notif
                        return None, 0
                    value = payload[offset : offset + attr_len].decode("utf-8", errors="replace")
                    offset += attr_len

                    if attr_id == ATTR_APP_ID:
                        notif["app"] = value
                    elif attr_id == ATTR_TITLE:
                        notif["title"] = value
                    elif attr_id == ATTR_SUBTITLE:
                        notif["subtitle"] = value
                    elif attr_id == ATTR_MESSAGE:
                        notif["body"] = value

                notif["t"] = "notif"
                return notif, offset

            async def handle_data_source(sender, data: bytearray):
                del sender
                if not data:
                    return
                data_buffer.extend(data)
                while data_buffer:
                    parsed, consumed = _try_parse_data_source(data_buffer)
                    if parsed is None:
                        if consumed > 0:
                            del data_buffer[:consumed]
                            continue
                        break
                    logger.info("ANCS notif: app=%s title=%s", parsed.get("app", "?"), parsed.get("title", "?"))
                    if self._on_notif_cb:
                        self._on_notif_cb(parsed)
                    del data_buffer[:consumed]

            async def handle_notif_source(sender, data: bytearray):
                del sender
                if len(data) < 8:
                    return

                event_id = data[0]
                category = data[2]
                uid = struct.unpack_from("<I", data, 4)[0]

                if event_id == EVENT_REMOVED:
                    return

                pending[uid] = {"uid": uid, "category": CATEGORY_NAMES.get(category, "Other")}

                cmd = struct.pack("<BI", 0, uid)
                cmd += bytes([ATTR_APP_ID])
                cmd += bytes([ATTR_TITLE]) + struct.pack("<H", 64)
                cmd += bytes([ATTR_MESSAGE]) + struct.pack("<H", 256)
                try:
                    await client.write_gatt_char(control_point_uuid, cmd, response=False)
                except Exception as exc:
                    logger.debug("ANCS control point write error: %s", exc)

            await client.start_notify(data_source_uuid, handle_data_source)
            await client.start_notify(notif_source_uuid, handle_notif_source)
            logger.info("ANCS subscribed. Waiting for notifications...")

            while self._running and client.is_connected:
                await asyncio.sleep(1.0)

            logger.info("ANCS client disconnecting")
