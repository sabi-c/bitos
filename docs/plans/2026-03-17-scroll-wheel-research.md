# Scroll Wheel / Rotary Encoder Research for BITOS

**Date:** 2026-03-17
**Goal:** Find the best side-mounted scroll wheel with magnetic/tactile detent feel, push-to-click, for a pocket-sized Pi Zero 2W device (240x280 OLED).

---

## 1. Encoder Options — Ranked Recommendations

### Tier 1: Best Fit for BITOS

#### A. Panasonic EVQWGD001 — "The Mouse Wheel" (RECOMMENDED)

This is a **roller wheel encoder with integrated push switch**, originally designed for mouse scroll wheels. It is the single best off-the-shelf option for a side-mounted thumb scroll on a pocket device.

| Spec | Value |
|------|-------|
| Type | Mechanical rotary encoder + push switch |
| Pulses/rev | 15 |
| Pins | 6 (A, B, Common, push SW x2, unused) |
| Detent feel | Crisp tactile clicks (mouse-wheel quality) |
| Wheel diameter | ~8mm exposed roller |
| Body | ~18mm square |
| Lifecycle | 100K+ rotations |
| Price | $3-5 (AliExpress), $16 (KEEBD retail) |
| Mounting | Through-hole, wheel protrudes from edge |

**Why this wins:**
- Designed exactly for thumb-scroll interaction
- Built-in push switch (no extra component)
- Roller wheel naturally protrudes from PCB edge = perfect side-mount
- 15 detents/rev = satisfying click density for menu scrolling
- Used in custom keyboards (proven in tiny enclosures)

**IMPORTANT — Discontinuation Notice:**
The EVQWGD001 is **no longer manufactured by Panasonic**. Remaining units are old stock only. Prices have risen from ~$7 to ~$30 at retail. However:
- **AliExpress clones** are still available at $3-5 (search "EVQWGD001 encoder roller") — test before committing to production
- **SparkFun Roller Encoder Breakout** (BOB-29094) provides a breakout PCB for the EVQWGD001, but does NOT include the encoder itself
- **MEH01** (github.com/EverydayErgo/MEH01) — a ~$1 USD drop-in replacement using a standard mouse encoder + tactile switch + 3D printed housing. Full STL/STEP files provided.
- **THQWGD001** (by Taro-Hayashi on GitHub) — another DIY replacement using mouse encoder + tact switch

**Recommendation:** Buy 3-5 EVQWGD001 clones from AliExpress for prototyping. For production, design around the MEH01 pattern (mouse encoder + tact switch + custom housing) so you are not dependent on discontinued stock.

**Pinout (verified via oscilloscope by rroels/EVQWGD001-Pinout):**
```
Pin 1: Channel A (encoder)
Pin 2: Channel B (encoder)
Pin 3: Common / GND (encoder)
Pin 4: Push switch terminal 1
Pin 5: Push switch terminal 2
Pin 6: Unused / NC
```

**Wiring to Pi Zero 2W:**
```
EVQWGD001          Pi Zero 2W
─────────          ──────────
Pin 1 (A)    ───→  GPIO 5  (Physical 29)
Pin 2 (B)    ───→  GPIO 6  (Physical 31)
Pin 3 (COM)  ───→  GND     (Physical 30 or 34)
Pin 4 (SW)   ───→  GPIO 12 (Physical 32)
Pin 5 (SW)   ───→  GND     (Physical 30 or 34)
```
Enable internal pull-ups on GPIO 5, 6, 12. No external resistors needed.

---

#### B. Bourns PEC11R-4215F-S0024 — "The Premium Knob"

A 12mm incremental encoder with push switch. The gold standard for custom electronics. Requires a knob cap for thumb operation.

| Spec | Value |
|------|-------|
| Type | Mechanical rotary + momentary push switch |
| Pulses/rev | 24 (also 12, 18 options) |
| Detents | 24 (also 12, 18, or 0/smooth) |
| Detent force | 30-90 gf-cm |
| Shaft | 6mm D-shaft, knurled metal, 15mm or 20mm length |
| Body | 12mm diameter |
| Push switch | SPST momentary, 10mA @ 5V DC, 0.5mm travel |
| Lifecycle | 30,000 cycles (with detent) |
| Weight | 5g max |
| Price | $1.50-3.00 |

