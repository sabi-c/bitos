"""
BITOS Device — Main Entry Point
Initializes display, input, screen manager, and runs the main loop at 30 FPS.
"""
import sys
import os
import time

import pygame

from display.driver import create_driver
from display.tokens import FPS
from input.handler import ButtonHandler, ButtonEvent
from screens.manager import ScreenManager
from screens.boot import BootScreen
from screens.panels.chat import ChatPanel
from client.api import BackendClient


def main():
    print("[BITOS] Starting device...")

    # ── Initialize systems ──
    driver = create_driver()
    driver.init()
    surface = driver.get_surface()

    button = ButtonHandler()
    screen_mgr = ScreenManager()
    client = BackendClient()

    # ── Check server health ──
    server_ok = client.health()
    if server_ok:
        print("[BITOS] Backend connected ✓")
    else:
        print("[BITOS] Backend not reachable — chat will not work until server starts")

    # ── Wire up screens ──
    def on_boot_complete():
        chat = ChatPanel(client)
        screen_mgr.replace(chat)

    boot = BootScreen(on_complete=on_boot_complete)
    screen_mgr.push(boot)

    # ── Button callbacks ──
    def on_short():
        print("[Button] SHORT_PRESS")

    def on_long():
        print("[Button] LONG_PRESS")

    def on_double():
        print("[Button] DOUBLE_PRESS")

    def on_triple():
        print("[Button] TRIPLE_PRESS")

    button.on(ButtonEvent.SHORT_PRESS, on_short)
    button.on(ButtonEvent.LONG_PRESS, on_long)
    button.on(ButtonEvent.DOUBLE_PRESS, on_double)
    button.on(ButtonEvent.TRIPLE_PRESS, on_triple)

    # ── Main loop ──
    clock = pygame.time.Clock()
    running = True
    last_time = time.time()

    while running:
        now = time.time()
        dt = now - last_time
        last_time = now

        # Events
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

        # Update
        button.update()
        screen_mgr.update(dt)

        # Render
        screen_mgr.render(surface)
        driver.update()

        clock.tick(FPS)

    # Cleanup
    driver.quit()
    print("[BITOS] Shut down.")


if __name__ == "__main__":
    main()
