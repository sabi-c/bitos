"""HTTP provisioning server — WiFi fallback for companion app.

Exposes the same provisioning operations as BLE characteristics over HTTP,
so the companion app can configure the device over the local network when
Web Bluetooth is unavailable (e.g., iOS Safari).

Runs on port 8080 in a daemon thread.  All endpoints mirror the BLE
characteristic read/write semantics.
"""
from __future__ import annotations

import json
import logging
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Any, Callable

logger = logging.getLogger(__name__)

_DEFAULT_PORT = int(os.environ.get("BITOS_PROVISION_PORT", "8080"))


class ProvisioningHandler(BaseHTTPRequestHandler):
    """Handles HTTP requests that mirror BLE characteristic operations."""

    # Injected by ProvisioningServer before serve_forever()
    auth_manager: Any = None
    wifi_config_fn: Callable | None = None
    wifi_status_fn: Callable | None = None
    wifi_remove_fn: Callable | None = None
    wifi_list_fn: Callable | None = None
    device_status_fn: Callable | None = None
    device_info_fn: Callable | None = None
    keyboard_input_fn: Callable | None = None
    repository: Any = None  # DeviceRepository instance

    def log_message(self, fmt, *args):
        logger.debug("[HTTP-Provision] " + fmt, *args)

    def _cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Max-Age", "3600")

    def _json_response(self, status: int, data: dict):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self._cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8"))

    # -- CORS preflight --

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors_headers()
        self.end_headers()

    # -- Routes --

    def do_GET(self):
        path = self.path.split("?")[0].rstrip("/")

        if path == "/api/health":
            self._json_response(200, {"status": "ok", "service": "bitos-provision"})

        elif path == "/api/ble/challenge":
            if self.auth_manager is None:
                self._json_response(503, {"error": "auth not configured"})
                return
            try:
                challenge = self.auth_manager.get_challenge()
                self._json_response(200, challenge)
            except Exception as exc:
                self._json_response(500, {"error": str(exc)})

        elif path == "/api/wifi/status":
            if self.wifi_status_fn is not None:
                try:
                    status = self.wifi_status_fn()
                    self._json_response(200, status)
                except Exception as exc:
                    self._json_response(500, {"error": str(exc)})
            else:
                self._json_response(200, {
                    "connected": False, "ssid": "", "signal": "weak",
                    "ip": "", "last_error": None,
                })

        elif path == "/api/device/status":
            if self.device_status_fn is not None:
                try:
                    status = self.device_status_fn()
                    self._json_response(200, status)
                except Exception as exc:
                    self._json_response(500, {"error": str(exc)})
            else:
                self._json_response(200, {})

        elif path == "/api/device/info":
            if self.device_info_fn is not None:
                try:
                    info = self.device_info_fn()
                    self._json_response(200, info)
                except Exception as exc:
                    self._json_response(500, {"error": str(exc)})
            else:
                self._json_response(200, {
                    "serial": "UNKNOWN", "model": "BITOS-1",
                    "ble_protocol_version": 1,
                })

        elif path == "/api/settings":
            # Read all device settings as a flat dict
            if self.repository is None:
                self._json_response(503, {"error": "repository not configured"})
                return
            try:
                self._json_response(200, _read_all_settings(self.repository))
            except Exception as exc:
                self._json_response(500, {"error": str(exc)})

        elif path.startswith("/api/settings/"):
            # Read a single setting: GET /api/settings/<key>
            key = path[len("/api/settings/"):]
            if not key:
                self._json_response(400, {"error": "key required"})
                return
            if self.repository is None:
                self._json_response(503, {"error": "repository not configured"})
                return
            try:
                value = self.repository.get_setting(key, default=None)
                self._json_response(200, {"key": key, "value": value})
            except Exception as exc:
                self._json_response(500, {"error": str(exc)})

        elif path == "/api/wifi/networks":
            # List saved WiFi networks
            if self.wifi_list_fn is not None:
                try:
                    networks = self.wifi_list_fn()
                    self._json_response(200, {"networks": networks})
                except Exception as exc:
                    self._json_response(500, {"error": str(exc)})
            else:
                self._json_response(200, {"networks": []})

        elif path == "/api/settings/schema":
            # Return setting definitions with types/defaults for UI generation
            schema = []
            for key, default in _KNOWN_SETTINGS:
                entry = {"key": key, "default": default}
                if isinstance(default, bool):
                    entry["type"] = "bool"
                elif isinstance(default, int):
                    entry["type"] = "int"
                elif isinstance(default, float):
                    entry["type"] = "float"
                else:
                    entry["type"] = "str"
                schema.append(entry)
            self._json_response(200, {"settings": schema})

        else:
            self._json_response(404, {"error": "not found"})

    def do_PUT(self):
        path = self.path.split("?")[0].rstrip("/")

        if path == "/api/settings":
            # Write one or more settings: { key: value } or { key: "k", value: "v" }
            if self.repository is None:
                self._json_response(503, {"error": "repository not configured"})
                return
            try:
                body = self._read_body()

                # Support two formats:
                # 1. { "key": "setting_name", "value": <val> }  (single setting)
                # 2. { "setting1": val1, "setting2": val2, ... } (batch)
                if "key" in body and "value" in body:
                    k = str(body["key"])
                    if k in _BLOCKED_SETTINGS:
                        self._json_response(403, {"error": f"setting '{k}' cannot be changed via API"})
                        return
                    self.repository.set_setting(k, body["value"])
                    _apply_side_effects(k, body["value"])
                    self._json_response(200, {"ok": True, "key": k})
                else:
                    changed = []
                    for k, v in body.items():
                        if k in _BLOCKED_SETTINGS:
                            continue
                        self.repository.set_setting(str(k), v)
                        _apply_side_effects(str(k), v)
                        changed.append(str(k))
                    self._json_response(200, {"ok": True, "changed": changed})
            except Exception as exc:
                self._json_response(500, {"error": str(exc)})

        else:
            self._json_response(404, {"error": "not found"})

    def do_POST(self):
        path = self.path.split("?")[0].rstrip("/")

        if path == "/api/ble/auth":
            if self.auth_manager is None:
                self._json_response(503, {"error": "auth not configured"})
                return
            try:
                body = self._read_body()
                nonce = str(body.get("nonce", ""))
                response_hex = str(body.get("response", ""))
                pairing_session = body.get("pairing_session")
                pairing_token = body.get("pairing_token")

                token = self.auth_manager.verify_response(
                    client_addr="http-companion",
                    nonce=nonce,
                    response_hex=response_hex,
                    pairing_session_id=pairing_session,
                    pairing_token=pairing_token,
                )
                self._json_response(200, {"session_token": token})
            except Exception as exc:
                self._json_response(401, {"error": str(exc)})

        elif path == "/api/wifi/config":
            try:
                body = self._read_body()
                session_token = str(body.get("session_token", ""))
                if self.auth_manager and not self.auth_manager.validate_session_token(session_token):
                    self._json_response(401, {"error": "INVALID_SESSION_TOKEN"})
                    return

                ssid = str(body.get("ssid", "")).strip()
                encrypted_password = str(body.get("password", ""))
                security = str(body.get("security", "WPA2")).upper()
                priority = int(body.get("priority", 100))

                if not ssid:
                    self._json_response(400, {"error": "SSID_REQUIRED"})
                    return

                if security == "OPEN":
                    password = ""
                else:
                    from bluetooth.crypto import decrypt_wifi_password
                    ble_secret = os.environ.get("BITOS_BLE_SECRET", "")
                    password = decrypt_wifi_password(
                        encrypted_password,
                        session_token=session_token,
                        ble_secret_hex=ble_secret,
                    )

                if self.wifi_config_fn is not None:
                    ok = bool(self.wifi_config_fn(ssid, password, security, priority))
                else:
                    ok = False

                self._json_response(200, {"ok": ok, "ssid": ssid})
            except Exception as exc:
                self._json_response(500, {"error": str(exc)})

        elif path == "/api/wifi/remove":
            try:
                body = self._read_body()
                ssid = str(body.get("ssid", "")).strip()
                if not ssid:
                    self._json_response(400, {"error": "SSID_REQUIRED"})
                    return
                if self.wifi_remove_fn is not None:
                    ok = bool(self.wifi_remove_fn(ssid))
                else:
                    ok = False
                self._json_response(200, {"ok": ok, "ssid": ssid})
            except Exception as exc:
                self._json_response(500, {"error": str(exc)})

        elif path == "/api/wifi/test":
            # Test internet connectivity from the device
            try:
                import urllib.request
                start = __import__("time").monotonic()
                req = urllib.request.Request(
                    "http://connectivitycheck.gstatic.com/generate_204",
                    method="GET",
                )
                with urllib.request.urlopen(req, timeout=5) as resp:
                    latency = round((__import__("time").monotonic() - start) * 1000)
                    self._json_response(200, {
                        "ok": resp.status == 204 or resp.status == 200,
                        "latency_ms": latency,
                    })
            except Exception as exc:
                self._json_response(200, {"ok": False, "error": str(exc)})

        elif path == "/api/keyboard/input":
            try:
                body = self._read_body()
                session_token = str(body.get("session_token", ""))
                if self.auth_manager and not self.auth_manager.validate_session_token(session_token):
                    self._json_response(401, {"error": "INVALID_SESSION_TOKEN"})
                    return

                text = str(body.get("text", ""))
                target = str(body.get("target", "any"))
                if self.keyboard_input_fn is not None:
                    ok = bool(self.keyboard_input_fn(target, text, 0))
                else:
                    ok = False
                self._json_response(200, {"ok": ok})
            except Exception as exc:
                self._json_response(500, {"error": str(exc)})

        else:
            self._json_response(404, {"error": "not found"})


