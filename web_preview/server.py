"""
BITOS Web Preview Server
Serves a live MJPEG stream of the Pygame framebuffer over HTTP.
View on any phone browser for mobile testing.
"""
import os
import sys
import time
import threading
import io

# Add device dir to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "device"))

from flask import Flask, Response, render_template

app = Flask(__name__)

# Frame buffer — updated by the device loop
_current_frame: bytes = b""
_frame_lock = threading.Lock()


def update_frame(frame_bytes: bytes):
    """Called from the device loop to push a new frame."""
    global _current_frame
    with _frame_lock:
        _current_frame = frame_bytes


def generate_mjpeg():
    """MJPEG stream generator."""
    while True:
        with _frame_lock:
            frame = _current_frame

        if frame:
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
            )
        time.sleep(1 / 30)  # 30 FPS cap


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/stream")
def stream():
    return Response(
        generate_mjpeg(),
        mimetype="multipart/x-mixed-replace; boundary=frame",
    )


def run_preview_server(port=5001):
    """Start the preview server in a background thread."""
    port = int(os.environ.get("PORT", port))
    thread = threading.Thread(
        target=lambda: app.run(host="0.0.0.0", port=port, debug=False),
        daemon=True,
    )
    thread.start()
    print(f"[Preview] Running on http://localhost:{port}")
    return thread


if __name__ == "__main__":
    # Standalone mode — start device loop + preview server
    print("[Preview] Starting BITOS device with web preview...")
    print("[Preview] Open on your phone: http://<your-ip>:5001")

    import pygame
    from display.driver import PygameDriver
    from display.tokens import FPS, PHYSICAL_W, PHYSICAL_H
    from input.handler import ButtonHandler
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

    # Init
    os.environ["SDL_VIDEODRIVER"] = "dummy"  # Headless pygame
    driver = PygameDriver()
    driver.init()
    surface = driver.get_surface()

    button = ButtonHandler()
    screen_mgr = ScreenManager()
    client = BackendClient()
    repository = DeviceRepository()
    repository.initialize()

    ui_settings = None
    try:
        ui_settings = client.get_ui_settings()
        print(f"[Preview] UI settings loaded (font={ui_settings.get('font_family')}, scale={ui_settings.get('font_scale')})")
    except Exception as exc:
        print(f"[Preview] UI settings unavailable, using defaults ({exc})")

    def open_chat():
        screen_mgr.replace(ChatPanel(client, ui_settings=ui_settings, repository=repository))

    def open_focus():
        screen_mgr.replace(FocusPanel(on_back=on_home, ui_settings=ui_settings))

    def open_notifications():
        screen_mgr.replace(NotificationsPanel(on_back=on_home, ui_settings=ui_settings))

    def open_settings():
        screen_mgr.replace(
            SettingsPanel(
                repository=repository,
                on_back=on_home,
                on_open_model_picker=open_model_picker,
                on_open_agent_mode=open_agent_mode,
                on_open_sleep_timer=open_sleep_timer,
                on_open_about=open_about,
                ui_settings=ui_settings,
            )
        )

    def open_model_picker():
        screen_mgr.replace(ModelPickerPanel(repository=repository, on_back=open_settings, ui_settings=ui_settings))

    def open_agent_mode():
        screen_mgr.replace(AgentModePanel(repository=repository, on_back=open_settings, ui_settings=ui_settings))

    def open_sleep_timer():
        screen_mgr.replace(SleepTimerPanel(repository=repository, on_back=open_settings, ui_settings=ui_settings))

    def open_about():
        screen_mgr.replace(AboutPanel(on_back=open_settings, ui_settings=ui_settings))

    def on_home():
        screen_mgr.replace(
            HomePanel(
                on_open_chat=open_chat,
                on_open_focus=open_focus,
                on_open_notifications=open_notifications,
                on_open_settings=open_settings,
                ui_settings=ui_settings,
            )
        )

    def on_boot_complete():
        screen_mgr.replace(LockScreen(on_home, ui_settings=ui_settings))

    screen_mgr.push(BootScreen(on_complete=on_boot_complete))

    # Start preview server
    port = int(os.environ.get("PORT", "5001"))
    run_preview_server(port)

    # Main loop
    clock = pygame.time.Clock()
    last_time = time.time()

    try:
        while True:
            now = time.time()
            dt = now - last_time
            last_time = now

            for event in pygame.event.get():
                button.handle_pygame_event(event)
                screen_mgr.handle_input(event)

            button.update()
            screen_mgr.update(dt)
            screen_mgr.render(surface)
            driver.update()

            # Capture frame for web preview
            frame_bytes = driver.capture_frame_bytes()
            if frame_bytes:
                update_frame(frame_bytes)

            clock.tick(FPS)
    except KeyboardInterrupt:
        pass
    finally:
        driver.quit()
