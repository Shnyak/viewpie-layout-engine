# This file was generated with assistance from Qwen AI
# Related project: https://github.com/snoack/viewpie
# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for viewpie_layout_engine.auto_placer."""

from __future__ import annotations

import pytest

from viewpie_layout_engine.auto_placer import (
    auto_place_cameras,
    auto_place_to_text,
    can_place,
    minimal_grid_size,
    place_block,
)
from viewpie_layout_engine.exceptions import TooManyCamerasError
from viewpie_layout_engine.models import CameraSpec
from viewpie_layout_engine.parser import parse_layout_text
from viewpie_layout_engine.validator import validate_layout


def _specs(n: int, w: int = 1, h: int = 1) -> list[CameraSpec]:
    return [CameraSpec(name=f"cam{i}", width=w, height=h) for i in range(n)]


def test_nine_small_cameras_use_3x3() -> None:
    """9 × 1×1 cameras fill exactly the smallest legal grid."""
    grid, n, blocks = auto_place_cameras(_specs(9))
    assert n == 3
    assert len(blocks) == 9
    assert all(cell != "." for row in grid for cell in row)
    validate_layout(grid, n)


def test_one_2x2_plus_five_small_in_3x3() -> None:
    """Area 4+5=9 fits perfectly into 3×3 via greedy packing."""
    cameras = [CameraSpec(name="big", width=2, height=2)] + _specs(5)
    grid, n, blocks = auto_place_cameras(cameras)
    assert n == 3
    assert len(blocks) == 6
    big = next(b for b in blocks if b.label == "big")
    assert (big.width, big.height) == (2, 2)
    validate_layout(grid, n)


def test_twenty_cameras_do_not_fit_3x3() -> None:
    """20 × 1×1 into an explicitly requested 3×3 → TooManyCamerasError."""
    with pytest.raises(TooManyCamerasError):
        auto_place_cameras(_specs(20), grid_size=3)


def test_auto_size_for_20_cameras_is_5x5() -> None:
    """Without explicit grid the placer picks ceil(sqrt(20)) = 5."""
    grid, n, blocks = auto_place_cameras(_specs(20))
    assert n == 5
    assert len(blocks) == 20
    validate_layout(grid, n)


def test_wide_camera_forces_bigger_grid() -> None:
    """A 1×4 camera needs N ≥ 4 even though its area is small."""
    cameras = [CameraSpec(name="strip", width=4, height=1)] + _specs(2)
    grid, n, _blocks = auto_place_cameras(cameras)
    assert n == 4
    validate_layout(grid, n)


def test_cameras_beyond_8x8_capacity_raise() -> None:
    """Total area > 64 cannot be placed at all."""
    with pytest.raises(TooManyCamerasError):
        auto_place_cameras(_specs(65))


def test_odd_shapes_pack_without_overlap() -> None:
    """Mixed rectangles produce a valid non-overlapping layout."""
    cameras = [
        CameraSpec(name="a", width=3, height=2),
        CameraSpec(name="b", width=2, height=2),
        CameraSpec(name="c", width=1, height=2),
        CameraSpec(name="d", width=2, height=1),
        CameraSpec(name="e", width=1, height=1),
    ]
    grid, n, blocks = auto_place_cameras(cameras, grid_size=4)
    assert n == 4
    assert len(blocks) == 5
    validate_layout(grid, n)  # rectangular + in-bounds + no overlap


def test_invalid_explicit_grid_size_rejected() -> None:
    """grid_size below 3 or above 8 fails fast."""
    with pytest.raises(TooManyCamerasError):
        auto_place_cameras(_specs(1), grid_size=2)


def test_empty_camera_list_raises() -> None:
    """Nothing to place → TooManyCamerasError."""
    with pytest.raises(TooManyCamerasError):
        auto_place_cameras([])


def test_can_place_and_place_block_primitives() -> None:
    """Low-level helpers behave per contract."""
    grid = [["."] * 3 for _ in range(3)]
    assert can_place(grid, 0, 0, 2, 2)
    assert not can_place(grid, 2, 2, 2, 2)   # out of bounds
    assert not can_place(grid, -1, 0, 1, 1)  # negative coord
    place_block(grid, 0, 0, 2, 2, "x")
    assert not can_place(grid, 1, 1, 1, 1)   # occupied now
    with pytest.raises(ValueError):
        place_block(grid, 1, 1, 2, 2, "y")


def test_minimal_grid_size_boundaries() -> None:
    """Area→N mapping respects min/max clamps."""
    assert minimal_grid_size(0) == 3
    assert minimal_grid_size(9) == 3
    assert minimal_grid_size(10) == 4
    assert minimal_grid_size(64) == 8
    with pytest.raises(TooManyCamerasError):
        minimal_grid_size(65)


def test_auto_place_to_text_roundtrip() -> None:
    """Text output re-parses into the same square grid."""
    text, n = auto_place_to_text(_specs(4))
    matrix, h, w = parse_layout_text(text)
    assert (h, w) == (n, n)
