# BITOS Device Architecture Audit

**Date:** 2026-03-15
**Scope:** `/Users/seb/bitos/device/` — the Pi Zero 2W device codebase
**Method:** Full read of every Python module, cross-reference of imports, thread model analysis, test coverage review

---

## 1. Current Architecture Map

### 1.1 Module Inventory

```
device/
├── main.py              — 675 lines. Monolithic entry point, wires everything.
├── __init__.py           — sys.path hack for intra-package imports.
├── audio/                — Recording, STT, TTS, voice pipeline
│   ├── pipeline.py       — AudioPipeline base + MockAudioPipeline + WM8960Pipeline
│   ├── voice_pipeline.py — VoicePipeline (currently UNUSED, see §2.1)
│   ├── recorder.py       — PyAudio recorder (hard dep, breaks tests)
│   ├── transcriber.py    — Whisper STT
│   ├── speaker.py        — Piper TTS
│   ├── player.py         — ALSA audio player
│   ├── stt.py            — STT wrapper
│   ├── tts.py            — TTS wrapper
│   └── wake_word.py      — Wake word detector
├── ble/                  — BLE NUS service + pairing
├── bluetooth/            — Full GATT server, auth, WiFi config, characteristics
├── client/
│   └── api.py            — BackendClient (httpx, SSE streaming)
├── display/
│   ├── tokens.py         — Design tokens (colors, sizes, fonts, layout)
│   ├── theme.py          — Runtime font loading + caching
│   ├── driver.py         — PygameDriver + ST7789Driver
│   ├── animator.py       — StepAnimator (blink, dots, loading bar)
│   └── corner_mask.py    — Rounded corner overlay
├── hardware/
│   ├── whisplay_board.py — WhisPlayBoard singleton, GPIO bridge
│   ├── status_poller.py  — 30s background poll (battery, WiFi, AI health)
│   ├── status_state.py   — Thread-safe shared StatusState
│   ├── system_monitor.py — CPU/RAM/temp/disk logger (psutil)
│   ├── battery.py        — Legacy, unused (see power/battery.py)
│   └── led.py, pi_led.py — Legacy LED control
├── input/
│   └── handler.py        — ButtonHandler: debounce, multi-click, power gesture
├── integrations/
│   ├── contracts.py      — Adapter interfaces (Task, Message, Email, Calendar)
│   ├── adapters.py       — Runtime adapter factory
│   ├── queue.py          — OutboundCommandQueue (SQLite-backed)
│   ├── worker.py         — Command dispatcher
│   ├── runtime.py        — Non-blocking tick loop
│   └── permissions.py    — Permission checking
├── notifications/
│   └── poller.py         — Background health + overdue-task polling
├── overlays/
│   ├── notification.py   — Toast queue, notification shade, records
│   ├── passkey.py        — BLE pairing passkey display
│   ├── power.py          — Shutdown/reboot menu
│   ├── qr_code.py        — QR code overlay for setup/pairing
│   └── quick_capture.py  — Voice quick capture
├── power/
│   ├── battery.py        — PiSugar battery monitor (UNIX socket)
│   ├── idle.py           — Display sleep/dim manager
│   └── leds.py           — LED controller (pulse/blink animations)
├── screens/              — ACTIVE screen system (full-screen panels)
│   ├── base.py           — Screen/BaseScreen base class
│   ├── manager.py        — ScreenManager (deprecated, still in use)
│   ├── boot.py           — Boot screen with health checks
│   ├── lock.py           — PIN lock screen
│   ├── components/
│   │   └── nav.py        — NavItem + VerticalNavController
│   ├── panels/           — Full-screen interactive panels (the real UI)
│   │   ├── chat.py       — 549 lines, voice-first chat
│   │   ├── settings.py   — 977 lines, 8 sub-panels in one file
│   │   ├── messages.py   — 321 lines, BlueBubbles iMessage
│   │   ├── mail.py       — 308 lines, Gmail
│   │   ├── focus.py      — 213 lines, Pomodoro timer
│   │   ├── home.py       — 209 lines, nav hub
│   │   ├── change_pin.py — 210 lines, PIN change flow
│   │   ├── tasks.py      — 120 lines, Things tasks
│   │   ├── captures.py   — 79 lines, voice captures list
│   │   └── notifications.py — 119 lines
│   ├── modals/           — Capture modal, power menu (for ui/ system)
│   └── subscreens/
│       └── integration_detail.py
├── storage/
│   └── repository.py     — DeviceRepository (SQLite, 5 migrations)
└── ui/                   — ALTERNATE screen system (sidebar composite)
    ├── screen_manager.py — Second ScreenManager (different API)
    ├── composite_screen.py — Sidebar + right panel layout
    ├── panel_registry.py — Maps sidebar labels to render-only panels
    ├── fonts.py          — get_font() with different FONT_PATH
    ├── font_sizes.py     — Separate font size constants
    ├── draw_utils.py     — WiFi/battery/lock/mail/settings icons
    ├── components/
    │   ├── sidebar.py    — 84px sidebar renderer
    │   ├── status_bar.py — White status bar
    │   └── hint_bar.py   — Bottom hint bar
    └── panels/           — Render-only right panels (9 panels, ~880 lines)
```

