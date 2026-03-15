import threading
import time
import logging

logger = logging.getLogger(__name__)


class StatusPoller:
    """# WHY THIS EXISTS: updates StatusState every 30s without blocking render."""

    def __init__(self, state, api_client, battery_monitor, network_manager, led=None):
        self._state = state
        self._api = api_client
        self._battery = battery_monitor
        self._network = network_manager
        self._led = led
        self._stop = threading.Event()

    def start(self):
        threading.Thread(target=self._loop, daemon=True).start()

    def stop(self):
        self._stop.set()

    def _loop(self):
        self._poll()  # immediate first poll
        while not self._stop.wait(30):
            self._poll()

    def _poll(self):
        try:
            batt = self._battery.get_status()
            online = self._api.health(timeout=2)
            conn = self._network.get_connectivity_symbol()
            integrations = self._api.get_integrations_status() if hasattr(self._api, "get_integrations_status") else {}
            msgs_unread = int((integrations.get("bluebubbles") or {}).get("unread", 0))
            gmail_unread = int((integrations.get("gmail") or {}).get("unread", 0))
            battery_text = self._battery.get_status_text() if hasattr(self._battery, "get_status_text") else f"{int(batt['pct'])}%"
            self._state.update(
                battery_pct=batt["pct"],
                battery_text=battery_text,
                charging=batt["charging"],
                ai_online=online,
                wifi_symbol=conn,
                msgs_unread=msgs_unread,
                gmail_unread=gmail_unread,
            )
            if hasattr(self, "_led") and self._led:
                if hasattr(self._battery, "is_low") and self._battery.is_low(5):
                    self._led.critical_battery()
                elif hasattr(self._battery, "is_low") and self._battery.is_low(15):
                    self._led.low_battery()
                elif batt.get("charging"):
                    self._led.connected()
                else:
                    self._led.idle()
        except Exception as e:
            logger.warning("status_poll_failed error=%s", e)

        try:
            integrations = self._api.get_integration_status()
            self._state.update(
                imessage_status=integrations.get("imessage", {}).get("status", "unknown"),
                imessage_unread=integrations.get("imessage", {}).get("unread", 0),
            )
        except Exception:
            pass
