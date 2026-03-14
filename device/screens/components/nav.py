from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class NavItem:
    """Declarative nav entry used by button-first menu screens."""

    key: str
    label: str
    status: str = ""
    enabled: bool = True
    action: Callable[[], None] | None = None


class VerticalNavController:
    """Keeps focus state and activation behavior for vertical nav menus."""

    def __init__(self, items: list[NavItem], start_index: int = 0):
        self._items = list(items)
        self._focus_index = 0
        if self._items:
            self._focus_index = start_index % len(self._items)

    @property
    def items(self) -> list[NavItem]:
        return self._items

    @property
    def focus_index(self) -> int:
        return self._focus_index

    @property
    def focused_item(self) -> NavItem | None:
        if not self._items:
            return None
        return self._items[self._focus_index]

    def move(self, direction: int) -> None:
        if not self._items:
            return
        self._focus_index = (self._focus_index + direction) % len(self._items)

    def activate_focused(self) -> bool:
        item = self.focused_item
        if item is None or not item.enabled or item.action is None:
            return False
        item.action()
        return True
