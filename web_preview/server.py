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
    from client.api import BackendClient

    # Init
    os.environ["SDL_VIDEODRIVER"] = "dummy"  # Headless pygame
    driver = PygameDriver()
    driver.init()
    surface = driver.get_surface()

    button = ButtonHandler()
    screen_mgr = ScreenManager()
    client = BackendClient()

    def open_chat():
        screen_mgr.replace(ChatPanel(client))

    def on_unlock():
        screen_mgr.replace(HomePanel(on_open_chat=open_chat))

    def on_boot_complete():
        screen_mgr.replace(LockScreen(on_unlock=on_unlock))

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
