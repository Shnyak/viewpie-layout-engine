# This file was generated with assistance from Qwen AI
# Related project: https://github.com/snoack/viewpie
# SPDX-License-Identifier: GPL-3.0-or-later
"""Parsing of textual layout grids into cell matrices.

A layout is a whitespace-separated grid of labels, e.g.::

    1 1 2 3
    1 1 4 5
    6 7 8 9
    10 11 12 13

Each token becomes one cell; ``.`` denotes an empty cell. Labels may be
arbitrary non-whitespace strings (camera names or numeric ids).
"""

from __future__ import annotations

import logging

from .exceptions import ValidationError
from .models import EMPTY_CELL

logger = logging.getLogger(__name__)


def parse_layout_text(text: str) -> tuple[list[list[str]], int, int]:
    """Parse a textual grid into a matrix of cell labels.

    Args:
        text: Raw layout text, rows separated by ``\\n``, cells by any run
            of whitespace. Trailing/leading blank lines are ignored.

    Returns:
        Tuple ``(matrix, height, width)`` where ``matrix`` is a list of
        rows of string labels.

    Raises:
        ValidationError: If the text is empty, has inconsistent row widths,
            or contains no rows at all.
    """
    if text is None or not text.strip():
        raise ValidationError("layout text is empty", details={"input": repr(text)})

    rows: list[list[str]] = []
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            # Skip fully blank lines (e.g. trailing newline).
            continue
        cells = stripped.split()
        rows.append(cells)

    if not rows:
        raise ValidationError("layout text contains no rows")

    widths = {len(r) for r in rows}
    if len(widths) != 1:
        bad = [
            {"row": idx + 1, "width": len(r)}
            for idx, r in enumerate(rows)
            if len(r) != max(widths)
        ]
        raise ValidationError(
            "layout rows have inconsistent widths",
            details={"widths": sorted(widths), "short_rows": bad},
        )

    width = len(rows[0])
    height = len(rows)

    # Sanity: every cell must be a non-empty token; '.' is reserved for empty.
    for y, row in enumerate(rows):
        for x, cell in enumerate(row):
            if cell == "":
                raise ValidationError(
                    f"empty cell at row {y + 1}, column {x + 1}",
                    details={"row": y, "col": x},
                )

    logger.debug("Parsed layout %dx%d with %d distinct labels",
                 height, width, len({c for r in rows for c in r}))
    return rows, height, width


def render_matrix(matrix: list[list[str]]) -> str:
    """Render a matrix back to canonical layout text (space separated).

    Args:
        matrix: Rows of cell labels.

    Returns:
        Multi-line string suitable for ``viewpie.yaml`` ``layout`` fields.
    """
    return "\n".join(" ".join(row) for row in matrix)


def count_empty_cells(matrix: list[list[str]]) -> int:
    """Return how many cells in the matrix are empty (``.``)."""
    return sum(1 for row in matrix for cell in row if cell == EMPTY_CELL)
