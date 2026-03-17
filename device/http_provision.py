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
    device_status_fn: Callable | None = None
    device_info_fn: Callable | None = None
    keyboard_input_fn: Callable | None = None

    def log_message(self, fmt, *args):
        logger.debug("[HTTP-Provision] " + fmt, *args)

    def _cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

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


class ProvisioningServer:
    """Lightweight HTTP server for companion WiFi fallback."""

    def __init__(
        self,
        auth_manager=None,
        on_wifi_config: Callable | None = None,
        wifi_status_fn: Callable | None = None,
        device_status_fn: Callable | None = None,
        device_info_fn: Callable | None = None,
        on_keyboard_input: Callable | None = None,
        port: int = _DEFAULT_PORT,
    ):
        self._port = port
        self._auth_manager = auth_manager
        self._on_wifi_config = on_wifi_config
        self._wifi_status_fn = wifi_status_fn
        self._device_status_fn = device_status_fn
        self._device_info_fn = device_info_fn
        self._on_keyboard_input = on_keyboard_input
        self._server: HTTPServer | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Start the HTTP provisioning server in a background thread."""
        # Inject dependencies into the handler class
        ProvisioningHandler.auth_manager = self._auth_manager
        ProvisioningHandler.wifi_config_fn = self._on_wifi_config
        ProvisioningHandler.wifi_status_fn = self._wifi_status_fn
        ProvisioningHandler.device_status_fn = self._device_status_fn
        ProvisioningHandler.device_info_fn = self._device_info_fn
        ProvisioningHandler.keyboard_input_fn = self._on_keyboard_input

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
