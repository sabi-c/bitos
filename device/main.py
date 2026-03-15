"""BITOS Device main entry point."""
import json
import logging
import os

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
import subprocess
import time

import httpx
import pygame

from display.driver import create_driver
import display.tokens as tokens
from display.tokens import FPS
from input.handler import ButtonEvent, create_button_handler
from notifications import NotificationPoller
from overlays import NotificationQueue, NotificationToast, QROverlay, QuickCaptureOverlay
from overlays.power import PowerOverlay
from bluetooth import AuthManager, get_gatt_server
from bluetooth.constants import PAIRING_MODE_TIMEOUT_SECONDS
from bluetooth.characteristics import DeviceInfoCharacteristic, DeviceStatusCharacteristic, KeyboardInputCharacteristic, WiFiConfigCharacteristic, WiFiStatusCharacteristic
from bluetooth.constants import build_pair_url, build_setup_url
from bluetooth.network_manager import NetworkPriorityManager
from bluetooth.wifi_manager import WiFiManager
from ble import BITOSBleService
from audio.pipeline import get_audio_pipeline
from hardware import StatusPoller, StatusState, SystemMonitor
from power.battery import BatteryMonitor
from power.leds import LEDController
from screens.manager import ScreenManager
from screens.boot import BootScreen
from screens.lock import LockScreen
from screens.panels.home import HomePanel
from screens.panels.chat import ChatPanel
from screens.panels.focus import FocusPanel
from screens.panels.notifications import NotificationsPanel
from screens.panels.tasks import TasksPanel
from screens.panels.messages import MessagesPanel
from screens.panels.mail import MailPanel
from screens.panels.captures import CapturesPanel
from screens.panels.settings import (
    AboutPanel,
    AgentModePanel,
    ModelPickerPanel,
    SettingsPanel,
    SleepTimerPanel,
)
from screens.subscreens.integration_detail import IntegrationDetailPanel
from client.api import BackendClient
from storage.repository import DeviceRepository
from integrations.adapters import create_runtime_adapter
from integrations.queue import OutboundCommandQueue
from integrations.runtime import OutboundWorkerRuntimeLoop
from integrations.worker import OutboundCommandWorker
from device.audio.voice_pipeline import VoicePipeline
import device.screens.chat_screen  # triggers @register_app

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


def _save_runtime_state(screen_mgr: ScreenManager, timestamp: float, path: str = "/tmp/bitos_state.json") -> None:
    state: dict[str, object] = {"timestamp": float(timestamp)}
    current = screen_mgr.current

    if current is not None and hasattr(current, "_session_id"):
        state["session_id"] = getattr(current, "_session_id")

    if current is not None and hasattr(current, "remaining_seconds") and hasattr(current, "is_running"):
        state["pomodoro"] = {
            "is_running": bool(getattr(current, "is_running", False)),
            "remaining_seconds": int(getattr(current, "remaining_seconds", 0)),
            "started_at": float(timestamp),
        }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f)


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


def _request_backend_shutdown(client):
    """Tell backend to save state before device shutdown."""
    try:
        client.health(timeout=1.0)
    except Exception:
        pass


def _execute_power_action(action: str) -> None:
    """Execute system power action."""
    if action == "shutdown":
        logger.info("[Power] Shutting down...")
        subprocess.run(["sudo", "shutdown", "-h", "now"], check=False)
    elif action == "reboot":
        logger.info("[Power] Rebooting...")
        subprocess.run(["sudo", "reboot"], check=False)


