"""Root conftest — prevent namespace collisions between device/ and server/.

Both trees share package names (integrations, notifications, etc.).  When
pytest collects all tests, whichever side is imported first wins the
`sys.modules` cache.  This conftest purges stale entries between test modules
so each test file gets the correct package from its own sys.path insert.
"""

import sys


# Packages that exist under both device/ and server/
_SHARED_NAMES = ("integrations", "notifications", "storage", "client")


def pytest_runtest_setup(item):
    """Before each test, clear any cached shared packages so that the test
    module's own sys.path insert takes effect."""
    for name in _SHARED_NAMES:
        if name in sys.modules:
            # Check whether the cached module came from the *other* tree
            # relative to what this test needs.  Rather than trying to guess,
            # we simply remove the cache — the next import will re-resolve.
            sys.modules.pop(name, None)
        # Also drop sub-modules (e.g. integrations.bluebubbles_adapter)
        for key in list(sys.modules):
            if key.startswith(name + "."):
                sys.modules.pop(key, None)