**Part number decoder:** `PEC11R-4[detent][shaft][mount]-[type]00[pulses]`
- Detent: 0=none, 1=18, 2=24, 3=12
- Shaft: 1=15mm, 2=20mm
- Best for BITOS: **PEC11R-4215F-S0024** (24 detent, 15mm shaft, push switch)

**Pros:** Incredibly well-documented, available everywhere, 24 detents = finer control than EVQWGD001's 15. Rock-solid reliability.

**Cons:** Requires a custom thumb-wheel knob for side-mount. Not inherently a "roller" — needs mechanical adaptation.

**Side-mount approach:** Mount horizontally on PCB so shaft pokes through case side wall. Attach a flat disc/coin knob (3D printed, ~15mm diameter, textured rim) so thumb can roll it. Shaft protrudes 2-3mm from case edge.

---

#### C. Panasonic EVQ-WKA001 — "The Edge-Drive Thumbwheel"

Purpose-built edge-drive jog encoder. Designed for side-mount by default.

| Spec | Value |
|------|-------|
| Type | Edge-drive jog encoder + push switch |
| Pulses/rev | 15 |
| Mounting | SMD (surface mount) |
| Orientation | Vertical — wheel at PCB edge |
| Detent | Yes, tactile |
| Lifecycle | 100K cycles |
| Height | 3.65mm (!!) |
| Price | $3-6 (DigiKey) |

**Pros:** Incredibly thin profile. Designed for exactly this use case. SMD mounting is clean.

**Cons:** Tiny wheel surface area — less satisfying than EVQWGD001's roller. Harder to solder by hand. Less "premium" detent feel.

---

### Tier 2: Interesting Alternatives

#### D. TTC Gold Mouse Encoder

The encoder inside premium gaming mice (Logitech, Razer).

| Spec | Value |
|------|-------|
| Detent feel | Moderate — balanced smooth/tactile |
| Torsion moment | 15-30 gf-cm (lighter) or 20-40 gf-cm (heavier) |
| Lifecycle | 50 million grid counts |
| Heights | 8mm, 9mm, 10mm, 11mm, 14mm |
| Smoothness | Middle ground (smoother than Alps, more tactile than Kailh) |

**The mouse encoder feel hierarchy:**
- **Alps Japan:** Most defined clicks, heaviest resistance — old-school clicky
- **TTC Gold:** Balanced smooth + tactile — the "premium" sweet spot
- **Kailh Red:** Smoothest, lightest — almost frictionless

**Problem:** These are designed for a specific mouse-wheel axle/bracket mechanism. Not trivially mountable without a custom bracket. No push switch. Better as inspiration than as a direct component.

#### E. Alps RKJXT1F42001 — "The Joystick Encoder"

4-direction stick + center push + rotary encoder in one 17x17x10.5mm package.

**Interesting but wrong form factor.** The joystick stick is the primary input, not a wheel. The encoder is secondary. Also, pushing any direction also triggers the push switch — confusing for BITOS.

#### F. Adafruit ANO Directional Encoder (#5001)

iPod-style click wheel: 5 directional buttons + rotary encoder ring.

| Spec | Value |
|------|-------|
| Inputs | 5 buttons (up/down/left/right/center) + rotary encoder |
| GPIO needed | 7 total |
| Lifecycle | 200K encoder, 1M clicks |
| Price | $8.95 |

**Pros:** Very satisfying iPod-like interaction. Tons of input options.
**Cons:** Way too big for side-mount on a pocket device. This is a face-mount component. Uses 7 GPIOs.

#### G. EBE BGE16 RT — "The Industrial Premium"

16mm diameter miniature encoder with magnetic (contactless) detent mechanism.

| Spec | Value |
|------|-------|
| Diameter | 16mm housing |
| Shaft | 4mm stainless steel |
| Detents | 16 or 24 per revolution (configurable) |
| Detent mechanism | Contactless magnetic — wear-free |
| Push switch | Contactless magnetic — wear-free |
| Voltage | 5V DC |
| Mounting | M10x0.75mm central thread |

