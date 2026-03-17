"""Bluetooth Connection Manager for BITOS.

Async service using dbus-next to interact with BlueZ for:
- Device discovery (scan for BT audio devices)
- Pairing + trusting
- Auto-reconnect on disconnect (exponential backoff)
- Connection state tracking
- Event callbacks for state changes

Falls back gracefully when dbus-next or BlueZ is not available (desktop/CI).
"""
from __future__ import annotations

import asyncio
import enum
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable

logger = logging.getLogger(__name__)

try:
    from dbus_next.aio import MessageBus
    from dbus_next import BusType, Message, MessageType, Variant
    _DBUS_AVAILABLE = True
except ImportError:
    _DBUS_AVAILABLE = False
    MessageBus = None  # type: ignore[assignment,misc]
    BusType = None  # type: ignore[assignment,misc]
    Message = None  # type: ignore[assignment,misc]
    MessageType = None  # type: ignore[assignment,misc]

    class Variant:  # type: ignore[no-redef]
        """Stub for dbus_next.Variant when dbus-next is not installed."""
        def __init__(self, sig: str, value):
            self.value = value


# BlueZ D-Bus constants
_BLUEZ_SERVICE = "org.bluez"
_ADAPTER_IFACE = "org.bluez.Adapter1"
_DEVICE_IFACE = "org.bluez.Device1"
_PROPERTIES_IFACE = "org.freedesktop.DBus.Properties"
_OBJECT_MANAGER_IFACE = "org.freedesktop.DBus.ObjectManager"
_AGENT_MANAGER_IFACE = "org.bluez.AgentManager1"

# A2DP sink UUID for audio device filtering
A2DP_SINK_UUID = "0000110b-0000-1000-8000-00805f9b34fb"
HANDSFREE_UUID = "0000111e-0000-1000-8000-00805f9b34fb"
AUDIO_UUIDS = {A2DP_SINK_UUID, HANDSFREE_UUID}