### 1.2 Dependency Graph (Key Flows)

#### Button Press → Screen Update

```
GPIO/Keyboard Event
    → ButtonHandler._on_press() / ._on_release()
    → ButtonHandler.update() detects gesture type
    → _emit(ButtonEvent.SHORT_PRESS | DOUBLE_PRESS | ...)
    → main._on_button() callback
        → IdleManager.wake()
        → if power_overlay: power_overlay.handle_input()
        → else: ScreenManager.handle_action(action_name)
            → if overlay active: overlay.handle_input()
            → if passkey overlay: passkey.handle_input()
            → if notification queue: queue.handle_input()
            → if notification shade: shade.handle_input()
            → else: current_screen.handle_action(action_name)
                → Panel-specific logic (e.g., ChatPanel._capture_voice_input())
    → [next frame] ScreenManager.render(surface)
        → current_screen.render(surface)
    → corner_mask.apply(surface)
    → driver.update() → SPI push to ST7789
```

#### Voice Input → Backend → Response → Display

```
ChatPanel: DOUBLE_PRESS on SPEAK
    → _capture_voice_input()
    → LED.listening()
    → NEW THREAD: _do_voice_capture()
        → audio_pipeline.record() → starts arecord subprocess
        → poll _voice_stop_requested flag (100ms ticks)
        → audio_pipeline.stop_recording() → terminates arecord
        → audio_pipeline.transcribe(path) → Whisper STT
        → _input_text = transcribed text
        → _send_message()
            → messages.append(user message)
            → repository.add_message()
            → LED.thinking()
            → NEW THREAD: _stream_response(text)
                → BackendClient.chat(text) → httpx SSE stream
                    → POST /chat with agent_mode, tasks, battery, model
                    → yields text chunks
                → Update messages[-1]["text"] under _messages_lock
                → repository.add_message(assistant)
                → audio_pipeline.speak(text) → Piper TTS
    → [main thread renders each frame, sees updated messages]
```

### 1.3 Threading Model

**Main thread:** pygame event loop at 15 FPS. Handles:
- `pygame.event.get()` + `button.handle_pygame_event()`
- `button.update()` (GPIO polling)
- `idle_mgr.tick()`
- `outbound_loop.tick()`
- `screen_mgr.update(dt)` + `screen_mgr.render(surface)`
- `driver.update()` (SPI blit)

**Background daemon threads (always running):**

| Thread | Module | Interval | Purpose |
|--------|--------|----------|---------|
| battery-monitor | `power/battery.py` | 30s | PiSugar UNIX socket polling |
| status-poller | `hardware/status_poller.py` | 30s | Battery + WiFi + AI health |
| system-monitor | `hardware/system_monitor.py` | 30s | CPU/RAM/temp/disk logging |
| notification-poller | `notifications/poller.py` | 1s check, 30s health, 300s tasks | Health + overdue task notifications |
| device-status-char | `bluetooth/characteristics/device_status.py` | 30s | BLE status broadcast |
| bitos-ble | `ble/ble_service.py` | Continuous | BLE NUS service |
| pairing-watcher | `ble/pairing_manager.py` | Continuous | ANCS + pairing |
| bitos-gatt | `bluetooth/server.py` | Continuous | GATT server |

**Ephemeral threads (created on demand):**

| Origin | Purpose |
|--------|---------|
| ChatPanel._do_voice_capture | Voice recording + transcription |
| ChatPanel._stream_response | SSE streaming + TTS |
| TasksPanel._fetch_tasks | Background task fetch |
| MessagesPanel._load_conversations | iMessage conversation fetch |
| MailPanel._load_threads | Gmail thread fetch |
| BootScreen checks | Parallel health check threads |
| LEDController._animate | LED pulse/blink animations |

**Synchronization primitives:**
- `StatusState._lock` — threading.Lock for status bar fields
- `ChatPanel._messages_lock` — threading.Lock for message deque
- `BatteryMonitor._lock` — threading.Lock for battery state
- `LEDController._lock` — threading.Lock for animation state
- `StatusPoller._stop` — threading.Event for clean shutdown
- `NotificationPoller._stop` — threading.Event for clean shutdown

