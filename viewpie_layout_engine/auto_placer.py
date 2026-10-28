# This file was generated with assistance from Qwen AI
# Related project: https://github.com/snoack/viewpie
# SPDX-License-Identifier: GPL-3.0-or-later
"""Automatic placement of rectangular cameras into a square grid.

Strategy: greedy top-down / left-to-right shelf packing. Cameras are
sorted by area (descending); each camera is placed at the first free
position where its rectangle fits without overlapping occupied cells.
Leftover cells become empty ``.`` cells, which viewpie renders as
background — so any combination that *fits* produces a valid layout.
"""

from __future__ import annotations

import logging
import math
from typing import Optional

from .exceptions import InvalidBlockError, TooManyCamerasError
from .models import EMPTY_CELL, Block, CameraSpec, MAX_GRID_SIZE, MIN_GRID_SIZE
from .parser import render_matrix
from .validator import validate_blocks

logger = logging.getLogger(__name__)


def minimal_grid_size(total_area: int) -> int:
    """Smallest N ∈ {3..8} whose N×N grid can hold ``total_area`` cells.

    Args:
        total_area: Sum of areas of all cameras to place.

    Returns:
        Grid dimension N.

    Raises:
        TooManyCamerasError: If even 8×8 cannot hold the cameras.
    """
    if total_area <= 0:
        return MIN_GRID_SIZE
    n = max(MIN_GRID_SIZE, math.ceil(math.sqrt(total_area)))
    # A single camera wider/taller than sqrt(area) may still need a bigger N.
    if n * n < total_area:  # pragma: no cover - defensive
        n += 1
    if n > MAX_GRID_SIZE:
        raise TooManyCamerasError(
            f"cameras require a grid larger than {MAX_GRID_SIZE}x{MAX_GRID_SIZE}",
            details={"total_area": total_area, "required_n": n},
        )
    return n


def can_place(grid: list[list[str]], x: int, y: int, w: int, h: int) -> bool:
    """Return True if a ``w×h`` rectangle fits at ``(x, y)`` in ``grid``.

    "Fits" means fully inside the grid and every covered cell is empty.
    """
    size = len(grid)
    if x < 0 or y < 0 or w < 1 or h < 1:
        return False
    if x + w > size or y + h > size:
        return False
    return all(grid[yy][xx] == EMPTY_CELL for yy in range(y, y + h) for xx in range(x, x + w))


def place_block(grid: list[list[str]], x: int, y: int, w: int, h: int, label: str) -> None:
    """Write ``label`` into a ``w×h`` rectangle starting at ``(x, y)``.

    Raises:
        ValueError: If the rectangle does not fit (see :func:`can_place`).
    """
    if not can_place(grid, x, y, w, h):
        raise ValueError(f"cannot place '{label}' ({w}x{h}) at ({x}, {y})")
    for yy in range(y, y + h):
        for xx in range(x, x + w):
            grid[yy][xx] = label


def _find_position(grid: list[list[str]], w: int, h: int) -> Optional[tuple[int, int]]:
    """First free top-left position for a ``w×h`` block (row-major scan)."""
    size = len(grid)
    for y in range(size - h + 1):
        for x in range(size - w + 1):
            if can_place(grid, x, y, w, h):
                return x, y
    return None


def auto_place_cameras(
    cameras: list[CameraSpec], grid_size: Optional[int] = None
) -> tuple[list[list[str]], int, list[Block]]:
    """Pack cameras into the smallest (or requested) square grid.

    Args:
        cameras: Camera specifications with their rectangles.
        grid_size: Explicit N (3..8). When ``None`` the minimal feasible
            square is chosen automatically.

    Returns:
        Tuple ``(matrix, N, blocks)`` — the placed grid, its dimension and
        the resulting validated blocks.

    Raises:
        TooManyCamerasError: If some camera cannot be placed within N×N,
            or N exceeds limits, or individual camera exceeds the grid.
        InvalidBlockError: Internal invariant violation (should not happen).
    """
    if not cameras:
        raise TooManyCamerasError("no cameras to place", details={"count": 0})

    total_area = sum(c.area for c in cameras)

    if grid_size is None:
        n = minimal_grid_size(total_area)
        # Individual camera dimensions may force a bigger grid than area alone.
        widest = max(max(c.width, c.height) for c in cameras)
        n = max(n, widest)
        if n > MAX_GRID_SIZE:
            raise TooManyCamerasError(
                f"cameras do not fit into maximum grid {MAX_GRID_SIZE}x{MAX_GRID_SIZE}",
                details={"required_n": n, "total_area": total_area},
            )
    else:
        n = grid_size
        if n < MIN_GRID_SIZE or n > MAX_GRID_SIZE:
            raise TooManyCamerasError(
                f"requested grid {n}x{n} is outside allowed range "
                f"{MIN_GRID_SIZE}..{MAX_GRID_SIZE}",
                details={"requested": n},
            )
        if total_area > n * n:
            raise TooManyCamerasError(
                f"cameras occupy {total_area} cells but grid {n}x{n} has only {n * n}",
                details={"total_area": total_area, "capacity": n * n},
            )

    grid: list[list[str]] = [[EMPTY_CELL] * n for _ in range(n)]

    # Greedy: largest area first; stable sort keeps user order for ties.
    ordered = sorted(cameras, key=lambda c: (-c.area, -c.width))

    for spec in ordered:
        pos = _find_position(grid, spec.width, spec.height)
        if pos is None:
            raise TooManyCamerasError(
                f"камера '{spec.name}' ({spec.width}x{spec.height}) "
                f"не помещается в сетку {n}x{n}",
                details={
                    "camera": spec.name,
                    "width": spec.width,
                    "height": spec.height,
                    "grid_size": n,
                    "total_area": total_area,
                },
            )
        place_block(grid, pos[0], pos[1], spec.width, spec.height, spec.name)

    blocks = validate_blocks(grid, n)  # invariant check: placement is rectangular
    logger.info("Auto-placed %d cameras into %dx%d grid", len(cameras), n, n)
    return grid, n, list(blocks.values())


def auto_place_to_text(cameras: list[CameraSpec], grid_size: Optional[int] = None) -> tuple[str, int]:
    """Convenience wrapper returning ``(layout_text, N)``."""
    grid, n, _blocks = auto_place_cameras(cameras, grid_size)
    return render_matrix(grid), n
