"""BITOS Device main entry point."""
import json
import logging
import logging.handlers
import os
import sys
import threading

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def _configure_device_logging():
    """Structured logging with file rotation for remote Pi debugging."""
    log_dir = os.environ.get("BITOS_LOG_DIR", "/var/log/bitos")
    try:
        os.makedirs(log_dir, exist_ok=True)
    except PermissionError:
        # Fall back to local dir if /var/log not writable
        log_dir = os.path.join(os.path.dirname(__file__), "logs")
        os.makedirs(log_dir, exist_ok=True)

    fmt = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    console = logging.StreamHandler(sys.stderr)
    console.setFormatter(fmt)

    file_handler = logging.handlers.RotatingFileHandler(
        os.path.join(log_dir, "device.log"),
        maxBytes=2 * 1024 * 1024,  # 2MB — constrained for Pi SD card
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(console)
    root.addHandler(file_handler)

    # Quiet noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("pygame").setLevel(logging.WARNING)


_configure_device_logging()

import time

import pygame

from display.corner_mask import CornerMask
from display.driver import create_driver
import display.tokens as tokens
from display.tokens import FPS
from input.handler import ButtonEvent, create_button_handler
from notifications import NotificationPoller
from overlays import AgentOverlay, NotificationQueue, NotificationToast, QROverlay
from overlays.notification_banner import NotificationBanner
from bluetooth import AuthManager, get_gatt_server
from bluetooth.characteristics import DeviceInfoCharacteristic, DeviceStatusCharacteristic, WiFiStatusCharacteristic
from bluetooth.constants import build_setup_url
from bluetooth.network_manager import NetworkPriorityManager
from bluetooth.wifi_manager import WiFiManager
from http_provision import ProvisioningServer
from ble.ble_service import get_ble_service
from ble.pairing_manager import PairingManager
from audio.pipeline import get_audio_pipeline
from audio.recording_adapter import RecordingAdapter
from hardware import StatusPoller, StatusState, SystemMonitor
from power.battery import BatteryMonitor
from power.idle import IdleManager
from power.leds import LEDController
from power.manager import PowerManager
from screens.manager import ScreenManager
from screens.boot import BootScreen
from screens.lock import LockScreen
from ui.composite_screen import CompositeScreen
from ui.panel_registry import create_right_panels
from screens.panels.chat import ChatPanel
from screens.panels.focus import FocusPanel
from screens.panels.tasks import TasksPanel
from screens.panels.captures import CapturesPanel
from screens.panels.messages import MessagesPanel
from screens.panels.mail import MailPanel
from screens.panels.notifications import NotificationsPanel
from screens.panels.activity import ActivityPanel
from screens.panels.agent_tasks import AgentTasksPanel
from screens.panels.files_browser import FilesBrowserPanel
from screens.panels.markdown_viewer import MarkdownViewerPanel
from screens.panels.chat_history import ChatHistoryPanel
from screens.panels.settings import SettingsPanel, ModelPickerPanel, AgentModePanel, SleepTimerPanel, AboutPanel, BatteryPanel, DevPanel, FontPickerPanel, TextSpeedPanel
from screens.panels.bluetooth import BluetoothPanel
from screens.panels.bt_audio import BluetoothAudioPanel
from screens.panels.change_pin import ChangePinPanel
from screens.subscreens.integration_detail import IntegrationDetailPanel
from overlays.power import PowerOverlay

from client.api import BackendClient
from network.geolocation import detect_and_set_timezone
from storage.repository import DeviceRepository
from integrations.adapters import create_runtime_adapter
from integrations.queue import OutboundCommandQueue
from integrations.runtime import OutboundWorkerRuntimeLoop
from integrations.worker import OutboundCommandWorker
from notifications.router import NotificationRouter
from notifications.ws_client import DeviceWSClient
logger = logging.getLogger(__name__)


def _read_device_serial() -> str:
    try:
        with open("/proc/cpuinfo", "r", encoding="utf-8") as f:
            for line in f:
                if line.strip().startswith("Serial"):
                    parts = line.strip().split(":", 1)
                    if len(parts) == 2 and parts[1].strip():
                        return parts[1].strip()
    except FileNotFoundError:
        pass
    return "desktop-sim"


def _restore_state() -> dict | None:
    path = "/tmp/bitos_state.json"
    try:
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            state = json.load(f)
        age = time.time() - state.get("timestamp", 0)
        if age > 300:
            return None
        os.remove(path)
        return state
    except Exception:
        return None


def _run_startup_health_check(client: BackendClient, repository: DeviceRepository, startup_health: dict) -> dict:
    startup_health["backend"] = client.health(timeout=2.0)
    try:
        repository.get_setting("agent_mode", "normal")
        startup_health["database"] = True
    except Exception:
        startup_health["database"] = False
    startup_health["api_key"] = bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("OPENAI_API_KEY"))
    return startup_health


def _handle_main_loop_crash(error: Exception, crash_path: str = "/tmp/bitos_crash.json"):
    logger.critical(
        "main_loop_crash",
        extra={"error": str(error), "type": type(error).__name__},
        exc_info=True,
    )
    with open(crash_path, "w", encoding="utf-8") as f:
        json.dump({"error": str(error), "timestamp": time.time()}, f)


