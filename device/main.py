"""BITOS Device main entry point."""
import time

import pygame

from display.driver import create_driver
from display.tokens import FPS
from input.handler import ButtonHandler, ButtonEvent
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


def main():
    print("[BITOS] Starting device...")

    driver = create_driver()
    driver.init()
    surface = driver.get_surface()

    button = ButtonHandler()
    screen_mgr = ScreenManager()
    client = BackendClient()
    repository = DeviceRepository()
    repository.initialize()
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
        print("[BITOS] Backend connected ✓")
    else:
        print("[BITOS] Backend not reachable — chat will not work until server starts")


    ui_settings = None
    try:
        ui_settings = client.get_ui_settings()
        print(f"[BITOS] UI settings loaded (font={ui_settings.get('font_family')}, scale={ui_settings.get('font_scale')})")
    except Exception as exc:
        print(f"[BITOS] UI settings unavailable, using defaults ({exc})")

    def open_chat():
        chat = ChatPanel(client, ui_settings=ui_settings, repository=repository)
        screen_mgr.replace(chat)

    def on_unlock():
        home = HomePanel(
            on_open_chat=open_chat,
            on_open_focus=open_focus,
            on_open_notifications=open_notifications,
            on_open_settings=open_settings,
            ui_settings=ui_settings,
        )
        screen_mgr.replace(home)

    def open_focus():
        focus = FocusPanel(on_back=on_unlock, ui_settings=ui_settings)
        screen_mgr.replace(focus)

    def open_notifications():
        notifications = NotificationsPanel(on_back=on_unlock, ui_settings=ui_settings)
        screen_mgr.replace(notifications)

    def open_settings():
        settings = SettingsPanel(
            repository=repository,
            on_back=on_unlock,
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
        lock = LockScreen(on_unlock=on_unlock, ui_settings=ui_settings)
        screen_mgr.replace(lock)

    boot = BootScreen(on_complete=on_boot_complete)
    screen_mgr.push(boot)

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
        screen_mgr.update(dt)
        screen_mgr.render(surface)
        driver.update()

        clock.tick(FPS)

    driver.quit()
    print("[BITOS] Shut down.")


if __name__ == "__main__":
    main()