**The dream encoder** — magnetic detents with perfect haptic feel, wear-free, industrial grade. **Problem:** likely expensive (industrial pricing, no hobbyist distribution), and 16mm diameter is borderline too large for BITOS.

---

### Tier 3: Custom / Advanced

#### H. SmartKnob-Inspired Magnetic Detent

Scott Bezek's SmartKnob uses a brushless gimbal motor + magnetic encoder (like AS5600) for software-defined detents via closed-loop torque feedback.

**Concept:** Mount a small diametric magnet on a thumb wheel axle, read angle with AS5600 Hall sensor (I2C), use tiny magnets in a ring to create physical detent feel.

**For BITOS this is overkill.** The motor + driver + firmware complexity far exceeds what a simple scroll wheel needs. But the magnet-ring-for-detents idea is worth stealing for a v2.

#### I. Custom Magnetic Detent Ring

DIY approach: 3D print a wheel with cavities for 1mm neodymium magnets, use a steel ball bearing or opposing magnet as the detent mechanism.

```
     ┌─ 3D printed wheel with magnet pockets
     │
   ╭─●─╮ ╭─●─╮ ╭─●─╮    ● = 1mm neodymium magnets
   │     │     │     │       (evenly spaced around rim)
   ╰─────╯─────╰─────╯
          ↕
     steel ball bearing      ← spring-loaded, clicks into
     in case wall               gaps between magnets
```

Read angle with AS5600 (I2C, only needs SDA/SCL). Push switch is a separate tact switch under the axle.

**Pros:** Completely custom feel. Infinite rotation. No mechanical wear on encoder.
**Cons:** Significant mechanical design effort. Overkill for v1.

---

## 2. What Makes a Scroll Wheel Feel "Premium"

### The Physics of Satisfying Clicks

| Factor | What it means | Sweet spot |
|--------|--------------|------------|
| Detent force | How hard you push to get past each click | 30-60 gf-cm (light enough for fast scroll, heavy enough to feel intentional) |
| Detent spacing | Degrees between clicks | 15-24 per rev (15°-24° apart). More detents = finer control but mushier feel |
| Detent sharpness | How sudden the force transition is | Sharp = premium (force drops abruptly). Gradual = mushy |
| Inter-detent friction | Resistance between click positions | Low = premium. High = grinding/cheap feel |
| Axial play | Wobble in the wheel | Zero = premium. Any play = cheap feel |
| Acoustic feedback | Click sound | Quiet, crisp tick = premium. Loud plastic clack = cheap |

### Why Mouse Encoders Feel Better Than Generic Rotary Encoders

Generic rotary encoders (EC11 etc.) use **spring-loaded metal wipers** against a patterned contact disc. The detent comes from a separate spring/ball mechanism. This creates:
- Slight grinding between detents
- Detent feel that degrades over time as springs weaken
- A "scratchy" undertone

Mouse encoders (TTC Gold, EVQWGD001) are designed for **millions of operations** with minimal friction between detents. The contact mechanism is tighter, the detent profile is sharper, and the wheel bearing is smoother.

### Mechanical vs Optical vs Magnetic

| Type | Detent feel | Durability | Complexity |
|------|-------------|-----------|------------|
| Mechanical (wipers) | Good — physical spring detents | 15K-100K cycles | Simple, 3 wires |
| Optical (slotted disc) | None inherently — must add separate detent | 1M+ cycles | Needs IR LED + sensor |
| Magnetic (Hall sensor) | None inherently — must add physical magnets | Infinite (contactless) | I2C, needs magnet + sensor |

**For BITOS v1:** Mechanical is the right choice. The EVQWGD001's built-in detent mechanism is tuned for exactly the interaction pattern we want.

---

## 3. Electrical Interface

### Quadrature Encoding (A/B Channels)

All recommended encoders output two square wave signals (A and B) that are 90 degrees out of phase:

```
Clockwise rotation:
A: ──┐  ┌──┐  ┌──┐  ┌──
     └──┘  └──┘  └──┘
B: ────┐  ┌──┐  ┌──┐  ┌
       └──┘  └──┘  └──┘

Counter-clockwise: B leads A instead of A leading B
```