def _cancel_inflight_voice_recording(screen_mgr):
    """Stop any in-progress voice recording before shutdown."""
    current = screen_mgr.current
    if current and hasattr(current, "_audio_pipeline"):
        try:
            pipeline = getattr(current, "_audio_pipeline", None)
            if pipeline and hasattr(pipeline, "stop_recording"):
                pipeline.stop_recording()
            if pipeline and hasattr(pipeline, "stop_speaking"):
                pipeline.stop_speaking()
        except Exception as exc:
            logger.warning("cancel_voice_failed error=%s", exc)


def _request_backend_shutdown(client: "BackendClient"):
    """Best-effort POST to /shutdown so the server can clean up."""
    try:
        client.post("/shutdown", json={}, timeout=2.0)
    except Exception as exc:
        logger.warning("backend_shutdown_request_failed error=%s", exc)


def _save_runtime_state(screen_mgr, now: float):
    """Persist minimal state so a quick reboot can skip the boot screen."""
    current = screen_mgr.current
    screen_name = current.__class__.__name__ if current else "none"
    state = {"screen": screen_name, "timestamp": now}
    try:
        with open("/tmp/bitos_state.json", "w", encoding="utf-8") as f:
            json.dump(state, f)
    except Exception as exc:
        logger.warning("save_state_failed error=%s", exc)


def _execute_power_action(action: str):
    """Run systemctl poweroff or reboot."""
    cmd = "poweroff" if action == "shutdown" else "reboot"
    logger.info("power_action=%s", cmd)
    try:
        os.system(f"sudo systemctl {cmd}")
    except Exception as exc:
        logger.warning("power_action_failed error=%s", exc)


