# Embedded UI Landscape Research

**Date:** 2026-03-15
**Context:** BITOS pocket AI companion -- Pi Zero 2W, 240x280 ST7789 display, pygame at 15 FPS, single-button navigation with planned scroll wheel and additional buttons.

---

## 1. Smartwatch OS UI Patterns

### 1.1 Pebble OS

Pebble is the closest spiritual ancestor to BITOS: a resource-constrained device with physical buttons and a tiny screen, running on FreeRTOS with ARM Cortex-M microcontrollers.

**Navigation model:** 4 physical buttons -- left (back), right-center (select/action), top-right and bottom-right (up/down). No touchscreen. All navigation is button-driven through hierarchical menus and lists.

**Timeline UI (Pebble OS 3.0):** The signature innovation was a temporal metaphor -- the watchface sits in the "present," scrolling up reveals past events (missed notifications, completed items), scrolling down reveals future events (calendar, reminders, weather). This is a powerful pattern for an AI companion: time as the primary organizational axis.

**Card-based system:** Each notification or app view is a discrete card. Transitions between cards use morphing animations to maintain spatial continuity on the constrained display. Apps are either watchfaces or watchapps, keeping the mental model simple.

**Key takeaway for BITOS:** Pebble proved that 4 buttons + cards + a clear spatial metaphor (timeline) is sufficient for a rich interaction model. The timeline concept maps well to an AI companion's conversation history.

