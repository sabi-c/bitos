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
from client.api import BackendClient


def main():
    print("[BITOS] Starting device...")

    driver = create_driver()
    driver.init()
    surface = driver.get_surface()

    button = ButtonHandler()
    screen_mgr = ScreenManager()
    client = BackendClient()

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
        chat = ChatPanel(client, ui_settings=ui_settings)
        screen_mgr.replace(chat)

    def on_unlock():
        home = HomePanel(on_open_chat=open_chat, ui_settings=ui_settings)
        screen_mgr.replace(home)

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
        screen_mgr.update(dt)
        screen_mgr.render(surface)
        driver.update()

        clock.tick(FPS)

    driver.quit()
    print("[BITOS] Shut down.")


if __name__ == "__main__":
    main()