Each "detent" position corresponds to one full cycle of both signals = 1 pulse. The direction is determined by which signal leads.

### GPIO Pin Allocation

Available free GPIOs on BITOS (from project notes):

| Physical Pin | BCM GPIO | Proposed Use |
|-------------|----------|-------------|
| 29 | GPIO 5 | Encoder Channel A |
| 31 | GPIO 6 | Encoder Channel B |
| 32 | GPIO 12 | Encoder Push Switch |
| 33 | GPIO 13 | (spare) |
| 36 | GPIO 16 | (spare) |
| 37 | GPIO 26 | (spare) |

Three GPIOs for the encoder (A, B, push switch), three spare for future use.

### Debouncing

Rotary encoders should NOT use traditional debounce delays — they generate legitimate rapid pulses when scrolled fast (up to 100Hz). Instead:
- Use **state machine decoding** (track A/B transition sequences)
- Use **pigpio daemon** which handles this at C level, not in Python
- Hardware: optional 10nF caps from A/B to GND (rarely needed with EVQWGD001)

### Pull-ups

The Pi Zero 2W has internal pull-ups (~50K ohm) on all GPIO pins. Enable via software. No external resistors needed for the EVQWGD001.

---

## 4. Mechanical Integration

### Option A: EVQWGD001 Roller Side-Mount (Recommended)

```
 Top view of BITOS device:
 ┌──────────────────────────┐
 │                          │
 │     240×280 OLED         │
 │                          │
 │                          ├──╥── ← roller wheel protrudes
 │                          │  ║     2-3mm from case edge
 │                          ├──╨──
 │                          │
 │          [button]        │
 └──────────────────────────┘

 Cross-section (side view):
 ┌─────────────────┐
 │  OLED display   │
 │                 │
 │  ┌──PCB──────┐  │
 │  │  [EVQWGD] ●══╪══● ← wheel pokes through slot in case
 │  └───────────┘  │
 │                 │
 └─────────────────┘

 Case slot dimensions:
 - Width: 10mm (wheel diameter + 1mm clearance each side)
 - Height: 4mm (wheel thickness + 0.5mm clearance)
 - Chamfer edges for smooth thumb contact
```

The EVQWGD001 mounts on the main PCB with the roller wheel oriented toward the case edge. A rectangular slot in the case wall allows the wheel to protrude. The wheel's own bearing provides the axle — no additional mounting hardware needed.

### Option B: PEC11R Horizontal Mount with Disc Knob

```
 Cross-section:
 ┌─────────────────┐
 │                 │
 │  ┌──PCB──┐     │
 │  │ [PEC11R]─────╪─●  ← D-shaft exits through case wall
 │  └───────┘     │     3D printed flat disc knob (15mm dia)
 │                 │     with textured rim for thumb grip
 └─────────────────┘

 Knob design:
      ╭─────────╮
     ╱  textured  ╲    ← 15mm diameter, 3mm thick
    │   rim grip    │      D-shaft hole in center
     ╲             ╱      friction-fit or set screw
      ╰─────────╯
```

Mount the PEC11R horizontally on the PCB. The 6mm D-shaft exits through a 6.5mm hole in the case wall. A flat disc knob (3D printed) with knurled/textured rim gives thumb purchase.

### 3D Printing Notes

- Print knobs in **resin (SLA)** for smooth finish and precise D-shaft bore
- FDM works but needs post-processing for the shaft hole tolerance
- Add 0.1-0.15mm clearance on the shaft bore for press-fit
- Knurling on the rim: use a diamond/crosshatch pattern at 0.3mm depth
- Material: PETG or resin (PLA gets slippery with skin oil over time)

### Recommended Knob STL Sources

- Thingiverse: "Rotary Encoder Thumb Knob" (thing:2466473) — flat disc design
- Printables: search "encoder knob flat" — multiple wheel/coin designs
- Custom: OpenSCAD parametric knob with configurable diameter, thickness, shaft type

---

## 5. Software Driver

### Recommended Stack: pigpio + Custom Wrapper

The `pigpio` daemon is the most reliable encoder interface for Pi — it runs a separate C daemon that catches every edge transition without the GIL dropping pulses. RPi.GPIO misses interrupts under CPU load. gpiozero works but uses RPi.GPIO internally unless configured otherwise.

