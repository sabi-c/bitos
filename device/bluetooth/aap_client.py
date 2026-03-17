"""Apple Accessory Protocol (AAP) client for AirPods gesture detection.

Connects to AirPods via L2CAP socket on PSM 0x1001, performs the AAP
handshake, and parses incoming packets for stem press events, battery
status, and ear detection.

Protocol details reverse-engineered by the LibrePods project
(github.com/kavishdevar/librepods).

Falls back gracefully when bluetooth socket support is not available.
"""
from __future__ import annotations

import asyncio
import enum
import logging
import struct
from dataclasses import dataclass
from typing import Any, Callable, Awaitable

logger = logging.getLogger(__name__)

# Try importing bluetooth socket support
try:
    import socket as _socket
    # Check for Bluetooth protocol support
    _AF_BLUETOOTH = getattr(_socket, "AF_BLUETOOTH", None)
    _BTPROTO_L2CAP = getattr(_socket, "BTPROTO_L2CAP", None)
    _BT_AVAILABLE = _AF_BLUETOOTH is not None and _BTPROTO_L2CAP is not None
except ImportError:
    _BT_AVAILABLE = False
    _socket = None  # type: ignore[assignment]


# AAP Protocol constants
AAP_PSM = 0x1001  # L2CAP Protocol/Service Multiplexer for AAP

# Handshake packets (3-phase)
AAP_HANDSHAKE = bytes.fromhex("00000400010002000000000000000000")
AAP_SET_FEATURES = bytes.fromhex("040004004d00ff00000000000000")
AAP_REQUEST_NOTIFICATIONS = bytes.fromhex("040004000F00FFFFFFFF")

# Packet header identifiers
AAP_HEADER_BATTERY = bytes.fromhex("040004000400")
AAP_HEADER_EAR_DETECT = bytes.fromhex("040004000600")
AAP_HEADER_NOISE_CONTROL = bytes.fromhex("04000400090D")
AAP_HEADER_CONV_AWARENESS = bytes.fromhex("040004004B00")


class AAPPressType(enum.Enum):
    """AirPods stem press types from AAP protocol."""
    SINGLE = 0x05
    DOUBLE = 0x06
    TRIPLE = 0x07
    LONG = 0x08


class EarState(enum.Enum):
    """AirPods ear detection states."""
    IN_EAR = 0x00
    OUT_OF_EAR = 0x01
    IN_CASE = 0x02


class NoiseControlMode(enum.Enum):
    """AirPods noise control modes."""
    OFF = 0x01
    ANC = 0x02
    TRANSPARENCY = 0x03
    ADAPTIVE = 0x04


@dataclass
class AAPBatteryStatus:
    """Battery levels for AirPods components."""
    left: int = 0       # 0-100
    right: int = 0      # 0-100
    case: int = 0       # 0-100
    left_charging: bool = False
    right_charging: bool = False
    case_charging: bool = False


@dataclass
class AAPEarDetection:
    """Ear detection state for both pods."""
    primary: EarState = EarState.OUT_OF_EAR
    secondary: EarState = EarState.OUT_OF_EAR

    @property
    def both_in_ear(self) -> bool:
        return self.primary == EarState.IN_EAR and self.secondary == EarState.IN_EAR

    @property
    def both_out(self) -> bool:
        return (self.primary != EarState.IN_EAR and
                self.secondary != EarState.IN_EAR)


# Callback type alias
AAPEventCallback = Callable[..., Awaitable[None] | None]


