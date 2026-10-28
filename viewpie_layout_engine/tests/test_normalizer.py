# This file was generated with assistance from Qwen AI
# Related project: https://github.com/snoack/viewpie
# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for viewpie_layout_engine.normalizer."""

from __future__ import annotations

import pytest

from viewpie_layout_engine.exceptions import NonSquareError
from viewpie_layout_engine.normalizer import fits_square, normalize_to_square


def test_square_3x3_unchanged() -> None:
    """An already valid square passes through untouched."""
    matrix = [["1", "2", "3"], ["4", "5", "6"], ["7", "8", "9"]]
    norm, n = normalize_to_square(matrix, 3, 3)
    assert n == 3
    assert norm == matrix


def test_non_square_2x4_padded_to_4x4() -> None:
    """The documented example: 2×4 grows to 4×4 filled with dots below."""
    matrix = [["1", "1", "2", "3"], ["4", "5", "6", "7"]]
    norm, n = normalize_to_square(matrix, 2, 4)
    assert n == 4
    assert norm == [
        ["1", "1", "2", "3"],
        ["4", "5", "6", "7"],
        [".", ".", ".", "."],
        [".", ".", ".", "."],
    ]


def test_1x1_grows_to_minimum_3x3() -> None:
    """viewpie forbids grids smaller than 3×3 — normalizer pads them."""
    norm, n = normalize_to_square([["x"]], 1, 1)
    assert n == 3
    assert norm[0] == ["x", ".", "."]
    assert norm[2] == [".", ".", "."]


def test_wide_short_grid_pads_rows_and_columns() -> None:
    """1×5 row becomes 5×5 with right-padding on short rows too."""
    norm, n = normalize_to_square([["a", "b"]], 1, 2)
    assert n == 3  # max(1, 2, 3) == 3
    assert norm == [["a", "b", "."], [".", ".", "."], [".", ".", "."]]


def test_9x9_raises_nonsquare() -> None:
    """Anything beyond 8×8 cannot be normalized."""
    matrix = [["."] * 9 for _ in range(9)]
    with pytest.raises(NonSquareError) as exc_info:
        normalize_to_square(matrix, 9, 9)
    assert exc_info.value.details["required_n"] == 9


def test_8x8_is_allowed() -> None:
    """Boundary: exactly 8×8 is still valid."""
    matrix = [["c"] * 8 for _ in range(8)]
    norm, n = normalize_to_square(matrix, 8, 8)
    assert n == 8
    assert len(norm) == 8


def test_original_matrix_not_mutated() -> None:
    """Normalization must not modify the caller's matrix."""
    matrix = [["1", "2"], ["3", "4"]]
    snapshot = [row[:] for row in matrix]
    normalize_to_square(matrix, 2, 2)
    assert matrix == snapshot


def test_fits_square_helper() -> None:
    """Boolean predicate mirrors the exception behaviour."""
    assert fits_square(2, 4)
    assert fits_square(8, 3)
    assert not fits_square(9, 2)
    assert not fits_square(8, 9)
