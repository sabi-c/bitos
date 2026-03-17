"""Shared pytest fixtures — flush font caches between test classes.

pygame.quit() invalidates all Font objects, but the module-level
_FONT_CACHE in display.theme keeps references to them.  Re-using a
dead Font object causes a segfault.  Clearing the caches after every
test class prevents cross-class contamination.
"""

import pytest


@pytest.fixture(autouse=True, scope="class")
def _flush_font_caches():
    """Yield to run the test class, then clear font caches."""
    yield
    try:
        from display.theme import flush_font_cache, get_font

        flush_font_cache()
        get_font.cache_clear()
    except Exception:
        pass
