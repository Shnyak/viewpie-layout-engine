# This file was generated with assistance from Qwen AI
# Related project: https://github.com/snoack/viewpie
# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for Pydantic models and a few remaining edge branches."""

from __future__ import annotations

import pytest
from pydantic import ValidationError as PydValidationError

from viewpie_layout_engine.exceptions import TooManyCamerasError
from viewpie_layout_engine.auto_placer import auto_place_cameras, minimal_grid_size
from viewpie_layout_engine.generator import generate_panel_yaml
from viewpie_layout_engine.models import Camera, CameraSpec, Panel, Viewport
from viewpie_layout_engine.parser import parse_layout_text
import yaml


def test_camera_rejects_non_rtsp_url() -> None:
    """http:// URLs are refused by the Camera validator."""
    with pytest.raises(PydValidationError, match="rtsp"):
        Camera(name="c", url="http://example.com/stream")


def test_camera_accepts_rtsps() -> None:
    c = Camera(name="c", url="rtsps://host/stream")
    assert c.url.startswith("rtsps")


def test_camera_rejects_bad_fullscreen_url() -> None:
    with pytest.raises(PydValidationError, match="fullscreen_url"):
        Camera(name="c", url="rtsp://h/s", fullscreen_url="ftp://bad")


def test_viewport_rejects_empty_slot() -> None:
    with pytest.raises(PydValidationError):
        Viewport(slot="   ", feeds=["a"])


def test_viewport_requires_feeds() -> None:
    with pytest.raises(PydValidationError):
        Viewport(slot="s", feeds=[])


def test_panel_model_validator_unknown_feed() -> None:
    """Panel refuses viewports referencing labels absent from layout."""
    with pytest.raises(PydValidationError, match="unknown feed"):
        Panel(
            id="p",
            name="P",
            layout="a b c\nd e f\ng h i",
            viewports=[Viewport(slot="s", feeds=["ghost"])],
        )


def test_panel_spacing_bounds() -> None:
    with pytest.raises(PydValidationError):
        Panel(id="p", name="P", layout="a b\nc d", spacing=99)


def test_auto_grid_bumped_by_wide_single_camera() -> None:
    """One 8×1 strip forces N=8 even though total area is tiny."""
    grid, n, _blocks = auto_place_cameras([CameraSpec(name="strip", width=8, height=1)])
    assert n == 8
    assert grid[0][7] == "strip"


def test_minimal_grid_negative_area_clamps() -> None:
    """Defensive branch: non-positive areas return the minimum grid."""
    assert minimal_grid_size(-5) == 3


def test_panel_fragment_spacing_and_rotation() -> None:
    """generate_panel_yaml emits spacing + rotation_interval when set."""
    p = Panel(
        id="pf",
        name="PF",
        layout="a b c\nd e f\ng h i",
        viewports=[Viewport(slot="s", feeds=["a"], rotation_interval=42)],
        spacing=3,
    )
    doc = yaml.safe_load(generate_panel_yaml(p))
    assert doc["panel"]["spacing"] == 3
    assert doc["panel"]["viewports"][0]["rotation_interval"] == 42


def test_layout_request_grid_bounds() -> None:
    """preferred_grid outside 3..8 rejected at model level."""
    from viewpie_layout_engine.models import LayoutRequest

    with pytest.raises(PydValidationError):
        LayoutRequest(panel_id="p", panel_name="P", preferred_grid=9)


def test_parser_skips_blank_middle_line_only_via_strip() -> None:
    """A single blank line between rows is skipped, not counted."""
    matrix, h, w = parse_layout_text("a b\n\nc d")
    assert (h, w) == (2, 2)
    assert matrix[1] == ["c", "d"]
