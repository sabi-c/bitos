"""BITOS Device main entry point."""
import json
import logging
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
import time

import pygame

from display.corner_mask import CornerMask
from display.driver import create_driver
import display.tokens as tokens
from display.tokens import FPS
from input.handler import ButtonEvent, create_button_handler
from notifications import NotificationPoller
from overlays import NotificationQueue, NotificationToast, QROverlay
from bluetooth import AuthManager, get_gatt_server
from bluetooth.characteristics import DeviceInfoCharacteristic, DeviceStatusCharacteristic, KeyboardInputCharacteristic, WiFiConfigCharacteristic, WiFiStatusCharacteristic
from bluetooth.constants import build_setup_url
from bluetooth.network_manager import NetworkPriorityManager
from bluetooth.wifi_manager import WiFiManager
from device.ble.ble_service import get_ble_service
from device.ble.pairing_manager import PairingManager
from audio.pipeline import get_audio_pipeline
from hardware import StatusPoller, StatusState, SystemMonitor
from power.battery import BatteryMonitor
from power.idle import IdleManager
from power.leds import LEDController
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
from screens.panels.settings import SettingsPanel, ModelPickerPanel, AgentModePanel, SleepTimerPanel, AboutPanel, BatteryPanel, DevPanel, FontPickerPanel, TextSpeedPanel
from screens.panels.change_pin import ChangePinPanel
from screens.subscreens.integration_detail import IntegrationDetailPanel
from overlays.power import PowerOverlay

from client.api import BackendClient
from storage.repository import DeviceRepository
from integrations.adapters import create_runtime_adapter
from integrations.queue import OutboundCommandQueue
from integrations.runtime import OutboundWorkerRuntimeLoop
from integrations.worker import OutboundCommandWorker
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
    idle_mgr = IdleManager(driver, repository)

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
        if power_overlay is not None:
            power_overlay.handle_input(btn_event.name)
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
            current._unlock()
            return
        open_power_overlay()

    button.on(ButtonEvent.POWER_GESTURE, _on_power_gesture)

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

    right_panels = create_right_panels()

    def on_home():
        panel_openers = {
            "HOME": lambda: None,  # already showing home
            "CHAT": open_chat,
            "TASKS": open_tasks,
            "SETTINGS": open_settings,
            "FOCUS": open_focus,
            "MAIL": open_mail,
            "MSGS": open_messages,
            "MUSIC": lambda: None,  # not yet implemented
            "HISTORY": open_captures,
        }
        home = CompositeScreen(
            panel_openers=panel_openers,
            status_state=status_state,
            right_panels=right_panels,
        )
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
            )
        )

    def open_focus():
        screen_mgr.push(FocusPanel(on_back=lambda: screen_mgr.pop(), ui_settings=ui_settings, repository=repository))

    def open_tasks():
        screen_mgr.push(TasksPanel(client=client, repository=repository, on_back=lambda: screen_mgr.pop(), ui_settings=ui_settings))

    def open_captures():
        screen_mgr.push(CapturesPanel(repository=repository, on_back=lambda: screen_mgr.pop(), ui_settings=ui_settings))

    def open_messages():
        battery_pct = int(battery_monitor.get_status().get("pct", 84))
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
        battery_pct = int(battery_monitor.get_status().get("pct", 84))
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
                on_push_overlay=screen_mgr.push_overlay,
                on_dismiss_overlay=screen_mgr.dismiss_overlay,
                get_ble_address=gatt_server.get_device_address,
                on_set_discoverable=gatt_server.set_discoverable,
                ui_settings=ui_settings,
                client=client,
                on_open_integration_detail=open_integration_detail,
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
        if power_overlay is not None:
            power_overlay.render(surface, tokens)
        corner_mask.apply(surface)
        driver.update()

        clock.tick(FPS)

    notification_poller.stop()
    status_poller.stop()
    monitor.stop()
    led.off()
    device_status_char.stop_periodic_updates()

    # Shutdown BLE subsystems safely — never let cleanup crash the shutdown sequence
    for name, subsystem in [("pairing_mgr", pairing_mgr), ("ble_service", ble_service), ("gatt_server", gatt_server)]:
        try:
            subsystem.stop()
        except Exception as exc:
            logger.error("[BITOS] %s stop failed: %s", name, exc)

    driver.quit()
    if board is not None:
        board.cleanup()
    logger.info("[BITOS] Shut down.")


if __name__ == "__main__":
    main()