# -- Settings helpers --

# Settings that cannot be written via the HTTP API (security-sensitive).
_BLOCKED_SETTINGS = frozenset({"device_pin"})

# All known setting keys and their types/defaults for bulk reads.
_KNOWN_SETTINGS: list[tuple[str, Any]] = [
    # Voice / audio
    ("voice_mode", "auto"),
    ("volume", 100),
    ("tts_engine", "auto"),
    ("voice_enabled", False),
    ("recording_quality", "medium"),
    ("audio_feedback", True),
    # AI / agent
    ("agent_mode", "producer"),
    ("ai_model", ""),
    ("extended_thinking", False),
    ("web_search", True),
    ("memory", True),
    ("meta_prompt", "default assistant"),
    # Display
    ("text_speed", "normal"),
    ("font_family", "press_start_2p"),
    ("font_scale", 1.0),
    ("screen_brightness", 80),
    ("screen_timeout", 30),
    # Sleep / power
    ("sleep_timeout_seconds", 60),
    ("safe_shutdown_pct", 5),
    # Notifications
    ("notif_reminders", True),
    ("notif_proactive", True),
    ("notif_system", True),
    ("notif_sound", True),
    ("quiet_hours_start", "22:00"),
    ("quiet_hours_end", "07:00"),
    # Heartbeat
    ("heartbeat_enabled", True),
    ("heartbeat_interval", 60),
    ("morning_greeting_time", "08:00"),
    ("evening_checkin_time", "21:00"),
    ("idle_checkins", True),
    # Sub-agents
    ("agent_gesture_annotator", True),
    ("agent_idle_director", True),
    ("agent_inner_thoughts", True),
    ("agent_memory_consolidator", True),
    ("consolidation_interval", 8),
    # Device identity
    ("device_name", "BITOS"),
    # Location
    ("geolocation", ""),
    ("timezone", ""),
    # Wake word
    ("wake_word_enabled", False),
    ("wake_word_phrase", "hey bitos"),
    ("wake_word_sensitivity", 0.5),
]


