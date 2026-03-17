"""BITOS Markdown Viewer Panel — display file content with pagination and typewriter."""
from __future__ import annotations

import pygame

from screens.base import BaseScreen
from display.pagination import split_into_pages, wrap_text
from display.typewriter import TypewriterRenderer, TypewriterConfig
from display.tokens import (
    BLACK,
    WHITE,
    DIM1,
    DIM2,
    DIM3,
    HAIRLINE,
    PHYSICAL_W,
    PHYSICAL_H,
    STATUS_BAR_H,
    SAFE_INSET,
)
from display.theme import merge_runtime_ui_settings, load_ui_font, ui_line_height
from display.markdown import (
    parse_line,
    wrap_markdown_text,
    STYLE_BOLD,
    STYLE_ITALIC,
    STYLE_CODE,
    STYLE_HEADER,
    STYLE_BULLET,
)


class MarkdownViewerPanel(BaseScreen):
    """Display a parsed markdown file with pagination and typewriter animation."""

    # Markdown style -> color mapping (same as chat panel)
    _MD_COLORS = {
        STYLE_BOLD: WHITE,
        STYLE_ITALIC: DIM3,
        STYLE_CODE: DIM2,
        STYLE_HEADER: WHITE,
        STYLE_BULLET: DIM1,
        "normal": WHITE,
    }

    def __init__(self, file_data: dict, client=None, on_back=None, on_agent_query=None, ui_settings=None, repository=None):
        """
        Args:
            file_data: dict with 'name', 'id', and either 'content' or 'pages'.
            client: BackendClient (used for file query).
            on_back: Callback when user navigates back.
            on_agent_query: Callback(context: str) to open agent overlay with document context.
            ui_settings: Runtime UI settings override.
            repository: DeviceRepository for text speed preference.
        """
        self._file_data = file_data
        self._client = client
        self._on_back = on_back
        self._on_agent_query = on_agent_query
        self._repository = repository
        self._ui_settings = merge_runtime_ui_settings(ui_settings)
        self._font = load_ui_font("body", self._ui_settings)
        self._font_small = load_ui_font("small", self._ui_settings)
        self._line_height = ui_line_height(self._font, self._ui_settings)

        # Pagination state
        self._pages: list[list[str]] = []
        self._current_page: int = 0
        self._page_revealed: list[bool] = []
        self._page_typewriter: TypewriterRenderer | None = None

        self._title = str(file_data.get("name", "file"))[:20]
        self._build_pages()

    def _build_pages(self) -> None:
        """Build paginated view from file data."""
        hint_px = 14
        available_h = PHYSICAL_H - (SAFE_INSET + STATUS_BAR_H + 2) - SAFE_INSET - hint_px
        lines_per_page = max(1, int(available_h / self._line_height) - 1)  # -1 for page indicator

        if "pages" in self._file_data and self._file_data["pages"]:
            # Pre-parsed pages (e.g. from LLM parse endpoint)
            raw_pages = self._file_data["pages"]
            self._pages = []
            for page_text in raw_pages:
                wrapped = wrap_markdown_text(str(page_text), self._font, PHYSICAL_W - SAFE_INSET * 2)
                # Truncate to fit one "page" worth of lines
                self._pages.append(wrapped[:lines_per_page])
        elif "content" in self._file_data:
            content = str(self._file_data.get("content", ""))
            wrapped = wrap_markdown_text(content, self._font, PHYSICAL_W - SAFE_INSET * 2)
            self._pages = split_into_pages(wrapped, lines_per_page)
        else:
            self._pages = [["(no content)"]]

        self._current_page = 0
        self._page_revealed = [False] * len(self._pages)
        self._page_typewriter = None
        self._start_page_typewriter()

    def _start_page_typewriter(self) -> None:
        """Start typewriter for current page if not yet revealed."""
        if not self._pages or self._current_page >= len(self._pages):
            self._page_typewriter = None
            return
        if self._current_page < len(self._page_revealed) and self._page_revealed[self._current_page]:
            self._page_typewriter = None
            return
        page_text = "\n".join(self._pages[self._current_page])
        speed = "slow"
        if self._repository:
            saved_speed = self._repository.get_setting("text_speed", None)
            if saved_speed:
                speed = str(saved_speed)
        if speed == "custom" and self._repository:
            config_raw = self._repository.get_setting("typewriter_config", "{}")
            config = TypewriterConfig.from_json(str(config_raw))
            self._page_typewriter = TypewriterRenderer(page_text, config=config)
        else:
            self._page_typewriter = TypewriterRenderer(page_text, speed=speed)

    def update(self, dt: float):
        if self._page_typewriter and not self._page_typewriter.finished:
            self._page_typewriter.update(dt)
        elif self._page_typewriter and self._page_typewriter.finished:
            if self._current_page < len(self._page_revealed):
                self._page_revealed[self._current_page] = True
            self._page_typewriter = None

    def handle_input(self, event: pygame.event.Event):
        _ = event

    def handle_action(self, action: str):
        if action == "LONG_PRESS":
            if self._on_back:
                self._on_back()
            return

        if action == "SHORT_PRESS" and len(self._pages) > 1:
            # Forward page navigation
            if self._current_page < len(self._page_revealed):
                self._page_revealed[self._current_page] = True
            self._page_typewriter = None
            self._current_page = (self._current_page + 1) % len(self._pages)
            self._start_page_typewriter()
            return

        if action == "TRIPLE_PRESS" and len(self._pages) > 1:
            # Backward page navigation
            if self._current_page < len(self._page_revealed):
                self._page_revealed[self._current_page] = True
            self._page_typewriter = None
            self._current_page = (self._current_page - 1) % len(self._pages)
            self._start_page_typewriter()
            return

        if action == "DOUBLE_PRESS":
            # Open agent overlay with document context
            if self._on_agent_query:
                context = f"Document: {self._title}"
                if "content" in self._file_data:
                    # Include a snippet for context
                    snippet = str(self._file_data["content"])[:500]
                    context = f"Document: {self._title}\n\n{snippet}"
                self._on_agent_query(context)
            return

    def render(self, surface: pygame.Surface):
        surface.fill(BLACK)

        # Status bar with file name
        title_surf = self._font_small.render(self._title.upper(), False, WHITE)
        surface.blit(title_surf, (SAFE_INSET, (STATUS_BAR_H - title_surf.get_height()) // 2))
        pygame.draw.line(surface, HAIRLINE, (0, STATUS_BAR_H - 1), (PHYSICAL_W, STATUS_BAR_H - 1))

        # Content area
        hint_px = 14
        msg_area_top = SAFE_INSET + STATUS_BAR_H + 2
        msg_area_bottom = PHYSICAL_H - SAFE_INSET - hint_px
        y = msg_area_top

        # Page text
        page = self._pages[self._current_page] if self._current_page < len(self._pages) else []

        if self._page_typewriter and not self._page_typewriter.finished:
            visible = self._page_typewriter.get_visible_text()
            display_lines = wrap_markdown_text(visible, self._font, PHYSICAL_W - SAFE_INSET * 2)
        else:
            display_lines = page

        for line_text in display_lines:
            if y + self._line_height > msg_area_bottom - self._line_height:
                break
            self._render_styled_line(surface, line_text, SAFE_INSET, y)
            y += self._line_height

        # Page indicator (centered, small font) -- only if 2+ pages
        if len(self._pages) > 1:
            indicator = f"{self._current_page + 1}/{len(self._pages)}"
            ind_surf = self._font_small.render(indicator, False, DIM1)
            ind_x = (PHYSICAL_W - ind_surf.get_width()) // 2
            surface.blit(ind_surf, (ind_x, msg_area_bottom - self._line_height))

        # Hint bar
        hint_y = PHYSICAL_H - SAFE_INSET - hint_px
        hint_center_y = hint_y + hint_px // 2
        self._render_hint_line(surface, hint_center_y)

    def _render_styled_line(self, surface: pygame.Surface, line_text: str, x: int, y: int) -> None:
        """Render a line with markdown styling (bold=bright, italic=dim, code=dimmer)."""
        segments = parse_line(line_text)
        cx = x
        for seg in segments:
            color = self._MD_COLORS.get(seg.style, WHITE)
            seg_surf = self._font.render(seg.text, False, color)
            surface.blit(seg_surf, (cx, y))
            cx += seg_surf.get_width()

    def _render_hint_line(self, surface: pygame.Surface, center_y: int):
        """Render compact gesture hint line."""
        items = []
        if len(self._pages) > 1:
            items.append(("tap", "next"))
            items.append(("triple", "prev"))
        items.append(("double", "ask"))
        items.append(("hold", "back"))

        rendered = []
        for icon_type, label in items:
            label_surf = self._font_small.render(label, False, DIM1)
            rendered.append((icon_type, label_surf))

        total_w = sum(8 + 2 + s.get_width() for _, s in rendered)
        spacing = max(4, (PHYSICAL_W - total_w) // (len(rendered) + 1))
        bx = spacing
        for icon_type, label_surf in rendered:
            ic = (bx + 3, center_y)
            if icon_type == "tap":
                pygame.draw.circle(surface, DIM1, ic, 2, 1)
            elif icon_type == "double":
                pygame.draw.circle(surface, DIM1, ic, 2, 1)
                pygame.draw.circle(surface, DIM1, ic, 1, 1)
            elif icon_type == "triple":
                for offset in (-3, 0, 3):
                    pygame.draw.circle(surface, DIM1, (ic[0] + offset, ic[1]), 2, 1)
            elif icon_type == "hold":
                pygame.draw.circle(surface, DIM1, ic, 2, 0)
            surface.blit(label_surf, (bx + 8, center_y - label_surf.get_height() // 2))
            bx += 8 + label_surf.get_width() + spacing
