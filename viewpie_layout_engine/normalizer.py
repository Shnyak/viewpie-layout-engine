# This file was generated with assistance from Qwen AI
# Related project: https://github.com/snoack/viewpie
# SPDX-License-Identifier: GPL-3.0-or-later
"""Normalization of arbitrary grids into valid square N×N grids.

viewpie only accepts square layouts (3×3 … 8×8). The normalizer pads any
rectangular grid on the right and bottom with empty cells (``.``) until it
becomes a square; grids that cannot become squares (> 8×8) raise
:class:`NonSquareError`.
"""

from __future__ import annotations

import logging

from .exceptions import NonSquareError
from .models import EMPTY_CELL, MAX_GRID_SIZE, MIN_GRID_SIZE

logger = logging.getLogger(__name__)


def normalize_to_square(
    matrix: list[list[str]], height: int, width: int
) -> tuple[list[list[str]], int]:
    """Pad a rectangular matrix into the smallest valid square grid.

    Algorithm:
        1. ``N = max(height, width, MIN_GRID_SIZE)`` — squares smaller than
           3×3 are illegal in viewpie, so they grow to 3×3.
        2. If ``N > MAX_GRID_SIZE`` → :class:`NonSquareError`.
        3. Every row is padded on the right with ``.`` up to length ``N``.
        4. Missing rows are appended at the bottom as full ``.`` rows.

    Args:
        matrix: Rows of cell labels (as produced by the parser).
        height: Number of rows in ``matrix``.
        width: Number of columns in ``matrix``.

    Returns:
        Tuple ``(normalized_matrix, N)`` where the matrix is N×N.

    Raises:
        NonSquareError: If the resulting square would exceed 8×8.
    """
    n = max(height, width, MIN_GRID_SIZE)
    if n > MAX_GRID_SIZE:
        raise NonSquareError(
            f"grid {height}x{width} cannot be normalized: "
            f"resulting square {n}x{n} exceeds maximum {MAX_GRID_SIZE}x{MAX_GRID_SIZE}",
            details={"height": height, "width": width, "required_n": n},
        )

    normalized: list[list[str]] = []
    for row in matrix:
        padded = list(row) + [EMPTY_CELL] * (n - len(row))
        normalized.append(padded[:n])

    while len(normalized) < n:
        normalized.append([EMPTY_CELL] * n)

    logger.debug("Normalized %dx%d grid to %dx%d", height, width, n, n)
    return normalized, n


def fits_square(height: int, width: int) -> bool:
    """Return True if a grid of given dimensions can be normalized."""
    return max(height, width, MIN_GRID_SIZE) <= MAX_GRID_SIZE