class BTState(enum.Enum):
    """Bluetooth connection states."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    PLAYING = "playing"


@dataclass
class BTDeviceInfo:
    """Discovered or known Bluetooth device."""
    address: str
    name: str = "Unknown"
    rssi: int = 0
    paired: bool = False
    trusted: bool = False
    connected: bool = False
    uuids: list[str] = field(default_factory=list)
    icon: str = ""

    @property
    def is_audio(self) -> bool:
        return any(u in AUDIO_UUIDS for u in self.uuids)

    @property
    def is_airpods(self) -> bool:
        return "airpods" in self.name.lower()

    @property
    def dbus_path(self) -> str:
        return f"/org/bluez/hci0/dev_{self.address.replace(':', '_')}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "address": self.address,
            "name": self.name,
            "rssi": self.rssi,
            "paired": self.paired,
            "trusted": self.trusted,
            "connected": self.connected,
            "is_audio": self.is_audio,
            "is_airpods": self.is_airpods,
        }


# Type alias for event callbacks
BTEventCallback = Callable[..., Awaitable[None] | None]


class BTService:
    """Unified Bluetooth service for BITOS.

    Manages device discovery, pairing, connection lifecycle, and
    auto-reconnect with exponential backoff.

    Usage:
        service = BTService()
        await service.start()
        await service.discover(timeout=15)
        await service.pair_and_connect("AA:BB:CC:DD:EE:FF")
    """

    RECONNECT_INTERVAL = 5.0
    RECONNECT_MAX_BACKOFF = 60.0
    SCAN_TIMEOUT = 30.0

    def __init__(self):
        self._bus: Any = None
        self._adapter: Any = None
        self._adapter_props: Any = None
        self._state = BTState.DISCONNECTED
        self._known_devices: dict[str, BTDeviceInfo] = {}
        self._connected_device: BTDeviceInfo | None = None
        self._reconnect_tasks: dict[str, asyncio.Task] = {}
        self._discovery_active = False
        self._running = False
        self._loop: asyncio.AbstractEventLoop | None = None  # stored on start() for thread-safe callbacks

        # Event callbacks
        self.on_state_change: BTEventCallback | None = None
        self.on_device_found: BTEventCallback | None = None
        self.on_connect: BTEventCallback | None = None
        self.on_disconnect: BTEventCallback | None = None

    @property
    def state(self) -> BTState:
        return self._state

    @property
    def connected_device(self) -> BTDeviceInfo | None:
        return self._connected_device

    @property
    def known_devices(self) -> dict[str, BTDeviceInfo]:
        return dict(self._known_devices)

    @property
    def is_available(self) -> bool:
        return _DBUS_AVAILABLE and self._bus is not None

    async def start(self) -> bool:
        """Initialize D-Bus connection and BlueZ adapter.

        Returns True if successfully connected to BlueZ.
        """
        if not _DBUS_AVAILABLE:
            logger.warning("[BT] dbus-next not available — BT service disabled")
            return False

        try:
            self._bus = await MessageBus(bus_type=BusType.SYSTEM).connect()

            # Get adapter proxy
            introspection = await self._bus.introspect(
                _BLUEZ_SERVICE, "/org/bluez/hci0"
            )
            proxy = self._bus.get_proxy_object(
                _BLUEZ_SERVICE, "/org/bluez/hci0", introspection
            )
            self._adapter = proxy.get_interface(_ADAPTER_IFACE)
            self._adapter_props = proxy.get_interface(_PROPERTIES_IFACE)

            # Ensure adapter is powered on
            await self._adapter_props.call_set(
                _ADAPTER_IFACE, "Powered", Variant("b", True)
            )

            # Register signal handler for property changes
            self._bus.add_message_handler(self._on_dbus_message)

            # Add match rule for BlueZ signals
            await self._bus.call(
                Message(
                    destination="org.freedesktop.DBus",
                    path="/org/freedesktop/DBus",
                    interface="org.freedesktop.DBus",
                    member="AddMatch",
                    signature="s",
                    body=[
                        "type='signal',sender='org.bluez',"
                        "interface='org.freedesktop.DBus.Properties',"
                        "member='PropertiesChanged'"
                    ],
                )
            )

            self._running = True
            self._loop = asyncio.get_event_loop()
            logger.info("[BT] Service started, adapter ready")

            # Try reconnecting trusted devices
            asyncio.ensure_future(self._reconnect_trusted())

            return True

        except Exception as exc:
            logger.error("[BT] Failed to start: %s", exc)
            self._bus = None
            return False

    async def stop(self):
        """Shut down the BT service."""
        self._running = False

        # Cancel all reconnect tasks
        for mac, task in self._reconnect_tasks.items():
            task.cancel()
        self._reconnect_tasks.clear()

        # Stop discovery if active
        if self._discovery_active:
            try:
                await self._adapter.call_stop_discovery()
            except Exception:
                pass
            self._discovery_active = False

        if self._bus:
            self._bus.disconnect()
            self._bus = None

        logger.info("[BT] Service stopped")

    async def discover(self, timeout: float | None = None) -> list[BTDeviceInfo]:
        """Scan for nearby Bluetooth devices.

        Returns list of discovered BTDeviceInfo after timeout.
        """
        if not self.is_available:
            logger.warning("[BT] discover: service not available")
            return []

        timeout = timeout or self.SCAN_TIMEOUT
        discovered: list[BTDeviceInfo] = []

        try:
            self._discovery_active = True
            await self._adapter.call_start_discovery()
            logger.info("[BT] Discovery started (timeout=%ss)", timeout)

            await asyncio.sleep(timeout)

            await self._adapter.call_stop_discovery()
            self._discovery_active = False

            # Enumerate discovered devices via ObjectManager
            discovered = await self._enumerate_devices()
            logger.info("[BT] Discovery complete: %d devices", len(discovered))

        except Exception as exc:
            logger.error("[BT] Discovery error: %s", exc)
            self._discovery_active = False
            try:
                await self._adapter.call_stop_discovery()
            except Exception:
                pass

        return discovered

    async def discover_stream(self, timeout: float | None = None):
        """Async generator that yields devices as they are found during scan.

        Usage:
            async for device in service.discover_stream(timeout=15):
                print(device.name)
        """
        if not self.is_available:
            return

        timeout = timeout or self.SCAN_TIMEOUT
        seen: set[str] = set()
        found_queue: asyncio.Queue[BTDeviceInfo] = asyncio.Queue()

        # Temporarily hook device_found to feed the queue
        original_cb = self.on_device_found

        async def _feed_queue(info: BTDeviceInfo):
            if info.address not in seen:
                seen.add(info.address)
                await found_queue.put(info)
            if original_cb:
                await original_cb(info)

        self.on_device_found = _feed_queue

        try:
            self._discovery_active = True
            await self._adapter.call_start_discovery()

            deadline = asyncio.get_event_loop().time() + timeout
            while asyncio.get_event_loop().time() < deadline:
                remaining = deadline - asyncio.get_event_loop().time()
                if remaining <= 0:
                    break
                try:
                    device = await asyncio.wait_for(
                        found_queue.get(), timeout=min(remaining, 1.0)
                    )
                    yield device
                except asyncio.TimeoutError:
                    continue
        finally:
            self.on_device_found = original_cb
            self._discovery_active = False
            try:
                await self._adapter.call_stop_discovery()
            except Exception:
                pass

    async def pair_and_connect(self, address: str) -> bool:
        """Pair, trust, and connect to a device by MAC address.

        Returns True on success.
        """
        if not self.is_available:
            return False

        device_path = f"/org/bluez/hci0/dev_{address.replace(':', '_')}"

        try:
            self._set_state(BTState.CONNECTING)

            introspection = await self._bus.introspect(_BLUEZ_SERVICE, device_path)
            proxy = self._bus.get_proxy_object(
                _BLUEZ_SERVICE, device_path, introspection
            )
            device_iface = proxy.get_interface(_DEVICE_IFACE)
            props_iface = proxy.get_interface(_PROPERTIES_IFACE)

            # Check if already paired
            paired = await props_iface.call_get(_DEVICE_IFACE, "Paired")
            if not paired.value:
                logger.info("[BT] Pairing with %s...", address)
                await device_iface.call_pair()

            # Trust the device for auto-reconnect
            await props_iface.call_set(
                _DEVICE_IFACE, "Trusted", Variant("b", True)
            )

            # Connect
            logger.info("[BT] Connecting to %s...", address)
            await device_iface.call_connect()

            # Update known device info
            info = await self._get_device_info(device_path)
            if info:
                self._known_devices[address] = info
                self._connected_device = info
                self._set_state(BTState.CONNECTED)

                # Cancel any reconnect task for this device
                if address in self._reconnect_tasks:
                    self._reconnect_tasks[address].cancel()
                    del self._reconnect_tasks[address]

                if self.on_connect:
                    try:
                        result = self.on_connect(address, info.to_dict())
                        if asyncio.iscoroutine(result):
                            await result
                    except Exception as exc:
                        logger.error("[BT] on_connect callback error: %s", exc)

            logger.info("[BT] Connected to %s (%s)", info.name if info else address, address)
            return True

        except Exception as exc:
            logger.error("[BT] pair_and_connect failed for %s: %s", address, exc)
            self._set_state(BTState.DISCONNECTED)
            return False

    async def disconnect(self, address: str) -> bool:
        """Disconnect from a device."""
        if not self.is_available:
            return False

        device_path = f"/org/bluez/hci0/dev_{address.replace(':', '_')}"

        try:
            introspection = await self._bus.introspect(_BLUEZ_SERVICE, device_path)
            proxy = self._bus.get_proxy_object(
                _BLUEZ_SERVICE, device_path, introspection
            )
            device_iface = proxy.get_interface(_DEVICE_IFACE)
            await device_iface.call_disconnect()

            if self._connected_device and self._connected_device.address == address:
                self._connected_device = None
                self._set_state(BTState.DISCONNECTED)

            logger.info("[BT] Disconnected from %s", address)
            return True

        except Exception as exc:
            logger.error("[BT] Disconnect failed for %s: %s", address, exc)
            return False

    async def forget(self, address: str) -> bool:
        """Remove (unpair) a device."""
        if not self.is_available:
            return False

        device_path = f"/org/bluez/hci0/dev_{address.replace(':', '_')}"

        try:
            # Disconnect first if connected
            if self._connected_device and self._connected_device.address == address:
                await self.disconnect(address)

            introspection = await self._bus.introspect(
                _BLUEZ_SERVICE, "/org/bluez/hci0"
            )
            proxy = self._bus.get_proxy_object(
                _BLUEZ_SERVICE, "/org/bluez/hci0", introspection
            )
            adapter = proxy.get_interface(_ADAPTER_IFACE)
            await adapter.call_remove_device(device_path)

            self._known_devices.pop(address, None)

            # Cancel reconnect task
            if address in self._reconnect_tasks:
                self._reconnect_tasks[address].cancel()
                del self._reconnect_tasks[address]

            logger.info("[BT] Forgot device %s", address)
            return True

        except Exception as exc:
            logger.error("[BT] Forget failed for %s: %s", address, exc)
            return False

    # ------------------------------------------------------------------
    # Internal: thread-safe callback dispatch
    # ------------------------------------------------------------------

    def _safe_callback(self, callback: Callable, *args: Any) -> None:
        """Invoke a callback safely from the D-Bus signal thread.

        If callback is async (returns coroutine), schedule it on the stored
        event loop via call_soon_threadsafe. If sync, just call it.
        """
        try:
            result = callback(*args)
            if asyncio.iscoroutine(result):
                if self._loop and self._loop.is_running():
                    self._loop.call_soon_threadsafe(asyncio.ensure_future, result)
                else:
                    logger.warning("[BT] No running loop for async callback, dropping")
        except Exception as exc:
            logger.error("[BT] Callback error: %s", exc)

    # ------------------------------------------------------------------
    # Internal: D-Bus signal handling
    # ------------------------------------------------------------------

    def _on_dbus_message(self, msg) -> None:
        """Handle incoming D-Bus signals (runs on bus thread)."""
        if not self._running:
            return

        if msg.message_type != MessageType.SIGNAL:
            return
        if msg.member != "PropertiesChanged":
            return
        if not msg.body or len(msg.body) < 2:
            return

        interface = msg.body[0]
        changed = msg.body[1]

        if interface == _DEVICE_IFACE:
            self._handle_device_props_changed(msg.path, changed)

    def _handle_device_props_changed(self, path: str, changed: dict) -> None:
        """Process Device1 property changes (connect/disconnect/discovery)."""
        # Extract MAC from path: /org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF
        parts = path.split("/")
        if len(parts) < 5 or not parts[-1].startswith("dev_"):
            return
        address = parts[-1][4:].replace("_", ":")

        if "Connected" in changed:
            connected = changed["Connected"].value
            if connected:
                logger.info("[BT] Device connected: %s", address)
                # Update state
                if address in self._known_devices:
                    self._known_devices[address].connected = True
                    self._connected_device = self._known_devices[address]
                self._set_state(BTState.CONNECTED)

                # Cancel reconnect task
                if address in self._reconnect_tasks:
                    self._reconnect_tasks[address].cancel()
                    del self._reconnect_tasks[address]
            else:
                logger.info("[BT] Device disconnected: %s", address)
                if address in self._known_devices:
                    self._known_devices[address].connected = False
                if self._connected_device and self._connected_device.address == address:
                    self._connected_device = None
                self._set_state(BTState.DISCONNECTED)

                # Start reconnect for trusted devices
                if address in self._known_devices and self._known_devices[address].trusted:
                    self._start_reconnect(address)

                if self.on_disconnect:
                    self._safe_callback(self.on_disconnect, address)

        # Track newly discovered devices
        if "Name" in changed or "RSSI" in changed:
            name = changed.get("Name", Variant("s", "Unknown")).value if "Name" in changed else None
            rssi = changed.get("RSSI", Variant("n", 0)).value if "RSSI" in changed else 0

            if address not in self._known_devices:
                info = BTDeviceInfo(address=address, name=name or "Unknown", rssi=rssi)
                self._known_devices[address] = info
                if self.on_device_found:
                    self._safe_callback(self.on_device_found, info)
            else:
                if name:
                    self._known_devices[address].name = name
                if rssi:
                    self._known_devices[address].rssi = rssi

    # ------------------------------------------------------------------
    # Internal: reconnect
    # ------------------------------------------------------------------

    def _start_reconnect(self, address: str) -> None:
        """Start an exponential-backoff reconnect loop for a device."""
        if address in self._reconnect_tasks:
            return  # Already reconnecting

        task = asyncio.ensure_future(self._reconnect_loop(address))
        self._reconnect_tasks[address] = task

    async def _reconnect_loop(self, address: str) -> None:
        """Persistent reconnect with exponential backoff."""
        backoff = self.RECONNECT_INTERVAL
        logger.info("[BT] Starting reconnect loop for %s", address)

        while self._running:
            try:
                await asyncio.sleep(backoff)
                if not self._running:
                    break

                success = await self.pair_and_connect(address)
                if success:
                    logger.info("[BT] Reconnected to %s", address)
                    return
            except asyncio.CancelledError:
                return
            except Exception as exc:
                logger.debug("[BT] Reconnect attempt failed for %s: %s", address, exc)

            backoff = min(backoff * 1.5, self.RECONNECT_MAX_BACKOFF)

    async def _reconnect_trusted(self) -> None:
        """On startup, try reconnecting all trusted audio devices."""
        try:
            devices = await self._enumerate_devices()
            for dev in devices:
                if dev.trusted and dev.is_audio and not dev.connected:
                    logger.info("[BT] Attempting reconnect to trusted device: %s (%s)",
                                dev.name, dev.address)
                    self._start_reconnect(dev.address)
        except Exception as exc:
            logger.error("[BT] Failed to enumerate trusted devices: %s", exc)

    # ------------------------------------------------------------------
    # Internal: device enumeration
    # ------------------------------------------------------------------

    async def _enumerate_devices(self) -> list[BTDeviceInfo]:
        """List all known BlueZ devices via ObjectManager."""
        if not self._bus:
            return []

        devices = []
        try:
            introspection = await self._bus.introspect(_BLUEZ_SERVICE, "/")
            proxy = self._bus.get_proxy_object(
                _BLUEZ_SERVICE, "/", introspection
            )
            obj_mgr = proxy.get_interface(_OBJECT_MANAGER_IFACE)
            objects = await obj_mgr.call_get_managed_objects()

            for path, interfaces in objects.items():
                if _DEVICE_IFACE not in interfaces:
                    continue
                props = interfaces[_DEVICE_IFACE]
                info = self._parse_device_props(path, props)
                if info:
                    devices.append(info)
                    self._known_devices[info.address] = info

        except Exception as exc:
            logger.error("[BT] enumerate_devices error: %s", exc)

        return devices

    async def _get_device_info(self, device_path: str) -> BTDeviceInfo | None:
        """Fetch device properties for a specific D-Bus path."""
        if not self._bus:
            return None
        try:
            introspection = await self._bus.introspect(_BLUEZ_SERVICE, device_path)
            proxy = self._bus.get_proxy_object(
                _BLUEZ_SERVICE, device_path, introspection
            )
            props = proxy.get_interface(_PROPERTIES_IFACE)

            address = (await props.call_get(_DEVICE_IFACE, "Address")).value
            name = (await props.call_get(_DEVICE_IFACE, "Name")).value
            paired = (await props.call_get(_DEVICE_IFACE, "Paired")).value
            trusted = (await props.call_get(_DEVICE_IFACE, "Trusted")).value
            connected = (await props.call_get(_DEVICE_IFACE, "Connected")).value

            try:
                uuids = (await props.call_get(_DEVICE_IFACE, "UUIDs")).value
            except Exception:
                uuids = []

            try:
                rssi = (await props.call_get(_DEVICE_IFACE, "RSSI")).value
            except Exception:
                rssi = 0

            return BTDeviceInfo(
                address=address,
                name=name,
                rssi=rssi,
                paired=paired,
                trusted=trusted,
                connected=connected,
                uuids=list(uuids) if uuids else [],
            )
        except Exception as exc:
            logger.debug("[BT] get_device_info failed for %s: %s", device_path, exc)
            return None

    @staticmethod
    def _parse_device_props(path: str, props: dict) -> BTDeviceInfo | None:
        """Parse D-Bus device properties into BTDeviceInfo."""
        try:
            address = props.get("Address", Variant("s", "")).value
            if not address:
                return None

            name = props.get("Name", Variant("s", "Unknown")).value
            paired = props.get("Paired", Variant("b", False)).value
            trusted = props.get("Trusted", Variant("b", False)).value
            connected = props.get("Connected", Variant("b", False)).value
            rssi = props.get("RSSI", Variant("n", 0)).value
            uuids_raw = props.get("UUIDs", Variant("as", [])).value
            icon = props.get("Icon", Variant("s", "")).value

            return BTDeviceInfo(
                address=address,
                name=name,
                rssi=rssi,
                paired=paired,
                trusted=trusted,
                connected=connected,
                uuids=list(uuids_raw) if uuids_raw else [],
                icon=icon,
            )
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Internal: state management
    # ------------------------------------------------------------------

    def _set_state(self, new_state: BTState) -> None:
        """Update connection state and fire callback."""
        old = self._state
        self._state = new_state
        if old != new_state:
            logger.info("[BT] State: %s -> %s", old.value, new_state.value)
            if self.on_state_change:
                try:
                    result = self.on_state_change(old, new_state)
                    if asyncio.iscoroutine(result):
                        asyncio.ensure_future(result)
                except Exception as exc:
                    logger.error("[BT] on_state_change callback error: %s", exc)


# ------------------------------------------------------------------
# Singleton accessor
# ------------------------------------------------------------------

_instance: BTService | None = None


def get_bt_service() -> BTService:
    """Get or create the singleton BTService instance."""
    global _instance
    if _instance is None:
        _instance = BTService()
    return _instance