class AAPClient:
    """AAP L2CAP client for AirPods feature access.

    Parses stem press events, battery status, ear detection, and
    noise control mode from the AAP packet stream.

    Usage:
        client = AAPClient()
        client.on_stem_press = handle_press
        client.on_battery = handle_battery
        await client.connect("AA:BB:CC:DD:EE:FF")
    """

    RECV_SIZE = 1024
    CONNECT_TIMEOUT = 10.0

    def __init__(self):
        self._sock: Any = None
        self._connected_mac: str | None = None
        self._running = False
        self._read_task: asyncio.Task | None = None

        # Latest known state
        self.battery = AAPBatteryStatus()
        self.ear_detection = AAPEarDetection()
        self.noise_control = NoiseControlMode.OFF

        # Event callbacks
        self.on_stem_press: AAPEventCallback | None = None
        self.on_battery: AAPEventCallback | None = None
        self.on_ear_detect: AAPEventCallback | None = None
        self.on_noise_control: AAPEventCallback | None = None

    @property
    def connected_mac(self) -> str | None:
        return self._connected_mac

    @property
    def is_connected(self) -> bool:
        return self._sock is not None and self._connected_mac is not None

    @property
    def is_available(self) -> bool:
        return _BT_AVAILABLE

    async def connect(self, mac: str) -> bool:
        """Connect to AirPods AAP service via L2CAP.

        Performs the 3-phase AAP handshake and starts the packet reader.
        Returns True on success.
        """
        if not _BT_AVAILABLE:
            logger.warning("[AAP] Bluetooth L2CAP not available on this platform")
            return False

        if self._connected_mac == mac and self._sock:
            logger.debug("[AAP] Already connected to %s", mac)
            return True

        # Disconnect any existing connection
        self.disconnect()

        try:
            logger.info("[AAP] Connecting to %s on PSM 0x%04X...", mac, AAP_PSM)

            # Create L2CAP socket
            sock = _socket.socket(
                _socket.AF_BLUETOOTH,
                _socket.SOCK_SEQPACKET,
                _socket.BTPROTO_L2CAP,
            )
            sock.setblocking(False)

            loop = asyncio.get_event_loop()

            # Connect with timeout
            try:
                await asyncio.wait_for(
                    loop.sock_connect(sock, (mac, AAP_PSM)),
                    timeout=self.CONNECT_TIMEOUT,
                )
            except asyncio.TimeoutError:
                logger.error("[AAP] Connection timeout to %s", mac)
                sock.close()
                return False

            self._sock = sock
            self._connected_mac = mac

            # Perform AAP handshake
            if not await self._handshake():
                logger.error("[AAP] Handshake failed with %s", mac)
                self.disconnect()
                return False

            # Start background packet reader
            self._running = True
            self._read_task = asyncio.ensure_future(self._read_loop())

            logger.info("[AAP] Connected and handshake complete with %s", mac)
            return True

        except Exception as exc:
            logger.error("[AAP] Connect failed for %s: %s", mac, exc)
            self.disconnect()
            return False

    def disconnect(self) -> None:
        """Disconnect from AirPods AAP service."""
        self._running = False

        if self._read_task:
            self._read_task.cancel()
            self._read_task = None

        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None

        mac = self._connected_mac
        self._connected_mac = None
        if mac:
            logger.info("[AAP] Disconnected from %s", mac)

    async def _handshake(self) -> bool:
        """Perform the 3-phase AAP handshake.

        Phase 1: HANDSHAKE -> HANDSHAKE_ACK
        Phase 2: SET_SPECIFIC_FEATURES -> FEATURES_ACK
        Phase 3: REQUEST_NOTIFICATIONS -> metadata
        """
        loop = asyncio.get_event_loop()

        try:
            # Phase 1: Handshake
            await loop.sock_sendall(self._sock, AAP_HANDSHAKE)
            ack1 = await asyncio.wait_for(
                loop.sock_recv(self._sock, 256), timeout=5.0
            )
            if not ack1:
                logger.error("[AAP] No handshake ACK received")
                return False
            logger.debug("[AAP] Handshake ACK: %s", ack1.hex())

            # Phase 2: Set features
            await loop.sock_sendall(self._sock, AAP_SET_FEATURES)
            ack2 = await asyncio.wait_for(
                loop.sock_recv(self._sock, 256), timeout=5.0
            )
            if not ack2:
                logger.error("[AAP] No features ACK received")
                return False
            logger.debug("[AAP] Features ACK: %s", ack2.hex())

            # Phase 3: Request notifications
            await loop.sock_sendall(self._sock, AAP_REQUEST_NOTIFICATIONS)
            # Initial metadata may come back — don't require it
            try:
                meta = await asyncio.wait_for(
                    loop.sock_recv(self._sock, 1024), timeout=3.0
                )
                logger.debug("[AAP] Initial metadata: %d bytes", len(meta))
            except asyncio.TimeoutError:
                logger.debug("[AAP] No initial metadata (OK)")

            return True

        except Exception as exc:
            logger.error("[AAP] Handshake error: %s", exc)
            return False

    async def _read_loop(self) -> None:
        """Background loop reading and parsing AAP packets."""
        loop = asyncio.get_event_loop()

        while self._running and self._sock:
            try:
                data = await loop.sock_recv(self._sock, self.RECV_SIZE)
                if not data:
                    logger.info("[AAP] Connection closed by remote")
                    break
                await self._parse_packet(data)
            except asyncio.CancelledError:
                break
            except OSError as exc:
                if self._running:
                    logger.error("[AAP] Read error: %s", exc)
                break
            except Exception as exc:
                logger.error("[AAP] Unexpected read error: %s", exc)
                continue

        # Clean up on exit
        if self._running:
            self._running = False
            logger.info("[AAP] Read loop ended, cleaning up")
            self.disconnect()

    async def _parse_packet(self, data: bytes) -> None:
        """Parse an AAP packet and dispatch events."""
        if len(data) < 6:
            return

        # Check packet header to determine type
        header = data[:6]

        if header == AAP_HEADER_BATTERY:
            self._parse_battery(data)
        elif header == AAP_HEADER_EAR_DETECT:
            self._parse_ear_detection(data)
        elif data[:5] == AAP_HEADER_NOISE_CONTROL[:5]:
            self._parse_noise_control(data)
        elif header == AAP_HEADER_CONV_AWARENESS:
            logger.debug("[AAP] Conversational awareness packet: %s", data.hex())
        else:
            # Check for stem press events in the data
            self._check_stem_press(data)

    def _parse_battery(self, data: bytes) -> None:
        """Parse battery status packet.

        Format: [header 6B] [count 1B] ([component 1B] 01 [level 1B] [status 1B] 01)...
        Components: 1=left, 2=right, 4=case
        """
        if len(data) < 7:
            return

        offset = 6
        count = data[offset]
        offset += 1

        for _ in range(count):
            if offset + 5 > len(data):
                break
            component = data[offset]
            # skip 0x01 byte
            level = data[offset + 2]
            status = data[offset + 3]
            # skip 0x01 byte
            offset += 5

            charging = bool(status & 0x01)

            if component == 0x01:  # Left
                self.battery.left = min(100, level)
                self.battery.left_charging = charging
            elif component == 0x02:  # Right
                self.battery.right = min(100, level)
                self.battery.right_charging = charging
            elif component == 0x04:  # Case
                self.battery.case = min(100, level)
                self.battery.case_charging = charging

        logger.debug("[AAP] Battery: L=%d%% R=%d%% C=%d%%",
                     self.battery.left, self.battery.right, self.battery.case)

        if self.on_battery:
            self._fire_callback(
                self.on_battery,
                self.battery.left, self.battery.right, self.battery.case
            )

    def _parse_ear_detection(self, data: bytes) -> None:
        """Parse ear detection packet.

        Format: [header 6B] [primary 1B] [secondary 1B]
        Values: 0x00=in ear, 0x01=out, 0x02=in case
        """
        if len(data) < 8:
            return

        try:
            primary = EarState(data[6])
        except ValueError:
            primary = EarState.OUT_OF_EAR

        try:
            secondary = EarState(data[7])
        except ValueError:
            secondary = EarState.OUT_OF_EAR

        self.ear_detection = AAPEarDetection(primary=primary, secondary=secondary)
        logger.debug("[AAP] Ears: primary=%s secondary=%s",
                     primary.name, secondary.name)

        if self.on_ear_detect:
            self._fire_callback(
                self.on_ear_detect,
                primary == EarState.IN_EAR,
                secondary == EarState.IN_EAR,
            )

    def _parse_noise_control(self, data: bytes) -> None:
        """Parse noise control mode packet.

        Format: [header ~6B] [mode 1B] 00 00 00
        """
        # Mode byte is typically at offset 6 or 7 depending on exact header
        for offset in (7, 6, 8):
            if offset < len(data):
                try:
                    mode = NoiseControlMode(data[offset])
                    self.noise_control = mode
                    logger.debug("[AAP] Noise control: %s", mode.name)
                    if self.on_noise_control:
                        self._fire_callback(self.on_noise_control, mode)
                    return
                except ValueError:
                    continue

    def _check_stem_press(self, data: bytes) -> None:
        """Scan packet data for stem press event bytes.

        Stem press identifiers from AAP protocol:
            0x05 = single press
            0x06 = double press
            0x07 = triple press
            0x08 = long press

        The exact packet format varies; we scan for these values
        in positions that are likely to contain the press type byte.
        """
        press_values = {
            0x05: AAPPressType.SINGLE,
            0x06: AAPPressType.DOUBLE,
            0x07: AAPPressType.TRIPLE,
            0x08: AAPPressType.LONG,
        }

        # Scan likely offsets for the press type byte
        # Based on LibrePods Android GestureDetector, the press type
        # appears in the AAP notification stream
        for offset in range(6, min(len(data), 20)):
            byte_val = data[offset]
            if byte_val in press_values:
                press_type = press_values[byte_val]
                logger.info("[AAP] Stem press detected: %s (byte 0x%02X at offset %d)",
                            press_type.name, byte_val, offset)
                if self.on_stem_press:
                    self._fire_callback(self.on_stem_press, press_type.value)
                return

    def _fire_callback(self, callback: AAPEventCallback, *args) -> None:
        """Fire callback, handling both sync and async variants."""
        try:
            result = callback(*args)
            if asyncio.iscoroutine(result):
                asyncio.ensure_future(result)
        except Exception as exc:
            logger.error("[AAP] Callback error: %s", exc)


# ------------------------------------------------------------------
# Module-level helpers
# ------------------------------------------------------------------

def press_type_name(value: int) -> str:
    """Convert AAP press type byte value to human-readable name."""
    try:
        return AAPPressType(value).name.lower()
    except ValueError:
        return f"unknown_0x{value:02x}"