### Core Driver Implementation

```python
"""
BITOS Scroll Wheel Driver
Uses pigpio for reliable edge detection.
Integrates with ButtonHandler event system.
"""

import time
import logging
import pigpio

logger = logging.getLogger(__name__)

# --- Configuration ---
ENCODER_A = 5      # BCM GPIO 5  (Physical 29)
ENCODER_B = 6      # BCM GPIO 6  (Physical 31)
ENCODER_SW = 12    # BCM GPIO 12 (Physical 32)

# Acceleration: if N detents within ACCEL_WINDOW_S, multiply scroll by ACCEL_FACTOR
ACCEL_WINDOW_S = 0.08   # 80ms between clicks = "fast scroll"
ACCEL_FACTOR = 3         # fast scroll jumps 3 items instead of 1
ACCEL_ULTRA_WINDOW_S = 0.04
ACCEL_ULTRA_FACTOR = 6


class ScrollWheel:
    """Rotary encoder with push switch for BITOS navigation."""

    def __init__(self, pi: pigpio.pi | None = None):
        self._pi = pi or pigpio.pi()
        if not self._pi.connected:
            raise RuntimeError("pigpio daemon not running — start with: sudo pigpiod")

        # State
        self._last_a = 1
        self._last_b = 1
        self._last_scroll_time = 0.0
        self._position = 0

        # Callbacks
        self._on_scroll_up: list = []     # scroll toward top of list
        self._on_scroll_down: list = []   # scroll toward bottom
        self._on_click: list = []         # push switch pressed
        self._on_long_click: list = []    # push switch held >400ms

        # Push switch state
        self._sw_press_time = 0.0
        self._sw_pressed = False

        self._setup_gpio()

    def _setup_gpio(self):
        pi = self._pi

        # Encoder pins: input with pull-up
        pi.set_mode(ENCODER_A, pigpio.INPUT)
        pi.set_mode(ENCODER_B, pigpio.INPUT)
        pi.set_pull_up_down(ENCODER_A, pigpio.PUD_UP)
        pi.set_pull_up_down(ENCODER_B, pigpio.PUD_UP)

        # Push switch: input with pull-up (active low)
        pi.set_mode(ENCODER_SW, pigpio.INPUT)
        pi.set_pull_up_down(ENCODER_SW, pigpio.PUD_UP)

        # Edge callbacks (pigpio handles debounce internally)
        self._cb_a = pi.callback(ENCODER_A, pigpio.EITHER_EDGE, self._encoder_edge)
        self._cb_b = pi.callback(ENCODER_B, pigpio.EITHER_EDGE, self._encoder_edge)
        self._cb_sw = pi.callback(ENCODER_SW, pigpio.EITHER_EDGE, self._switch_edge)

        logger.info("scroll_wheel_init: A=GPIO%d B=GPIO%d SW=GPIO%d", ENCODER_A, ENCODER_B, ENCODER_SW)

    def _encoder_edge(self, gpio, level, tick):
        """Called on every A/B edge — full quadrature state machine."""
        a = self._pi.read(ENCODER_A)
        b = self._pi.read(ENCODER_B)

        # Grey code state machine
        old_state = (self._last_a << 1) | self._last_b
        new_state = (a << 1) | b

        self._last_a = a
        self._last_b = b

        # Valid transitions (skips same-state and impossible jumps)
        # CW:  00→01→11→10→00
        # CCW: 00→10→11→01→00
        transition = (old_state << 2) | new_state

        cw_transitions = {0b0001, 0b0111, 0b1110, 0b1000}
        ccw_transitions = {0b0010, 0b1011, 0b1101, 0b0100}

        if transition in cw_transitions:
            self._on_detent(direction=1)
        elif transition in ccw_transitions:
            self._on_detent(direction=-1)

    def _on_detent(self, direction: int):
        """Process one detent click with acceleration."""
        now = time.monotonic()
        dt = now - self._last_scroll_time
        self._last_scroll_time = now

        # Velocity-based acceleration
        if dt < ACCEL_ULTRA_WINDOW_S:
            multiplier = ACCEL_ULTRA_FACTOR
        elif dt < ACCEL_WINDOW_S:
            multiplier = ACCEL_FACTOR
        else:
            multiplier = 1

        self._position += direction * multiplier

        callbacks = self._on_scroll_up if direction > 0 else self._on_scroll_down
        for cb in callbacks:
            try:
                cb(multiplier)
            except Exception as e:
                logger.error("scroll_callback_error: %s", e)

    def _switch_edge(self, gpio, level, tick):
        """Push switch edge handler."""
        if level == 0:  # pressed (active low)
            self._sw_pressed = True
            self._sw_press_time = time.monotonic()
        elif level == 1 and self._sw_pressed:  # released
            self._sw_pressed = False
            duration = time.monotonic() - self._sw_press_time
            if duration >= 0.4:
                for cb in self._on_long_click:
                    try:
                        cb()
                    except Exception as e:
                        logger.error("long_click_error: %s", e)
            else:
                for cb in self._on_click:
                    try:
                        cb()
                    except Exception as e:
                        logger.error("click_error: %s", e)

    # --- Public API ---

    def on_scroll_up(self, callback):
        """Register callback for upward scroll. Receives multiplier (1, 3, or 6)."""
        self._on_scroll_up.append(callback)

    def on_scroll_down(self, callback):
        """Register callback for downward scroll. Receives multiplier (1, 3, or 6)."""
        self._on_scroll_down.append(callback)

    def on_click(self, callback):
        """Register callback for push-click (select)."""
        self._on_click.append(callback)

    def on_long_click(self, callback):
        """Register callback for long push-click (back)."""
        self._on_long_click.append(callback)

    @property
    def position(self) -> int:
        """Cumulative scroll position."""
        return self._position

    def cleanup(self):
        """Release pigpio resources."""
        self._cb_a.cancel()
        self._cb_b.cancel()
        self._cb_sw.cancel()
```