### 1.4 State Management

**SQLite (DeviceRepository):**
- Sessions + messages (chat history)
- Settings (key-value, typed get/set)
- Tasks (cached from server)
- Notifications (persisted records)
- Quick captures
- Outbound command queue (pending/retrying/dead_letter)

**In-memory (component-local):**
- Each panel holds its own UI state (cursor position, scroll offset, loading state)
- `StatusState` — shared mutable object, thread-safe with lock
- `ScreenManager._stack` — screen navigation stack
- `NotificationQueue._active` + `_queue` — active toast + pending toasts

**State restoration:**
- `/tmp/bitos_state.json` — minimal screen name + timestamp, expires after 300s
- `pomodoro_state` setting — focus timer state for hot restarts

---

## 2. Code Quality Audit

### 2.1 Dead Code and Unused Imports

**VoicePipeline (device/audio/voice_pipeline.py):**
The file header says "STATUS: Currently unused." It is imported in `main.py` with `# noqa: F401`, instantiated, and stashed as `screen_mgr._voice_pipeline` but never consumed. The `ai_send_fn` placeholder in `main.py` (lines 195-205) creates a raw `anthropic.Anthropic` client that duplicates the backend's job. This entire subsystem is dead weight.

**hardware/battery.py vs power/battery.py:**
There are two battery modules. `hardware/battery.py` exists alongside the active `power/battery.py` (PiSugar socket-based). The `hardware/__init__.py` exports `StatusPoller` and `StatusState` but the battery module in `hardware/` may be vestigial.

**hardware/led.py + hardware/pi_led.py vs power/leds.py:**
LED control exists in both `hardware/` and `power/` directories. `main.py` uses `power.leds.LEDController`. The hardware LED files appear to be earlier versions.

**ui/ panel system:**
The entire `ui/panels/` directory (9 render-only panels, ~880 lines) provides static previews for the sidebar composite view. These panels duplicate panel names and rendering logic from `screens/panels/` but contain hardcoded dummy data (e.g., `HomePanel` in `ui/panels/home.py` has hardcoded weather "72 PARTLY CLOUDY BURBANK CA" and fake tasks). They are not wired to real data.

**BackendClient.chat() redundancy (lines 91-116):**
The `chat()` method creates a fresh `DeviceRepository()` and `BatteryMonitor()` on every call rather than receiving them as constructor dependencies. This means a new SQLite connection and a new battery socket connection per chat message.

### 2.2 Duplicated Logic

**`_wrap_text()` — 3 identical implementations:**
- `screens/panels/chat.py:501`
- `screens/panels/messages.py:307`
- `screens/panels/mail.py:294`

All three are character-level word wrap using `self._font.size()`. Should be a single utility function in `display/theme.py` or a mixin.

**`_render_skeleton()` — 3 identical implementations:**
- `screens/panels/tasks.py:76`
- `screens/panels/messages.py:179`
- `screens/panels/mail.py:163`

Identical blinking skeleton loading rows. Should be in `BaseScreen` or a rendering utility.

**`_render_status_bar()` — 2 near-identical implementations:**
- `screens/panels/messages.py:200` — renders `"dot TITLE battery%"` on white bg
- `screens/panels/mail.py:184` — same pattern but subtly different (white text vs black bg)

The main `ScreenManager` also has its own `_render_status_bar()` with different behavior.

**Font loading — 3 competing systems:**
1. `display/tokens.py` — `FONT_PATH = "assets/fonts/PressStart2P.ttf"`, `FONT_REGISTRY`
2. `display/theme.py` — `load_ui_font()` with `_FONT_CACHE`, uses `FONT_REGISTRY`
3. `ui/fonts.py` — `FONT_PATH = "assets/fonts/PressStart2P-Regular.ttf"` (different filename!), `@lru_cache get_font()`

The `ui/` system references a different font filename (`PressStart2P-Regular.ttf` vs `PressStart2P.ttf`). This will silently fall back to monospace if the file doesn't exist.

**Font size constants — 2 competing sources:**
1. `display/tokens.py` — `FONT_SIZES` dict with time_large, timer, title, body, small, hint
2. `ui/font_sizes.py` — Named constants: `TIME_LARGE=24, TITLE=16, BODY=12, CAPTION=10, HINT=8` plus extras

**Color constants — 3 competing sources:**
1. `display/tokens.py` — `BLACK, WHITE, DIM1-DIM4, HAIRLINE`
2. `ui/panels/base.py` — `GRAY_080808, GRAY_0A, GRAY_111, GRAY_1A, GRAY_222, GRAY_333, GRAY_444, GRAY_555, GRAY_666, GRAY_AAA` (12 grays)
3. `ui/screen_manager.py` — `GRAY_11, GRAY_51, GRAY_85` (3 more grays)

