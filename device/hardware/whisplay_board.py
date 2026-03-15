"""Singleton accessor for WhisPlayBoard."""

from __future__ import annotations

import logging
import os
import sys
from typing import Optional

logger = logging.getLogger(__name__)

_instance = None


def get_board() -> Optional[object]:
    """Return a singleton WhisPlayBoard instance or None on initialization failure."""
    global _instance
    if _instance is not None:
        return _instance

    try:
        sys.path.insert(0, os.environ.get("WHISPLAY_DRIVER_PATH", "/home/pi/Whisplay/Driver"))
        from WhisPlay import WhisPlayBoard

        _instance = WhisPlayBoard()
        return _instance
    except Exception as exc:
        logger.exception("whisplay_board_init_failed: %s", exc)
        return None
