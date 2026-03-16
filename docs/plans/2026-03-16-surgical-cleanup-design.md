# Surgical Cleanup Sprint — Design

**Goal:** Remove dead code, consolidate duplicated font/color/component systems, and bump composite screen font sizes — without changing screen behavior or layout.

**Architecture:** Four pillars: (1) dead code removal, (2) font/color consolidation, (3) composite screen font bump, (4) shared component extraction. Each pillar is independently shippable.

**Tech Stack:** Python 3, pygame, Pi Zero 2W + ST7789 240x280

---

## 1. Dead Code Removal

Delete confirmed-unused files and imports:

| File | Why dead | Superseded by |
|------|----------|---------------|
| `device/audio/voice_pipeline.py` | Marked "STATUS: Currently unused", imported with `# noqa` | `device/audio/pipeline.py` (AudioPipeline) |
| `device/hardware/battery.py` | Legacy, not imported by active code | `device/power/battery.py` (PiSugar) |
| `device/hardware/led.py` | Legacy LED control | `device/power/leds.py` |
| `device/hardware/pi_led.py` | Legacy LED control | `device/power/leds.py` |
| `device/ui/panels/*.py` (9 files) | Render-only dummy panels with hardcoded data | `device/screens/panels/*.py` (active) |
| `device/ui/panels/base.py` | BasePanel for dummy panels | `device/screens/base.py` |
| `device/ui/screen_manager.py` | Second ScreenManager, unused in production | `device/screens/manager.py` |

Also clean `main.py`:
- Remove `voice_pipeline` import and instantiation
- Remove stash to `screen_mgr._voice_pipeline`

## 2. Font/Color Consolidation

**Current state:** Three font loading systems, three color palettes, two font size registries.

**Target state:** `display/tokens.py` is the single source for constants, `display/theme.py` is the single source for font loading.

### Fonts
- Merge `ui/font_sizes.py` named constants into `display/tokens.py` `FONT_SIZES` dict
- Merge `ui/fonts.py` `get_font()` into `display/theme.py` `load_ui_font()`
- Update all `ui/` components to import from `display/theme.py`
- Delete `ui/fonts.py` and `ui/font_sizes.py`
- Fix font filename inconsistency (`PressStart2P-Regular.ttf` vs `PressStart2P.ttf`)

### Colors
- Merge grays from `ui/panels/base.py` (12 grays) and `ui/screen_manager.py` (3 grays) into `display/tokens.py`
- Only add grays actually used by surviving `ui/` components (sidebar, status_bar, hint_bar, composite_screen)
- Update imports in surviving files
- Dead grays from deleted `ui/panels/` don't need migration

## 3. Composite Screen Font Bump

- Increase sidebar item font from current size to next size up (~10pt → 12pt)
- Increase right-panel content font similarly
- Verify at new size: no text overlap, proper spacing, fits within 240px width
- Only affects `ui/composite_screen.py`, `ui/components/sidebar.py`

## 4. Shared Component Extraction

- Extract `render_panel_status_bar(surface, title, font, ...)` from duplicate implementations in `messages.py:200` and `mail.py:184`
- Place in `display/status_bar.py` or extend existing `ui/components/status_bar.py`
- Panels delegate to shared function

---

## Risk Assessment

**Low risk:** We're only deleting confirmed-unused code, merging constants, and bumping font sizes. No screen lifecycle changes, no new features, no behavior changes.

**Testing:** Existing tests cover chat, typewriter, safe area, action bar, settings. The deleted `ui/panels/` have zero tests (they're dummy panels). Font/color changes are verified by visual inspection on device.

## Success Criteria

- `device/ui/panels/` directory deleted
- Dead hardware/audio files deleted
- Single font loading system (`display/theme.py`)
- Single color palette (`display/tokens.py`)
- `ui/fonts.py` and `ui/font_sizes.py` deleted
- Composite screen renders with larger fonts
- All existing tests pass
- Device boots and renders correctly