These 3 systems define overlapping but inconsistent color palettes.

**Overlay font caching — 5 identical `_font()` methods:**
Every overlay (`notification.py` NotificationToast + NotificationShade, `passkey.py`, `power.py`, `qr_code.py`, `quick_capture.py`) has its own `_font()` method with identical try/except logic. Should be centralized.

### 2.3 Inconsistent Patterns

**Two ScreenManagers:**
- `screens/manager.py` — Active, used by `main.py`. Issues deprecation warning in `__init__`.
- `ui/screen_manager.py` — Different API (takes surface in constructor, draws status bar itself). Used by... nothing in production?

**Two BaseScreen/Screen classes:**
- `screens/base.py` — `Screen` class with `handle_event(ButtonEvent)`, `draw()`, `get_hint()`, `get_breadcrumb()`. Aliased as `BaseScreen`.
- `ui/panels/base.py` — `BasePanel` class with `render()`, `draw_header()`, `draw_action_row()`.

The `screens/panels/` panels extend `BaseScreen` but override `render()` and `handle_action(str)` — neither of which is defined on `BaseScreen`. They also define `handle_input(pygame.event.Event)` for keyboard fallback. The base class methods (`handle_event`, `draw`, `get_hint`) are mostly unused.

**Two competing UI paradigms:**
1. **Full-screen panels** (`screens/panels/`): Each panel owns the entire 240x280 surface. Used by main.py via ScreenManager. Interactive, data-connected.
2. **Sidebar composite** (`ui/`): CompositeScreen splits screen into sidebar (84px) + right panel (156px). Right panels are render-only with dummy data. Used as the home screen.

This creates confusion: when the user selects "CHAT" on the sidebar, it triggers `open_chat()` which pushes a full-screen ChatPanel, completely replacing the sidebar layout.

**Panel `__init__` signatures:**
No consistency. Some panels take `client, repository, audio_pipeline, led, on_back, ui_settings`. Others take `repository, on_back, ui_settings`. Settings panel takes 18 constructor arguments. These should use a context/config object.

**`handle_action` vs `handle_event` vs `handle_input`:**
Three different input method names across the codebase:
- `handle_action(str)` — used by all `screens/panels/` panels. Receives "SHORT_PRESS", "DOUBLE_PRESS", etc.
- `handle_event(ButtonEvent)` — defined on `Screen` base class, used by `ui/screen_manager.py`.
- `handle_input(pygame.event.Event)` — keyboard fallback on panels, also used by ScreenManager for raw pygame events.

### 2.4 Missing Error Handling / Swallowed Exceptions

**ChatPanel._stream_response (line 456):**
```python
except Exception:
    self._mark_failed(message, "unknown", True)
```
Catches all exceptions silently. No logging. If the SSE stream fails mid-parse, the user gets a generic "unknown error" with no diagnostic trail.

**ChatPanel._do_voice_capture TTS (line 447):**
```python
except Exception:
    pass
```
TTS failure is completely swallowed. If the speaker fails, the user gets no audio and no visual indication of why.

**CapturesPanel.handle_action (lines 46-54):**
Imports `VikunjaAdapter` from the server package at runtime (`sys.path.insert`), catches all exceptions with a warning log. This cross-package import is fragile and will fail on the device where the server code isn't co-located.

**StatusPoller._poll (lines 60-67):**
Second API call block (`get_integration_status`) has a bare `except Exception: pass`. If the API returns unexpected data, it's silently ignored.

**BackendClient.chat() (lines 91-122):**
Creates a new `DeviceRepository()` and `BatteryMonitor()` per call. If repository init fails, it catches with `logging.debug` — easy to miss. The `BatteryMonitor()` creates a new instance that tries to connect to the PiSugar socket, which is wasteful and potentially racy.

### 2.5 Thread Safety Issues

**TasksPanel — no lock on `_tasks` and `_state`:**
`_fetch_tasks()` spawns a thread that writes `self._tasks` and `self._state`. The main thread reads both in `render()` and `handle_action()`. No lock protects these fields. On CPython the GIL provides some protection for simple attribute assignments, but list replacement during iteration could cause stale reads.

**MessagesPanel — no lock on `_conversations`, `_messages`, `_loading`:**
Same pattern. Constructor spawns `_load_conversations` thread that sets `self._conversations` and `self._loading`. The main thread reads both in `render()`.

**MailPanel — identical to MessagesPanel.**
No lock on `_threads`, `_messages`, `_loading`.

