<!DOCTYPE html>

<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>BITOS — Menu Tree & Navigation Architecture</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=VT323&display=swap');

:root {
–bg: #0a0a0a;
–fg: #e8e8e8;
–accent: #ffffff;
–dim: #444444;
–mid: #888888;
–green: #b8ffb8;
–amber: #ffd080;
–blue: #80c8ff;
–red: #ff8888;
–border: 1px solid #333;
–border-bright: 1px solid #666;
}

- { box-sizing: border-box; margin: 0; padding: 0; }

body {
background: var(–bg);
color: var(–fg);
font-family: ‘Share Tech Mono’, monospace;
font-size: 13px;
line-height: 1.5;
padding: 24px;
min-height: 100vh;
}

/* ── HEADER ── */
.header {
border: 1px solid var(–dim);
padding: 16px 20px;
margin-bottom: 32px;
display: flex;
align-items: center;
justify-content: space-between;
gap: 16px;
}
.header h1 {
font-family: ‘VT323’, monospace;
font-size: 32px;
letter-spacing: 2px;
color: var(–accent);
}
.header .meta {
color: var(–mid);
font-size: 11px;
text-align: right;
}
.header .meta span { color: var(–amber); }

/* ── SECTION LABELS ── */
.section-label {
font-size: 10px;
letter-spacing: 3px;
color: var(–mid);
text-transform: uppercase;
margin-bottom: 12px;
padding-bottom: 6px;
border-bottom: var(–border);
}

