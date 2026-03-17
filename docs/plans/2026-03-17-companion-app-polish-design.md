# Companion App Polish — Design Document

**Date:** 2026-03-17
**Scope:** Research + design only — no implementation

---

## 1. Current State Analysis

### Structure

The companion app is a vanilla HTML/CSS/JS PWA — no framework, no build step. 13 HTML pages, 1 shared CSS file, 5 JS modules, a service worker, and SVG icons.

**Pages:**
- `index.html` — Router/splash (redirects to dashboard or setup)
- `dashboard.html` — Main hub: connection status, device status card, mode indicator, quick actions, weather/event widgets, activity feed
- `chat.html` — Chat interface with SSE streaming, session history overlay, search, delete
- `tasks.html` — Task list with add bar, filter tabs (active/all/done), checkboxes, completion animation
- `calendar.html` — 7-day picker, event list with time columns and status dots
- `activity.html` — Activity feed with type filters and expandable items
- `settings.html` — Tabbed settings: device, display, agent, connection, integrations, about
- `setup.html` — 4-step onboarding wizard (connect, auth, wifi, done)
- `pair.html` — 5-step BLE/HTTP pairing flow with QR support
- `bt-guide.html` — Bluetooth pairing walkthrough
- `test_crypto.html` — Dev/debug page

**JS Modules:**
- `nav.js` — Bottom tab bar injection, server URL helpers, toast, time formatting
- `connection.js` — `ConnectionManager` singleton (auto-discover HTTP/BLE, polling, settings persistence)
- `ble.js` — `BitosCompanion` (BLE) + `BitosHttpCompanion` (HTTP) transport classes
- `auth.js` — Authentication helpers
- `crypto.js` — Crypto/pairing utilities
- `settings.js` — Settings read/write logic

### What's Good