**ChatPanel._do_voice_capture:**
Sets `self._is_streaming`, `self._status_detail` from a background thread. `_is_streaming` is read by `handle_action()` and `render()` on the main thread. While individually atomic in CPython, the combination of multiple field updates without a lock means the render thread can see inconsistent intermediate states (e.g., `_is_streaming=True` but `_status_detail` not yet updated).

**StatusPoller writes to StatusState:**
Properly locked via `StatusState._lock`. This is the correct pattern.

**LEDController — proper lock usage.**
Animation thread checks `self._running` under lock. Correct pattern.

### 2.6 Hardcoded Values Not in tokens.py

- `ChatPanel._ACTION_ROW_H = 18`, `_HINT_H = 12` — layout constants embedded in panel
- `MessagesPanel` constants: `LIST_ROW_H`, `THREAD_ROW_H`, `CONFIRM_BOX_H`, etc. (29 lines of constants at top)
- `MailPanel.CONFIRM_HINT_ROWS` — UI strings embedded in class
- `CornerMask.CORNER_RADIUS = 8` — conflicts with `tokens.CORNER_RADIUS = 20`
- `Sidebar.ITEM_H = 27` — not in tokens
- `StatusBar.BAR_H = 20` — duplicates `tokens.STATUS_BAR_H = 20` (same value, different constant)
- `BasePanel.HDR_H = 22` — panel header height, conflicts with `STATUS_BAR_H = 20`
- Version string `"1.0.0"` hardcoded in `main.py:338` and `settings.py:605`

---

## 3. Testing Gaps

### 3.1 Test Coverage Summary

**377 tests collected**, 2 collection errors (pyaudio import). Based on file names:

| Panel | Test File | Coverage |
|-------|-----------|----------|
| ChatPanel | test_chat_panel.py, test_chat_persistence.py, test_chat_reliability.py, test_chat_templates.py, test_chat_queue_status.py | Good logic coverage, render tests skipped on macOS |
| TasksPanel | test_tasks_panel.py | Has tests |
| FocusPanel | test_focus_panel.py, test_pomodoro_persist.py | Has tests |
| MessagesPanel | test_messages_panel.py | Has tests |
| MailPanel | test_mail_panel.py | Has tests |
| SettingsPanel | test_settings_wiring.py, test_settings_companion.py | Has tests |
| NotificationsPanel | test_notification_overlay.py, test_notification_shade.py, test_notification_poller.py, test_notification_persistence.py | Good coverage |
| HomePanel | (none found) | **NO TESTS** |
| CapturesPanel | test_quick_capture.py | Partial |
| ChangePinPanel | test_pin_lock.py | Has tests |
| CompositeScreen | test_composite_screen.py | Has tests |
| ButtonHandler | test_button_handler.py | Has tests |
| DeviceRepository | test_device_repository.py | Has tests |
| BackendClient | test_server_chat_bridge_api.py | Has tests |
| Bluetooth | test_bluetooth_auth.py, test_bluetooth_server.py, test_ble_*.py | Good coverage |
| LED | test_led.py | Has tests |
| IdleManager | test_idle_manager.py | Has tests |
| BatteryMonitor | test_battery_monitor.py | Has tests |
| AudioPipeline | test_audio_pipeline.py | Has tests |
| SystemMonitor | test_system_monitor.py | Has tests |

### 3.2 Untested Areas

1. **HomePanel (screens/panels/home.py)** — no dedicated test file. Navigation routing, capture count refresh, status badge logic untested.
2. **IntegrationDetailPanel** — no test file.
3. **BootScreen health check flow** — test_boot_sequence.py fails to import (pyaudio dependency).
4. **DevPanel** — no dedicated tests. `_get_ip()` and `_get_commit()` are static methods with external dependencies (socket, subprocess).
5. **ui/ panel system** — render-only panels have no tests at all (HomePanel, ChatPanel, etc. in `ui/panels/`). The CompositeScreen test covers the container but not individual right panels.
6. **Thread safety** — no tests verify that concurrent thread access to TasksPanel, MessagesPanel, or MailPanel state is safe.
7. **ST7789Driver** — `_rgb888_to_rgb565()` has no unit test. The frame diff skip logic is untested.
8. **Power flow** — `_execute_power_action()`, `_save_runtime_state()`, `_request_backend_shutdown()` — no tests.
9. **WhisPlayBoard integration** — untestable on macOS, no mock.

### 3.3 The pygame Segfault Problem

**Affected tests:** Any test that calls `font.render()` with `SDL_VIDEODRIVER=dummy` on macOS.

