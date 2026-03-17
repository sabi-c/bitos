"""Standalone 2D Simplex Noise implementation.

Provides organic, smooth pseudo-random values for blob movement.
Based on the simplex noise algorithm by Ken Perlin.
Pure Python, no dependencies beyond stdlib.
"""

import math
import random

# Permutation table (doubled for wrapping)
_PERM_BASE = list(range(256))
random.seed(42)  # Deterministic for reproducibility
random.shuffle(_PERM_BASE)
_PERM = _PERM_BASE * 2

# Gradient vectors for 2D
_GRAD2 = [
    (1, 1), (-1, 1), (1, -1), (-1, -1),
    (1, 0), (-1, 0), (0, 1), (0, -1),
]

_F2 = 0.5 * (math.sqrt(3.0) - 1.0)
_G2 = (3.0 - math.sqrt(3.0)) / 6.0


def _dot2(g, x, y):
    return g[0] * x + g[1] * y


def noise2d(x: float, y: float) -> float:
    """Compute 2D simplex noise at coordinates (x, y).

    Returns a float in the range approximately -1.0 to 1.0.
    """
    s = (x + y) * _F2
    i = math.floor(x + s)
    j = math.floor(y + s)

    t = (i + j) * _G2
    x0 = x - (i - t)
    y0 = y - (j - t)

    if x0 > y0:
        i1, j1 = 1, 0
    else:
        i1, j1 = 0, 1

    x1 = x0 - i1 + _G2
    y1 = y0 - j1 + _G2
    x2 = x0 - 1.0 + 2.0 * _G2
    y2 = y0 - 1.0 + 2.0 * _G2

    ii = i & 255
    jj = j & 255

    gi0 = _PERM[ii + _PERM[jj]] % 8
    gi1 = _PERM[ii + i1 + _PERM[jj + j1]] % 8
    gi2 = _PERM[ii + 1 + _PERM[jj + 1]] % 8

    n0 = n1 = n2 = 0.0

    t0 = 0.5 - x0 * x0 - y0 * y0
    if t0 >= 0:
        t0 *= t0
        n0 = t0 * t0 * _dot2(_GRAD2[gi0], x0, y0)

    t1 = 0.5 - x1 * x1 - y1 * y1
    if t1 >= 0:
        t1 *= t1
        n1 = t1 * t1 * _dot2(_GRAD2[gi1], x1, y1)

    t2 = 0.5 - x2 * x2 - y2 * y2
    if t2 >= 0:
        t2 *= t2
        n2 = t2 * t2 * _dot2(_GRAD2[gi2], x2, y2)

    return 70.0 * (n0 + n1 + n2)