Sources:
- [Pebble OS Open Source](https://opensource.googleblog.com/2025/01/see-code-that-powered-pebble-smartwatches.html)
- [Pebble UX Design Guide](https://www.scribd.com/document/281212800/UX-Guide-for-Pebble-Watch)

### 1.2 Apple Watch / watchOS

**Digital Crown:** A scroll wheel that serves as the primary navigation input. In watchOS 10, Apple went all-in on the Crown: turning it from any watch face reveals the Smart Stack (a vertically-scrolling stack of widgets), and continuing to turn flips through widgets. Apps use the Crown to scroll, paginate, and make precise adjustments.

**Smart Stack widgets:** Widgets occupy roughly one-third of the screen, so two are visible at once with a peek at the next. On-device machine learning reorders widgets by relevance (time of day, location, recent usage). Design guidance: widgets should be glanceable in under 10 seconds. Content uses standardized layouts with bar gauges, circular graphics, or text blocks.

**Page-based navigation:** Apps can split content into full-screen pages that the Crown flips between (horizontal or vertical pagination), rather than long scrolling lists. This is more natural on a tiny screen than continuous scroll.

**Complications:** Small data widgets embedded directly on the watch face (weather, heart rate, next calendar event). Tapping a complication launches its parent app. These are the ultimate glanceable pattern -- single-value data points visible without any interaction.

**Key takeaway for BITOS:** The scroll wheel + page-flipping paradigm is directly applicable. Smart Stack's relevance-based ordering is a pattern BITOS should adopt: surface the most contextually relevant card/widget automatically.

Sources:
- [watchOS 10 Digital Crown](https://eshop.macsales.com/blog/86076-watchos-10-finally-makes-full-use-of-the-digital-crown-on-apple-watch/)
- [watchOS 10 Design (Domus)](https://www.domusweb.it/en/news/2023/07/11/watchos-10-how-apple-refounded-the-wearable-interface.html)
- [WWDC23: Design widgets for Smart Stack](https://developer.apple.com/videos/play/wwdc2023/10309/)
- [WWDC23: Design and build for watchOS 10](https://developer.apple.com/videos/play/wwdc2023/10138/)

### 1.3 Garmin (Connect IQ)

**5-button interface:** Up, Down, Select, Back, Menu/Power. No touchscreen on most models. The bottom two left-side buttons scroll through a customizable widget carousel.

**Widget Glances:** A newer pattern where scrolling through widgets shows a compressed "glance" view (three visible at once) rather than full-screen widgets. Users press Select to expand a glance into the full widget. This reduces key presses and lets users scan more information faster.

**Menu system:** Action menus auto-dismiss when an item is selected or back is pressed. Long-press on the Menu button opens system settings.

**Key takeaway for BITOS:** The glance-then-expand pattern is highly relevant. Show compressed previews (conversation snippet, task count, weather) in a scrollable list, expand on select. This works perfectly with a scroll wheel + button.

Sources:
- [Garmin Connect IQ WatchUi API](https://developer.garmin.com/connect-iq/api-docs/Toybox/WatchUi.html)
- [Garmin Widget Glances](https://the5krunner.com/2020/02/04/garmin-widget-glances-on-the-945-and-beyond/)
- [Garmin Core UI Topics](https://developer.garmin.com/connect-iq/core-topics/user-interface/)

### 1.4 Fitbit OS

**Swipe-based navigation (OS 5.0+):** From the clock face: swipe down for notifications, left for app grid, up for health stats/widgets, right for quick settings. Swipe left-to-right acts as "back." Side button always returns to clock face.

**Key design change:** Fitbit removed horizontal Panorama views and Pagination Dots because they conflicted with the swipe-back gesture. Replaced with vertical scroll lists -- a lesson in how navigation gestures constrain layout options.

**Design philosophy:** "Experiences that are accessible, clear, and consistent." Emphasis on visual simplicity and standard components.

**Key takeaway for BITOS:** Since BITOS uses buttons not touch, Fitbit's swipe model isn't directly applicable. But the principle of dedicating one input to "always go home/back" is universal. The side button = home is a strong pattern.

Sources:
- [Fitbit OS SDK 5.0 Navigation](https://dev.fitbit.com/blog/2020-09-24-announcing-fitbit-os-sdk-5.0/)
- [Fitbit OS 5.0 Updates (9to5Google)](https://9to5google.com/2020/09/25/fitbit-os-5-update-navigation-ui/)

### 1.5 Cross-Platform Patterns Summary

| Pattern | Pebble | watchOS | Garmin | Fitbit |
|---------|--------|---------|--------|--------|
| Primary input | 4 buttons | Crown + touch | 5 buttons | Touch + 1 button |
| Navigation metaphor | Timeline (temporal) | Smart Stack (relevance) | Widget carousel | Directional swipes |
| Back action | Left button | Swipe right | Back button | Swipe right / button |
| Home action | Long-press back | Crown press | Menu button | Side button |
| Glanceable data | Watchface + timeline | Complications + widgets | Glances | Tiles |
| Notification overlay | Full-screen card | Banner + stack | Full-screen alert | Pull-down list |

---

## 2. Embedded UI Frameworks

### 2.1 LVGL (Light and Versatile Graphics Library)

LVGL is the dominant open-source embedded UI framework. It is directly relevant as an architectural reference even if BITOS stays with pygame.

**Architecture:**
- Object-oriented C with hierarchical widget tree (all widgets inherit from `lv_obj_t`)
- Hardware abstraction via callbacks: `flush_cb` (push pixels to display) and `read_cb` (read input devices)
- Runs on anything from 64 MHz MCUs with 48 KB RAM to full Linux systems
- 30+ built-in widgets, 100+ style properties, flexbox/grid layout engines

**Rendering pipeline (the most relevant part for BITOS):**
- **Partial rendering mode:** Draw buffers smaller than the display (recommended minimum 1/10 screen size). Only invalidated (dirty) regions are re-rendered. The flush callback receives the dirty rectangle coordinates and pixel data. This is LVGL's default and most memory-efficient mode.
- **Direct rendering mode:** Two full-size frame buffers. LVGL renders only dirty areas into the active buffer, then swaps. After flush, dirty regions are automatically copied to the back buffer to keep them synchronized. The flush callback only needs to swap the buffer pointer.
- **Full refresh mode:** Entire screen redrawn every frame. Used when the display controller doesn't support partial updates.

**Dirty region invalidation:** When a widget property changes (text, color, position), the widget's bounding rectangle is marked invalid. LVGL coalesces overlapping dirty rects. During the refresh cycle, only invalid areas are redrawn. The flush callback may be called multiple times per frame (one per dirty region), and `lv_disp_flush_is_last()` signals the final chunk.

**Event system:** Events bubble through the widget tree. Types include `LV_EVENT_CLICKED`, `LV_EVENT_RELEASED`, `LV_EVENT_SCROLL`, `LV_EVENT_VALUE_CHANGED`. Custom events are supported. Input devices are abstracted into pointer, keypad, button, and encoder types -- the encoder type (rotary with button) maps directly to a scroll wheel.

**Key takeaway for BITOS:** LVGL's partial rendering with dirty rect tracking is the gold standard. Even using pygame, BITOS should implement the same pattern: maintain a dirty rect list, only re-render and blit changed regions, and only push changed regions over SPI.

Sources:
- [LVGL Official](https://lvgl.io/)
- [LVGL Core Architecture (DeepWiki)](https://deepwiki.com/lvgl/lvgl/3-core-architecture)
- [LVGL Display Interface Docs](https://docs.lvgl.io/8.4/porting/display.html)
- [LVGL Display Setup v9.6](https://docs.lvgl.io/master/main-modules/display/setup.html)
- [LVGL Events Docs](https://docs.lvgl.io/master/common-widget-features/events.html)

### 2.2 SquareLine Studio

A visual drag-and-drop UI editor for LVGL. Generates C code from visual layouts. Runs on Windows/Linux/macOS. Relevant as a design tool if BITOS ever moves to LVGL, but not directly useful for the current pygame approach.

Source: [SquareLine Studio](https://squareline.io/)

### 2.3 uGFX

A lightweight embedded graphics library similar to LVGL but less widely adopted. Written in C, includes a GUI designer. Claims to be "the smallest, fastest and most advanced embedded library for display and touchscreen solutions." Supports window managers, widgets, and input handling. Less community support and documentation than LVGL.

Source: [uGFX](https://ugfx.io/)

### 2.4 Python-Based Alternatives to pygame

**Luma.OLED / Luma.Core:**
- Python library for OLED displays (SSD1306, SSD1351, SH1106, etc.) over I2C/SPI
- Uses Pillow (PIL) as the drawing backend -- `canvas` context manager creates a `PIL.ImageDraw`, and the result is flushed to hardware when the context exits
- Also includes a pygame emulator device (`luma.core.emulator.pygame`) for desktop testing
- Limitation: designed for OLED controllers, not TFT controllers like ST7789
- Pattern worth stealing: the context-manager rendering model (`with canvas(device) as draw:`) ensures every frame is complete before flush

**LVGL MicroPython binding:**
- Full LVGL widget system accessible from Python (MicroPython, not CPython)
- Auto-generated bindings from C headers
- Supports ESP32, STM32, RP2, Linux
- Primarily for MicroPython on bare metal, not CPython on Linux -- not directly usable on Pi Zero 2W without significant effort
- Could be relevant if BITOS ever moves to an ESP32-based architecture

**Pillow (PIL) directly:**
- pygame is overkill for a non-interactive display loop. Pillow can render to a raw RGB buffer, which can be sent directly to the ST7789 via SPI using `spidev` or the Pimoroni `st7789-python` library
- Eliminates SDL dependency entirely
- No event loop or window management, but BITOS doesn't need those for the display -- input handling is separate GPIO polling

**Key takeaway for BITOS:** Consider whether pygame is the right tool. For a 240x280 display driven over SPI with no touch input, Pillow + direct SPI might be lighter weight and give more control over the rendering pipeline. pygame's strength (event loop, windowing, audio) isn't needed here.

Sources:
- [Luma.OLED Documentation](https://luma-oled.readthedocs.io/en/latest/python-usage.html)
- [LVGL MicroPython Binding](https://github.com/lvgl/lv_micropython)
- [Pimoroni ST7789 Python](https://github.com/pimoroni/st7789-python)

### 2.5 Framework Comparison

| Feature | LVGL | uGFX | pygame | Pillow+SPI |
|---------|------|------|--------|------------|
| Language | C | C | Python | Python |
| Dirty rect rendering | Built-in | Built-in | Manual (LayeredDirty) | Manual |
| Double buffering | Built-in (1-2 buffers) | Built-in | Manual | Manual |
| Widget system | 30+ widgets | Yes | None (DIY) | None (DIY) |
| Input abstraction | Encoder/keypad/pointer | Yes | Event queue | None (GPIO) |
| Memory footprint | 48 KB RAM | Similar | ~20 MB (Python+SDL) | ~15 MB (Python+PIL) |
| Pi Zero suitability | Excellent | Good | Adequate | Good |
| Learning curve | Medium (C) | Medium (C) | Low (Python) | Low (Python) |

---

## 3. Single-Button / Minimal-Input UX

### 3.1 iPod Click Wheel

The click wheel is the single most relevant historical precedent for BITOS's planned scroll wheel + button input.

**Core interaction model:**
- **Scroll** = navigate through lists (songs, artists, albums, playlists)
- **Center button** = select/enter
- **Menu button** = back/up one level
- **Forward/Back buttons** = next/previous track (context-dependent)

**Why it worked:**
- Lists are the fundamental UI element. Every screen is either a list or a detail view. Scrolling speed is proportional to finger velocity on the wheel, enabling fast traversal of thousands of items.
- Hierarchical navigation: always one level deep from where you are. Menu = back. Center = forward. The user's mental model is a tree.
- Audio feedback: click sounds on each list item, with pitch/speed matching scroll velocity. This gave tactile-like feedback from a capacitive surface.
- Minimal visual chrome: black text on white/gray background, simple highlight bar on the selected item.

**Design legacy:** Apple's Phil Schiller adapted the idea from a Bang & Olufsen rotary phone dial. The insight was that a wheel maps naturally to long lists -- linear input for linear data.

**Key takeaway for BITOS:** If adding a scroll wheel, adopt the iPod model directly. Lists as the primary UI primitive. Scroll = move highlight. Button = select. Another button = back. Speed-proportional scrolling for long lists. Audio/haptic feedback per item.

Sources:
- [iPod Click Wheel (Wikipedia)](https://en.wikipedia.org/wiki/IPod_click_wheel)
- [Click Wheel Design Masterpiece (Bytole)](https://www.bytole.com/insights/design/why-apples-ipod-click-wheel-is-a-design-masterpiece/)
- [iPod Scroll Wheel Design (WebDevSupply)](https://webdevsupply.com/ipod-scroll-wheel-iconic-interface-design/)

### 3.2 Single-Button Interfaces

**Duration-based multiplexing:** The fundamental pattern for single-button devices:
- Short press = primary action (e.g., advance, select, wake)
- Long press (1-2s) = secondary action (e.g., menu, mode switch)
- Very long press (5-10s) = system action (e.g., power off, factory reset)
- Double-tap = tertiary action

**Drumless (case study):** A production audio device with a single button. Key insight: firmware freezes require a 10-second hold for force power-off, separate from the normal long-press power-off. This "escape hatch" is critical for reliability.

**Hick's Law application:** Single-button UIs benefit from Hick's Law -- with fewer options, decision time is faster. But discoverability suffers. Users must learn through exploration or documentation. For a voice-first device like BITOS, this is acceptable since voice is the primary input and the button is a mode trigger, not a navigation tool.

**Feedback is critical:** Without multiple buttons to differentiate actions, feedback must clearly communicate which action was triggered. Patterns: LED color/pattern, screen state change, haptic pulse pattern, audio tone.

**Key takeaway for BITOS (current single-button state):**
- Short press = talk to AI (push-to-talk) or primary action
- Long press = secondary action (settings, power menu)
- Double-tap = quick action (dismiss, repeat last response)
- Visual feedback on screen must confirm which action was recognized

Sources:
- [Single Button UX (DesignSpark)](https://www.rs-online.com/designspark/thinking-about-ux-single-button-user-interface)
- [Maximum Minimalism (UX Tigers)](https://www.uxtigers.com/post/maximum-minimalism)

### 3.3 Scroll Wheel + Button Combinations

When BITOS adds the scroll wheel, the input vocabulary expands significantly:

| Input | Action |
|-------|--------|
| Scroll up/down | Navigate list / adjust value |
| Button press | Select / confirm |
| Button + scroll | Secondary mode (e.g., volume while in chat) |
| Long press button | Back / menu / power |
| Double-tap button | Quick action |
| Scroll wheel press (if clickable) | Select (redundant with button, but ergonomic) |

This gives 6+ distinct inputs from two physical controls -- enough for a complete navigation system without touch.

---

## 4. Voice-First Device UX

### 4.1 Amazon Echo Show / Google Nest Hub

These are the most mature voice-first-with-screen devices and define the category's UX patterns.

**Amazon's "VUI + GUI" principles:**
- Voice is always the primary interaction. Screen complements but never replaces voice.
- Users should be able to use core functions without looking at the screen.
- Display content must be "glanceable" -- readable from 7 feet away on Echo Show.
- Template-based rendering: Body Templates (text + images), List Templates (selectable items). Content auto-adapts to different screen sizes.
- List items must be selectable via both voice ("select the second one") and touch.
- Alexa Presentation Language (APL) enables rich visual layouts that respond to voice events.

**Google Nest Hub ambient patterns:**
- Ambient EQ: display adjusts brightness and color temperature to match room lighting. In low light, screen dims to clock-only or turns off entirely.
- Visual feedback for voice: sound plays when "Hey Google" is detected, another when listening stops.
- Dark/light theme auto-switches based on time of day and ambient light.
- When idle, the display becomes a photo frame / ambient information display rather than going blank.

**Key interaction states:**

| State | Visual | Audio |
|-------|--------|-------|
| Idle | Ambient display (photos, clock, weather) | Silent |
| Listening | Animation / colored indicator | Wake sound |
| Processing | Thinking animation | Silent |
| Responding | Text + rich media | Spoken response |
| Error | Error message | Error tone |
| Follow-up | Prompt for more input | Question intonation |

**Key takeaway for BITOS:** The ambient/idle state is critical. When not in conversation, the display should show useful ambient information (time, weather, next task, blob animation) rather than a blank screen or static UI. The state machine (idle -> listening -> processing -> responding -> idle) needs clear visual differentiation at each step.

Sources:
- [Amazon VUI+GUI Best Practices](https://developer.amazon.com/en-US/blogs/alexa/post/05a2ea89-2118-4dcb-a8df-af3d8ac623a8/building-for-echo-show-and-echo-spot-vui-gui-best-practice)
- [Amazon Multimodal Design Tips](https://developer.amazon.com/en-US/blogs/alexa/post/a7f25291-5418-4488-a6e3-fa531e49545c/7-tips-for-creating-great-multimodal-experiences-for-echo-sho)
- [Nest Hub Ambient EQ](https://support.google.com/googlenest/answer/9137130?hl=en)

### 4.2 Rabbit R1

The R1 is the most directly comparable device to BITOS: a pocket-sized AI companion with a small screen, push-to-talk, and a scroll wheel.

**Hardware inputs:**
- 2.88" touchscreen display
- Push-to-talk button (no always-listening mode -- requires deliberate button press)
- Analog scroll wheel for navigating "cards"
- "Rabbit eye" rotating camera for vision tasks

**Card-based UI:** Information is presented as cards that the scroll wheel navigates through. Cards include: conversation responses, voice note summaries, search results, camera captures.

**Voice interaction flow:**
1. User holds push-to-talk button
2. Speaks request
3. Device processes (spinner/animation)
4. Response appears as text card on screen + spoken aloud
5. Scroll to review previous responses

**Voice notes:** Can record audio, automatically summarizes recordings with key points. Review on device or via "Rabbit Hole" web interface.

**Key takeaway for BITOS:** The R1 validates the scroll-wheel + push-to-talk + card UI model. BITOS is building essentially the same interaction paradigm. The card-as-conversation-turn metaphor is worth adopting directly.

Sources:
- [Rabbit R1 Official](https://www.rabbit.tech/rabbit-r1)
- [Rabbit R1 Review (Pixel Refresh)](https://www.pixelrefresh.com/rabbit-r1-review-4-months-down-the-a-i-rabbit-hole/)
- [Rabbit R1 (Wikipedia)](https://en.wikipedia.org/wiki/Rabbit_r1)

### 4.3 Humane AI Pin

**Radical screen-lessness:** No traditional display. Uses a "Laser Ink Display" that projects green text/icons onto the user's palm.

**Input model:**
- Touchpad on the device surface: one/two-finger taps, double-taps, tap-and-hold
- Hand gestures in the projected display: pinch to select, tilt/roll to scroll, close fist to go back
- Voice via "AI Mic" -- spoken responses through directional "personic speaker" (only the wearer hears it)

**Trust Light:** A colored LED that illuminates when the camera, microphone, or phone are active -- privacy indicator for bystanders. This is a critical design pattern for any always-carried AI device.

**Cosmos OS:** The projected interface uses palm gestures for navigation. Tilting the hand scrolls, finger tap selects, closing the fist goes back.

**What went wrong (design critique):** Reviews widely criticized the interaction model as slow, unreliable, and cognitively demanding. The hand-gesture navigation requires both hands (one to hold still as a screen, the other unavailable) and fails in bright light. The lack of a proper display means every interaction requires the projection ritual.

**Key takeaway for BITOS:** The AI Pin is a cautionary tale. Having a screen is an advantage -- use it. The Trust Light concept (visible indicator when recording) is worth adopting. The directional speaker idea is interesting but impractical. Most importantly: fast, reliable feedback is non-negotiable.

Sources:
- [Humane AI Pin UX Critique (Core77)](https://www.core77.com/posts/131842/The-Horrific-UIUX-Design-of-Humanes-AI-Pin)
- [AI Pin Review (Inverse)](https://www.inverse.com/tech/humane-ai-pin-in-depth-review)
- [AI Pin UX Review (Infinum)](https://infinum.com/blog/ai-pin-ux-design-review/)

### 4.4 Tab (AI Wearable)

**Always-on listening pendant:** Tab is a wearable AI companion by Avi Schiffmann. It continuously monitors conversations and builds a knowledge base (without storing raw transcripts or audio).

**No traditional screen:** Like the AI Pin, Tab lacks a conventional display. Some prototypes use a palm projector. The device looks like a miniaturized Google Nest.

**Privacy model:** Explicitly does not store recordings -- instead extracts and stores semantic information. This "knowledge base without transcripts" approach is a meaningful privacy pattern.

**Key takeaway for BITOS:** Tab's always-listening model is the opposite of BITOS's push-to-talk model. But the knowledge-base-without-raw-data privacy pattern is worth considering for how BITOS stores conversation context.

Sources:
- [Tab AI (AiBase)](https://www.aibase.com/tool/27175)
- [Tab Wearable (VentureBeat)](https://venturebeat.com/ai/tabs-always-on-ai-pendant-just-got-funded-but-do-we-need-it/)

### 4.5 Voice Interaction State Machine

Synthesizing across all voice-first devices, the universal state machine for BITOS:

```
[Idle/Ambient] --button press--> [Listening]
[Listening] --button release--> [Processing]
[Processing] --response ready--> [Responding]
[Responding] --response complete--> [Idle/Ambient]
[Any State] --error--> [Error] --timeout--> [Idle/Ambient]
[Responding] --button press--> [Listening] (follow-up)
```

**Visual indicators per state:**

| State | Display | Blob | LED/Indicator |
|-------|---------|------|---------------|
| Idle | Ambient info (time, weather, blob) | Idle breathing + micro-gestures | Off or dim pulse |
| Listening | Waveform / "listening" indicator | Audio-reactive | Solid color (recording) |
| Processing | Thinking animation | Thinking sequence | Pulsing |
| Responding | Typewriter text response | Speaking gestures | Steady |
| Error | Error message + retry hint | Error shake | Red flash |

---

## 5. Pygame Optimization for Pi Zero

### 5.1 Dirty Rectangle Rendering

The single most impactful optimization for BITOS's 15 FPS target on Pi Zero 2W.

**Core concept:** Instead of redrawing and blitting the entire 240x280 display every frame, track which regions changed and only update those.

**pygame's built-in support:**

1. **`DirtySprite` + `LayeredDirty` group:** Drop-in replacement for `Sprite` and `Group`. Each sprite has a `dirty` attribute:
   - `0` = clean, not redrawn
   - `1` = dirty, redrawn this frame, then reset to 0
   - `2` = always dirty, redrawn every frame (for animated elements like the blob)

2. **`RenderUpdates` group:** Returns a list of `Rect` objects representing changed areas. Pass this list to `pygame.display.update(rect_list)` instead of `pygame.display.flip()`. This tells SDL to only push the changed rectangles to the display surface.

3. **Manual approach:** Maintain a `dirty_rects = []` list. When any UI element changes, append its bounding rect. At render time, only redraw elements that intersect dirty rects. Call `pygame.display.update(dirty_rects)`.

**Practical impact:** If only the text area updates (say 240x60 pixels), you're pushing 14,400 pixels instead of 67,200 (240x280) -- a 78% reduction in rendering and SPI transfer work.

**Key implementation pattern:**
```
# Pseudocode -- NOT actual BITOS code
dirty_rects = []

# When something changes:
dirty_rects.append(widget.rect)

# Each frame:
for widget in widgets:
    if widget.rect.collidelist(dirty_rects) != -1:
        widget.draw(screen)

pygame.display.update(dirty_rects)
dirty_rects.clear()
```

Sources:
- [pygame DirtySprite / LayeredDirty docs](https://www.pygame.org/docs/ref/sprite.html)
- [pygame Optimisations wiki](https://www.pygame.org/wiki/Optimisations)
- [Quick & Dirty LayeredDirty tutorial](https://n0nick.github.io/blog/2012/06/03/quick-dirty-using-pygames-dirtysprite-layered/)

### 5.2 Surface Caching Strategies

**`convert()` and `convert_alpha()`:** After creating any surface, call `surface.convert()` (opaque) or `surface.convert_alpha()` (with transparency) to convert it to the display's pixel format. This eliminates per-pixel format conversion during blit, which is the most common performance pitfall.

**Pre-render static elements:** For UI elements that don't change (borders, labels, icons), render once to a surface and cache it. Blit the cached surface each frame rather than re-rendering text/shapes.

**Sprite sheet / atlas:** Load all icons and UI elements from a single image file. Use `subsurface()` to create views into the atlas without copying pixel data. Reduces file I/O (critical on Pi Zero's slow SD card) and improves cache locality.

**Text surface caching:** `font.render()` is expensive. Cache rendered text surfaces keyed by (text, color, size). Only re-render when the text actually changes.

**Disable antialiasing:** On a 240x280 display at arm's length, antialiased text is imperceptible. Setting `antialias=False` in `font.render()` halves the rendering work.

Sources:
- [pygame Optimisations wiki](https://www.pygame.org/wiki/Optimisations)
- [pygame Performance Optimization (Toxigon)](https://toxigon.com/pygame-performance-optimization)
- [pygame Newbie Guide](https://www.pygame.org/docs/tut/newbieguide.html)

### 5.3 SPI Display Driver Stack

The display driver stack is where BITOS can gain or lose the most performance. There are several approaches, from highest to lowest level:

**Option A: fbcp-ili9341 (Recommended)**

A user-space display driver that copies the Linux framebuffer to SPI displays. It is purpose-built for this exact use case.

Key features:
- **Adaptive dirty-region updates:** Only transmits changed pixels over SPI. In practice, typically only 40-50% of pixels change per frame, so effective bandwidth is nearly doubled.
- **DMA + polled SPI hybrid:** Uses DMA for large transfers, polled mode for latency-sensitive operations. CPU usage drops to 15-30% with `ALL_TASKS_SHOULD_DMA` enabled (default on Pi Zero).
- **Interlacing:** When bandwidth is insufficient for full frame rate, automatically interlaces (even/odd scanlines on alternating frames), effectively doubling the update rate at the cost of vertical resolution per frame.
- **Supports ST7789** directly via `-DST7789=ON` cmake flag.
- **Achieves 60 FPS** on ILI9341 displays; ST7789 at 240x280 should achieve 30+ FPS easily.
- **2-3ms input-to-pixel latency** -- far better than fbdev approaches.

Architecture: runs as a daemon, reads from `/dev/fb0` (the HDMI framebuffer), diffs against previous frame, and pushes changed regions to the SPI display. pygame renders to the HDMI framebuffer normally; fbcp-ili9341 handles the SPI mirroring transparently.

**Option B: DRM/KMS tinydrm**

The modern kernel-level approach. The `gpu/drm/tiny` drivers replaced the deprecated `staging/fbtft` drivers.

- Integrates SPI displays as proper DRM devices
- Supports PRIME buffer sharing between GPU and SPI
- Official Raspberry Pi recommendation going forward
- Challenge: SPI bandwidth limits. At 240x280x16bpp x 30fps = ~32 MB/s needed; typical SPI maxes out at ~32-62 MHz, so bandwidth is tight
- Less mature than fbcp-ili9341 for this specific use case

**Option C: Direct SPI from Python**

Skip the framebuffer entirely. Use `spidev` or `st7789-python` (Pimoroni) to push pixels directly from Python.

- Eliminates SDL, X11, and framebuffer overhead entirely
- Full control over what regions to update and when
- Pimoroni's library handles ST7789 initialization and SPI commands
- Can send partial screen updates (set column/row address window, then push pixels for just that region)
- Pairs naturally with Pillow for rendering

**Option D: fbdev (Legacy)**

The old `fbtft` framebuffer driver. Deprecated, unmaintained, replaced by tinydrm. Avoid for new projects.

**Recommendation for BITOS:** Start with **fbcp-ili9341** for the fastest path to good performance. It lets pygame render normally to the framebuffer while the daemon handles SPI optimization transparently. If more control is needed later, consider migrating to **Pillow + direct SPI** to eliminate SDL overhead and gain per-region update control.

Sources:
- [fbcp-ili9341 (GitHub)](https://github.com/juj/fbcp-ili9341)
- [Graphics Acceleration on Pi Zero (Symbolibre)](https://symbolibre.org/graphics-acceleration-on-the-raspberry-pi-zero.html)
- [TinyDRM for ST7789 (RPi Forums)](https://forums.raspberrypi.com/viewtopic.php?t=355870)
- [pygame to Framebuffer (Adafruit)](https://learn.adafruit.com/pi-video-output-using-pygame/pointing-pygame-to-the-framebuffer)

### 5.4 Framebuffer vs X11 vs DRM/KMS

**Performance comparison (from Symbolibre benchmarks on Pi Zero):**

| Backend | Scroll FPS | Window Resize FPS | Notes |
|---------|-----------|-------------------|-------|
| X11 + Glamor (GPU) | ~1 FPS | ~5 FPS | Paradoxically slower than fbdev |
| X11 + fbdev | ~2 FPS | ~10 FPS | CPU-only baseline |
| Wayland native | ~15 FPS | ~20 FPS | Best general-purpose option |
| Wayland + glxgears | -- | 30 FPS | Direct GPU rendering |

**For BITOS (headless SPI display):**

X11 and Wayland are irrelevant overhead. BITOS should render to the raw Linux framebuffer (`/dev/fb0` or `/dev/fb1`) and let fbcp-ili9341 handle SPI output. pygame can target the framebuffer directly:

```
# Environment setup for headless framebuffer rendering
os.environ['SDL_VIDEODRIVER'] = 'fbcon'
os.environ['SDL_FBDEV'] = '/dev/fb0'
```

If using Raspberry Pi OS Bookworm (which defaults to Wayland), pygame 2.x with SDL2 may need different configuration. Testing is required.

Sources:
- [Graphics Acceleration on Pi Zero (Symbolibre)](https://symbolibre.org/graphics-acceleration-on-the-raspberry-pi-zero.html)
- [pygame Framebuffer (Adafruit)](https://learn.adafruit.com/pi-video-output-using-pygame/pointing-pygame-to-the-framebuffer)
- [pygame + Bookworm + SPI (RPi Forums)](https://forums.raspberrypi.com/viewtopic.php?t=358144)

### 5.5 Double Buffering on SPI Displays

**The problem:** SPI is slow relative to display resolution. At 62 MHz SPI clock, a full 240x280x16bpp frame takes ~17ms to transfer -- just barely enough for 60 FPS, with zero time left for rendering. Any rendering during SPI transfer causes tearing.

**Solution 1: Software double buffering (pygame)**
```
# Create two surfaces
back_buffer = pygame.Surface((240, 280))
# Draw everything to back_buffer
# When frame is complete, blit to display surface
screen.blit(back_buffer, (0, 0))
pygame.display.flip()
```

**Solution 2: fbcp-ili9341 handles it**
The daemon maintains its own frame diff buffer. pygame just renders to the framebuffer; the daemon reads it asynchronously and pushes changes over SPI using DMA without blocking the CPU.

**Solution 3: Direct SPI with partial updates**
Only send the changed rectangle's worth of pixels. Set the ST7789's column/row address window to the dirty region, then push only those pixels. A 240x40 dirty region takes ~3ms instead of ~17ms for a full frame.

**Recommendation:** Let fbcp-ili9341 handle double buffering and SPI timing. Focus pygame efforts on minimizing dirty regions so the daemon has less data to transfer.

---

## 6. Synthesis: Recommended Architecture for BITOS UI

Based on the research above, here are the key architectural recommendations:

### 6.1 Navigation Model

Adopt a hybrid of **Pebble's card stack** and the **iPod's scroll wheel**:
- **Scroll wheel** = navigate between cards (conversation turns, widgets, menus)
- **Primary button** = select / push-to-talk
- **Secondary button** = back / dismiss
- **Long-press primary** = power / settings menu
- **Cards** as the fundamental UI unit: each conversation turn, notification, widget, or menu is a card

### 6.2 UI State Architecture

```
[Ambient/Idle] -- blob animation + ambient info (time, weather, next task)
    |
    v (button press)
[Listening] -- waveform + recording indicator
    |
    v (button release)
[Processing] -- thinking animation
    |
    v (response ready)
[Responding] -- typewriter text + blob expression
    |
    v (complete)
[Ambient/Idle]

Scroll wheel at any time: browse conversation history / widget stack
```

### 6.3 Rendering Pipeline

1. **Dirty rect tracking** at the widget level (clock, blob, text area, status bar are independent regions)
2. **Surface caching** for static elements (labels, icons, borders)
3. **Text surface cache** keyed by content hash
4. **fbcp-ili9341** for SPI output with adaptive dirty-region transfer
5. **15 FPS target** is very achievable -- only the blob animation region needs continuous updates; text/status regions update rarely

### 6.4 Widget / Glance System

Adopt Garmin's glance pattern:
- Default view: blob + ambient info (the "watch face")
- Scroll through "glances": weather detail, task list, conversation history, system status
- Select a glance to expand to full-screen detail view
- Smart ordering by time-of-day relevance (morning: weather + calendar; evening: task summary)

### 6.5 Voice Interaction Feedback

Steal from Echo Show:
- Clear visual state transitions between idle/listening/processing/responding
- Recording indicator visible to bystanders (like Humane's Trust Light)
- Ambient mode when idle (never a blank screen)
- Response text on screen even while speaking (multimodal reinforcement)