**Pattern seen in test_chat_panel.py (line 64-68):**
```python
@unittest.skipIf(
    os.environ.get("SDL_VIDEODRIVER") == "dummy",
    "pygame segfaults rendering fonts with dummy video driver on macOS",
)
def test_render_without_error(self):
    panel.render(self.surface)
```

**Root cause:** pygame's dummy video driver on macOS lacks a real rendering backend. `Font.render()` with anti-aliasing disabled (`False`) on some pygame builds triggers a segfault in the underlying SDL_ttf C library.

**Scope:** This affects ALL `render()` test methods. Currently, render tests are either skipped or run only in CI (Linux with Xvfb).

**Potential solutions:**
1. **Headless rendering with `pygame.NOFRAME`** — Create a hidden window instead of using dummy driver. Works on macOS with XQuartz but requires a display server.
2. **Surface-only rendering** — Use `pygame.init()` without `pygame.display.set_mode()`. Create surfaces manually. The segfault may be in font init, not surface blitting.
3. **pytest-xvfb** — On CI, use Xvfb virtual framebuffer. For local macOS dev, skip render tests.
4. **Extract rendering logic** — Make panels compute layout data (positions, text, colors) as pure functions, test those. Only test actual blitting in integration tests.
5. **Use `pygame.freetype`** — The `freetype` module is more robust than `pygame.font` and may not segfault in headless mode.

### 3.4 Mock Realism

- `MockAudioPipeline` is realistic — records to temp file, transcribe returns file content.
- `BackendClient` is well-mocked in tests with `MagicMock`.
- `DeviceRepository` — tests use real SQLite (`:memory:` or temp files). Good.
- `WhisPlayBoard` — mocked as `None` everywhere. Board interaction code is untestable.
- `BatteryMonitor` — tests mock the UNIX socket. Good.

---

## 4. Performance Concerns (Pi Zero 2W)

### 4.1 Memory Usage

**Font caching:**
- `display/theme.py` has `_FONT_CACHE: dict[tuple[str, int], pygame.font.Font]` — unbounded growth. Every unique (family, size) pair persists forever. With 2 font families and 6 size roles, this is ~12 entries max. Acceptable.
- `ui/fonts.py` uses `@lru_cache(maxsize=16)`. Bounded. Good.
- Overlays cache fonts per-instance in `self._fonts: dict`. Since overlays are short-lived, these get GC'd. Acceptable.
- **CONCERN:** Each `NotificationToast` creates its own `_fonts` dict. If toasts queue up, each has its own cached fonts. The queue is bounded to 3, so max ~9 extra font objects.

**Surface allocation:**
- `CornerMask.__init__` pre-renders a 240x280 SRCALPHA surface (~269KB). Created once. Fine.
- `CompositeScreen.__init__` creates `_right_surface = pygame.Surface((156, 250))` — ~156KB. Created once. Fine.
- `PygameDriver` creates one 240x280 surface + scales to window on every `update()`. The `pygame.transform.scale()` creates a temporary surface each frame. On desktop this is fine; on Pi it's not reached (ST7789Driver is used instead).
- **CONCERN:** `ST7789Driver.update()` calls `pygame.image.tostring(surface, "RGB")` every frame — allocates a 201,600-byte string (240x280x3). Then `_rgb888_to_rgb565()` allocates a 134,400-byte `bytearray`. That's 336KB of allocation per frame at 15 FPS = ~5MB/s of allocation churn. The GC can handle this but it's wasteful.
- **Frame diff optimization:** `ST7789Driver` stores `self._board.previous_frame` and skips SPI writes if the raw RGB bytes match. Good optimization, but the string comparison itself is O(200K) per frame.

**SQLite connections:**
`DeviceRepository._connect()` opens a new connection for every operation (`with closing(self._connect())`). On Pi Zero 2W, SQLite connection setup is cheap (~0.1ms), but frequent DB access (e.g., `_queue_status_copy()` called every render frame from ChatPanel) means many short-lived connections. Consider a persistent connection with WAL mode.

### 4.2 CPU Hotspots

**Full-screen redraw every frame:**
Yes, every frame clears and redraws the entire 240x280 surface. At 15 FPS this is ~66ms per frame budget. On Pi Zero 2W:
- `surface.fill(BLACK)` — memset 201KB, fast
- Font rendering — `Font.render()` is the expensive call. Each panel renders 5-15 text strings per frame. Press Start 2P is bitmap font, so this should be cheap.
- The real CPU cost is in the SPI transfer: pushing 134KB of RGB565 data over SPI at the typical 32MHz clock takes ~4ms. Acceptable.

**`_rgb888_to_rgb565()` — pure Python byte loop:**
This is a hot path: 67,200 iterations of Python bytecode per frame. On Pi Zero 2W (~350 MIPS for Python), this could take 20-50ms. **This is the single biggest CPU bottleneck.** Should be replaced with numpy vectorized conversion or a C extension.

