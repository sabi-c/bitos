# UI Spec Gaps — Resolved

All visual gaps between HTML reference designs and Python panel implementations
have been addressed. Changes made (visual rendering only, no business logic):

## tokens.py
- `STATUS_BAR_H`: 12 → 18px (matches `.sbar{height:18px}` in reference)
- `ROW_H_MIN`: added 26px constant (fingertip-navigable row height)
- `FONT_SIZES["hint"]`: added 4px (matches `.kh{font-size:4px}` in reference)

## All Panels (home, settings, chat, focus, notifications)
- **Status bar**: 18px inverted (white bg, black text) on all panels
- **Row height**: 26px minimum everywhere (was 15–20px)
- **Focused row**: fully inverted (white bg, black text) — was outline-only border
- **Key hint bar**: 4px font, centered, `SHORT:X · LONG:Y · DBL:Z` format

## Panel-Specific Fixes
- **HomePanel**: status bar replaces bare title; health indicator in status bar
- **SettingsPanel**: status values include `›` chevron per reference; row spacing fixed
- **ModelPickerPanel**: subtitle text per model (FAST · BALANCED, etc.); ACTIVE badge
- **AgentModePanel**: subtitle per mode (Operations · coordination, etc.); ACTIVE badge
- **FocusPanel**: progress bar added; timer centered below status bar
- **NotificationsPanel**: proper nav row layout at bottom with inverted focus
- **ChatPanel**: dark status bar variant; template items use inverted focus; hint bar added
- **SleepTimerPanel**: status bar; centered timer display; hint bar
- **AboutPanel**: status bar; hint bar

## Overlay Fixes
- **PowerOverlay**: hint uses 4px `hint` font, `SHORT:TOGGLE · LONG:CONFIRM · DBL:CANCEL`
- **QROverlay**: hint uses 4px `hint` font, `LONG:CANCEL`
