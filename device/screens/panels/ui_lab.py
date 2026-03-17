"""BITOS UI Lab panel — test/demo page for all UI widgets and overlays."""
from __future__ import annotations

from typing import Callable

import pygame

from display.theme import load_ui_font, merge_runtime_ui_settings
from display.tokens import (
    BLACK, DIM2, DIM3, HAIRLINE, PHYSICAL_H, PHYSICAL_W, WHITE,
    STATUS_BAR_H, ROW_H_MIN,
)
from screens.base import BaseScreen
from screens.components import (
    CheckmarkAnimation, NavItem, OnScreenKeyboard, ToastAnimation,
    VerticalNavController, Widget, WidgetStrip,
)


class AnimationOverlay:
    """Wraps a CheckmarkAnimation or ToastAnimation as a screen manager overlay."""

    def __init__(self, animation):
        self._anim = animation

    @property
    def dismissed(self) -> bool:
        return self._anim.finished

    def tick(self, dt_ms: int) -> bool:
        return self._anim.tick(dt_ms)

    def handle_action(self, action: str) -> bool:
        return False  # don't consume actions

    def render(self, surface: pygame.Surface) -> None:
        self._anim.render(surface)


class UILabPanel(BaseScreen):
    """Vertical nav list where each item triggers a UI component demo."""

    _owns_status_bar = True

    def __init__(
        self,
        on_back: Callable[[], None] | None = None,
        on_show_overlay: Callable | None = None,
        ui_settings: dict | None = None,
    ):
        self._on_back = on_back
        self._on_show_overlay = on_show_overlay
        self._ui_settings = merge_runtime_ui_settings(ui_settings)
        self._font_body = load_ui_font("body", self._ui_settings)
        self._font_small = load_ui_font("small", self._ui_settings)
        self._font_hint = load_ui_font("hint", self._ui_settings)

        self._keyboard_result: str = ""
        self._showing_widgets = False
        self._demo_widget_strip: WidgetStrip | None = None

        self._nav = VerticalNavController([
            NavItem(key="keyboard", label="KEYBOARD", status="TYPE", action=self._demo_keyboard),
            NavItem(key="confirm", label="CONFIRM", status="DLG", action=self._demo_confirm),
            NavItem(key="permission", label="PERMISSION", status="DLG", action=self._demo_permission),
            NavItem(key="check_anim", label="CHECK ANIM", status="FX", action=self._demo_checkmark),
            NavItem(key="toast_ok", label="TOAST OK", status="FX", action=self._demo_toast_ok),
            NavItem(key="toast_warn", label="TOAST WARN", status="FX", action=self._demo_toast_warn),
            NavItem(key="toast_err", label="TOAST ERR", status="FX", action=self._demo_toast_err),
            NavItem(key="widgets", label="WIDGETS", status="UI", action=self._demo_widgets),
        ])

    def handle_action(self, action: str):
        if action == "SHORT_PRESS":
            self._nav.move(1)
        elif action == "DOUBLE_PRESS":
            self._nav.activate_focused()
        elif action == "LONG_PRESS":
            if self._showing_widgets:
                self._showing_widgets = False
                self._demo_widget_strip = None
            elif self._on_back:
                self._on_back()
        elif action == "TRIPLE_PRESS":
            self._nav.move(-1)

    def handle_input(self, event: pygame.event.Event):
        if event.type != pygame.KEYDOWN:
            return
        if event.key in (pygame.K_RETURN, pygame.K_SPACE):
            self._nav.activate_focused()
        elif event.key in (pygame.K_DOWN, pygame.K_j):
            self._nav.move(1)
        elif event.key in (pygame.K_UP, pygame.K_k):
            self._nav.move(-1)

    def update(self, dt: float):
        pass

    def render(self, surface: pygame.Surface):
        surface.fill(BLACK)

        # Status bar
        pygame.draw.rect(surface, WHITE, pygame.Rect(0, 0, PHYSICAL_W, STATUS_BAR_H))
        title = self._font_small.render("UI LAB", False, BLACK)
        surface.blit(title, (6, (STATUS_BAR_H - title.get_height()) // 2))

        # If showing demo widget strip, render that instead of nav
        if self._showing_widgets and self._demo_widget_strip is not None:
            widget_fonts = {"hint": self._font_hint, "small": self._font_small}
            self._demo_widget_strip.render(surface, STATUS_BAR_H + 12, PHYSICAL_W, 50, fonts=widget_fonts)
            hint = self._font_hint.render("LONG:BACK", False, DIM3)
            surface.blit(hint, ((PHYSICAL_W - hint.get_width()) // 2, STATUS_BAR_H + 70))
            return

        # Keyboard result display
        result_y = STATUS_BAR_H + 2
        if self._keyboard_result:
            result_text = self._font_hint.render(f"KB: {self._keyboard_result[:20]}", False, DIM2)
            surface.blit(result_text, (6, result_y))
            result_y += result_text.get_height() + 4

        # Nav rows
        y = result_y + 4
        for idx, item in enumerate(self._nav.items):
            if y + ROW_H_MIN > PHYSICAL_H - 14:
                break
            focused = idx == self._nav.focus_index
            if focused:
                pygame.draw.rect(surface, WHITE, pygame.Rect(0, y, PHYSICAL_W, ROW_H_MIN))
            row_color = BLACK if focused else WHITE
            status_color = BLACK if focused else DIM2
            indicator = "> " if focused else "- "
            row = self._font_body.render(indicator + item.label, False, row_color)
            status = self._font_small.render(item.status, False, status_color)
            text_y = y + (ROW_H_MIN - row.get_height()) // 2
            surface.blit(row, (4, text_y))
            surface.blit(status, (PHYSICAL_W - status.get_width() - 8, text_y + 2))
            if not focused:
                pygame.draw.line(surface, HAIRLINE, (0, y + ROW_H_MIN - 1), (PHYSICAL_W, y + ROW_H_MIN - 1))
            y += ROW_H_MIN

        # Key hint bar
        hint = self._font_hint.render("SHORT:NEXT \u00b7 DBL:SEL \u00b7 LONG:BACK", False, DIM3)
        surface.blit(hint, ((PHYSICAL_W - hint.get_width()) // 2, PHYSICAL_H - hint.get_height() - 2))

    # ── Demo triggers ─────────────────────────────────────────────

    def _push_overlay(self, overlay):
        if self._on_show_overlay:
            self._on_show_overlay(overlay)

    def _demo_keyboard(self):
        def _on_done(text: str):
            self._keyboard_result = text

        keyboard = OnScreenKeyboard(
            prompt="TYPE SOMETHING",
            on_done=_on_done,
            on_cancel=lambda: None,
        )
        self._push_overlay(keyboard)

    def _demo_confirm(self):
        from overlays.confirm_dialogue import ConfirmDialogue
        dialogue = ConfirmDialogue(
            title="DELETE NOTE?",
            message="This action cannot be undone.",
            confirm_label="DELETE",
            cancel_label="CANCEL",
            destructive=True,
        )
        self._push_overlay(dialogue)

    def _demo_permission(self):
        from overlays.approval_overlay import ApprovalOverlay
        overlay = ApprovalOverlay(
            request_id="ui-lab-test",
            prompt="AI CHAT WANTS TO ACCESS LOCATION",
            options=["DENY", "ALLOW"],
            category="permission",
        )
        self._push_overlay(overlay)

    def _demo_checkmark(self):
        anim = CheckmarkAnimation(text="TASK DONE")
        self._push_overlay(AnimationOverlay(anim))

    def _demo_toast_ok(self):
        anim = ToastAnimation(text="NOTE SAVED", style="success")
        self._push_overlay(AnimationOverlay(anim))

    def _demo_toast_warn(self):
        anim = ToastAnimation(text="CONTEXT AT 85%", style="warning")
        self._push_overlay(AnimationOverlay(anim))

    def _demo_toast_err(self):
        anim = ToastAnimation(text="CONNECTION FAILED", style="error")
        self._push_overlay(AnimationOverlay(anim))

    def _demo_widgets(self):
        self._showing_widgets = True
        self._demo_widget_strip = WidgetStrip([
            Widget(key="demo", label="DEMO", value="42"),
            Widget(key="test", label="TEST", value="OK"),
            Widget(key="lab", label="LAB", value="3.14"),
        ])