**`SystemMonitor.get_snapshot()` — `psutil.cpu_percent(interval=0.1)`:**
Called from DevPanel every 2 seconds. The `interval=0.1` parameter blocks for 100ms. On the main thread this would be a problem, but `_log_stats()` runs in a background thread with `interval=1`, so the main thread is only affected when DevPanel calls `_refresh()` → `get_snapshot()` from `update()`. Since DevPanel is rarely open, this is low priority.

**ChatPanel._wrap_text() — called every render frame:**
Wraps every message character-by-character using `font.size()` per character. For 50 messages averaging 100 chars each, that's 5,000 `font.size()` calls per frame. Should cache wrapped text and only re-wrap when messages change.

### 4.3 I/O Bottlenecks

**SPI display:** As noted, ~4ms per frame for full-frame SPI write. The frame-diff skip helps when the screen is static.

**Audio pipeline:** `arecord` and `aplay` are subprocess-based. Process creation on Pi Zero 2W is ~50-100ms. Recording uses 48kHz stereo S16_LE, which is 192KB/s — well within the SD card write speed.

**Network calls:** `BackendClient` uses httpx with 5-60s timeouts. All network calls run in background threads. The SSE streaming in `_stream_chat_sse` holds a connection open during the entire response. If the server is local (same Pi or LAN), latency is minimal.

**SQLite:** Single-threaded access pattern (each call opens/closes its own connection). No WAL mode configured. Under heavy write load (chat messages + queue commands + settings), write contention could cause 10-50ms delays. The repository should use WAL mode.

---

## 5. Refactoring Recommendations

### 5.1 Quick Wins (1-2 hours each)

**Q1. Extract `_wrap_text()` to shared utility**
Move the character-level word wrap to `display/theme.py` as `wrap_text(text, max_width, font)`. Remove 3 duplicate implementations. Add result caching keyed on `(text, max_width)`.

**Q2. Extract `_render_skeleton()` to shared utility**
Move skeleton loading rows to a function in `display/theme.py` or a new `display/render_utils.py`. Remove 3 duplicates.

**Q3. Centralize overlay font caching**
Create a single `get_overlay_font(tokens, role)` function. Replace 5 identical `_font()` methods across overlays.

**Q4. Fix the font path inconsistency**
`ui/fonts.py` references `PressStart2P-Regular.ttf` while `display/tokens.py` references `PressStart2P.ttf`. Unify to one path from `tokens.py`.

**Q5. Remove dead VoicePipeline import and instantiation**
Delete lines 63-65 and 207-214 from `main.py`. Remove `ai_send_fn` placeholder. The `audio/voice_pipeline.py` file can remain for future use but shouldn't be imported at startup.

**Q6. Add locks to TasksPanel, MessagesPanel, MailPanel**
Add `threading.Lock()` to protect `_tasks`/`_state`, `_conversations`/`_loading`, `_threads`/`_loading`. Match the pattern already used in ChatPanel.

**Q7. Fix CornerMask radius conflict**
`corner_mask.py` uses `CORNER_RADIUS = 8`, `tokens.py` defines `CORNER_RADIUS = 20`. Import from tokens or document the intentional difference.

**Q8. Enable WAL mode in DeviceRepository**
Add `conn.execute("PRAGMA journal_mode=WAL")` in `_connect()`. Reduces write contention.

### 5.2 Medium-Term Improvements (half-day to 1 day each)

**M1. Optimize `_rgb888_to_rgb565()` with numpy**
Replace the pure-Python byte loop with:
```python
import numpy as np
raw = np.frombuffer(raw_rgb, dtype=np.uint8).reshape(-1, 3)
r, g, b = raw[:, 0], raw[:, 1], raw[:, 2]
rgb565 = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
return rgb565.astype('>u2').tobytes()
```
Expected speedup: 10-50x (20-50ms → 1-5ms per frame).

**M2. Unify the ScreenManager**
Delete `ui/screen_manager.py` (the unused one). Remove the deprecation warning from `screens/manager.py`. Establish `screens/manager.py` as the single source of truth.

**M3. Merge font/color constant systems**
Move all colors into `display/tokens.py` (including the grays from `ui/panels/base.py`). Move all font sizes there too. Delete `ui/font_sizes.py`. Make `ui/fonts.py` import from `display/tokens.py`.

**M4. Create PanelContext dataclass**
Replace the 10-18 constructor arguments with:
```python
@dataclass
class PanelContext:
    client: BackendClient
    repository: DeviceRepository
    audio_pipeline: AudioPipeline
    led: LEDController
    ui_settings: dict
    on_back: Callable | None = None
```
Pass this to all panels. Reduces main.py wiring from 200 lines to ~50.

