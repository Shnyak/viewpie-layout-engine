# This file was generated with assistance from Qwen AI
# Related project: https://github.com/snoack/viewpie
# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for viewpie_layout_engine.validator."""

from __future__ import annotations

import pytest

from viewpie_layout_engine.exceptions import InvalidBlockError, OutOfBoundsError
from viewpie_layout_engine.models import Block
from viewpie_layout_engine.validator import (
    check_no_overlap,
    validate_blocks,
    validate_layout,
)


def test_all_1x1_blocks_succeed() -> None:
    """A full 3×3 grid of single-cell blocks validates cleanly."""
    matrix = [["1", "2", "3"], ["4", "5", "6"], ["7", "8", "9"]]
    blocks = validate_blocks(matrix, 3)
    assert len(blocks) == 9
    b = blocks["5"]
    assert (b.top, b.left, b.width, b.height) == (1, 1, 1, 1)


def test_2x2_block_detected() -> None:
    """The documented 4×4 example yields one 2×2 block plus singles."""
    matrix = [
        ["1", "1", "2", "3"],
        ["1", "1", "4", "5"],
        ["6", "7", "8", "9"],
        ["10", "11", "12", "13"],
    ]
    blocks = validate_blocks(matrix, 4)
    assert len(blocks) == 13
    cam1 = blocks["1"]
    assert cam1.top == 0 and cam1.left == 0 and cam1.width == 2 and cam1.height == 2
    assert cam1.area == 4


def test_l_shape_raises_invalid_block() -> None:
    """Documented invalid example: label '1' forms an L → error."""
    matrix = [["1", "1", "2"], ["1", "2", "2"], ["3", "4", "5"]]
    with pytest.raises(InvalidBlockError) as exc_info:
        validate_blocks(matrix, 3)
    assert "не прямоугольник" in exc_info.value.message
    assert exc_info.value.details["label"] == "1"
    assert exc_info.value.details["expected_area"] == 4
    assert exc_info.value.details["actual_area"] == 3


def test_hole_inside_block_raises() -> None:
    """A 3×3 label with a hole in the middle is not a rectangle."""
    matrix = [
        ["a", "a", "a"],
        ["a", ".", "a"],
        ["a", "a", "a"],
    ]
    with pytest.raises(InvalidBlockError):
        validate_blocks(matrix, 3)


def test_empty_cells_allowed() -> None:
    """Dots are ignored by the validator (background cells)."""
    matrix = [[".", ".", "."], [".", "x", "."], [".", ".", "."]]
    blocks = validate_blocks(matrix, 3)
    assert set(blocks) == {"x"}


def test_matrix_wrong_row_count_raises_out_of_bounds() -> None:
    """validate_blocks refuses matrices that are not size×size."""
    matrix = [["1", "2"], ["3", "4"]]
    with pytest.raises(OutOfBoundsError):
        validate_blocks(matrix, 3)


def test_matrix_ragged_rows_raise_out_of_bounds() -> None:
    """A row shorter than N raises OutOfBoundsError."""
    matrix = [["1", "2", "3"], ["4", "5"], ["7", "8", "9"]]
    with pytest.raises(OutOfBoundsError):
        validate_blocks(matrix, 3)


def test_overlap_detected() -> None:
    """Two explicit rectangles covering the same cell → error."""
    blocks = {
        "a": Block(label="a", camera_name="a", top=0, left=0, width=2, height=2),
        "b": Block(label="b", camera_name="b", top=1, left=1, width=2, height=2),
    }
    with pytest.raises(OutOfBoundsError) as exc_info:
        check_no_overlap(blocks, 4)
    assert "пересекаются" in exc_info.value.message


def test_block_outside_grid_raises() -> None:
    """An explicit rectangle exceeding N×N bounds → error."""
    blocks = {"a": Block(label="a", camera_name="a", top=2, left=2, width=3, height=3)}
    with pytest.raises(OutOfBoundsError) as exc_info:
        check_no_overlap(blocks, 4)
    assert "выходит за границы" in exc_info.value.message


def test_non_overlapping_blocks_pass() -> None:
    """Adjacent (touching edges) rectangles do not overlap."""
    blocks = {
        "a": Block(label="a", camera_name="a", top=0, left=0, width=2, height=2),
        "b": Block(label="b", camera_name="b", top=0, left=2, width=2, height=2),
    }
    check_no_overlap(blocks, 4)  # no exception


def test_validate_layout_wrapper() -> None:
    """Full pipeline wrapper returns the same blocks."""
    matrix = [["1", "1", "2"], ["1", "1", "3"], ["4", "5", "6"]]
    blocks = validate_layout(matrix, 3)
    assert blocks["1"].width == 2 and blocks["1"].height == 2