/* ── TIMING TABLE ── */
.timing-grid {
display: grid;
grid-template-columns: 1fr 1fr 1fr;
gap: 12px;
margin-bottom: 32px;
}
.timing-card {
border: var(–border);
padding: 14px;
position: relative;
}
.timing-card:hover { border-color: #555; }
.timing-card .label {
font-size: 10px;
color: var(–mid);
letter-spacing: 2px;
margin-bottom: 8px;
}
.timing-card .value {
font-family: ‘VT323’, monospace;
font-size: 28px;
color: var(–accent);
}
.timing-card .unit { font-size: 13px; color: var(–mid); }
.timing-card .note {
font-size: 11px;
color: var(–dim);
margin-top: 8px;
line-height: 1.4;
}
.timing-card .note em { color: var(–amber); font-style: normal; }
.timing-card .source {
font-size: 10px;
color: #333;
margin-top: 6px;
border-top: var(–border);
padding-top: 6px;
}
.timing-card.highlight { border-color: #555; }
.timing-card .tag {
position: absolute;
top: 8px;
right: 8px;
font-size: 9px;
padding: 2px 6px;
background: #1a1a1a;
border: 1px solid #333;
color: var(–dim);
letter-spacing: 1px;
}
.tag.final { border-color: var(–green); color: var(–green); }
.tag.ref { border-color: var(–blue); color: var(–blue); }
.tag.discard { border-color: var(–red); color: var(–red); }

/* ── GESTURE MAP ── */
.gesture-table {
width: 100%;
border-collapse: collapse;
margin-bottom: 32px;
}
.gesture-table th {
font-size: 10px;
letter-spacing: 2px;
color: var(–mid);
text-align: left;
padding: 8px 12px;
border-bottom: var(–border);
}
.gesture-table td {
padding: 10px 12px;
border-bottom: var(–border);
vertical-align: top;
}
.gesture-table tr:hover td { background: #111; }
.gesture-key {
font-family: ‘VT323’, monospace;
font-size: 18px;
color: var(–accent);
white-space: nowrap;
}
.gesture-sym {
font-size: 18px;
margin-right: 8px;
opacity: 0.6;
}
.gesture-timing { color: var(–amber); font-size: 11px; }
.gesture-action { color: var(–fg); }
.gesture-note { color: var(–mid); font-size: 11px; margin-top: 3px; }
.badge {
display: inline-block;
font-size: 9px;
padding: 1px 5px;
letter-spacing: 1px;
margin-left: 6px;
vertical-align: middle;
}
.badge-global { background: #1a2a1a; border: 1px solid var(–green); color: var(–green); }
.badge-ctx    { background: #1a1a2a; border: 1px solid var(–blue);  color: var(–blue);  }

/* ── MENU TREE ── */
.tree-container {
position: relative;
margin-bottom: 32px;
overflow-x: auto;
}

.tree-row {
display: flex;
gap: 0;
margin-bottom: 0;
}

/* SVG tree */
.tree-svg {
width: 100%;
display: block;
}

/* Node cards */
.nodes-layout {
display: grid;
gap: 12px;
margin-bottom: 32px;
}

.tree-level {
display: flex;
gap: 12px;
align-items: flex-start;
}

.node {
border: 1px solid var(–dim);
padding: 12px 14px;
cursor: default;
transition: border-color 0.15s, background 0.15s;
flex: 1;
min-width: 140px;
position: relative;
}
.node:hover { border-color: #777; background: #111; }

.node-lock  { border-color: #444; }
.node-home  { border-color: #888; background: #111; }
.node-spoke { border-color: #333; }
.node-modal { border-color: #2a2a1a; }
.node-sub   { border-color: #222; font-size: 12px; }

.node-label {
font-family: ‘VT323’, monospace;
font-size: 20px;
color: var(–accent);
margin-bottom: 4px;
}
.node-lock  .node-label { color: var(–mid); }
.node-home  .node-label { color: var(–accent); font-size: 22px; }
.node-modal .node-label { color: var(–amber); }
.node-sub   .node-label { font-size: 16px; }

.node-enter {
font-size: 10px;
color: var(–mid);
margin-top: 6px;
line-height: 1.6;
}
.node-enter .k { color: var(–amber); }
.node-enter .v { color: var(–fg); }

.node-desc {
font-size: 11px;
color: #555;
margin-bottom: 8px;
line-height: 1.4;
}

.node-badge {
position: absolute;
top: 6px;
right: 8px;
font-size: 9px;
letter-spacing: 1px;
color: var(–dim);
}
.node-home .node-badge { color: var(–green); }
.node-modal .node-badge { color: var(–amber); }

.arrow-label {
font-size: 10px;
color: var(–mid);
text-align: center;
padding: 4px 0;
}
.arrow-label .a { color: var(–amber); }

/* connector lines */
.connector {
display: flex;
align-items: center;
color: var(–dim);
font-size: 18px;
padding: 0 4px;
align-self: center;
}

/* ── SCREEN STACK ── */
.stack-diagram {
border: var(–border);
padding: 20px;
margin-bottom: 32px;
font-family: ‘VT323’, monospace;
font-size: 18px;
}
.stack-row {
display: flex;
align-items: center;
gap: 12px;
margin-bottom: 10px;
color: var(–mid);
}
.stack-row.active { color: var(–accent); }
.stack-row.top { color: var(–green); }
.stack-index { width: 20px; text-align: right; color: #333; font-size: 14px; }
.stack-box {
border: 1px solid currentColor;
padding: 4px 12px;
min-width: 140px;
font-size: 16px;
}
.stack-row.active .stack-box { background: #111; }
.stack-row.top .stack-box { background: #101a10; }
.stack-arrow { font-size: 12px; color: var(–mid); }

/* ── PAGE TEMPLATE ── */
.template-grid {
display: grid;
grid-template-columns: 1fr 1fr;
gap: 12px;
margin-bottom: 32px;
}
.template-card {
border: var(–border);
padding: 0;
overflow: hidden;
}
.template-card h3 {
font-family: ‘VT323’, monospace;
font-size: 18px;
padding: 8px 12px;
border-bottom: var(–border);
color: var(–accent);
background: #0f0f0f;
}
.template-body { padding: 12px; }
.zone {
font-size: 11px;
margin-bottom: 8px;
padding: 8px;
border: 1px dashed var(–dim);
color: var(–mid);
}
.zone .zone-label {
font-size: 10px;
letter-spacing: 2px;
color: #444;
margin-bottom: 4px;
text-transform: uppercase;
}
.zone .zone-content { color: var(–fg); }

/* ── IMPLEMENTATION NOTES ── */
.impl-grid {
display: grid;
grid-template-columns: 1fr 1fr;
gap: 12px;
margin-bottom: 32px;
}
.impl-card {
border: var(–border);
padding: 14px;
}
.impl-card h4 {
font-family: ‘VT323’, monospace;
font-size: 18px;
color: var(–accent);
margin-bottom: 10px;
padding-bottom: 6px;
border-bottom: var(–border);
}
.impl-card ul {
list-style: none;
padding: 0;
}
.impl-card li {
padding: 4px 0;
font-size: 12px;
color: var(–mid);
padding-left: 14px;
position: relative;
line-height: 1.5;
}
.impl-card li::before {
content: ‘›’;
position: absolute;
left: 0;
color: var(–dim);
}
.impl-card li em { color: var(–amber); font-style: normal; }
.impl-card li strong { color: var(–fg); }

/* ── FULL TREE VISUAL ── */
.full-tree {
margin-bottom: 32px;
overflow-x: auto;
}
.ft-level {
display: flex;
gap: 8px;
margin-bottom: 0;
}
.ft-node {
border: 1px solid var(–dim);
padding: 8px 10px;
font-size: 12px;
flex: 1;
min-width: 100px;
max-width: 160px;
}
.ft-node-name {
font-family: ‘VT323’, monospace;
font-size: 17px;
color: var(–accent);
display: block;
margin-bottom: 2px;
}
.ft-node-desc { font-size: 10px; color: var(–dim); }
.ft-connector {
display: flex;
justify-content: center;
gap: 8px;
color: var(–dim);
padding: 4px 0;
font-size: 11px;
}
.ft-connector-col {
flex: 1;
min-width: 100px;
max-width: 160px;
text-align: center;
}

/* ── COMPARISON TABLE ── */
.compare-table {
width: 100%;
border-collapse: collapse;
margin-bottom: 32px;
font-size: 12px;
}
.compare-table th {
font-size: 10px;
letter-spacing: 2px;
color: var(–mid);
text-align: left;
padding: 8px 10px;
border-bottom: 1px solid #333;
background: #0f0f0f;
}
.compare-table td {
padding: 8px 10px;
border-bottom: 1px solid #1a1a1a;
color: var(–mid);
}
.compare-table tr:hover td { background: #0d0d0d; }
.compare-table .good { color: var(–green); }
.compare-table .bad { color: var(–red); }
.compare-table .name { color: var(–fg); font-size: 13px; }
.compare-table .verdict {
font-size: 10px;
padding: 2px 6px;
border: 1px solid currentColor;
letter-spacing: 1px;
}
.compare-table .v-use { color: var(–green); border-color: var(–green); }
.compare-table .v-ref { color: var(–blue); border-color: var(–blue); }
.compare-table .v-skip { color: #444; border-color: #333; }

.divider {
border: none;
border-top: var(–border);
margin: 28px 0;
}

.callout {
border: 1px solid #333;
border-left: 3px solid var(–amber);
padding: 12px 16px;
margin-bottom: 20px;
font-size: 12px;
color: var(–mid);
line-height: 1.6;
}
.callout strong { color: var(–amber); }

/* blinking cursor */
.cursor::after {
content: ‘█’;
animation: blink 1s step-end infinite;
color: var(–accent);
}
@keyframes blink { 50% { opacity: 0; } }

/* scroll fade */
@keyframes fadeIn {
from { opacity: 0; transform: translateY(8px); }
to   { opacity: 1; transform: translateY(0); }
}
section { animation: fadeIn 0.3s ease forwards; }

.footer {
border-top: var(–border);
padding-top: 16px;
color: #333;
font-size: 10px;
display: flex;
justify-content: space-between;
}

/* tab navigation */
.tabs {
display: flex;
gap: 0;
margin-bottom: 24px;
border-bottom: var(–border);
}
.tab {
padding: 8px 16px;
font-size: 11px;
letter-spacing: 2px;
color: var(–dim);
cursor: pointer;
text-transform: uppercase;
border: 1px solid transparent;
border-bottom: none;
margin-bottom: -1px;
}
.tab:hover { color: var(–mid); }
.tab.active {
color: var(–accent);
border-color: var(–dim);
background: var(–bg);
border-bottom-color: var(–bg);
}
.tab-content { display: none; }
.tab-content.active { display: block; }
</style>

</head>
<body>

<div class="header">
  <div>
    <div class="section-label">BITOS / RESEARCH DOCUMENT</div>
    <h1>MENU TREE + NAVIGATION ARCH<span class="cursor"></span></h1>
  </div>
  <div class="meta">
    Pi Zero 2W + WhisPlay HAT<br>
    ST7789 · 240×280 · 1 button<br>
    <span>REV 1 · MARCH 2026</span>
  </div>
</div>

<div class="tabs">
  <div class="tab active" onclick="showTab('timing')">TIMING</div>
  <div class="tab" onclick="showTab('tree')">MENU TREE</div>
  <div class="tab" onclick="showTab('screens')">SCREEN ARCH</div>
  <div class="tab" onclick="showTab('refs')">REFERENCES</div>
</div>

<!-- ══ TAB 1: TIMING ══════════════════════════════════════════════ -->

<div id="tab-timing" class="tab-content active">

  <div class="section-label">BUTTON TIMING RESEARCH — COMPARISON</div>

  <div class="callout">
    <strong>FINDING:</strong> iOS/Android and the OneButton library converge on the same core values: 30–50ms debounce, 300–400ms double-tap window, 500–800ms long press. Our deployed v2 handler is well-tuned. The main remaining improvement is the OneButton FSM port, which cleans up the boolean-flag state into a single integer state machine.
  </div>

  <div class="timing-grid">
    <div class="timing-card highlight">
      <div class="tag final">✓ DEPLOYED</div>
      <div class="label">DEBOUNCE</div>
      <div class="value">30<span class="unit">ms</span></div>
      <div class="note">Mechanical button bounce settling. <em>OneButton default: 50ms.</em> 30ms is safe — most buttons settle in 10–20ms. Could tighten to 20ms if needed.</div>
      <div class="source">source: OneButton.cpp bouncetime · iOS HIG</div>
    </div>
    <div class="timing-card highlight">
      <div class="tag final">✓ DEPLOYED</div>
      <div class="label">LONG PRESS THRESHOLD</div>
      <div class="value">500<span class="unit">ms</span></div>
      <div class="note">Fires <em>during hold</em> (iOS behavior). OneButton default: 800ms. iOS: 500ms. Android: 500ms. 500ms is correct — 800ms is too slow for embedded wearables.</div>
      <div class="source">source: iOS HIG · UILongPressGestureRecognizer</div>
    </div>
    <div class="timing-card highlight">
      <div class="tag final">✓ DEPLOYED</div>
      <div class="label">DOUBLE-TAP WINDOW</div>
      <div class="value">300<span class="unit">ms</span></div>
      <div class="note">Wait window before confirming single tap as SHORT_PRESS. <em>OneButton: 400ms. iOS: 300ms. Android: 300ms.</em> 300ms is correct — feels snappy.</div>
      <div class="source">source: OneButton clickTicks · Android GestureDetector</div>
    </div>
    <div class="timing-card">
      <div class="tag ref">REFERENCE</div>
      <div class="label">ONEBUTTON (ARDUINO DEFAULT)</div>
      <div class="value">50<span class="unit">/400/800ms</span></div>
      <div class="note">Debounce / double-tap / long press. Conservative — designed for noisy hardware buttons with gloves. Works but feels slow on clean hardware.</div>
      <div class="source">source: mathertel/OneButton · 15yr, 3000+ stars</div>
    </div>
    <div class="timing-card">
      <div class="tag ref">REFERENCE</div>
      <div class="label">iOS HIG</div>
      <div class="value">300<span class="unit">/500ms</span></div>
      <div class="note">Double-tap / long press thresholds. iOS fires long press DURING hold via haptic feedback cue. Short press = confirmed after double-tap window expires.</div>
      <div class="source">source: Apple Human Interface Guidelines 2024</div>
    </div>
    <div class="timing-card">
      <div class="tag ref">REFERENCE</div>
      <div class="label">ANDROID GestureDetector</div>
      <div class="value">300<span class="unit">/500ms</span></div>
      <div class="note">doubleTapTimeout = 300ms. longPressTimeout = 500ms. Same as iOS in practice. <em>Single tap delayed 300ms</em> to confirm no double tap — identical to our handler.</div>
      <div class="source">source: android.view.GestureDetector · AOSP</div>
    </div>
    <div class="timing-card">
      <div class="tag ref">REFERENCE</div>
      <div class="label">M5STACK MicroPython</div>
      <div class="value">1200<span class="unit">/2000ms</span></div>
      <div class="note">pressedFor() / releasedFor() — designed for UI menus on embedded displays. Much slower thresholds. Optimized for casual kiosk use, not wearable.</div>
      <div class="source">source: m5stack/M5Stack_MicroPython · GitHub</div>
    </div>
    <div class="timing-card">
      <div class="tag ref">REFERENCE</div>
      <div class="label">peterhinch micro-gui</div>
      <div class="value">n/a<span class="unit"> encoder</span></div>
      <div class="note">Uses rotary encoder + button. Double-click = adjust mode. Long press = precision mode. No documented ms values — callback-driven FSM. Navigation architecture is the reference, not timing.</div>
      <div class="source">source: peterhinch/micropython-micro-gui</div>
    </div>
    <div class="timing-card">
      <div class="tag final">NEXT</div>
      <div class="label">ONEBUTTON FSM PORT</div>
      <div class="value">6<span class="unit"> states</span></div>
      <div class="note">Replace boolean flags (_is_pressed, _long_fired, _was_pressed, _pending_tap_check) with single int _state. Same timing values, cleaner architecture. <em>This is the pending improvement.</em></div>
      <div class="source">source: mathertel/OneButton FSM diagram</div>
    </div>
  </div>

  <div class="section-label">GESTURE MAP — FINAL BITOS MAPPING</div>

  <table class="gesture-table">
    <thead>
      <tr>
        <th>GESTURE</th>
        <th>TIMING</th>
        <th>GLOBAL ACTION</th>
        <th>CONTEXT NOTES</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td><span class="gesture-sym">▸</span><span class="gesture-key">SHORT_PRESS</span></td>
        <td class="gesture-timing">tap → confirm 300ms later</td>
        <td class="gesture-action">
          <strong>ADVANCE / SCROLL</strong>
          <div class="gesture-note">Move focus to next item in current screen</div>
        </td>
        <td class="gesture-note">
          On home menu: cycles through 5 items, wraps<br>
          On list: scroll down one item<br>
          On active content: scroll / next page
        </td>
      </tr>
      <tr>
        <td><span class="gesture-sym">⬛</span><span class="gesture-key">LONG_PRESS</span></td>
        <td class="gesture-timing">hold ≥500ms (fires during hold)</td>
        <td class="gesture-action">
          <strong>SELECT / ENTER / CONFIRM</strong>
          <div class="gesture-note">Activate focused item or confirm action</div>
        </td>
        <td class="gesture-note">
          On home menu: enter selected screen<br>
          On list item: open / activate<br>
          On lock: unlock → home<br>
          On timer: start / pause
        </td>
      </tr>
      <tr>
        <td><span class="gesture-sym">▸▸</span><span class="gesture-key">DOUBLE_PRESS</span></td>
        <td class="gesture-timing">2 taps within 300ms</td>
        <td class="gesture-action">
          <strong>BACK / POP SCREEN</strong>
          <div class="gesture-note">Return to previous screen (pops stack)</div>
        </td>
        <td class="gesture-note">
          From any spoke: back to HOME HUB<br>
          From home: back to LOCK SCREEN<br>
          Modal: dismiss / cancel<br>
          <em>Universal — always works</em>
        </td>
      </tr>
      <tr>
        <td><span class="gesture-sym">▸▸▸</span><span class="gesture-key">TRIPLE_PRESS</span></td>
        <td class="gesture-timing">3 taps within 300ms</td>
        <td class="gesture-action">
          <strong>QUICK CAPTURE</strong> <span class="badge badge-global">GLOBAL</span>
          <div class="gesture-note">Opens capture overlay from anywhere</div>
        </td>
        <td class="gesture-note">
          Works from any screen<br>
          Modal overlay — preserves current screen<br>
          Voice note or text snippet → memory
        </td>
      </tr>
      <tr>
        <td><span class="gesture-sym">▸×5</span><span class="gesture-key">POWER_GESTURE</span></td>
        <td class="gesture-timing">5 presses within 1200ms</td>
        <td class="gesture-action">
          <strong>POWER MENU</strong> <span class="badge badge-global">GLOBAL</span>
          <div class="gesture-note">Sleep / Restart / Shutdown</div>
        </td>
        <td class="gesture-note">
          Works from any screen<br>
          Full-screen modal takeover<br>
          Requires confirmation (LONG_PRESS)
        </td>
      </tr>
      <tr>
        <td><span class="gesture-sym">↕</span><span class="gesture-key">HOLD_START / END</span></td>
        <td class="gesture-timing">immediate on press / release</td>
        <td class="gesture-action">
          <strong>UI FEEDBACK ONLY</strong>
          <div class="gesture-note">Highlight pressed item, draw press indicator</div>
        </td>
        <td class="gesture-note">
          No navigation logic<br>
          Used to animate hint bar, invert selected row<br>
          Shows visual feedback before gesture resolves
        </td>
      </tr>
    </tbody>
  </table>

  <div class="section-label">ONEBUTTON FSM — STATE MACHINE TO PORT</div>

  <div class="impl-grid">
    <div class="impl-card">
      <h4>6 STATES</h4>
      <ul>
        <li><em>0 IDLE</em> — waiting for press</li>
        <li><em>1 DOWN</em> — button held, timing starts, _start_time set</li>
        <li><em>2 UP_WAIT</em> — released, watching for double-tap within window</li>
        <li><em>3 COUNT</em> — second tap registered, waiting for release</li>
        <li><em>4 LONG_WAIT</em> — held past threshold, waiting for release (add: fire during hold)</li>
        <li><em>5 LONG_END</em> — released after long press, reset</li>
      </ul>
    </div>
    <div class="impl-card">
      <h4>PORT PLAN</h4>
      <ul>
        <li>Keep <strong>ButtonEvent enum</strong> — no changes</li>
        <li>Keep <strong>on() / _emit() / create_button_handler()</strong> — no changes</li>
        <li>Replace 4 boolean flags with <strong>single int _state</strong></li>
        <li>Rename update() → <em>tick()</em> (OneButton convention)</li>
        <li>Add <em>LONG fires during hold</em> (OneButton fires on release by default — we override)</li>
        <li>Keep GPIO polling path unchanged — orthogonal to FSM</li>
        <li>Negative debounce option: debounce only on release, not press</li>
      </ul>
    </div>
  </div>

</div>

<!-- ══ TAB 2: MENU TREE ══════════════════════════════════════════ -->

<div id="tab-tree" class="tab-content">

  <div class="section-label">BITOS MENU TREE — RECOMMENDED ARCHITECTURE</div>

  <div class="callout">
    <strong>MODEL: HUB-AND-SPOKE</strong> — Lock screen → Home hub (5 items max) → spokes. Back always returns to hub. Global gestures (TRIPLE_PRESS, POWER) work everywhere. This is the right model for single-button task-oriented devices.
  </div>

  <!-- LEVEL 0: LOCK -->

  <div class="section-label">LEVEL 0 — ALWAYS ON / AMBIENT</div>
  <div class="ft-level" style="margin-bottom:4px;">
    <div class="ft-node node-lock" style="max-width:100%; border-color:#444;">
      <span class="ft-node-name">🔒 LOCK SCREEN</span>
      <span class="ft-node-desc">Clock · Date · Status bar (WiFi/bat) · Ambient display mode · SHORT/LONG = unlock → HOME</span>
    </div>
  </div>
  <div class="ft-connector" style="font-size:14px; color:#555; margin-bottom:4px;">
    ↓ <span style="color:var(--amber)">LONG_PRESS</span> = unlock &nbsp;&nbsp; ↓ <span style="color:var(--amber)">SHORT_PRESS</span> = wake display
  </div>

  <!-- LEVEL 1: HOME HUB -->

  <div class="section-label">LEVEL 1 — HOME HUB (max 5 items)</div>
  <div class="ft-level" style="margin-bottom:4px;">
    <div class="ft-node node-home" style="max-width:100%; border-color:#888;">
      <span class="ft-node-name">⌂ HOME HUB</span>
      <span class="ft-node-desc">Menu list: [Chat] [Capture] [Tasks] [Focus] [Settings] · SHORT = advance cursor · LONG = enter · DOUBLE = back to Lock</span>
    </div>
  </div>
  <div class="ft-connector" style="margin-bottom: 4px;">
    <div class="ft-connector-col">↓ <span style="color:var(--amber)">LONG</span></div>
    <div class="ft-connector-col">↓ <span style="color:var(--amber)">LONG</span></div>
    <div class="ft-connector-col">↓ <span style="color:var(--amber)">LONG</span></div>
    <div class="ft-connector-col">↓ <span style="color:var(--amber)">LONG</span></div>
    <div class="ft-connector-col">↓ <span style="color:var(--amber)">LONG</span></div>
  </div>

  <!-- LEVEL 2: SPOKES -->

  <div class="section-label">LEVEL 2 — SPOKES (hub-and-spoke model)</div>
  <div class="ft-level" style="margin-bottom:4px;">
    <div class="ft-node node-spoke">
      <span class="ft-node-name">💬 CHAT</span>
      <span class="ft-node-desc">Active conversation · Streaming response · SHORT = scroll · LONG = chat options · DOUBLE = home</span>
    </div>
    <div class="ft-node node-spoke">
      <span class="ft-node-name">✦ CAPTURE</span>
      <span class="ft-node-desc">Quick text/voice note · Record → memory → done · SHORT = submit · DOUBLE = cancel</span>
    </div>
    <div class="ft-node node-spoke">
      <span class="ft-node-name">☑ TASKS</span>
      <span class="ft-node-desc">Things: today's list · SHORT = scroll · LONG = toggle done · DOUBLE = home</span>
    </div>
    <div class="ft-node node-spoke">
      <span class="ft-node-name">◉ FOCUS</span>
      <span class="ft-node-desc">Pomodoro timer · LONG = start/pause · SHORT = +5min · DOUBLE = home</span>
    </div>
    <div class="ft-node node-spoke">
      <span class="ft-node-name">⚙ SETTINGS</span>
      <span class="ft-node-desc">Submenu list · SHORT = scroll · LONG = enter/toggle · DOUBLE = home</span>
    </div>
  </div>

  <div class="ft-connector" style="margin-bottom: 4px;">
    <div class="ft-connector-col">↓ <span style="color:var(--amber)">LONG</span></div>
    <div class="ft-connector-col">&nbsp;</div>
    <div class="ft-connector-col">↓ <span style="color:var(--amber)">LONG</span></div>
    <div class="ft-connector-col">&nbsp;</div>
    <div class="ft-connector-col">↓ <span style="color:var(--amber)">LONG</span></div>
  </div>

  <!-- LEVEL 3: DEPTH-2 CHILDREN (only where needed) -->

  <div class="section-label">LEVEL 3 — DEPTH-2 (sparingly — only where needed)</div>
  <div class="ft-level" style="margin-bottom:4px;">
    <div class="ft-node node-sub">
      <span class="ft-node-name">📋 CONVOS LIST</span>
      <span class="ft-node-desc">Past conversations · SHORT scroll · LONG open · DOUBLE back to chat</span>
    </div>
    <div class="ft-node" style="border-color:#111; background:transparent; flex:2; min-width:0;"></div>
    <div class="ft-node node-sub">
      <span class="ft-node-name">⊕ NEW TASK</span>
      <span class="ft-node-desc">Quick add via voice · SHORT confirm · DOUBLE cancel</span>
    </div>
    <div class="ft-node" style="border-color:#111; background:transparent;"></div>
    <div class="ft-node node-sub">
      <span class="ft-node-name">⚙ SUBMENUS</span>
      <span class="ft-node-desc">Display · Button timing · WiFi · About · SHORT scroll · LONG enter · DOUBLE back</span>
    </div>
  </div>

  <div class="ft-connector" style="font-size:14px; color:#333; margin: 8px 0;">
    ──────────────────────────────── GLOBAL OVERLAYS ────────────────────────────────
  </div>

  <!-- MODALS -->

  <div class="section-label">GLOBAL — MODAL OVERLAYS (any screen, any depth)</div>
  <div class="ft-level">
    <div class="ft-node node-modal">
      <span class="ft-node-name">✦ QUICK CAPTURE</span>
      <span class="ft-node-desc">Triggered by TRIPLE_PRESS anywhere · Overlays current screen · SHORT submit · DOUBLE cancel · Returns to where you were</span>
    </div>
    <div class="ft-node node-modal">
      <span class="ft-node-name">⚡ POWER MENU</span>
      <span class="ft-node-desc">Triggered by 5× rapid press · Full-screen takeover · SHORT scroll [Sleep/Restart/Shutdown] · LONG confirm · DOUBLE cancel</span>
    </div>
    <div class="ft-node node-modal">
      <span class="ft-node-name">◈ CONFIRM DIALOG</span>
      <span class="ft-node-desc">Generic confirmation overlay · Yes/No · LONG = yes · DOUBLE = no/cancel · Used for destructive actions</span>
    </div>
  </div>

  <hr class="divider">
  <div class="section-label">NAVIGATION RULES</div>

  <table class="gesture-table">
    <thead>
      <tr><th>RULE</th><th>DESCRIPTION</th><th>WHY</th></tr>
    </thead>
    <tbody>
      <tr>
        <td class="gesture-key" style="font-size:14px;">Max 5 home items</td>
        <td>Chat, Capture, Tasks, Focus, Settings. Never add to this list.</td>
        <td class="gesture-note">With SHORT_PRESS cycling, >5 items = too many taps to reach the last one</td>
      </tr>
      <tr>
        <td class="gesture-key" style="font-size:14px;">Max 2 depth levels</td>
        <td>Home → Spoke → (optional one sublevel). No deeper.</td>
        <td class="gesture-note">Every level deeper = another DOUBLE_PRESS to navigate back. Gets disorienting fast.</td>
      </tr>
      <tr>
        <td class="gesture-key" style="font-size:14px;">DOUBLE always = back</td>
        <td>On any screen at any depth. Always. No exceptions.</td>
        <td class="gesture-note">Muscle memory. Users must be able to escape anything. Never trap the user.</td>
      </tr>
      <tr>
        <td class="gesture-key" style="font-size:14px;">Hint bar everywhere</td>
        <td>[tap] scroll &nbsp; [hold] select &nbsp; [2×] back — always visible at bottom</td>
        <td class="gesture-note">Single-button devices are opaque. Users must always know what pressing does.</td>
      </tr>
      <tr>
        <td class="gesture-key" style="font-size:14px;">Hub-and-spoke back</td>
        <td>From any spoke, DOUBLE returns to HOME, not to the previous spoke.</td>
        <td class="gesture-note">Simpler mental model than arbitrary back-stack across sibling screens</td>
      </tr>
      <tr>
        <td class="gesture-key" style="font-size:14px;">Globals are modal</td>
        <td>TRIPLE_PRESS capture and POWER overlay the current screen, not push to stack.</td>
        <td class="gesture-note">Preserves where the user was. After capture, they return to their context.</td>
      </tr>
    </tbody>
  </table>

</div>

<!-- ══ TAB 3: SCREEN ARCH ════════════════════════════════════════ -->

<div id="tab-screens" class="tab-content">

  <div class="section-label">SCREEN STACK ARCHITECTURE (peterhinch micro-gui pattern, adapted)</div>

  <div class="callout">
    <strong>MODEL:</strong> Each screen is a class. The ScreenManager holds a stack of screen instances. LONG_PRESS pushes a new screen. DOUBLE_PRESS pops. Modals overlay without pushing (they draw on top). Every screen inherits the same base template.
  </div>

  <!-- Stack visualization -->

  <div class="section-label">SCREEN STACK — EXAMPLE STATE: user is in Chat → Conversations List</div>
  <div class="stack-diagram">
    <div class="stack-row" style="color:#333;">
      <div class="stack-index">—</div>
      <div>[ POWER MENU ] &nbsp;&nbsp; <span style="font-size:12px; color:#2a2a2a;">modal overlay, not on stack</span></div>
    </div>
    <div class="stack-row" style="color:#333;">
      <div class="stack-index">—</div>
      <div>[ CAPTURE ] &nbsp;&nbsp; <span style="font-size:12px; color:#2a2a2a;">modal overlay, not on stack</span></div>
    </div>
    <div style="border-top: 1px dashed #222; margin: 8px 20px;"></div>
    <div class="stack-row top">
      <div class="stack-index">2</div>
      <div class="stack-box">ConversationsListScreen</div>
      <div class="stack-arrow">← ACTIVE / TOP OF STACK</div>
    </div>
    <div class="stack-row active">
      <div class="stack-index">1</div>
      <div class="stack-box">ChatScreen</div>
      <div class="stack-arrow">← paused, still in memory</div>
    </div>
    <div class="stack-row" style="color:#444;">
      <div class="stack-index">0</div>
      <div class="stack-box">HomeScreen</div>
      <div class="stack-arrow">← always at bottom</div>
    </div>
    <div style="border-top: 1px solid #222; margin: 8px 20px;"></div>
    <div class="stack-row" style="color:#333;">
      <div class="stack-index">—</div>
      <div>[ LockScreen ] &nbsp;&nbsp; <span style="font-size:12px; color:#2a2a2a;">separate layer, not part of nav stack</span></div>
    </div>
  </div>

  <!-- Page Template -->

  <div class="section-label">UNIVERSAL SCREEN TEMPLATE — every screen uses this 3-zone layout</div>

  <div class="template-grid">
    <div class="template-card">
      <h3>SCREEN TEMPLATE (240×280px)</h3>
      <div class="template-body">
        <div class="zone" style="height:28px; padding:6px 8px;">
          <div class="zone-label">STATUS BAR · 24px · fixed</div>
          <div class="zone-content">WiFi · Battery · Clock · Screen name</div>
        </div>
        <div class="zone" style="height:96px; padding:8px;">
          <div class="zone-label">CONTENT AREA · flex · fills remaining space</div>
          <div class="zone-content">
            Menu list OR conversation OR timer<br>
            Scrollable. Selected item highlighted.<br>
            Breadcrumb: HOME &gt; CHAT (if depth &gt; 1)
          </div>
        </div>
        <div class="zone" style="height:28px; padding:6px 8px;">
          <div class="zone-label">HINT BAR · 24px · fixed</div>
          <div class="zone-content">[tap] scroll &nbsp; [hold] select &nbsp; [2×] back</div>
        </div>
      </div>
    </div>
    <div class="template-card">
      <h3>SCREEN PYTHON INTERFACE</h3>
      <div class="template-body" style="font-size:11px; color: var(--mid); line-height:1.8;">
        <div style="color: #555; margin-bottom:8px;">Every screen subclasses Screen:</div>
        <code style="display:block; color:var(--mid);">
          class Screen:<br>
          &nbsp;&nbsp;<em style="color:#444">def on_enter(self)</em><br>
          &nbsp;&nbsp;<em style="color:#444">def on_exit(self)</em><br>
          &nbsp;&nbsp;def handle_event(self, event)<br>
          &nbsp;&nbsp;def draw(self, display)<br>
          &nbsp;&nbsp;def get_hint(self) → str<br>
          &nbsp;&nbsp;def get_breadcrumb() → str<br>
        </code>
        <div style="margin-top:12px; color:#555; margin-bottom:8px;">ScreenManager:</div>
        <code style="display:block; color:var(--mid);">
          manager.push(ChatScreen())<br>
          manager.pop() &nbsp; # DOUBLE_PRESS<br>
          manager.overlay(CaptureModal())<br>
          manager.clear_to(HomeScreen)<br>
        </code>
      </div>
    </div>
  </div>

  <div class="section-label">SCREEN INVENTORY — FULL LIST</div>

  <table class="gesture-table">
    <thead>
      <tr>
        <th>SCREEN</th>
        <th>TYPE</th>
        <th>SHORT_PRESS</th>
        <th>LONG_PRESS</th>
        <th>DOUBLE_PRESS</th>
        <th>SPECIAL</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td><strong class="gesture-key" style="font-size:15px;">LockScreen</strong></td>
        <td style="color:var(--mid);">layer-0</td>
        <td>wake display</td>
        <td>unlock → HOME</td>
        <td>—</td>
        <td style="color:var(--dim);">ambient clock, auto-lock after 60s idle</td>
      </tr>
      <tr>
        <td><strong class="gesture-key" style="font-size:15px;">HomeScreen</strong></td>
        <td style="color:var(--mid);">hub</td>
        <td>advance cursor</td>
        <td>enter selected</td>
        <td>back → Lock</td>
        <td style="color:var(--dim);">5 items max, wraps around</td>
      </tr>
      <tr>
        <td><strong class="gesture-key" style="font-size:15px;">ChatScreen</strong></td>
        <td style="color:var(--mid);">spoke</td>
        <td>scroll response</td>
        <td>open options submenu</td>
        <td>back → HOME</td>
        <td style="color:var(--dim);">streaming response display, HOLD_START = show cursor</td>
      </tr>
      <tr>
        <td><strong class="gesture-key" style="font-size:15px;">ConversationsScreen</strong></td>
        <td style="color:var(--mid);">depth-2</td>
        <td>scroll list</td>
        <td>open conversation</td>
        <td>back → Chat</td>
        <td style="color:var(--dim);">from Chat → [Options] → View convos</td>
      </tr>
      <tr>
        <td><strong class="gesture-key" style="font-size:15px;">CaptureScreen</strong></td>
        <td style="color:var(--mid);">modal</td>
        <td>submit / next field</td>
        <td>confirm + save</td>
        <td>cancel</td>
        <td style="color:var(--dim);">TRIPLE_PRESS from anywhere, overlays stack</td>
      </tr>
      <tr>
        <td><strong class="gesture-key" style="font-size:15px;">TasksScreen</strong></td>
        <td style="color:var(--mid);">spoke</td>
        <td>scroll list</td>
        <td>toggle complete</td>
        <td>back → HOME</td>
        <td style="color:var(--dim);">pulls from Things today list</td>
      </tr>
      <tr>
        <td><strong class="gesture-key" style="font-size:15px;">FocusScreen</strong></td>
        <td style="color:var(--mid);">spoke</td>
        <td>+5 min</td>
        <td>start / pause</td>
        <td>back → HOME</td>
        <td style="color:var(--dim);">Pomodoro countdown, big number display</td>
      </tr>
      <tr>
        <td><strong class="gesture-key" style="font-size:15px;">SettingsScreen</strong></td>
        <td style="color:var(--mid);">spoke</td>
        <td>scroll items</td>
        <td>enter / toggle</td>
        <td>back → HOME</td>
        <td style="color:var(--dim);">Display · Button timing · WiFi · About</td>
      </tr>
      <tr>
        <td><strong class="gesture-key" style="font-size:15px;">PowerMenuScreen</strong></td>
        <td style="color:var(--amber);">modal</td>
        <td>scroll [Sleep/Restart/Shutdown]</td>
        <td>confirm</td>
        <td>cancel</td>
        <td style="color:var(--dim);">5× rapid press global trigger</td>
      </tr>
      <tr>
        <td><strong class="gesture-key" style="font-size:15px;">ConfirmDialog</strong></td>
        <td style="color:var(--amber);">modal</td>
        <td>toggle Yes↔No</td>
        <td>confirm selected</td>
        <td>cancel</td>
        <td style="color:var(--dim);">generic — reusable for any destructive action</td>
      </tr>
    </tbody>
  </table>

  <div class="section-label">IMPLEMENTATION PRIORITIES</div>

  <div class="impl-grid">
    <div class="impl-card">
      <h4>PHASE 1 — CORE SKELETON</h4>
      <ul>
        <li><strong>ScreenManager class</strong> with push/pop/overlay</li>
        <li><strong>Base Screen class</strong> with draw/handle_event/get_hint</li>
        <li><strong>LockScreen + HomeScreen</strong> — minimal, working</li>
        <li><strong>ChatScreen</strong> — most important spoke, get this right first</li>
        <li><strong>Consistent hint bar</strong> on every screen, auto-generated from context</li>
        <li><em>Result:</em> can navigate Lock → Home → Chat → back</li>
      </ul>
    </div>
    <div class="impl-card">
      <h4>PHASE 2 — FILL OUT SPOKES</h4>
      <ul>
        <li><strong>TasksScreen</strong> — Things API integration</li>
        <li><strong>FocusScreen</strong> — simple Pomodoro timer</li>
        <li><strong>CaptureModal</strong> — TRIPLE_PRESS overlay</li>
        <li><strong>PowerMenuScreen</strong> — power gesture overlay</li>
        <li><em>Deferred:</em> ConversationsScreen, SettingsScreen</li>
        <li><em>Result:</em> full MVP loop working on device</li>
      </ul>
    </div>
    <div class="impl-card">
      <h4>EFFICIENCY — THE KEY INSIGHT</h4>
      <ul>
        <li>Every screen is a <em>Python class</em> with identical interface</li>
        <li>Adding a new screen = subclass Screen, implement draw() + handle_event()</li>
        <li>Hint bar is <em>auto-generated</em> — no per-screen copy-paste</li>
        <li>Status bar is <em>shared widget</em> drawn by ScreenManager on top of everything</li>
        <li><em>Result:</em> new screens take ~50 lines, not 200</li>
      </ul>
    </div>
    <div class="impl-card">
      <h4>AVOID THESE MISTAKES</h4>
      <ul>
        <li>Don't put more than <em>5 items</em> on home menu</li>
        <li>Don't go deeper than <em>2 levels</em> without a back route</li>
        <li>Don't let DOUBLE_PRESS do different things on different screens</li>
        <li>Don't skip the hint bar on "obvious" screens — there are no obvious screens</li>
        <li>Don't make SHORT_PRESS context-sensitive in non-obvious ways</li>
      </ul>
    </div>
  </div>

</div>

<!-- ══ TAB 4: REFERENCES ════════════════════════════════════════ -->

<div id="tab-refs" class="tab-content">

  <div class="section-label">LIBRARY / REFERENCE COMPARISON</div>

  <table class="compare-table">
    <thead>
      <tr>
        <th>NAME</th>
        <th>LANGUAGE</th>
        <th>WHAT IT DOES WELL</th>
        <th>LIMITATIONS FOR BITOS</th>
        <th>USE?</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td class="name">mathertel/OneButton</td>
        <td>C++ (Arduino)</td>
        <td class="good">15yr battle-tested FSM. 6-state machine. 3000+ stars. Single click, double click, long press. tick() pattern. Negative debounce option.</td>
        <td>C++ only. We port the FSM logic to Python — no direct dependency.</td>
        <td><span class="verdict v-use">PORT FSM</span></td>
      </tr>
      <tr>
        <td class="name">elliotmade/This-Button</td>
        <td>CircuitPython</td>
        <td class="good">Python port of OneButton. Non-blocking. Clean API. assignClick() / assignLongPressStart().</td>
        <td>CircuitPython only (uses board module). Not RPi.GPIO. Would need adaptation. Less battle-tested than OneButton.</td>
        <td><span class="verdict v-ref">REFERENCE ONLY</span></td>
      </tr>
      <tr>
        <td class="name">peterhinch/micropython-micro-gui</td>
        <td>MicroPython</td>
        <td class="good">Best reference for embedded Python GUI architecture. Screen class, screen stack, modal Windows. push/pop navigation. Screen replace for non-tree nav. April 2024 actively maintained.</td>
        <td>MicroPython only. Full GUI framework — overkill for BITOS. But Screen/Window architecture pattern is exactly what we want to adapt.</td>
        <td><span class="verdict v-ref">ARCH REFERENCE</span></td>
      </tr>
      <tr>
        <td class="name">LVGL</td>
        <td>C + MicroPython bindings</td>
        <td class="good">30+ built-in widgets. Used in production devices (Xiaomi). Full navigation system. ePaper, OLED, TFT support.</td>
        <td>Requires C build system. Massive footprint. Way overengineered for BITOS's 1-bit pixel art UI. Pi Zero 2W would handle it but it's the wrong tool.</td>
        <td><span class="verdict v-skip">SKIP</span></td>
      </tr>
      <tr>
        <td class="name">m5stack/M5Stack_MicroPython</td>
        <td>MicroPython</td>
        <td class="good">Clean polling API: wasPressed(), pressedFor(), releasedFor(). Shows how a professional embedded product handles multi-button state.</td>
        <td>Multi-button device (3 buttons). Polling API is reference for button.py design. Timing values (1.2s/2s) are too slow for BITOS.</td>
        <td><span class="verdict v-ref">API PATTERN REF</span></td>
      </tr>
      <tr>
        <td class="name">adafruit_debouncer (CircuitPython)</td>
        <td>CircuitPython</td>
        <td class="good">Clean debouncing via update() polling. rose / fell properties for edge detection without interrupts.</td>
        <td>CircuitPython only. Debounce-only — no gesture detection. Our polling approach already handles debounce.</td>
        <td><span class="verdict v-skip">SKIP</span></td>
      </tr>
      <tr>
        <td class="name">iOS UILongPressGestureRecognizer</td>
        <td>Swift/ObjC</td>
        <td class="good">Industry standard reference. 500ms long press threshold. Fires during hold, not on release. 300ms double-tap. Haptic feedback cue at threshold.</td>
        <td>Not portable. Reference values only. Our v2 handler already matches iOS timing.</td>
        <td><span class="verdict v-ref">TIMING REFERENCE</span></td>
      </tr>
      <tr>
        <td class="name">Android GestureDetector</td>
        <td>Java/Kotlin</td>
        <td class="good">doubleTapTimeout=300ms, longPressTimeout=500ms. Single tap confirmed after double-tap window. Same values as iOS. onSingleTapConfirmed fires 300ms after release.</td>
        <td>Not portable. Reference values only.</td>
        <td><span class="verdict v-ref">TIMING REFERENCE</span></td>
      </tr>
    </tbody>
  </table>

  <div class="section-label">NAVIGATION ARCHITECTURE PATTERNS — EVALUATED</div>

  <table class="compare-table">
    <thead>
      <tr>
        <th>PATTERN</th>
        <th>DESCRIPTION</th>
        <th>WORKS FOR BITOS?</th>
        <th>VERDICT</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td class="name">Hub-and-Spoke</td>
        <td>Central home screen, all features branch off. Must return to hub to switch features.</td>
        <td class="good">Perfect. Minimizes button presses to reach any feature. Simple mental model. DOUBLE always = home.</td>
        <td><span class="verdict v-use">RECOMMENDED</span></td>
      </tr>
      <tr>
        <td class="name">Linear / Hierarchical (iPod)</td>
        <td>Every screen pushes deeper. Back = up one level. Arbitrary nesting depth.</td>
        <td class="bad">Gets lost. With one button, navigating back 3+ levels is tedious. Lost in menu hell.</td>
        <td><span class="verdict v-skip">AVOID</span></td>
      </tr>
      <tr>
        <td class="name">Page-based / Carousel</td>
        <td>Lateral navigation between sibling screens. SHORT = next page.</td>
        <td>Works for siblings but no clear "home" concept. Disorienting on single-button — can't distinguish depth from breadth.</td>
        <td><span class="verdict v-skip">AVOID</span></td>
      </tr>
      <tr>
        <td class="name">Screen Stack + Modal Overlays</td>
        <td>Stack for navigation depth. Modals for global shortcuts (capture, power) that don't break nav.</td>
        <td class="good">Combined with hub-and-spoke this is the right architecture. Modals preserve context. Globals always work.</td>
        <td><span class="verdict v-use">IMPLEMENT THIS</span></td>
      </tr>
    </tbody>
  </table>

  <div class="section-label">KEY SOURCES</div>
  <div class="impl-card" style="border-color:#222;">
    <h4>CITATIONS</h4>
    <ul>
      <li><strong>mathertel.de/Arduino/OneButtonLibrary</strong> — FSM diagram, state descriptions, timing defaults</li>
      <li><strong>github.com/mathertel/OneButton</strong> — OneButton.cpp, OneButton.h source</li>
      <li><strong>github.com/elliotmade/This-Button</strong> — Python port reference (CircuitPython)</li>
      <li><strong>github.com/peterhinch/micropython-micro-gui</strong> — Screen class, modal Window, screen replace pattern, push/pop navigation</li>
      <li><strong>github.com/m5stack/M5Stack_MicroPython</strong> — wasPressed() / pressedFor() polling API pattern</li>
      <li><strong>Apple HIG — Gestures</strong> — 300ms double-tap, 500ms long press during hold</li>
      <li><strong>Android GestureDetector AOSP</strong> — doubleTapTimeout, longPressTimeout values</li>
      <li><strong>nngroup.com — Mobile Navigation Patterns</strong> — hub-and-spoke for task-oriented apps</li>
      <li><strong>frankrausch.com/ios-navigation</strong> — iOS navigation hierarchy model</li>
      <li><strong>WhisPlay commit 51d09cf</strong> — PUD_OFF fix, button HIGH=pressed confirmed</li>
    </ul>
  </div>

</div>

<hr class="divider">
<div class="footer">
  <div>BITOS · Pi Zero 2W + WhisPlay HAT · single-button navigation research</div>
  <div>generated march 2026 · rev 1</div>
</div>

<script>
function showTab(name) {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
  document.querySelector(`[onclick="showTab('${name}')"]`).classList.add('active');
  document.getElementById(`tab-${name}`).classList.add('active');
}
</script>

</body>
</html>