**M5. Fix BackendClient.chat() to use injected dependencies**
Stop creating new `DeviceRepository()` and `BatteryMonitor()` instances per call. Accept them in the constructor or via a context object.

**M6. Add render-output caching**
ChatPanel wraps all messages every frame. Cache the wrapped lines and only recompute when `_messages` changes (check a generation counter).

**M7. Consolidate the dual panel systems**
Either:
- (A) Make `ui/panels/` read real data from a shared state store, turning them into useful sidebar previews. Or:
- (B) Delete `ui/panels/` entirely and make the sidebar composite show a simple icon/label instead of a rendered preview.

Option B is simpler and removes ~880 lines of dead code.

**M8. Fix pyaudio import chain for tests**
Make `audio/recorder.py` use lazy imports for `pyaudio` (import inside methods, not at module level). This unblocks `test_boot_sequence.py` and `test_audio_wm8960.py` on environments without pyaudio.

### 5.3 Architectural Changes (OS Rethink Phase)

**A1. Event bus / message passing**
Replace the current callback-heavy wiring in `main.py` (660+ lines of closures and function wiring) with a simple event bus:
```python
class EventBus:
    def emit(self, event: str, **data): ...
    def on(self, event: str, handler: Callable): ...
```
Panels emit events ("open_chat", "navigate_back", "voice_captured"), the bus routes them. Decouples panels from the screen manager and from each other.

**A2. Proper screen lifecycle with DI container**
Replace the closure-based panel construction in `main.py` with a registry:
```python
class ScreenFactory:
    def create(self, name: str, **overrides) -> BaseScreen: ...
```
The factory holds references to shared services (client, repository, audio, led). Screens request what they need. main.py shrinks to ~100 lines.

**A3. Dirty-rectangle rendering**
Instead of clearing and redrawing the entire screen every frame:
1. Each panel tracks which regions changed.
2. Only redraw changed rectangles.
3. Only push changed regions to ST7789 (the WhisPlayBoard API supports region writes).

This could reduce per-frame CPU and SPI time by 50-90% for static screens.

**A4. Persistent SQLite connection + connection pool**
Replace per-call `_connect()` / `closing()` with a module-level persistent connection:
```python
class DeviceRepository:
    def __init__(self, db_path):
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._lock = threading.Lock()
```
Use the lock for thread safety. Eliminates connection setup overhead.

**A5. Separate `screens/panels/settings.py` into individual files**
The 977-line settings file contains 8 panel classes (SettingsPanel, ModelPickerPanel, AgentModePanel, SleepTimerPanel, AboutPanel, BatteryPanel, DevPanel, FontPickerPanel). Each should be its own file under `screens/panels/settings/`.

**A6. Formalize the input protocol**
Define a single `handle_button(action: str) -> bool` method on BaseScreen. Remove `handle_event(ButtonEvent)`, `handle_input(pygame.event.Event)`, and `handle_action(str)`. The ScreenManager translates both GPIO events and keyboard events into action strings before dispatching.

**A7. Extract main.py orchestration**
Split main.py into:
- `device/app.py` — `BitosApp` class with `setup()`, `run()`, `shutdown()`
- `device/wiring.py` — dependency construction and panel registration
- `device/main.py` — just `if __name__ == "__main__": BitosApp().run()`

---

## 6. Summary of Top Priorities

| # | Item | Type | Impact | Effort |
|---|------|------|--------|--------|
| 1 | Optimize `_rgb888_to_rgb565()` with numpy | Performance | High (20-50ms/frame saved) | 1h |
| 2 | Add thread locks to 3 panels | Safety | High (prevents race conditions) | 30m |
| 3 | Extract `_wrap_text()` + `_render_skeleton()` | Cleanup | Medium (removes 90 lines duplication) | 1h |
| 4 | Fix BackendClient.chat() per-call instantiation | Performance + Safety | Medium | 30m |
| 5 | Remove dead VoicePipeline wiring | Cleanup | Low (removes confusion) | 15m |
| 6 | Unify font path + color constant systems | Cleanup | Medium (prevents silent fallback bugs) | 2h |
| 7 | Enable WAL mode in SQLite | Performance | Medium | 10m |
| 8 | Lazy-import pyaudio in recorder.py | Testing | Medium (unblocks 2 test files) | 15m |
| 9 | Delete or data-connect ui/panels/ | Cleanup | Medium (removes 880 lines dead code) | 2-4h |
| 10 | Split settings.py into individual files | Maintainability | Medium | 2h |