### Integration with BITOS Input System

The existing `ButtonHandler` in `device/input/handler.py` uses `ButtonEvent` enums (SHORT_PRESS, LONG_PRESS, DOUBLE_PRESS, etc.). The scroll wheel adds two new event types:

```python
# In device/input/handler.py, extend ButtonEvent:
class ButtonEvent(Enum):
    SHORT_PRESS = auto()
    LONG_PRESS = auto()
    DOUBLE_PRESS = auto()
    TRIPLE_PRESS = auto()
    POWER_GESTURE = auto()
    HOLD_START = auto()
    HOLD_END = auto()
    # New scroll events
    SCROLL_UP = auto()      # scroll wheel turned up
    SCROLL_DOWN = auto()    # scroll wheel turned down
    SCROLL_CLICK = auto()   # wheel pushed in
```

### Integration Pattern

```python
# In device/main.py or wherever input is initialized:

from input.scroll_wheel import ScrollWheel

scroll = ScrollWheel()

# Map scroll to existing navigation:
# SCROLL_UP   → previous item (replaces repeated SHORT_PRESS)
# SCROLL_DOWN → next item
# CLICK       → select (same as DOUBLE_PRESS)
# LONG_CLICK  → back (same as LONG_PRESS)

scroll.on_scroll_up(lambda mult: button_handler._emit(ButtonEvent.SCROLL_UP))
scroll.on_scroll_down(lambda mult: button_handler._emit(ButtonEvent.SCROLL_DOWN))
scroll.on_click(lambda: button_handler._emit(ButtonEvent.SCROLL_CLICK))
scroll.on_long_click(lambda: button_handler._emit(ButtonEvent.LONG_PRESS))
```

### Desktop Emulation (pygame)

For development without hardware, map arrow keys or mouse scroll to the same events:

```python
# In ButtonHandler.handle_pygame_event():
if event.type == pygame.MOUSEWHEEL:
    if event.y > 0:
        self._emit(ButtonEvent.SCROLL_UP)
    elif event.y < 0:
        self._emit(ButtonEvent.SCROLL_DOWN)
    return True

# Or keyboard arrows:
if event.type == pygame.KEYDOWN:
    if event.key == pygame.K_UP:
        self._emit(ButtonEvent.SCROLL_UP)
        return True
    if event.key == pygame.K_DOWN:
        self._emit(ButtonEvent.SCROLL_DOWN)
        return True
```

