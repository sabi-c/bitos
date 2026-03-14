"""BITOS Device main entry point."""
import json
import logging
import os
import time

import pygame

from display.driver import create_driver
from display.tokens import FPS
from input.handler import ButtonHandler, ButtonEvent
from notifications import NotificationPoller
from overlays import NotificationQueue, NotificationToast
from bluetooth import AuthManager, get_gatt_server
from bluetooth.constants import PAIRING_MODE_TIMEOUT_SECONDS
from bluetooth.characteristics import DeviceStatusCharacteristic, KeyboardInputCharacteristic, WiFiConfigCharacteristic, WiFiStatusCharacteristic
from bluetooth.wifi_manager import WiFiManager
from screens.manager import ScreenManager
from screens.boot import BootScreen
from screens.lock import LockScreen
from screens.panels.home import HomePanel
from screens.panels.chat import ChatPanel
from screens.panels.focus import FocusPanel
from screens.panels.notifications import NotificationsPanel
from screens.panels.settings import (
    AboutPanel,
    AgentModePanel,
    ModelPickerPanel,
    SettingsPanel,
    SleepTimerPanel,
)
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


def _run_main_loop(driver, button: ButtonHandler, screen_mgr: ScreenManager, outbound_loop: OutboundWorkerRuntimeLoop):
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

            button.handle_pygame_event(event)
            screen_mgr.handle_input(event)

        if not running:
            break

        button.update()
        worker_results = outbound_loop.tick(now=now)
        for result in worker_results:
            if result.status in ("retrying", "dead_letter"):
                reason = result.reason or "unknown"
                print(f"[Queue] command={result.command_id} status={result.status} reason={reason}")

        surface = driver.get_surface()
        screen_mgr.update(dt)
        screen_mgr.render(surface)
        driver.update()

        clock.tick(FPS)


def main():
    print("[BITOS] Starting device...")
    start_time = time.time()

    driver = create_driver()
    driver.init()

    button = ButtonHandler()
    client = BackendClient()
    repository = DeviceRepository()
    repository.initialize()
    notification_queue = NotificationQueue(repository=repository)
    screen_mgr = ScreenManager(notification_queue=notification_queue)
    notification_poller = NotificationPoller(queue=notification_queue, api_client=client, repository=repository)

    # SD-002: BLE auth bootstrap binds device identity + shared secret before any protected characteristic writes.
    auth_manager = AuthManager(
        # SD-005: PIN hash and BLE secret are sourced from env-backed device secrets.
        pin_hash=os.environ.get("BITOS_PIN_HASH", ""),
        device_serial=_read_device_serial(),
        ble_secret=os.environ.get("BITOS_BLE_SECRET", ""),
    )

    def on_show_passkey(code: str):
        screen_mgr.show_passkey_overlay(code=code, timeout_s=PAIRING_MODE_TIMEOUT_SECONDS)

    def on_pairing_complete(success: bool):
        screen_mgr.hide_passkey_overlay()
        notification_queue.push(
            NotificationToast(
                app="BLE",
                icon="B",
                message="COMPANION PAIRED ✓" if success else "PAIRING FAILED ✗",
                time_str=time.strftime("%H:%M"),
            )
        )

    wifi_manager = WiFiManager()
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
    _ = (wifi_config_char, keyboard_input_char)

    startup_health = {"backend": None, "database": None, "api_key": bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("OPENAI_API_KEY"))}

    def _collect_device_status() -> dict:
        current = screen_mgr.current
        active_screen = current.__class__.__name__.replace("Panel", "").replace("Screen", "").lower() if current else "none"
        return {
            "battery_pct": int(repository.get_setting("battery_pct", 0) or 0),
            "charging": bool(repository.get_setting("charging", False)),
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

    try:
        ui_settings = client.get_ui_settings()
        print(f"[BITOS] UI settings loaded (font={ui_settings.get('font_family')}, scale={ui_settings.get('font_scale')})")
    except Exception as exc:
        ui_settings = None
        print(f"[BITOS] UI settings unavailable, using defaults ({exc})")

    restored_state = _restore_state()
    restored_session_id = restored_state.get("session_id") if restored_state else None
    restored_pomodoro = restored_state.get("pomodoro") if restored_state else None

    def open_chat():
        chat = ChatPanel(client, ui_settings=ui_settings, repository=repository)
        chat.restore_session_id(restored_session_id)
        screen_mgr.replace(chat)

    def on_home():
        home = HomePanel(
            on_open_chat=open_chat,
            on_open_focus=open_focus,
            on_open_notifications=open_notifications,
            on_open_settings=open_settings,
            on_show_shade=screen_mgr.show_shade,
            ui_settings=ui_settings,
            startup_health=startup_health,
        )
        screen_mgr.replace(home)

    def open_focus():
        focus = FocusPanel(on_back=on_home, ui_settings=ui_settings)
        if restored_pomodoro and restored_pomodoro.get("is_running"):
            started_at = float(restored_pomodoro.get("started_at", restored_state.get("timestamp", time.time()))) if restored_state else time.time()
            elapsed = max(0, int(time.time() - started_at))
            remaining = max(0, int(restored_pomodoro.get("remaining_seconds", focus.remaining_seconds)) - elapsed)
            focus.restore_state(remaining_seconds=remaining, is_running=remaining > 0)
        screen_mgr.replace(focus)

    def open_notifications():
        notifications = NotificationsPanel(on_back=on_home, ui_settings=ui_settings)
        screen_mgr.replace(notifications)

    def open_settings():
        settings = SettingsPanel(
            repository=repository,
            on_back=on_home,
            on_open_model_picker=open_model_picker,
            on_open_agent_mode=open_agent_mode,
            on_open_sleep_timer=open_sleep_timer,
            on_open_about=open_about,
            ui_settings=ui_settings,
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

    def on_boot_complete():
        lock = LockScreen(on_home=on_home, ui_settings=ui_settings)
        screen_mgr.replace(lock)

    boot = BootScreen(on_complete=on_boot_complete, startup_health=startup_health, health_check=lambda: _run_startup_health_check(client, repository, startup_health))

    if restored_state:
        on_boot_complete()
    else:
        screen_mgr.push(boot)

    screen_mgr.attach_device_status_characteristic(device_status_char)

    notification_poller.start()
    gatt_server.start()
    gatt_server.set_discoverable(False)
    device_status_char.start_periodic_updates(_collect_device_status, interval_s=30)

    def on_short():
        print("[Button] SHORT_PRESS")
        screen_mgr.handle_action("SHORT_PRESS")

    def on_long():
        print("[Button] LONG_PRESS")
        screen_mgr.handle_action("LONG_PRESS")

    def on_double():
        print("[Button] DOUBLE_PRESS")
        screen_mgr.handle_action("DOUBLE_PRESS")

    def on_triple():
        print("[Button] TRIPLE_PRESS")
        screen_mgr.handle_action("TRIPLE_PRESS")

    button.on(ButtonEvent.SHORT_PRESS, on_short)
    button.on(ButtonEvent.LONG_PRESS, on_long)
    button.on(ButtonEvent.DOUBLE_PRESS, on_double)
    button.on(ButtonEvent.TRIPLE_PRESS, on_triple)

    try:
        _run_main_loop(driver=driver, button=button, screen_mgr=screen_mgr, outbound_loop=outbound_loop)
    except Exception as exc:
        _handle_main_loop_crash(exc)
        raise
    finally:
        notification_poller.stop()
        device_status_char.stop_periodic_updates()
        gatt_server.stop()
        driver.quit()
        print("[BITOS] Shut down.")


if __name__ == "__main__":
    main()