- **Architecture is solid.** Vanilla PWA with no build step means zero dependency rot. Service worker caches all assets. Connection manager cleanly abstracts BLE vs HTTP.
- **Feature coverage is complete.** Dashboard, chat, tasks, calendar, activity, settings, setup, pairing — all the right pages exist.
- **Connection resilience.** Graceful fallbacks, timeout handling, auto-reconnect, manual IP entry.
- **Touch targets.** Already using `min-height: 44px` on interactive elements (Apple's minimum).
- **Dark theme.** Already black background with white/gray text — matches device.

### What Needs Work

1. **Typography mismatch.** Device uses Press Start 2P (pixel font) and Monocraft. Companion uses generic `monospace` (renders as Courier or SF Mono depending on platform). The pixel aesthetic is completely lost.

2. **No rounded corners.** Device has 16px corner radius mask. Companion uses sharp rectangles everywhere.

3. **Color usage is inconsistent.** Device has a precise gray scale (DIM1–DIM4, GRAY_08–GRAY_AA, HAIRLINE) defined in `tokens.py`. Companion uses ad-hoc hex values (#1a1a1a, #333, #444, #555, etc.) that roughly overlap but aren't systematic.

4. **Cards use borders, not fills.** Device UI uses filled backgrounds (GRAY_08, GRAY_0A, GRAY_11) with subtle hairline dividers. Companion uses 2px white borders on cards — looks more "wireframe" than "product."

5. **Status bar missing.** Device has an inverted (white bg, black text) status bar at 20px height. Companion has no equivalent persistent header — each page just has `<h1>BITOS</h1>` inline.

6. **No page transitions.** Navigation is full page reload via `location.href`. Feels jarring vs the device's screen push/pop.

7. **Widget styling is flat.** Dashboard widgets (weather, event) have 1px borders and look like placeholder boxes, not designed cards.

8. **Settings page is dense.** The tabbed settings UI works but has 6 sub-tabs crammed into a small horizontal scroll — hard to discover.

9. **PWA manifest is minimal.** No splash screen, no orientation lock, no shortcut actions, no screenshots for install prompt.

10. **Chat bubbles have no personality.** Plain rectangles with no visual distinction beyond left/right alignment.

---

## 2. Target Visual Design

### 2.1 Typography

**Device fonts (from `tokens.py`):**
- Primary: **Press Start 2P** (pixel bitmap font, Google Fonts available)
- Secondary: **Monocraft** (Minecraft-style monospace)

**Companion font strategy:**

| Role | Device | Companion (proposed) |
|------|--------|---------------------|
| Titles, headers, labels | Press Start 2P @ 22px | Press Start 2P @ 14–16px (scaled for phone readability) |
| Body text, chat, descriptions | Press Start 2P @ 17px | **Monocraft** @ 14px (more readable at body size) |
| Small text, hints, timestamps | Press Start 2P @ 11–13px | Press Start 2P @ 9–10px |
| Input fields | n/a (hardware) | Monocraft @ 14px |

**Loading:** Both fonts are available on Google Fonts. Load Press Start 2P via Google Fonts CDN; host Monocraft locally from `device/assets/fonts/Monocraft.ttf` (it's already in the repo). Add `@font-face` declarations and a font-display: swap strategy.

```css
@import url('https://fonts.googleapis.com/css2?family=Press+Start+2P&display=swap');

@font-face {
  font-family: 'Monocraft';
  src: url('/fonts/Monocraft.ttf') format('truetype');
  font-display: swap;
}
```

**Fallback chain:** `'Press Start 2P', 'Monocraft', monospace`

**Note:** Press Start 2P is intentionally hard to read at small sizes. For body copy (chat messages, task descriptions, activity feed), Monocraft is a better choice — it preserves the pixel/game aesthetic but is more legible. Use Press Start 2P for headers, labels, and accent text only.

### 2.2 Color Palette

Extracted from `device/display/tokens.py`, mapped to CSS custom properties:

```css
:root {
  /* Core */
  --black:    #000000;
  --white:    #ffffff;

  /* Gray scale (matches device tokens exactly) */
  --dim1:     #cccccc;  /* 80% — primary text */
  --dim2:     #999999;  /* 60% — secondary text */
  --dim3:     #666666;  /* 40% — tertiary/disabled */
  --dim4:     #333333;  /* 20% — borders, dividers */
  --hairline: #1a1a1a;  /* Subtle separators */

  /* Extended grays */
  --gray-08:  #080808;  /* Deep background */
  --gray-0a:  #0a0a0a;  /* Card background */
  --gray-11:  #111111;  /* Elevated surface */
  --gray-1a:  #1a1a1a;  /* Divider */
  --gray-22:  #222222;  /* Border */
  --gray-33:  #333333;  /* Stronger border */
  --gray-44:  #444444;
  --gray-55:  #555555;
  --gray-66:  #666666;
  --gray-aa:  #aaaaaa;

  /* Semantic (from existing companion usage) */
  --accent-green:  #44ff44;  /* Online, success, confirm */
  --accent-red:    #ff4444;  /* Error, offline, danger */
  --accent-amber:  #ffaa00;  /* Warning, partial, today */
  --accent-blue:   #44aaff;  /* Links, info, wifi badge */
  --accent-purple: #aa44ff;  /* BLE badge */

  /* Spacing (from device tokens) */
  --safe-inset: 16px;
  --corner-radius: 16px;
  --pad-row: 4px;
  --pad-widget: 6px;
  --border-outer: 2px;
  --border-inner: 1px;
  --row-h-min: 28px;
  --status-bar-h: 20px;
}
```

### 2.3 Spacing & Layout

- **Max content width:** Keep 400px max-width (good for phone screens)
- **Safe inset:** 16px horizontal padding (matches device `SAFE_INSET`)
- **Corner radius:** 16px on cards and major containers (matches device `CORNER_RADIUS`)
- **Row minimum height:** 44px for touch targets (already in use, keep it)
- **Card padding:** 16px (matches device `PAD_WIDGET * 2 + extra`)
- **Dividers:** 1px `var(--hairline)` lines between list items
- **Gap between cards:** 12px

### 2.4 Component Design Language

**Cards:** Replace 2px white border cards with filled background cards:
```css
.card {
  background: var(--gray-0a);
  border: 1px solid var(--gray-22);
  border-radius: var(--corner-radius);
  padding: 16px;
}
```

**Status bar (new):** Fixed top bar matching device's inverted status bar:
```css
.status-bar {
  position: fixed; top: 0; left: 0; right: 0;
  height: var(--status-bar-h);
  background: var(--white);
  color: var(--black);
  font-family: 'Press Start 2P'; font-size: 9px;
  display: flex; align-items: center;
  justify-content: space-between;
  padding: 0 var(--safe-inset);
  z-index: 60;
}
```
Shows: page title (left), connection dot + battery indicator (right).

**Buttons:**
- Primary: `background: var(--white); color: var(--black); border-radius: 8px;`
- Secondary: `background: var(--gray-11); border: 1px solid var(--gray-33); border-radius: 8px;`
- Danger: `border-color: var(--accent-red); color: var(--accent-red);`
- All buttons: `font-family: 'Press Start 2P'; font-size: 10px; min-height: 44px;`

**Inputs:**
```css
input, textarea, select {
  background: var(--gray-11);
  border: 1px solid var(--gray-33);
  border-radius: 8px;
  color: var(--white);
  font-family: 'Monocraft'; font-size: 14px;
  padding: 12px;
  min-height: 44px;
}
input:focus { border-color: var(--white); }
```

**Toggle switches:** Keep current design — already clean.

**Tabs/Filters:** Keep underline-style tabs but update font:
```css
.filter-tab {
  font-family: 'Press Start 2P'; font-size: 8px;
  letter-spacing: .04em;
}
```

**Bottom nav:** Keep structure but update styling:
```css
.bottom-nav {
  border-top: 1px solid var(--gray-22);
  background: var(--gray-08);
  backdrop-filter: blur(8px);
}
.nav-tab { font-family: 'Press Start 2P'; font-size: 7px; }
.nav-tab.active { color: var(--white); }
```

**Connection badge:** Existing dot + label pattern is good. Add rounded corners.

**Skeleton loading:** Match device's blinking rectangle pattern from `display/skeleton.py` — two gray bars alternating brightness at 800ms interval.

---

## 3. Page-by-Page Redesign Recommendations

### 3.1 Dashboard (`dashboard.html`)

**Current:** Linear stack of connection badge, status card, mode indicator, quick actions, widgets, activity feed.

**Proposed changes:**
- Add fixed status bar at top (BITOS title left, connection dot + battery right)
- Replace "BITOS" h1 + circled dot with clean status bar — removes redundancy
- Connection status card: rounded corners, filled background, condense into 2 rows
- Device status card: keep info-row pattern but use `var(--gray-0a)` background + rounded corners
- Mode indicator: make it a proper pill-shaped chip with rounded corners
- Quick actions: use rounded corner buttons with subtle background
- Widgets: rounded cards with `var(--gray-11)` background, slightly larger text
- Activity feed: rounded container, hairline dividers, truncated previews

### 3.2 Chat (`chat.html`)

**Current:** Flat bubbles, fixed input bar, sessions overlay.

**Proposed changes:**
- Chat bubbles: add `border-radius: 12px;` — user bubbles top-right square, agent bubbles top-left square (messaging convention)
- Agent bubble: `background: var(--gray-11)` with no border (cleaner)
- User bubble: keep white bg with black text
- Streaming cursor: keep blinking block cursor — fits pixel aesthetic
- Input bar: rounded input field, send button as a circle
- Sessions overlay: use slide-up animation, rounded session cards
- Add voice input button placeholder (mic icon, greyed out for now)

### 3.3 Tasks (`tasks.html`)

**Current:** Functional task list with checkboxes, filter tabs, add bar.

**Proposed changes:**
- Add bar: rounded input + circular "+" button
- Checkboxes: change from `border-radius: 4px` to `border-radius: 6px` (slightly rounder)
- Task items: add subtle left border accent for priority (red=urgent, amber=high)
- Project badges: rounded pill shape
- Completion animation: add a brief confetti-like pulse (optional)
- Empty states: add a small pixel art icon (checkbox with checkmark)

### 3.4 Calendar (`calendar.html`)

**Current:** 7-day picker tabs, event list with time columns and status dots.

**Proposed changes:**
- Day picker: make each tab a rounded chip, selected tab gets white fill
- Event items: add rounded card wrapping per event
- Time column: use `var(--accent-green)` for "now" event highlight more prominently
- All-day events: distinct pill badge styling
- Add "no events" illustration (simple clock pixel art)

### 3.5 Activity (`activity.html`)

**Current:** Filter tabs + flat feed items.

**Proposed changes:**
- Feed items: add subtle left color bar by type (blue=email, green=message, amber=task, gray=system)
- Expandable items: smooth height transition instead of instant toggle
- Type badges: rounded pill shape with type-specific background tint
- Pull-to-refresh indicator (see section 4)

### 3.6 Settings (`settings.html`)

**Current:** 6 horizontal sub-tabs, setting rows with toggles/pickers/sliders.

**Proposed changes:**
- Replace horizontal tab bar with vertical section cards (scrollable page of grouped settings)
- Each section: collapsible card with header + chevron (partially exists already)
- Section groups: DEVICE, DISPLAY, AGENT, CONNECTION, INTEGRATIONS, ABOUT
- Slider thumb: make it square (pixel aesthetic) instead of round
- Integration cards: keep current setup-card pattern but add rounded corners
- Add "Danger Zone" section at bottom (factory reset, unpair) with red accent

### 3.7 Setup (`setup.html`)

**Current:** 4-step wizard with progress dots, connection diagram, wifi config.

**Proposed changes:**
- Progress dots: replace with a progress bar (thin line, filled portion = completed steps)
- Connection diagram: add rounded borders to device icons
- WiFi network list items: rounded cards with signal bars
- Step transitions: add fade/slide animation between steps
- Success state: add pixel art checkmark animation

### 3.8 Pair (`pair.html`)

**Current:** 5-step pairing flow with numbered progress, PIN display, error states.

**Proposed changes:**
- Progress: keep numbered steps but add connecting lines that fill as you proceed
- PIN display: keep large monospace digits — this already looks great
- Celebration screen: add subtle animation (pulsing glow on checkmark)
- Rounded corners on all cards and buttons

### 3.9 BT Guide (`bt-guide.html`)

**Current:** Step-by-step guide with numbered blocks and device mockups.

**Proposed changes:**
- Step numbers: use filled circles (white bg, black number) matching device status bar aesthetic
- Device mockups: add rounded corners to match actual device appearance
- Add platform-specific tips (iOS disclaimer, Android Chrome recommendation)

---

## 4. Touch UX Patterns

The device uses a 5-way nav (single button: short=next, double=select, long=back, triple=agent). The companion has full touch capability. Adapt accordingly:

### 4.1 Pull-to-Refresh

Add to: Dashboard, Tasks, Calendar, Activity, Chat sessions list.

Implementation: CSS overscroll indicator + JS touch event handler. Show a pixel-art loading spinner (spinning square, not circle — fits the aesthetic).

### 4.2 Swipe Gestures

- **Task items:** Swipe right to complete, swipe left to delete (with confirmation)
- **Chat sessions:** Swipe left to delete
- **Activity items:** Swipe to dismiss/archive
- Keep tap-to-expand on activity items

### 4.3 Long Press

- **Task items:** Long press for context menu (edit, move to project, set due date, set priority)
- **Chat messages:** Long press to copy text
- **Calendar events:** Long press for event details

### 4.4 Haptic Feedback

Use `navigator.vibrate()` for:
- Task completion checkbox: 10ms pulse
- Mode cycle: 5ms pulse
- Error states: [50, 50, 50] pattern
- Not supported on iOS but degrades gracefully

### 4.5 Bottom Sheet

Replace `prompt()` dialogs (quick note, focus timer) with slide-up bottom sheets:
- Dark overlay backdrop
- Rounded top corners on sheet
- Drag handle bar at top
- Swipe down to dismiss

### 4.6 Scroll Snap

Calendar day picker: use CSS `scroll-snap-type: x mandatory` so day tabs snap cleanly.

---

## 5. CSS Architecture Changes

### 5.1 Move to CSS Custom Properties

Replace all hardcoded hex values with `var(--token-name)`. This makes theming possible and ensures consistency with device tokens.

### 5.2 Add Shared Animations

```css
/* Skeleton loading (matches device/display/skeleton.py) */
@keyframes skeleton-blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

/* Page transition */
@keyframes slide-in {
  from { transform: translateX(20px); opacity: 0; }
  to { transform: translateX(0); opacity: 1; }
}

/* Bottom sheet */
@keyframes sheet-up {
  from { transform: translateY(100%); }
  to { transform: translateY(0); }
}

/* Toast (replace instant show with slide-up) */
@keyframes toast-in {
  from { transform: translate(-50%, 20px); opacity: 0; }
  to { transform: translate(-50%, 0); opacity: 1; }
}
```

### 5.3 File Structure

Current single `shared.css` works fine for this project size. Do NOT introduce a CSS framework or preprocessor — keep it vanilla. But split into logical sections with clear comment headers:

```
/* ── Reset ── */
/* ── Custom Properties ── */
/* ── Typography ── */
/* ── Layout ── */
/* ── Status Bar ── */
/* ── Cards ── */
/* ── Buttons ── */
/* ── Inputs ── */
/* ── Navigation ── */
/* ── Lists & Rows ── */
/* ── Badges & Pills ── */
/* ── Widgets ── */
/* ── Chat ── */
/* ── Toast ── */
/* ── Loading ── */
/* ── Animations ── */
/* ── Utilities ── */
```

---

## 6. PWA Enhancements

### 6.1 Manifest Updates

```json
{
  "name": "BITOS Companion",
  "short_name": "BITOS",
  "start_url": "/index.html",
  "display": "standalone",
  "orientation": "portrait",
  "background_color": "#000000",
  "theme_color": "#000000",
  "icons": [
    { "src": "icon-192.svg", "sizes": "192x192", "type": "image/svg+xml", "purpose": "any" },
    { "src": "icon-512.svg", "sizes": "512x512", "type": "image/svg+xml", "purpose": "any" },
    { "src": "icon-maskable-192.svg", "sizes": "192x192", "type": "image/svg+xml", "purpose": "maskable" },
    { "src": "icon-maskable-512.svg", "sizes": "512x512", "type": "image/svg+xml", "purpose": "maskable" }
  ],
  "shortcuts": [
    { "name": "Chat", "url": "/chat.html", "icons": [{"src": "icon-chat.svg", "sizes": "96x96"}] },
    { "name": "Tasks", "url": "/tasks.html", "icons": [{"src": "icon-tasks.svg", "sizes": "96x96"}] }
  ],
  "categories": ["utilities", "productivity"]
}
```

Key changes: separate `any` and `maskable` icon purposes (current combines them which causes display issues on Android), add orientation lock, add shortcuts for quick actions.

### 6.2 Maskable Icons

Create maskable variants of the SVG icons with extra padding (safe zone is a centered circle at ~80% of the icon area). The current icon (B in a circle) works well but needs padding for maskable.

### 6.3 Apple Touch Icon

Add to all HTML pages:
```html
<link rel="apple-touch-icon" href="/icon-apple-touch.png">
```
Generate a 180x180 PNG from the SVG for iOS home screen icon quality.

### 6.4 Splash Screen (iOS)

Add `apple-touch-startup-image` meta tags for various device sizes, or use a simple black background with the BITOS logo centered (matches the device boot screen aesthetic).

### 6.5 Service Worker Updates

Current service worker is solid (network-first, cache fallback). Add:
- Font files to the cache list (`/fonts/Monocraft.ttf`)
- Background sync for offline task creation (queue tasks locally, sync when online)
- Periodic background sync for pre-fetching dashboard data (if supported)

### 6.6 Offline Support

- Dashboard: show cached data with a "LAST UPDATED: X ago" indicator
- Chat: show "OFFLINE — messages will send when connected" in input bar
- Tasks: allow local task creation with sync queue
- Calendar: show cached events with staleness indicator

---

## 7. Font Loading Strategy

Press Start 2P is ~15KB from Google Fonts. Monocraft.ttf is ~50KB.

**Strategy:**
1. Add Google Fonts `<link>` with `preconnect` for Press Start 2P
2. Copy `Monocraft.ttf` from `device/assets/fonts/` to `companion/fonts/`
3. Use `font-display: swap` so text renders immediately in fallback monospace, then swaps when fonts load
4. Add both font files to service worker cache list
5. Use `@supports` or a font loading observer to add a `.fonts-loaded` class to `<body>`, enabling pixel-font-specific spacing tweaks only after fonts are available

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Press+Start+2P&display=swap" rel="stylesheet">
```

**Fallback for offline:** Both fonts should be cached by the service worker after first load. If fonts haven't loaded yet (first offline visit), `monospace` fallback is fine.

---

## 8. Implementation Priority

Recommended order of implementation:

1. **CSS custom properties + color palette** — Foundation for everything else. Migrate all hardcoded colors to variables.
2. **Font loading** — Copy Monocraft, add Google Fonts link, update font-family declarations.
3. **Card redesign** — Replace bordered cards with filled/rounded cards across all pages.
4. **Status bar** — Add fixed top bar with page title and connection indicator.
5. **Dashboard polish** — Apply new card styles, widget styling, connection status.
6. **Chat polish** — Rounded bubbles, input bar redesign.
7. **Tasks polish** — Rounded inputs, swipe gestures, priority indicators.
8. **Calendar polish** — Day picker chips, event cards.
9. **Settings restructure** — Vertical sections instead of horizontal tabs.
10. **Touch UX** — Pull-to-refresh, bottom sheets, swipe gestures.
11. **PWA manifest** — Maskable icons, shortcuts, orientation.
12. **Offline enhancements** — Sync queue, staleness indicators.

Each step is independently deployable and testable.

---

## 9. What NOT to Change

- **No framework migration.** Vanilla HTML/CSS/JS is the right call for a companion app this size. No React, no Svelte, no build step.
- **No CSS preprocessor.** Custom properties give us everything we need.
- **No icon library.** Keep inline SVG icons — they're already crisp and cacheable.
- **No client-side routing.** Full page navigation with service worker caching is fast enough and simpler to maintain.
- **No WebSocket for chat.** SSE streaming works well and is simpler.
- **Connection manager architecture.** `ConnectionManager` + `BitosCompanion`/`BitosHttpCompanion` pattern is clean — keep it.