### pigpio Daemon Setup

```bash
# Install pigpio (if not already present)
sudo apt install pigpio python3-pigpio

# Start daemon at boot
sudo systemctl enable pigpiod
sudo systemctl start pigpiod

# Verify
pigs t    # should return current tick value
```

### Alternative: gpiozero (Simpler, Slightly Less Reliable)

```python
from gpiozero import RotaryEncoder, Button

encoder = RotaryEncoder(5, 6, max_steps=0)  # unlimited steps
switch = Button(12, pull_up=True)

encoder.when_rotated_clockwise = lambda: on_scroll_down(1)
encoder.when_rotated_counter_clockwise = lambda: on_scroll_up(1)
switch.when_pressed = on_click
```

gpiozero is simpler but uses RPi.GPIO under the hood, which can miss fast edges. For a scroll wheel that will be flicked quickly, pigpio is the safer choice.

---

## 6. Reference Designs — Lessons Learned

### Rabbit R1 Scroll Wheel
- Uses a **Hall effect sensor** (not a mechanical encoder) with a magnet inside the roller
- Contactless = no wear, no drift
- Detent feel comes from a separate mechanical spring mechanism
- **Takeaway:** Magnetic sensing is the gold standard for durability, but adds complexity

### Playdate Crank
- Cylindrical magnet rotates against a Hall sensor on a flex cable
- No wipers, no springs, no wear surfaces
- "Won't wear out or drift" (iFixit)
- **Takeaway:** Magnetic = forever. But the Playdate has no detents — it's smooth rotation. For BITOS we want clicks.

### Logitech MX Master MagSpeed Wheel
- **Electromagnetic ratchet** — an electromagnet engages/disengages a physical ratchet mechanism
- Can switch between "click-click" ratchet mode and "free spin" mode electronically
- Speed-adaptive: scrolls slowly = ratchet clicks, scroll fast = auto-freewheel
- **Takeaway:** The dream UX. Way too complex for BITOS v1, but the auto-freewheel concept is interesting for v2.

### Teenage Engineering OP-1
- Standard D-shaft mechanical encoders with custom-milled aluminum knobs
- ~8-9 full rotations min-to-max (high resolution mapping)
- **Takeaway:** The feel comes from the knob, not the encoder. Premium knob materials (aluminum, machined surfaces) make cheap encoders feel expensive.

### SmartKnob (scottbez1)
- Brushless gimbal motor + magnetic encoder = software-defined detents
- ESP32-based, 240x240 round LCD on the rotor
- **Takeaway:** Beautiful but wildly over-engineered for a scroll wheel. The concept of software-defined detent strength is compelling for future versions.

### iPod Click Wheel (Historical)
- Capacitive touch ring — no moving parts
- "Scroll" was a finger sliding around the ring surface
- Detent feedback was purely audio (click sound through speaker)
- **Takeaway:** Audio feedback as a substitute for physical detents. BITOS could play a quiet click sound through the speaker to enhance wheel feel.

---

## 7. Final Recommendation

### For BITOS v1: Panasonic EVQWGD001

**Buy this:** Panasonic EVQWGD001 ($3-5 on AliExpress, search "EVQWGD001 encoder roller")

**Why:**
1. It is literally a mouse scroll wheel with a push switch — exactly what you want
2. The roller protrudes naturally from the PCB edge — minimal mechanical design
3. 15 detents/rev gives satisfying, precise clicks
4. Push switch is built in — one component, not two
5. Used successfully in dozens of custom keyboard builds (proven form factor)
6. $3-5 is nothing compared to the value of getting the UX right early

**Wire it to:** GPIO 5 (A), GPIO 6 (B), GPIO 12 (push switch), GND

**Drive it with:** pigpio daemon + the ScrollWheel class above

**Case integration:** 10mm x 4mm rectangular slot in the right side wall, wheel protrudes 2-3mm

### For BITOS v2 (Future Upgrade Path)

Consider the **Bourns PEC11R with a custom CNC aluminum thumb wheel** for a premium feel upgrade. Or go full magnetic: AS5600 Hall sensor + diametric magnet + 3D printed detent ring with neodymium magnets. That gets you contactless sensing, infinite rotation, and a custom detent profile — but it is a significant mechanical engineering project.

