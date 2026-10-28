# This file was generated with assistance from Qwen AI
# Related project: https://github.com/snoack/viewpie
# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for viewpie_layout_engine.parser."""

from __future__ import annotations

import pytest

from viewpie_layout_engine.exceptions import LayoutError, ValidationError
from viewpie_layout_engine.parser import (
    count_empty_cells,
    parse_layout_text,
    render_matrix,
)


def test_valid_4x4_text() -> None:
    """Canonical 4×4 example parses into a matrix of matching shape."""
    text = "1 1 2 3\n1 1 4 5\n6 7 8 9\n10 11 12 13"
    matrix, height, width = parse_layout_text(text)
    assert (height, width) == (4, 4)
    assert matrix[0] == ["1", "1", "2", "3"]
    assert matrix[3] == ["10", "11", "12", "13"]


def test_trailing_newline_and_extra_spaces_are_tolerated() -> None:
    """Blank lines and repeated whitespace must not break parsing."""
    text = "\n  1   1 2 3 \n1 1  2 3\n\n"
    matrix, height, width = parse_layout_text(text)
    assert (height, width) == (2, 4)
    assert matrix[0] == ["1", "1", "2", "3"]


def test_empty_text_raises_layout_error() -> None:
    """Empty or whitespace-only input is a validation failure."""
    with pytest.raises(LayoutError):
        parse_layout_text("")
    with pytest.raises(ValidationError):
        parse_layout_text("   \n  \n")


def test_none_input_raises() -> None:
    """Defensive: None behaves like empty text."""
    with pytest.raises(LayoutError):
        parse_layout_text(None)  # type: ignore[arg-type]


def test_inconsistent_row_widths_raise() -> None:
    """Rows with different cell counts are rejected."""
    with pytest.raises(ValidationError) as exc_info:
        parse_layout_text("1 2 3 4\n5 6\n7 8 9 10")
    assert "inconsistent widths" in exc_info.value.message
    assert exc_info.value.details["widths"] == [2, 4]


def test_render_matrix_roundtrip() -> None:
    """parse → render reproduces canonical text."""
    text = "a b\n. c"
    matrix, _, _ = parse_layout_text(text)
    assert render_matrix(matrix) == "a b\n. c"


def test_count_empty_cells() -> None:
    """Empty-cell counter ignores labels."""
    matrix, _, _ = parse_layout_text(". . 1\n2 . .\n. . .")
    assert count_empty_cells(matrix) == 7


def test_single_cell_grid() -> None:
    """A 1×1 grid parses fine (normalizer will grow it later)."""
    matrix, h, w = parse_layout_text("cam1")
    assert (h, w) == (1, 1)
    assert matrix == [["cam1"]]
