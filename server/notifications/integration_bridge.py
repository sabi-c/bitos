"""Bridges existing integrations into the NotificationDispatcher."""
import asyncio
import logging

from .dispatcher import NotificationDispatcher
from .models import NotificationEvent, Priority, CATEGORY_DEFAULTS

log = logging.getLogger(__name__)


class IntegrationBridge:
    """Polls integration adapters and dispatches new items as notifications."""

    def __init__(self, dispatcher: NotificationDispatcher, adapters: dict):
        self._dispatcher = dispatcher
        self._adapters = adapters  # {"bluebubbles": adapter, "gmail": adapter, ...}
        self._seen_ids: set[str] = set()

    async def poll_once(self) -> int:
        """Poll all integrations, dispatch new items. Returns count."""
        total = 0
        for name, adapter in self._adapters.items():
            try:
                items = await self._fetch(name, adapter)
            except Exception:
                log.exception("integration_bridge: failed to fetch %s", name)
                continue
            for item in items:
                key = f"{name}:{item.get('source_id', '')}"
                if key in self._seen_ids:
                    continue
                self._seen_ids.add(key)
                if not item.get("unread", True):
                    continue
                category = self._map_category(name)
                evt = NotificationEvent(
                    type="notification",
                    priority=CATEGORY_DEFAULTS.get(category, Priority.NORMAL),
                    category=category,
                    payload={
                        "title": item.get("source", name),
                        "body": item.get("preview", "")[:60],
                        "app": name.title(),
                        "source_id": item.get("source_id", ""),
                        "icon": self._icon_for(category),
                    },
                )
                self._dispatcher.dispatch(evt)
                total += 1
        return total

    async def _fetch(self, name: str, adapter) -> list[dict]:
        if hasattr(adapter, "get_unread"):
            result = adapter.get_unread()
            if asyncio.iscoroutine(result):
                return await result
            return result
        return []

    @staticmethod
    def _map_category(name: str) -> str:
        return {
            "bluebubbles": "sms",
            "gmail": "mail",
            "calendar": "calendar",
            "vikunja": "task",
        }.get(name, "system")

    @staticmethod
    def _icon_for(category: str) -> str:
        return {
            "sms": "S",
            "mail": "M",
            "calendar": "E",
            "task": "#",
        }.get(category, "!")