def _read_all_settings(repo: Any) -> dict:
    """Read all known settings from the repository into a flat dict."""
    result = {}
    for key, default in _KNOWN_SETTINGS:
        result[key] = repo.get_setting(key, default=default)
    return result


def _apply_side_effects(key: str, value: Any) -> None:
    """Apply immediate side effects for certain setting changes."""
    try:
        if key == "volume":
            from audio.player import AudioPlayer
            player = AudioPlayer()
            player.set_volume(max(0, min(100, int(value))) / 100.0)
    except Exception as exc:
        logger.debug("[HTTP-Provision] side-effect for %s failed: %s", key, exc)


class ProvisioningServer:
    """Lightweight HTTP server for companion WiFi fallback."""

    def __init__(
        self,
        auth_manager=None,
        on_wifi_config: Callable | None = None,
        wifi_status_fn: Callable | None = None,
        wifi_remove_fn: Callable | None = None,
        wifi_list_fn: Callable | None = None,
        device_status_fn: Callable | None = None,
        device_info_fn: Callable | None = None,
        on_keyboard_input: Callable | None = None,
        repository: Any = None,
        port: int = _DEFAULT_PORT,
    ):
        self._port = port
        self._auth_manager = auth_manager
        self._on_wifi_config = on_wifi_config
        self._wifi_status_fn = wifi_status_fn
        self._wifi_remove_fn = wifi_remove_fn
        self._wifi_list_fn = wifi_list_fn
        self._device_status_fn = device_status_fn
        self._device_info_fn = device_info_fn
        self._on_keyboard_input = on_keyboard_input
        self._repository = repository
        self._server: HTTPServer | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Start the HTTP provisioning server in a background thread."""
        # Inject dependencies into the handler class
        ProvisioningHandler.auth_manager = self._auth_manager
        ProvisioningHandler.wifi_config_fn = self._on_wifi_config
        ProvisioningHandler.wifi_status_fn = self._wifi_status_fn
        ProvisioningHandler.wifi_remove_fn = self._wifi_remove_fn
        ProvisioningHandler.wifi_list_fn = self._wifi_list_fn
        ProvisioningHandler.device_status_fn = self._device_status_fn
        ProvisioningHandler.device_info_fn = self._device_info_fn
        ProvisioningHandler.keyboard_input_fn = self._on_keyboard_input
        ProvisioningHandler.repository = self._repository

        try:
            self._server = HTTPServer(("0.0.0.0", self._port), ProvisioningHandler)
        except OSError as exc:
            logger.error("[HTTP-Provision] Failed to bind port %d: %s", self._port, exc)
            return

        self._thread = threading.Thread(
            target=self._server.serve_forever,
            name="http-provision",
            daemon=True,
        )
        self._thread.start()
        logger.info("[HTTP-Provision] Listening on port %d", self._port)

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server = None
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        logger.info("[HTTP-Provision] Stopped")
