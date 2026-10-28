# This file was generated with assistance from Qwen AI
# Related project: https://github.com/snoack/viewpie
# SPDX-License-Identifier: GPL-3.0-or-later
"""Validation of labelled blocks inside a normalized square grid.

Rules enforced here (see README §"Критические правила валидации"):

* every label must occupy a perfect rectangle — the bounding box area has
  to equal the number of cells carrying that label;
* blocks must stay inside the grid;
* blocks must not overlap (structurally impossible for labels in one
  matrix, but explicit rectangles built by other modules are checked).
"""

from __future__ import annotations

import logging

from .exceptions import InvalidBlockError, OutOfBoundsError
from .models import EMPTY_CELL, Block

logger = logging.getLogger(__name__)


def _collect_positions(matrix: list[list[str]], size: int) -> dict[str, list[tuple[int, int]]]:
    """Group cell coordinates ``(x, y)`` by label.

    Args:
        matrix: Square N×N matrix of labels.
        size: Expected N.

    Returns:
        Mapping ``label -> [(x, y), ...]`` excluding empty cells.

    Raises:
        OutOfBoundsError: If any row is shorter/longer than ``size``.
    """
    if len(matrix) != size:
        raise OutOfBoundsError(
            f"matrix has {len(matrix)} rows, expected {size}",
            details={"rows": len(matrix), "expected": size},
        )
    positions: dict[str, list[tuple[int, int]]] = {}
    for y, row in enumerate(matrix):
        if len(row) != size:
            raise OutOfBoundsError(
                f"row {y} has width {len(row)}, expected {size}",
                details={"row": y, "width": len(row), "expected": size},
            )
        for x, cell in enumerate(row):
            if cell == EMPTY_CELL:
                continue
            positions.setdefault(cell, []).append((x, y))
    return positions


def validate_blocks(matrix: list[list[str]], size: int) -> dict[str, Block]:
    """Extract and validate rectangular blocks from a square matrix.

    For each distinct label the bounding box is computed; a block is valid
    only when ``expected_area == actual_area`` (a filled rectangle).

    Args:
        matrix: Normalized N×N matrix of labels.
        size: Grid dimension N.

    Returns:
        Dictionary ``{label: Block}`` for all valid blocks.

    Raises:
        InvalidBlockError: If some label is not a rectangle
            (L-shape, hole, protrusion…).
        OutOfBoundsError: If the matrix itself is not N×N.
    """
    positions = _collect_positions(matrix, size)
    blocks: dict[str, Block] = {}

    for label, cells in sorted(positions.items(), key=lambda kv: (kv[1][0][1], kv[1][0][0])):
        xs = [p[0] for p in cells]
        ys = [p[1] for p in cells]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        width = max_x - min_x + 1
        height = max_y - min_y + 1
        expected_area = width * height
        actual_area = len(cells)

        if expected_area != actual_area:
            raise InvalidBlockError(
                f"блок '{label}' не прямоугольник",
                details={
                    "label": label,
                    "bounding_box": {
                        "left": min_x,
                        "top": min_y,
                        "right": max_x,
                        "bottom": max_y,
                    },
                    "expected_area": expected_area,
                    "actual_area": actual_area,
                    "cells": [{"x": x, "y": y} for x, y in cells],
                },
            )

        blocks[label] = Block(
            label=label,
            camera_name=label,
            top=min_y,
            left=min_x,
            width=width,
            height=height,
        )

    logger.debug("Validated %d blocks in %dx%d grid", len(blocks), size, size)
    return blocks


def check_no_overlap(blocks: dict[str, Block], size: int) -> None:
    """Verify that explicit rectangles neither overlap nor exceed the grid.

    Args:
        blocks: Mapping of label → rectangular block.
        size: Grid dimension N (bounds are ``0..N-1``).

    Raises:
        OutOfBoundsError: On the first overlapping or out-of-bounds pair.
    """
    items = list(blocks.values())
    for block in items:
        if block.top < 0 or block.left < 0 or block.bottom >= size or block.right >= size:
            raise OutOfBoundsError(
                f"блок '{block.label}' выходит за границы сетки {size}x{size}",
                details={
                    "label": block.label,
                    "top": block.top,
                    "left": block.left,
                    "bottom": block.bottom,
                    "right": block.right,
                    "grid_size": size,
                },
            )

    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            a, b = items[i], items[j]
            if a.left <= b.right and b.left <= a.right and a.top <= b.bottom and b.top <= a.bottom:
                raise OutOfBoundsError(
                    f"блоки '{a.label}' и '{b.label}' пересекаются",
                    details={"first": a.label, "second": b.label},
                )


def validate_layout(matrix: list[list[str]], size: int) -> dict[str, Block]:
    """Full validation pipeline: rectangularity + bounds + overlaps.

    Convenience wrapper used by the API layer.
    """
    blocks = validate_blocks(matrix, size)
    check_no_overlap(blocks, size)
    return blocks