### Audio Enhancement (Both Versions)

Play a quiet tick sound through the speaker on each scroll detent. This is the iPod trick — audio reinforcement makes physical feedback feel 2x more satisfying. The BITOS click_sounds module already exists at `device/audio/click_sounds.py`.

---

## 8. Shopping List

| Item | Qty | Source | Price |
|------|-----|--------|-------|
| Panasonic EVQWGD001 | 3 (spares) | AliExpress | ~$10 |
| Dupont jumper wires (F-F) | 5 | Amazon/local | ~$3 |
| 10nF ceramic capacitors (optional debounce) | 2 | Amazon/local | ~$1 |
| M2 screws for PCB mount (if needed) | 4 | Amazon/local | ~$2 |
| **Total** | | | **~$16** |

For PEC11R alternative, add:
| Bourns PEC11R-4215F-S0024 | 2 | DigiKey/Mouser | ~$5 |
| 3D printed thumb knob | 1 | Self-print | ~$0.50 |

---

## Sources

- [Alps EC11E Series Datasheet](https://tech.alpsalpine.com/e/products/category/encorders/sub/01/series/ec11e/)
- [Bourns PEC11R Datasheet](https://www.bourns.com/docs/Product-Datasheets/PEC11R.pdf)
- [Bourns PEC11H High Detent Force](https://www.bourns.com/docs/product-datasheets/pec11h.pdf)
- [Panasonic EVQWGD001 Pinout Verification](https://github.com/rroels/EVQWGD001-Pinout)
- [Panasonic EVQ-WKA001 on DigiKey](https://www.digikey.com/en/products/detail/panasonic-electronic-components/EVQ-WKA001/275359)
- [EVQWGD001 on KEEBD](https://keebd.com/en-us/products/encoder-roller-with-push-switch)
- [SmartKnob — Haptic Input Knob](https://github.com/scottbez1/smartknob)
- [EBE BGE16 RT Miniature Encoder](https://www.ebe.de/en/news/ebe-sensors-motion-presents-the-new-miniature-encoder-bge16-rt-wear-free-hmi-signal-generation-with-super-haptic-feedback/)
- [ANO Directional Encoder (Adafruit 5001)](https://www.adafruit.com/product/5001)
- [ANO Encoder Guide](https://learn.adafruit.com/ano-rotary-encoder/overview)
- [TTC/Kailh/Alps Encoder Selection Guide](https://shop.facfox.com/scroll-wheel-encoder-selection-guide/?v=0b3b97fa6688)
- [TTC Gold Scroll Wheel Encoder](https://mechkeys.com/products/ttc-gold-silver-scroll-wheel-mouse-encoder)
- [Alps RKJXT1F42001 on DigiKey](https://www.digikey.com/en/products/detail/alps-alpine/RKJXT1F42001/19529127)
- [Rabbit R1 Teardown (iFixit)](https://www.ifixit.com/News/95474/rabbit-r1-and-humane-ai-pin-teardown-the-beginning-of-a-new-device-category)
- [Playdate Teardown (iFixit)](https://www.ifixit.com/Teardown/Playdate+Teardown/143811)
- [Logitech MX Master 3S Review](https://www.tomshardware.com/reviews/logitech-mx-master-3s-mouse)
- [gpiozero RotaryEncoder API](https://gpiozero.readthedocs.io/en/stable/api_input.html)
- [pigpio_encoder Library](https://github.com/vash3d/pigpio_encoder)
- [Rotary Encoder Thumb Knob (Thingiverse)](https://www.thingiverse.com/thing:2466473)
- [3D Printed Encoder Knobs (Hackaday)](https://hackaday.com/2023/01/14/make-your-own-pot-and-encoder-knobs-without-reinventing-them/)
- [Raspberry Pi Rotary Encoder Tutorial](https://thepihut.com/blogs/raspberry-pi-tutorials/how-to-use-a-rotary-encoder-with-the-raspberry-pi)
- [EEVBlog Encoder Recommendations](https://www.eevblog.com/forum/chat/any-rotary-encoder-recommendations/)