def main():
    from hardware.whisplay_board import get_board

    # Ensure the shared board instance is created before button handler setup.
    # If `board` is omitted, create_button_handler falls back to keyboard mode.
    board = get_board()

    logger.info("[BITOS] Starting device...")
    start_time = time.time()

    driver = create_driver(board=board)
    driver.init()

    audio_pipeline = get_audio_pipeline()
    led = LEDController(board=board)
    monitor = SystemMonitor(interval=30)
    battery_monitor = BatteryMonitor()
    battery_monitor.start()
    battery_monitor.configure_safe_shutdown(threshold_pct=5, delay_s=30)
    led.idle()
    client = BackendClient()
    repository = DeviceRepository()
    repository.initialize()
    notification_queue = NotificationQueue(repository=repository)
    status_state = StatusState()
    screen_mgr = ScreenManager(notification_queue=notification_queue, status_state=status_state)

    openai_key = os.getenv("OPENAI_API_KEY", "")

    def ai_send_fn(text: str) -> str:
        # Placeholder — replace with real Anthropic call later
        import anthropic

        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            messages=[{"role": "user", "content": text}],
        )
        return msg.content[0].text

    voice_pipeline = VoicePipeline(
        openai_key=openai_key,
        ai_send_fn=ai_send_fn,
        voice_model=os.getenv("PIPER_VOICE_MODEL", "assets/voices/en_US-ryan-low.onnx"),
    )
    screen_mgr._voice_pipeline = voice_pipeline

    def _active_screen_name() -> str:
        current = screen_mgr.current
        if current is None:
            return "none"
        return current.__class__.__name__

    button = create_button_handler(board=board, active_screen_name_getter=_active_screen_name)
    logger.info("[Button] handler ready mode=%s gpio_wired=%s", os.environ.get("BITOS_BUTTON", "unset"), board is not None)
    notification_poller = NotificationPoller(queue=notification_queue, api_client=client, repository=repository)

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
    ble_service = BITOSBleService()

    def on_ble_message(text: str):
        logger.info("[BLE] message -> chat route pending: %r", text)

    def on_ble_connect():
        logger.info("[BLE] phone connected")

    def on_ble_disconnect():
        logger.info("[BLE] phone disconnected")

    ble_service.on_message(on_ble_message)
    ble_service.on_connect(on_ble_connect)
    ble_service.on_disconnect(on_ble_disconnect)

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

    wifi_config_char = WiFiConfigCharacteristic(auth_manager=auth_manager, on_wifi_config=on_wifi_config, wifi_status=wifi_status_char)
    keyboard_input_char = KeyboardInputCharacteristic(auth_manager=auth_manager, on_keyboard_input=on_keyboard_input)
    device_status_char = DeviceStatusCharacteristic()
    device_info_char = DeviceInfoCharacteristic()
    _ = (wifi_config_char, keyboard_input_char, device_info_char)

    startup_health = {"backend": None, "database": None, "api_key": bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("OPENAI_API_KEY"))}

    def _collect_device_status() -> dict:
        current = screen_mgr.current
        active_screen = current.__class__.__name__.replace("Panel", "").replace("Screen", "").lower() if current else "none"
        battery = battery_monitor.get_status()
        repository.set_setting("battery_pct", int(battery["pct"]))
        repository.set_setting("charging", bool(battery["charging"]))
        return {
            "battery_pct": int(battery["pct"]),
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
        on_show_passkey=on_show_passkey,
        on_pairing_complete=on_pairing_complete,
        device_info_characteristic=device_info_char,
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

    restored_state = _restore_state()
    restored_session_id = restored_state.get("session_id") if restored_state else None
    restored_pomodoro = restored_state.get("pomodoro") if restored_state else None
    focus_panel: FocusPanel | None = None

    def open_chat():
        chat = ChatPanel(client, ui_settings=ui_settings, repository=repository, audio_pipeline=audio_pipeline, led=led, on_back=on_home)
        screen_mgr.replace(chat)

    def on_home():
        home = HomePanel(
            on_open_chat=open_chat,
            on_open_focus=open_focus,
            on_open_notifications=open_notifications,
            on_open_messages=open_messages,
            on_open_mail=open_mail,
            on_open_tasks=open_tasks,
            on_open_captures=open_captures,
            on_open_settings=open_settings,
            on_show_shade=screen_mgr.show_shade,
            ui_settings=ui_settings,
            startup_health=startup_health,
            repository=repository,
            client=client,
            status_state=status_state,
        )
        screen_mgr.replace(home)

    def open_focus():
        nonlocal focus_panel
        focus = FocusPanel(on_back=on_home, ui_settings=ui_settings, repository=repository)

        raw = repository.get_setting("pomodoro_state", None)
        if raw:
            try:
                focus.restore_state(json.loads(raw))
            except Exception:
                pass

        if restored_pomodoro and restored_pomodoro.get("is_running"):
            started_at = float(restored_pomodoro.get("started_at", restored_state.get("timestamp", time.time()))) if restored_state else time.time()
            elapsed = max(0, int(time.time() - started_at))
            remaining = max(0, int(restored_pomodoro.get("remaining_seconds", focus.remaining_seconds)) - elapsed)
            focus.restore_state(remaining_seconds=remaining, is_running=remaining > 0)
        focus_panel = focus
        screen_mgr.replace(focus)


    def open_messages():
        messages = MessagesPanel(client=client, battery_pct=battery_monitor.get_status().get("pct", 84), audio_pipeline=audio_pipeline, led=led, on_back=on_home, ui_settings=ui_settings)
        screen_mgr.replace(messages)


    def open_mail():
        mail = MailPanel(client=client, battery_pct=battery_monitor.get_status().get("pct", 84), audio_pipeline=audio_pipeline, led=led, on_back=on_home, ui_settings=ui_settings)
        screen_mgr.replace(mail)

    def open_notifications():
        notifications = NotificationsPanel(on_back=on_home, ui_settings=ui_settings)
        screen_mgr.replace(notifications)

    def open_tasks():
        tasks = TasksPanel(client=client, repository=repository, on_back=on_home, ui_settings=ui_settings)
        screen_mgr.replace(tasks)

    def open_captures():
        captures = CapturesPanel(repository=repository, on_back=on_home, ui_settings=ui_settings)
        screen_mgr.replace(captures)

    def open_settings():
        settings = SettingsPanel(
            repository=repository,
            client=client,
            on_back=on_home,
            on_open_model_picker=open_model_picker,
            on_open_agent_mode=open_agent_mode,
            on_open_sleep_timer=open_sleep_timer,
            on_open_about=open_about,
            on_open_companion_app=open_companion_app,
            get_ble_address=gatt_server.get_device_address,
            on_set_discoverable=lambda enabled, timeout: gatt_server.set_discoverable(enabled, timeout),
            on_push_overlay=screen_mgr.push_overlay,
            on_dismiss_overlay=screen_mgr.dismiss_overlay,
            ui_settings=ui_settings,
            on_open_integration_detail=open_integration_detail,
        )
        screen_mgr.replace(settings)

    def open_model_picker():
        screen_mgr.replace(ModelPickerPanel(repository=repository, on_back=open_settings, ui_settings=ui_settings))

    def open_agent_mode():
        screen_mgr.replace(AgentModePanel(repository=repository, on_back=open_settings, ui_settings=ui_settings))

    def open_sleep_timer():
        screen_mgr.replace(SleepTimerPanel(repository=repository, on_back=open_settings, ui_settings=ui_settings))

    def open_about():
        screen_mgr.replace(AboutPanel(on_back=open_settings, ui_settings=ui_settings))

    def open_integration_detail(integration_name: str, status_data: dict):
        screen_mgr.replace(IntegrationDetailPanel(integration_name=integration_name, status_data=status_data, on_back=open_settings, ui_settings=ui_settings))

    def open_companion_app():
        ble_addr = gatt_server.get_device_address()
        qr = QROverlay(
            url=build_pair_url(ble_addr),
            title="PAIR COMPANION APP",
            subtitle="SCAN WITH YOUR PHONE",
            on_dismiss=lambda: screen_mgr.dismiss_overlay(qr),
        )
        screen_mgr.push_overlay(qr)
        gatt_server.set_discoverable(True, 120)


    def _enter_offline_mode():
        screen_mgr.dismiss_overlay()
        lock = LockScreen(on_home=on_home, ui_settings=ui_settings)
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
        lock = LockScreen(on_home=on_home, ui_settings=ui_settings)
        screen_mgr.replace(lock)
        _show_setup_qr_if_needed()

    boot = BootScreen(on_complete=on_boot_complete, startup_health=startup_health, health_check=lambda: _run_startup_health_check(client, repository, startup_health))

    if restored_state:
        on_boot_complete()
    else:
        screen_mgr.push(boot)

    power_overlay: PowerOverlay | None = None

    def close_power_overlay():
        nonlocal power_overlay
        power_overlay = None

    def run_power_action(action: str):
        nonlocal running
        _cancel_inflight_voice_recording(screen_mgr)
        _request_backend_shutdown(client)
        if focus_panel is not None:
            focus_panel.save_state()
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

    screen_mgr.attach_device_status_characteristic(device_status_char)

    notification_poller.start()
    status_poller.start()
    monitor.start()
    led.off()
    ble_service.start()
    gatt_server.start()
    gatt_server.set_discoverable(False)
    device_status_char.start_periodic_updates(_collect_device_status, interval_s=30)

    def _dispatch_action(action: str):
        if power_overlay is not None:
            power_overlay.handle_input(action)
            return
        screen_mgr.handle_action(action)

    def on_short():
        logger.info("[Button] SHORT_PRESS")
        _dispatch_action("SHORT_PRESS")

    def on_long():
        logger.info("[Button] LONG_PRESS")
        _dispatch_action("LONG_PRESS")

    def on_double():
        logger.info("[Button] DOUBLE_PRESS")
        _dispatch_action("DOUBLE_PRESS")

    def on_triple():
        # VERIFIED: TRIPLE_PRESS anywhere opens QuickCaptureOverlay above current screen.
        logger.info("[Button] TRIPLE_PRESS")
        if screen_mgr.current.__class__.__name__ != "QuickCaptureOverlay":
            def _dismiss_capture():
                screen_mgr.dismiss_overlay(overlay)

            def _saved(_capture_id: str, _text: str):
                # VERIFIED: successful quick capture shows a brief "Captured ✓" toast.
                screen_mgr.notification_queue.push(NotificationToast(app="CAPTURE", icon="✓", message="Captured ✓", time_str="now", duration_ms=1500))

            overlay = QuickCaptureOverlay(
                repository=repository,
                client=client,
                audio_pipeline=audio_pipeline,
                context=screen_mgr.current.__class__.__name__.replace("Panel", "").upper() if screen_mgr.current else "",
                on_saved=_saved,
                on_dismiss=_dismiss_capture,
            )
            screen_mgr.push_overlay(overlay)
            return
        _dispatch_action("TRIPLE_PRESS")

    def on_power_gesture():
        # VERIFIED: five-press power gesture opens blocking PowerOverlay.
        logger.info("[Button] POWER_GESTURE")
        open_power_overlay()

    button.on(ButtonEvent.SHORT_PRESS, on_short)
    button.on(ButtonEvent.LONG_PRESS, on_long)
    button.on(ButtonEvent.DOUBLE_PRESS, on_double)
    button.on(ButtonEvent.TRIPLE_PRESS, on_triple)
    button.on(ButtonEvent.POWER_GESTURE, on_power_gesture)

    clock = pygame.time.Clock()
    running = True
    last_time = time.time()

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
        worker_results = outbound_loop.tick(now=now)
        for result in worker_results:
            if result.status in ("retrying", "dead_letter"):
                reason = result.reason or "unknown"
                logger.error("[Queue] command=%s status=%s reason=%s", result.command_id, result.status, reason)
        surface = driver.get_surface()
        screen_mgr.update(dt)
        screen_mgr.render(surface)
        if power_overlay:
            power_overlay.render(surface, tokens)
        driver.update()

        clock.tick(FPS)

    notification_poller.stop()
    status_poller.stop()
    monitor.stop()
    led.off()
    device_status_char.stop_periodic_updates()
    gatt_server.stop()
    driver.quit()
    logger.info("[BITOS] Shut down.")


if __name__ == "__main__":
    main()
