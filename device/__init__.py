"""BITOS device package bootstrap.

Ensures legacy intra-package imports like `from display...` resolve when
`device.main` is imported as a package module from repository root.
"""
from __future__ import annotations

import sys
from pathlib import Path

_pkg_dir = str(Path(__file__).resolve().parent)
if _pkg_dir not in sys.path:
    sys.path.insert(0, _pkg_dir)