def main():
    from hardware.whisplay_board import get_board

    # Ensure the shared board instance is created before button handler setup.
    # If `board` is omitted, create_button_handler falls back to keyboard mode.
    board = get_board()

    logger.info("[BITOS] Starting device...")
    start_time = time.time()

    driver = create_driver(board=board)
    driver.init()
    corner_mask = CornerMask()

    audio_pipeline = get_audio_pipeline()

    # Soft-start ALSA speaker to prevent WM8960 pop/click on boot
    from audio.player import init_alsa_soft_start
    try:
        vol = DeviceRepository().get_setting("volume", 100)
        init_alsa_soft_start(target_pct=max(0, min(100, int(vol))))
    except Exception:
        init_alsa_soft_start()

    led = LEDController(board=board)
    monitor = SystemMonitor(interval=30)
    battery_monitor = BatteryMonitor()
    battery_monitor.start()
    battery_monitor.configure_safe_shutdown(threshold_pct=5, delay_s=30)
    led.idle()
    client = BackendClient()
    repository = DeviceRepository()
    repository.initialize()

    # Bluetooth audio manager — scans, pairs, routes audio to BT devices
    from bluetooth.audio_manager import BluetoothAudioManager
    bt_audio_manager = BluetoothAudioManager(repository=repository)

    # NOTE: BT audio auto-reconnect moved to after GATT server start (see below)
    # to avoid D-Bus contention with bluezero's GLib main loop.

    # Detect timezone from IP geolocation in background (like greeting fetch)
    threading.Thread(
        target=detect_and_set_timezone,
        kwargs={"repository": repository},
        daemon=True,
        name="geolocation",
    ).start()

    notification_queue = NotificationQueue(repository=repository)
    status_state = StatusState()
    screen_mgr = ScreenManager(notification_queue=notification_queue, status_state=status_state)
    idle_mgr = IdleManager(driver, repository)
    power_mgr = PowerManager()
    power_mgr.system_power_save()

    def _active_screen_name() -> str:
        current = screen_mgr.current
        if current is None:
            return "none"
        return current.__class__.__name__

    button = create_button_handler(board=board, active_screen_name_getter=_active_screen_name)
    logger.info("[Button] handler ready mode=%s gpio_wired=%s", os.environ.get("BITOS_BUTTON", "unset"), board is not None)

    def _on_button(btn_event: ButtonEvent):
        logger.info("[Button] %s", btn_event.name)
        idle_mgr.wake()
        power_mgr.poke()
        if power_overlay is not None:
            power_overlay.handle_input(btn_event.name)
            return
        # Agent overlay intercepts all gestures while active
        if agent_overlay is not None:
            if btn_event == ButtonEvent.TRIPLE_PRESS:
                # Triple-press again dismisses the overlay
                toggle_agent_overlay()
                return
            agent_overlay.handle_action(btn_event.name)
            return
        # Triple-press from any screen opens the agent overlay
        if btn_event == ButtonEvent.TRIPLE_PRESS:
            toggle_agent_overlay()
            return
        screen_mgr.handle_action(btn_event.name)

    button.on(ButtonEvent.SHORT_PRESS, lambda: _on_button(ButtonEvent.SHORT_PRESS))
    button.on(ButtonEvent.LONG_PRESS, lambda: _on_button(ButtonEvent.LONG_PRESS))
    button.on(ButtonEvent.DOUBLE_PRESS, lambda: _on_button(ButtonEvent.DOUBLE_PRESS))
    button.on(ButtonEvent.TRIPLE_PRESS, lambda: _on_button(ButtonEvent.TRIPLE_PRESS))
    button.on(ButtonEvent.HOLD_START, lambda: _on_button(ButtonEvent.HOLD_START))
    button.on(ButtonEvent.HOLD_END, lambda: _on_button(ButtonEvent.HOLD_END))
    def _on_power_gesture():
        # Dev bypass: 5-press on lock screen skips PIN
        current = screen_mgr.current if hasattr(screen_mgr, 'current') else None
        if isinstance(current, LockScreen):
            current.bypass_unlock()
            return
        open_power_overlay()

    button.on(ButtonEvent.POWER_GESTURE, _on_power_gesture)

    notification_poller = NotificationPoller(queue=notification_queue, api_client=client, repository=repository)

    def show_proactive_notification(app: str, icon: str, message: str):
        """Show an interactive notification banner that wakes the screen.

        Called from notification poller or heartbeat when agent has something to say.
        """
        was_sleeping = idle_mgr.state in ("dim", "sleep")
        idle_mgr.wake()

        def on_banner_reply(mode: str):
            """Route reply to chat panel — open it if needed."""
            logger.info("[Banner] reply mode=%s", mode)
            # TODO: open chat panel with recording pre-started

        def on_banner_dismiss():
            logger.info("[Banner] dismissed")

        banner = NotificationBanner(
            app=app,
            icon=icon,
            message=message,
            time_str=time.strftime("%H:%M"),
            was_sleeping=was_sleeping,
            on_reply=on_banner_reply,
            on_dismiss=on_banner_dismiss,
        )
        screen_mgr.show_banner(banner)

    # Expose to poller so it can trigger banners for high-priority notifications
    notification_poller.on_banner = show_proactive_notification

    # ── Notification Router + WebSocket client ──
    # Mutable ref so badge callback can reach the home screen once it's created
    _home_screen_ref: list = []  # [CompositeScreen] when set

    def _show_banner_from_event(event):
        payload = event.get("payload", {})
        was_sleeping = idle_mgr.state in ("dim", "sleep")
        idle_mgr.wake()

        def on_banner_reply(mode: str):
            logger.info("[Router/Banner] reply mode=%s", mode)

        def on_banner_dismiss():
            logger.info("[Router/Banner] dismissed")

        banner = NotificationBanner(
            app=payload.get("app", event.get("category", "").upper()),
            icon=payload.get("icon", "!"),
            message=payload.get("body", ""),
            time_str=payload.get("time_str", time.strftime("%H:%M")),
            was_sleeping=was_sleeping,
            category=event.get("category", "system"),
            on_reply=on_banner_reply,
            on_dismiss=on_banner_dismiss,
        )
        screen_mgr.show_banner(banner)

    def _show_toast_from_event(event):
        payload = event.get("payload", {})
        notification_queue.push(NotificationToast(
            app=payload.get("app", event.get("category", "").upper()),
            icon=payload.get("icon", "!"),
            message=payload.get("body", ""),
            time_str=time.strftime("%H:%M"),
            category=event.get("category", "system"),
        ))

    def _on_badge(count):
        if _home_screen_ref:
            _home_screen_ref[0].set_unread_count(count)

    notification_router = NotificationRouter(
        on_banner=_show_banner_from_event,
        on_toast=_show_toast_from_event,
        on_badge=_on_badge,
    )

    server_url = os.environ.get("BITOS_SERVER_URL", "ws://localhost:8000")
    ws_client = DeviceWSClient(f"{server_url}/ws/device")
    ws_client.on_event = notification_router.on_event
    ws_client.start()

    # ── Agent approval overlay wiring ──
    from overlays.approval_overlay import ApprovalOverlay

    def show_approval_overlay(request_id: str, prompt: str, options: list[str]):
        """Show an approval overlay when the agent requests permission."""
        idle_mgr.wake()

        def on_choice(req_id: str, chosen: str):
            logger.info("[Approval] choice: id=%s option=%s", req_id, chosen)
            # Submit choice back to server in background thread
            import threading
            threading.Thread(
                target=lambda: client.submit_approval(req_id, chosen),
                daemon=True,
            ).start()

        def on_cancel(req_id: str):
            logger.info("[Approval] cancelled: id=%s", req_id)
            import threading
            threading.Thread(
                target=lambda: client.submit_approval(req_id, "cancelled"),
                daemon=True,
            ).start()

        overlay = ApprovalOverlay(
            request_id=request_id,
            prompt=prompt,
            options=options,
            on_choice=on_choice,
            on_cancel=on_cancel,
        )
        screen_mgr.show_banner(overlay)

    client.on_approval_request = show_approval_overlay

    # SD-002: BLE auth bootstrap binds device identity + shared secret before any protected characteristic writes.
    auth_manager = AuthManager(
        # SD-005: PIN hash and BLE secret are sourced from env-backed device secrets.
        pin_hash=os.environ.get("BITOS_PIN_HASH", ""),
        device_serial=_read_device_serial(),
        ble_secret=os.environ.get("BITOS_BLE_SECRET", ""),
    )

    def on_show_passkey(code: str):
        screen_mgr.show_passkey_overlay(passkey=code, timeout_seconds=30)

    def on_pairing_complete(success: bool):
        if success:
            screen_mgr.confirm_passkey()
        else:
            screen_mgr.reject_passkey()
        notification_queue.push(
            NotificationToast(
                app="BLE",
                icon="B",
                message="COMPANION PAIRED \u2713" if success else "PAIRING FAILED \u2717",
                time_str=time.strftime("%H:%M"),
            )
        )

    wifi_manager = WiFiManager()
    ble_service = get_ble_service()
    pairing_mgr = PairingManager()

    def on_ble_message(msg: dict):
        message_type = msg.get("t")
        if message_type == "msg":
            logger.info("[BLE] chat message: %r", msg.get("body", ""))
        elif message_type == "vol":
            logger.info("[BLE] volume: %s", msg.get("v"))
        else:
            logger.info("[BLE] unhandled message: %s", msg)

    def on_ble_connect():
        led.connected()
        logger.info("[BLE] phone connected")

    def on_ble_disconnect():
        logger.info("[BLE] phone disconnected")

    def on_ancs_notification(notif: dict):
        logger.info(
            "[ANCS] iOS notif: %s — %s: %s",
            notif.get("app", "?"),
            notif.get("title", "?"),
            notif.get("body", "?"),
        )
        if ble_service.is_connected:
            ble_service.send(notif)

    ble_service.on_message(on_ble_message)
    ble_service.on_connect(on_ble_connect)
    ble_service.on_disconnect(on_ble_disconnect)
    pairing_mgr.on_notification(on_ancs_notification)

    network_manager = NetworkPriorityManager()
    status_poller = StatusPoller(status_state, client, battery_monitor, network_manager, led=led)
    wifi_status_char = WiFiStatusCharacteristic()

    def on_wifi_config(ssid: str, password: str, security: str, priority: int) -> bool:
        ok = wifi_manager.add_or_update_network(ssid, password, security, priority)
        status = wifi_manager.get_status()
        status["last_error"] = None if ok else "apply_failed"
        wifi_status_char.update(status)
        return ok

    def on_keyboard_input(target: str, text: str, cursor_pos: int) -> bool:
        return screen_mgr.set_compose_text(target=target, text=text, cursor=cursor_pos)

    device_info_char = DeviceInfoCharacteristic()
    device_status_char = DeviceStatusCharacteristic()

    startup_health = {"backend": None, "database": None, "api_key": bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("OPENAI_API_KEY"))}

    def _collect_device_status() -> dict:
        current = screen_mgr.current
        active_screen = current.__class__.__name__.replace("Panel", "").replace("Screen", "").lower() if current else "none"
        battery = battery_monitor.get_status()
        batt_pct = int(battery["pct"]) if battery["pct"] is not None else None
        repository.set_setting("battery_pct", batt_pct if batt_pct is not None else -1)
        repository.set_setting("charging", bool(battery["charging"]))
        return {
            "battery_pct": batt_pct,
            "charging": bool(battery["charging"]),
            "wifi_connected": bool(wifi_status_char._status.get("connected", False)),
            "wifi_ssid": str(wifi_status_char._status.get("ssid", "")),
            "ai_online": bool(startup_health.get("backend")) if startup_health.get("backend") is not None else bool(client.health(timeout=2.0)),
            "active_screen": active_screen,
            "agent_mode": str(repository.get_setting("agent_mode", "normal")),
            "bitos_version": "1.0.0",
            "uptime_seconds": int(time.time() - start_time),
        }

    gatt_server = get_gatt_server(
        auth_manager=auth_manager,
        on_wifi_config=on_wifi_config,
        on_keyboard_input=on_keyboard_input,
        on_show_passkey=on_show_passkey,
        on_pairing_complete=on_pairing_complete,
        device_info_characteristic=device_info_char,
    )

    # HTTP provisioning server — WiFi fallback for iOS companion (no Web Bluetooth)
    def _wifi_status_for_http() -> dict:
        return json.loads(wifi_status_char.ReadValue(None).decode("utf-8"))

    def _device_info_for_http() -> dict:
        return json.loads(device_info_char.ReadValue(None).decode("utf-8"))

    provision_server = ProvisioningServer(
        auth_manager=auth_manager,
        on_wifi_config=on_wifi_config,
        wifi_status_fn=_wifi_status_for_http,
        device_status_fn=_collect_device_status,
        device_info_fn=_device_info_for_http,
        on_keyboard_input=on_keyboard_input,
        repository=repository,
    )

    outbound_queue = OutboundCommandQueue(repository)
    runtime_adapter = create_runtime_adapter()
    outbound_worker = OutboundCommandWorker(
        outbound_queue,
        task_adapter=runtime_adapter,
        message_adapter=runtime_adapter,
        email_adapter=runtime_adapter,
        calendar_adapter=runtime_adapter,
    )
    outbound_loop = OutboundWorkerRuntimeLoop(outbound_worker, interval_seconds=0.2, max_per_tick=1)

    server_ok = client.health()
    if server_ok:
        logger.info("[BITOS] Backend connected ✓")
    else:
        logger.warning("[BITOS] Backend not reachable — chat will not work until server starts")

    ui_settings = None
    try:
        ui_settings = client.get_ui_settings()
        logger.info(
            "[BITOS] UI settings loaded (font=%s, scale=%s)",
            ui_settings.get("font_family"),
            ui_settings.get("font_scale"),
        )
    except Exception as exc:
        logger.warning("[BITOS] UI settings unavailable, using defaults (%s)", exc)

    # Apply on-device font scale override from local repository
    local_font_scale = repository.get_setting("font_scale", default=None)
    if local_font_scale is not None:
        if ui_settings is None:
            ui_settings = {}
        ui_settings["font_scale"] = float(local_font_scale)

    # Apply on-device font family override from local repository
    local_font_family = repository.get_setting("font_family", default=None)
    if local_font_family is not None:
        if ui_settings is None:
            ui_settings = {}
        ui_settings["font_family"] = str(local_font_family)

    restored_state = _restore_state()

    def on_home():
        panel_openers = {
            "HOME": lambda: None,  # already showing home
            "CHAT": open_chat,
            "CHAT_NEW": open_chat_new,
            "CHAT_RESUME": open_chat_resume,
            "CHAT_GREETING": open_chat_greeting,
            "CHAT_HISTORY": open_chat_history,
            "CHAT_SETTINGS": open_chat_settings,
            "TASKS": open_tasks,
            "SETTINGS": open_settings,
            "FOCUS": open_focus,
            "MAIL": open_mail,
            "MSGS": open_messages,
            "COMMS": open_messages,  # default to messages view
            "CONTACTS": lambda: None,  # not yet implemented
            "FILES": open_files_browser,
            "NOTIFICATIONS": open_activity,  # notifications use activity panel
            "AGENT": open_agent_tasks,
            "ACTIVITY": open_activity,
        }
        recording_adapter = RecordingAdapter(audio_pipeline)

        def _stt_callable(path: str) -> str:
            return audio_pipeline.transcribe(path)

        right_panels = create_right_panels(
            panel_openers=panel_openers,
            repository=repository,
            status_state=status_state,
            audio_pipeline=recording_adapter,
            stt_callable=_stt_callable,
            led=led,
        )

        # Fetch greeting for chat preview
        def _fetch_greeting():
            try:
                existing = repository.get_greeting_session()
                if existing:
                    msgs = repository.get_session_messages(str(existing["id"]), limit=1)
                    if msgs:
                        chat_panel = right_panels.get("CHAT")
                        if chat_panel and hasattr(chat_panel, "set_greeting"):
                            chat_panel.set_greeting(msgs[0]["text"], session_id=existing["id"])
                    return

                # No recent greeting — request one from backend
                result = client.chat(
                    "Give a brief contextual greeting in under 100 characters. "
                    "Lowercase, casual, no emojis. Mention time of day and any "
                    "relevant tasks or context."
                )
                greeting_text = ""
                if isinstance(result, dict) and result.get("error"):
                    logger.warning("greeting_fetch_error: %s", result.get("error"))
                    return
                for chunk in result:
                    greeting_text += chunk
                greeting_text = greeting_text.strip()[:120]

                if greeting_text:
                    sid = repository.create_greeting_session(greeting_text)
                    chat_panel = right_panels.get("CHAT")
                    if chat_panel and hasattr(chat_panel, "set_greeting"):
                        chat_panel.set_greeting(greeting_text, session_id=sid)
            except Exception as exc:
                logger.warning("greeting_fetch_failed: %s", exc)

        threading.Thread(target=_fetch_greeting, daemon=True).start()

        # ── Fetch live data for Activity, Comms, and Tasks previews ──
        _home_data_alive = threading.Event()
        _home_data_alive.set()

        def _fetch_activity_loop():
            """Poll activity counts every 30s while home screen is active."""
            while _home_data_alive.is_set():
                try:
                    items = client.get_activity()
                    msgs = sum(1 for i in items if i.get("type") == "message" and not i.get("read"))
                    mail = sum(1 for i in items if i.get("type") == "email" and not i.get("read"))
                    tasks = sum(1 for i in items if i.get("type") == "task" and not i.get("read"))
                    activity_panel = right_panels.get("ACTIVITY")
                    if activity_panel and hasattr(activity_panel, "set_counts"):
                        activity_panel.set_counts(msgs=msgs, mail=mail, tasks=tasks)
                except Exception as exc:
                    logger.warning("activity_preview_fetch_failed: %s", exc)
                # Sleep in small increments so we can exit promptly
                for _ in range(30):
                    if not _home_data_alive.is_set():
                        return
                    time.sleep(1)

        def _fetch_comms():
            """Fetch latest message and email snippets for comms preview."""
            try:
                latest_msg = None
                latest_mail = None

                # Latest message from conversations
                conversations = client.get_conversations()
                if conversations:
                    top = conversations[0]
                    sender = str(top.get("sender", top.get("name", "")))[:12]
                    body = str(top.get("last_message", top.get("snippet", "")))[:20]
                    if sender or body:
                        latest_msg = f"{sender}: {body}" if sender else body

                # Latest email from mail inbox
                threads = client.get_mail_inbox()
                if threads:
                    top = threads[0]
                    sender = str(top.get("from", top.get("sender", "")))[:12]
                    body = str(top.get("subject", top.get("snippet", "")))[:20]
                    if sender or body:
                        latest_mail = f"{sender}: {body}" if sender else body

                comms_panel = right_panels.get("COMMS")
                if comms_panel and hasattr(comms_panel, "set_latest"):
                    comms_panel.set_latest(msg=latest_msg, mail=latest_mail)
            except Exception as exc:
                logger.warning("comms_preview_fetch_failed: %s", exc)

        def _fetch_tasks_preview():
            """Fetch today's tasks for the tasks preview panel."""
            try:
                raw_tasks = client.get_tasks()
                tasks = [
                    {"title": str(t.get("title", "")), "done": bool(t.get("done", False))}
                    for t in raw_tasks
                ]
                tasks_panel = right_panels.get("TASKS")
                if tasks_panel and hasattr(tasks_panel, "set_tasks"):
                    tasks_panel.set_tasks(tasks)
            except Exception as exc:
                logger.warning("tasks_preview_fetch_failed: %s", exc)

        def _fetch_context():
            """Fetch live context (weather, headlines, events, counts) for home ticker."""
            try:
                data = client.get_context()
                if not data:
                    return
                home_panel = right_panels.get("HOME")
                if home_panel is None:
                    return
                if data.get("weather"):
                    home_panel.set_weather(data["weather"])
                if data.get("headlines"):
                    home_panel.set_headlines(data["headlines"])
                if data.get("next_event"):
                    home_panel.set_next_event(data["next_event"])
                if data.get("tasks_today") is not None:
                    home_panel.set_task_count(data["tasks_today"])
                if data.get("unread_msgs") is not None or data.get("unread_mail") is not None:
                    home_panel.set_unread(
                        data.get("unread_msgs", 0),
                        data.get("unread_mail", 0),
                    )
            except Exception as exc:
                logger.warning("context_fetch_failed: %s", exc)

        threading.Thread(target=_fetch_activity_loop, daemon=True, name="home_activity").start()
        threading.Thread(target=_fetch_comms, daemon=True, name="home_comms").start()
        threading.Thread(target=_fetch_tasks_preview, daemon=True, name="home_tasks").start()
        threading.Thread(target=_fetch_context, daemon=True, name="home_context").start()

        # Set resume info on chat preview
        latest_chat = repository.get_latest_chat_session()
        if latest_chat:
            age_s = time.time() - float(latest_chat.get("updated_at", 0))
            if age_s < 60:
                time_ago = "just now"
            elif age_s < 3600:
                time_ago = f"{int(age_s / 60)}m ago"
            elif age_s < 86400:
                time_ago = f"{int(age_s / 3600)}h ago"
            else:
                time_ago = f"{int(age_s / 86400)}d ago"
            title = str(latest_chat.get("title", ""))[:16] or "untitled"
            chat_panel = right_panels.get("CHAT")
            if chat_panel and hasattr(chat_panel, "set_resume_info"):
                chat_panel.set_resume_info(title, time_ago)

        home = CompositeScreen(
            panel_openers=panel_openers,
            status_state=status_state,
            right_panels=right_panels,
        )
        _home_screen_ref.clear()
        _home_screen_ref.append(home)
        screen_mgr.replace(home)

    def open_chat():
        screen_mgr.push(
            ChatPanel(
                client=client,
                ui_settings=ui_settings,
                repository=repository,
                audio_pipeline=audio_pipeline,
                led=led,
                on_back=lambda: screen_mgr.pop(),
                on_settings=open_chat_settings,
            )
        )

    def open_chat_new():
        screen_mgr.push(
            ChatPanel(
                client=client,
                ui_settings=ui_settings,
                repository=repository,
                audio_pipeline=audio_pipeline,
                led=led,
                on_back=lambda: screen_mgr.pop(),
                on_settings=open_chat_settings,
                mode="blank",
            )
        )

    def open_chat_resume():
        screen_mgr.push(
            ChatPanel(
                client=client,
                ui_settings=ui_settings,
                repository=repository,
                audio_pipeline=audio_pipeline,
                led=led,
                on_back=lambda: screen_mgr.pop(),
                on_settings=open_chat_settings,
                mode="resume",
            )
        )

    def open_chat_greeting(**kwargs):
        text = kwargs.get("text")
        try:
            panel = ChatPanel(
                client=client,
                ui_settings=ui_settings,
                repository=repository,
                audio_pipeline=audio_pipeline,
                led=led,
                on_back=lambda: screen_mgr.pop(),
                on_settings=open_chat_settings,
                mode="greeting",
            )
            screen_mgr.push(panel)
            # If text was provided from inline recording, auto-send it
            if text and hasattr(panel, "send_message"):
                panel.send_message(text)
        except Exception as exc:
            logger.error("[BITOS] open_chat_greeting crashed: %s", exc, exc_info=True)

    def open_chat_history():
        def _open_session(session_id: int):
            screen_mgr.push(
                ChatPanel(
                    client=client,
                    ui_settings=ui_settings,
                    repository=repository,
                    audio_pipeline=audio_pipeline,
                    led=led,
                    on_back=lambda: screen_mgr.pop(),
                    on_settings=open_chat_settings,
                    mode="session",
                    session_id=session_id,
                )
            )

        screen_mgr.push(
            ChatHistoryPanel(
                repository=repository,
                on_open_session=_open_session,
                on_back=lambda: screen_mgr.pop(),
                ui_settings=ui_settings,
            )
        )

    def open_chat_settings():
        from screens.panels.chat_settings import ChatSettingsPanel
        screen_mgr.push(
            ChatSettingsPanel(
                repository=repository,
                on_back=lambda: screen_mgr.pop(),
                ui_settings=ui_settings,
            )
        )

    def open_focus():
        screen_mgr.push(FocusPanel(on_back=lambda: screen_mgr.pop(), ui_settings=ui_settings, repository=repository))

    def open_tasks():
        screen_mgr.push(TasksPanel(client=client, repository=repository, on_back=lambda: screen_mgr.pop(), ui_settings=ui_settings))

    def open_activity():
        screen_mgr.push(ActivityPanel(client=client, repository=repository, on_back=lambda: screen_mgr.pop(), ui_settings=ui_settings))

    def open_agent_tasks():
        screen_mgr.push(AgentTasksPanel(client=client, repository=repository, on_back=lambda: screen_mgr.pop(), ui_settings=ui_settings))

    def open_files_browser():
        def _open_file_viewer(file_data: dict):
            screen_mgr.push(
                MarkdownViewerPanel(
                    file_data=file_data,
                    client=client,
                    on_back=lambda: screen_mgr.pop(),
                    ui_settings=ui_settings,
                    repository=repository,
                )
            )

        screen_mgr.push(
            FilesBrowserPanel(
                client=client,
                repository=repository,
                on_back=lambda: screen_mgr.pop(),
                on_open_file=_open_file_viewer,
                ui_settings=ui_settings,
            )
        )

    def open_captures():
        screen_mgr.push(CapturesPanel(repository=repository, on_back=lambda: screen_mgr.pop(), ui_settings=ui_settings))

    def open_messages():
        raw_pct = battery_monitor.get_status().get("pct")
        battery_pct = int(raw_pct) if raw_pct is not None else 0
        screen_mgr.push(
            MessagesPanel(
                client=client,
                battery_pct=battery_pct,
                audio_pipeline=audio_pipeline,
                led=led,
                on_back=lambda: screen_mgr.pop(),
                ui_settings=ui_settings,
            )
        )

    def open_mail():
        raw_pct = battery_monitor.get_status().get("pct")
        battery_pct = int(raw_pct) if raw_pct is not None else 0
        screen_mgr.push(
            MailPanel(
                client=client,
                battery_pct=battery_pct,
                audio_pipeline=audio_pipeline,
                led=led,
                on_back=lambda: screen_mgr.pop(),
                ui_settings=ui_settings,
            )
        )

    def open_notifications():
        screen_mgr.push(NotificationsPanel(on_back=lambda: screen_mgr.pop(), ui_settings=ui_settings))

    def open_settings():
        screen_mgr.push(
            SettingsPanel(
                repository=repository,
                on_back=lambda: screen_mgr.pop(),
                on_open_model_picker=open_model_picker,
                on_open_agent_mode=open_agent_mode,
                on_open_sleep_timer=open_sleep_timer,
                on_open_about=open_about,
                on_open_change_pin=open_change_pin,
                on_open_battery=open_battery,
                on_open_dev=open_dev,
                on_open_font_picker=open_font_picker,
                on_open_text_speed=open_text_speed,
                on_open_bt_audio=open_bt_audio,
                on_open_bluetooth=open_bluetooth,
                on_push_overlay=screen_mgr.push_overlay,
                on_dismiss_overlay=screen_mgr.dismiss_overlay,
                get_ble_address=gatt_server.get_device_address,
                on_set_discoverable=gatt_server.set_discoverable,
                ui_settings=ui_settings,
                client=client,
                on_open_integration_detail=open_integration_detail,
                auth_manager=auth_manager,
            )
        )

    def open_model_picker():
        screen_mgr.push(ModelPickerPanel(repository=repository, on_back=lambda: screen_mgr.pop(), ui_settings=ui_settings))

    def open_agent_mode():
        screen_mgr.push(AgentModePanel(repository=repository, on_back=lambda: screen_mgr.pop(), ui_settings=ui_settings))

    def open_sleep_timer():
        screen_mgr.push(SleepTimerPanel(repository=repository, on_back=lambda: screen_mgr.pop(), ui_settings=ui_settings))

    def open_about():
        screen_mgr.push(AboutPanel(on_back=lambda: screen_mgr.pop(), ui_settings=ui_settings))

    def open_change_pin():
        screen_mgr.push(ChangePinPanel(repository=repository, on_back=lambda: screen_mgr.pop(), ui_settings=ui_settings))

    def open_battery():
        screen_mgr.push(BatteryPanel(battery_monitor=battery_monitor, repository=repository, on_back=lambda: screen_mgr.pop(), ui_settings=ui_settings))

    def open_font_picker():
        screen_mgr.push(FontPickerPanel(repository=repository, on_back=lambda: screen_mgr.pop(), ui_settings=ui_settings))

    def open_text_speed():
        screen_mgr.push(TextSpeedPanel(repository=repository, on_back=lambda: screen_mgr.pop(), ui_settings=ui_settings))

    def open_bluetooth():
        screen_mgr.push(BluetoothPanel(
            gatt_server=gatt_server,
            auth_manager=auth_manager,
            on_back=lambda: screen_mgr.pop(),
            on_push_overlay=screen_mgr.push_overlay,
            on_dismiss_overlay=screen_mgr.dismiss_overlay,
            ui_settings=ui_settings,
        ))

    def open_bt_audio():
        screen_mgr.push(BluetoothAudioPanel(bt_audio_manager=bt_audio_manager, repository=repository, on_back=lambda: screen_mgr.pop(), ui_settings=ui_settings))

    def open_dev():
        screen_mgr.push(DevPanel(system_monitor=monitor, on_back=lambda: screen_mgr.pop(), ui_settings=ui_settings))

    def open_integration_detail(integration_name: str, status_data: dict):
        screen_mgr.push(
            IntegrationDetailPanel(
                integration_name=integration_name,
                status_data=status_data,
                on_back=lambda: screen_mgr.pop(),
                ui_settings=ui_settings,
            )
        )

    def _enter_offline_mode():
        screen_mgr.dismiss_overlay()
        lock = LockScreen(on_home=on_home, ui_settings=ui_settings, repository=repository)
        screen_mgr.replace(lock)

    def _show_setup_qr_if_needed():
        from pathlib import Path
        # Skip onboarding if device is already configured
        if Path("/etc/bitos/configured").exists():
            return
        if os.environ.get("ANTHROPIC_API_KEY"):
            return
        active = network_manager.get_active_connection()
        if active:
            return
        ble_addr = gatt_server.get_device_address()
        qr = QROverlay(
            url=build_setup_url(ble_addr),
            title="NO NETWORK FOUND",
            subtitle="SCAN TO CONFIGURE WI-FI",
            timeout_s=120,
            on_connected=lambda: screen_mgr.dismiss_overlay(qr),
            on_timeout=lambda: _enter_offline_mode(),
            on_dismiss=lambda: _enter_offline_mode(),
        )
        screen_mgr.push_overlay(qr)
        gatt_server.set_discoverable(True, timeout_s=120)

    def on_boot_complete():
        lock = LockScreen(on_home=on_home, ui_settings=ui_settings, repository=repository)
        screen_mgr.replace(lock)
        _show_setup_qr_if_needed()

    boot = BootScreen(on_complete=on_boot_complete, startup_health=startup_health, health_check=lambda: _run_startup_health_check(client, repository, startup_health))

    if restored_state:
        on_boot_complete()
    else:
        _run_startup_health_check(client, repository, startup_health)
        screen_mgr.push(boot)

    power_overlay: PowerOverlay | None = None
    agent_overlay: AgentOverlay | None = None

    def close_power_overlay():
        nonlocal power_overlay
        power_overlay = None

    def run_power_action(action: str):
        nonlocal running
        _cancel_inflight_voice_recording(screen_mgr)
        _request_backend_shutdown(client)
        _save_runtime_state(screen_mgr, time.time())
        _execute_power_action(action)
        running = False

    def open_power_overlay():
        nonlocal power_overlay
        if power_overlay is not None:
            return
        _cancel_inflight_voice_recording(screen_mgr)
        power_overlay = PowerOverlay(
            on_shutdown=lambda: run_power_action("shutdown"),
            on_reboot=lambda: run_power_action("reboot"),
            on_cancel=close_power_overlay,
        )

    def toggle_agent_overlay():
        nonlocal agent_overlay
        if agent_overlay is not None:
            # Already showing — dismiss it
            agent_overlay._dismiss()
            agent_overlay = None
            return
        agent_overlay = AgentOverlay(
            audio_pipeline=audio_pipeline,
            client=client,
            led=led,
            on_dismiss=lambda: _clear_agent_overlay(),
        )

    def _clear_agent_overlay():
        nonlocal agent_overlay
        agent_overlay = None

    screen_mgr.attach_device_status_characteristic(device_status_char)

    notification_poller.start()
    status_poller.start()
    monitor.start()
    led.off()

    # BLE subsystems must never crash the device — wrap each in try/except
    try:
        ble_service.start()
    except Exception as exc:
        logger.error("[BITOS] BLE NUS service failed to start: %s", exc)

    try:
        pairing_mgr.start()
    except Exception as exc:
        logger.error("[BITOS] Pairing manager failed to start: %s", exc)

    try:
        gatt_server.start()
        gatt_server.set_discoverable(False)
    except Exception as exc:
        logger.error("[BITOS] GATT server failed to start: %s", exc)

    # Auto-reconnect BT audio AFTER GATT is initialized to avoid D-Bus contention
    threading.Thread(
        target=bt_audio_manager.auto_reconnect_last,
        name="bt-audio-reconnect",
        daemon=True,
    ).start()

    try:
        provision_server.start()
    except Exception as exc:
        logger.error("[BITOS] HTTP provisioning server failed to start: %s", exc)

    device_status_char.start_periodic_updates(_collect_device_status, interval_s=30)

    clock = pygame.time.Clock()
    running = True
    last_time = time.time()

    logger.info("[Startup] stack=%s", [type(s).__name__ for s in screen_mgr._stack])

    while running:
        now = time.time()
        dt = now - last_time
        last_time = now

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                break
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False
                break

            consumed = button.handle_pygame_event(event)
            if not consumed:
                screen_mgr.handle_input(event)

        if not running:
            break

        button.update()
        idle_mgr.tick()
        worker_results = outbound_loop.tick(now=now)
        for result in worker_results:
            if result.status in ("retrying", "dead_letter"):
                reason = result.reason or "unknown"
                logger.error("[Queue] command=%s status=%s reason=%s", result.command_id, result.status, reason)
        surface = driver.get_surface()
        screen_mgr.update(dt)
        screen_mgr.render(surface)
        # Agent overlay renders on top of everything except power overlay
        if agent_overlay is not None:
            dt_ms = int(max(0.0, dt) * 1000)
            if not agent_overlay.tick(dt_ms):
                agent_overlay = None
            else:
                agent_overlay.render(surface)
        if power_overlay is not None:
            power_overlay.render(surface, tokens)
        corner_mask.apply(surface)
        driver.update()

        clock.tick(power_mgr.get_target_fps())

    notification_poller.stop()
    ws_client.stop()
    status_poller.stop()
    monitor.stop()
    led.off()
    device_status_char.stop_periodic_updates()

    # Shutdown BLE + HTTP subsystems safely — never let cleanup crash the shutdown sequence
    for name, subsystem in [("provision_server", provision_server), ("pairing_mgr", pairing_mgr), ("ble_service", ble_service), ("gatt_server", gatt_server)]:
        try:
            subsystem.stop()
        except Exception as exc:
            logger.error("[BITOS] %s stop failed: %s", name, exc)

    driver.quit()
    if board is not None:
        board.cleanup()
    logger.info("[BITOS] Shut down.")


if __name__ == "__main__":
    try:
        main()
    except Exception as fatal:
        _handle_main_loop_crash(fatal)
        logging.critical("BITOS device crashed — see /tmp/bitos_crash.json")
        sys.exit(1)
