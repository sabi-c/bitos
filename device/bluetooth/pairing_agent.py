"""BlueZ pairing agent for LESC passkey flow with desktop mock fallback."""
from __future__ import annotations

import logging

try:
    import dbus  # type: ignore
    import dbus.service  # type: ignore

    _DBUS_AVAILABLE = True
except ImportError:  # pragma: no cover
    dbus = None
    _DBUS_AVAILABLE = False


AGENT_INTERFACE = "org.bluez.Agent1"


if _DBUS_AVAILABLE:

    class BitosPairingAgent(dbus.service.Object):
        """BlueZ pairing agent implementing LESC Passkey Entry."""

        CAPABILITY = "DisplayYesNo"

        def __init__(self, bus, path: str, on_show_passkey, on_pairing_complete):
            super().__init__(bus, path)
            self._on_show_passkey = on_show_passkey
            self._on_pairing_complete = on_pairing_complete

        @dbus.service.method(AGENT_INTERFACE, in_signature="ou")
        def DisplayPasskey(self, device, passkey):
            _ = device
            code = str(int(passkey)).zfill(6)
            self._on_show_passkey(code)

        @dbus.service.method(AGENT_INTERFACE, in_signature="ou")
        def RequestConfirmation(self, device, passkey):
            _ = (device, passkey)
            self._on_pairing_complete(True)

        @dbus.service.method(AGENT_INTERFACE)
        def Cancel(self):
            self._on_pairing_complete(False)

else:

    class BitosPairingAgent:
        """Mock-compatible placeholder when dbus is unavailable."""

        CAPABILITY = "DisplayYesNo"

        def __init__(self, _bus=None, _path: str = "/com/bitos/Agent", on_show_passkey=None, on_pairing_complete=None):
            self._on_show_passkey = on_show_passkey or (lambda _code: None)
            self._on_pairing_complete = on_pairing_complete or (lambda _ok: None)

        def DisplayPasskey(self, device, passkey):
            _ = device
            code = str(int(passkey)).zfill(6)
            logging.info("[BLE][MOCK] DisplayPasskey %s", code)
            self._on_show_passkey(code)

        def RequestConfirmation(self, device, passkey):
            _ = (device, passkey)
            logging.info("[BLE][MOCK] RequestConfirmation")
            self._on_pairing_complete(True)

        def Cancel(self):
            logging.info("[BLE][MOCK] Cancel")
            self._on_pairing_complete(False)


class MockPairingAgent:
    """Explicit mock pairing agent for tests and desktop runtime."""

    CAPABILITY = "DisplayYesNo"

    def __init__(self, on_show_passkey, on_pairing_complete):
        self._on_show_passkey = on_show_passkey
        self._on_pairing_complete = on_pairing_complete

    def DisplayPasskey(self, device, passkey):
        _ = device
        code = str(int(passkey)).zfill(6)
        logging.info("[BLE][MOCK] DisplayPasskey %s", code)
        self._on_show_passkey(code)

    def RequestConfirmation(self, device, passkey):
        _ = (device, passkey)
        logging.info("[BLE][MOCK] RequestConfirmation")
        self._on_pairing_complete(True)

    def Cancel(self):
        logging.info("[BLE][MOCK] Cancel")
        self._on_pairing_complete(False)
