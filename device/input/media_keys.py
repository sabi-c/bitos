"""AVRCP / Bluetooth media key listener for BITOS.

Captures media key events (play/pause, next, prev) from connected
Bluetooth audio devices (AirPods, headphones) via evdev on Linux.

Falls back gracefully on macOS or when evdev is not installed.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Callable

logger = logging.getLogger(__name__)

# Optional evdev import — not available on macOS dev machines
try:
    import evdev
    import evdev.ecodes as ecodes
    _HAS_EVDEV = True
except ImportError:
    evdev = None  # type: ignore[assignment]
    ecodes = None  # type: ignore[assignment]
    _HAS_EVDEV = False

# How often to re-scan for BT input devices when none is found (seconds)
_DEVICE_SCAN_INTERVAL = 5.0

# Key code constants (duplicated so tests can reference without evdev)
KEY_PLAYPAUSE = 164
KEY_NEXTSONG = 163
KEY_PREVIOUSSONG = 165
KEY_STOPCD = 166
KEY_PLAYCD = 200
KEY_PAUSECD = 201


# Default mapping: media key action name -> ButtonEvent name
# These map to the same action names the button handler emits,
# so they flow through the same _on_button() dispatch in main.py.
MEDIA_KEY_MAP: dict[str, str] = {
    "play_pause": "toggle_agent",   # single tap on AirPods -> toggle agent listening
    "next": "next_item",            # double tap -> next item/track
    "prev": "prev_item",            # triple tap -> previous item/track
}


class MediaKeyListener:
    """Listen for AVRCP media key events from Bluetooth input devices.

    Uses evdev to read KEY_PLAYPAUSE, KEY_NEXTSONG, KEY_PREVIOUSSONG
    from the AVRCP input device that BlueZ creates when a BT audio
    device is connected.

    Parameters
    ----------
    on_play_pause : callable, optional
        Called when play/pause key is pressed.
    on_next : callable, optional
        Called when next-track key is pressed.
    on_prev : callable, optional
        Called when previous-track key is pressed.
    key_map : dict, optional
        Override the default MEDIA_KEY_MAP.
    """

    def __init__(
        self,
        on_play_pause: Callable[[], None] | None = None,
        on_next: Callable[[], None] | None = None,
        on_prev: Callable[[], None] | None = None,
        key_map: dict[str, str] | None = None,
    ):
        self._callbacks: dict[int, Callable[[], None] | None] = {}
        if on_play_pause is not None:
            self._callbacks[KEY_PLAYPAUSE] = on_play_pause
        if on_next is not None:
            self._callbacks[KEY_NEXTSONG] = on_next
        if on_prev is not None:
            self._callbacks[KEY_PREVIOUSSONG] = on_prev

        self._key_map = key_map or dict(MEDIA_KEY_MAP)
        self._thread: threading.Thread | None = None
        self._running = False
        self._device: object | None = None  # evdev.InputDevice when connected
        self._lock = threading.Lock()

    @property
    def available(self) -> bool:
        """True if evdev is installed and media key listening is possible."""
        return _HAS_EVDEV

    @property
    def connected(self) -> bool:
        """True if currently reading from a BT input device."""
        return self._device is not None

    @property
    def key_map(self) -> dict[str, str]:
        """Current media key -> action mapping."""
        return dict(self._key_map)

    def start(self) -> None:
        """Start the background listener thread.

        Safe to call even if evdev is not available (logs and returns).
        """
        if not _HAS_EVDEV:
            logger.info("[MEDIA-KEYS] evdev not available — media key listener disabled")
            return

        if self._running:
            logger.debug("[MEDIA-KEYS] already running")
            return

        self._running = True
        self._thread = threading.Thread(
            target=self._run_loop,
            name="media-key-listener",
            daemon=True,
        )
        self._thread.start()
        logger.info("[MEDIA-KEYS] listener started")

    def stop(self) -> None:
        """Stop the background listener thread."""
        self._running = False
        # Close the device to unblock the read
        with self._lock:
            if self._device is not None and hasattr(self._device, "close"):
                try:
                    self._device.close()
                except Exception:
                    pass
                self._device = None

        if self._thread is not None:
            self._thread.join(timeout=3.0)
            self._thread = None
        logger.info("[MEDIA-KEYS] listener stopped")

    def _run_loop(self) -> None:
        """Main loop: find device, read events, reconnect on disconnect."""
        while self._running:
            try:
                dev = self._find_bt_input_device()
                if dev is None:
                    time.sleep(_DEVICE_SCAN_INTERVAL)
                    continue

                with self._lock:
                    self._device = dev
                logger.info(
                    "[MEDIA-KEYS] attached to device: %s (%s)",
                    dev.name, dev.path,
                )

                self._read_events(dev)

            except Exception as exc:
                logger.warning("[MEDIA-KEYS] loop error: %s", exc)
                with self._lock:
                    self._device = None
                if self._running:
                    time.sleep(_DEVICE_SCAN_INTERVAL)

        with self._lock:
            self._device = None

    def _read_events(self, dev) -> None:
        """Read key events from the evdev device until disconnected."""
        try:
            for event in dev.read_loop():
                if not self._running:
                    break
                # Only handle key-press events (value=1), not release (0) or repeat (2)
                if event.type == ecodes.EV_KEY and event.value == 1:
                    callback = self._callbacks.get(event.code)
                    if callback is not None:
                        try:
                            callback()
                        except Exception as exc:
                            logger.error(
                                "[MEDIA-KEYS] callback error for key %s: %s",
                                event.code, exc,
                            )
                    else:
                        logger.debug("[MEDIA-KEYS] unhandled key code: %s", event.code)
        except OSError:
            # Device disconnected
            logger.info("[MEDIA-KEYS] device disconnected")
        finally:
            with self._lock:
                self._device = None
            try:
                dev.close()
            except Exception:
                pass

    @staticmethod
    def _find_bt_input_device():
        """Find the AVRCP input device created by BlueZ.

        When a Bluetooth audio device connects, BlueZ creates an evdev
        input device for AVRCP transport controls. Its name typically
        contains "AVRCP" or the BT device name, and it lives under
        /dev/input/eventN.

        Returns an evdev.InputDevice or None.
        """
        if not _HAS_EVDEV:
            return None

        try:
            for path in evdev.list_devices():
                try:
                    dev = evdev.InputDevice(path)
                    name_lower = dev.name.lower()

                    # Match AVRCP transport or known BT audio patterns
                    if any(kw in name_lower for kw in ("avrcp", "bluetooth", "airpods")):
                        # Verify it can emit media key events
                        caps = dev.capabilities().get(ecodes.EV_KEY, [])
                        if KEY_PLAYPAUSE in caps or KEY_NEXTSONG in caps:
                            return dev
                        dev.close()
                    else:
                        dev.close()
                except Exception:
                    continue
        except Exception as exc:
            logger.debug("[MEDIA-KEYS] device scan error: %s", exc)

        return None
