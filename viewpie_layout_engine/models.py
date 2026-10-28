# This file was generated with assistance from Qwen AI
# Related project: https://github.com/snoack/viewpie
# SPDX-License-Identifier: GPL-3.0-or-later
"""Pydantic v2 models shared by every module of the layout engine.

The models intentionally mirror the structure of a ``viewpie.yaml``
configuration file (feeds / panels / defaults) while adding the fields
required by the REST API (requests, responses, blocks…).
"""

from __future__ import annotations

import re
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator

RTSP_URL_RE = re.compile(r"^rtsps?://[^\s]+$", re.IGNORECASE)

MIN_GRID_SIZE = 3
MAX_GRID_SIZE = 8
VALID_GRID_SIZES: tuple[int, ...] = (3, 4, 5, 6, 7, 8)
EMPTY_CELL = "."


class Camera(BaseModel):
    """A single RTSP camera feed registered in the system."""

    name: str = Field(pattern=r"^[a-z0-9_]+$", min_length=1, max_length=64)
    url: str
    fullscreen_url: Optional[str] = None

    @field_validator("url")
    @classmethod
    def _validate_url(cls, value: str) -> str:
        """Ensure the feed URL uses the RTSP/RTSPS protocol."""
        if not RTSP_URL_RE.match(value):
            raise ValueError("url must start with rtsp:// or rtsps://")
        return value

    @field_validator("fullscreen_url")
    @classmethod
    def _validate_fullscreen_url(cls, value: Optional[str]) -> Optional[str]:
        """Ensure the optional fullscreen URL uses RTSP/RTSPS too."""
        if value is not None and not RTSP_URL_RE.match(value):
            raise ValueError("fullscreen_url must start with rtsp:// or rtsps://")
        return value


class Viewport(BaseModel):
    """A panel slot that can rotate between several feeds."""

    slot: str
    feeds: list[str] = Field(min_length=1)
    rotation_interval: Optional[int] = Field(None, ge=5, le=3600)

    @field_validator("slot")
    @classmethod
    def _validate_slot(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("slot must not be empty")
        return value


class Block(BaseModel):
    """A rectangular region of the grid occupied by one camera label.

    Coordinates follow matrix convention: ``top``/``left`` are row/column
    indices of the upper-left cell; ``height``/``width`` are in cells.
    """

    label: str
    camera_name: str
    top: int = Field(ge=0)
    left: int = Field(ge=0)
    width: int = Field(ge=1)
    height: int = Field(ge=1)

    @property
    def area(self) -> int:
        """Number of grid cells covered by this block."""
        return self.width * self.height

    @property
    def bottom(self) -> int:
        """Index of the last row occupied by the block (inclusive)."""
        return self.top + self.height - 1

    @property
    def right(self) -> int:
        """Index of the last column occupied by the block (inclusive)."""
        return self.left + self.width - 1


class DisplaySettings(BaseModel):
    """Global display settings mapped onto viewpie's ``display`` section."""

    spacing: int = Field(default=1, ge=0, le=20)
    pause_off_screen: bool = True
    background: str = Field(default="#000000", pattern=r"^#[0-9a-fA-F]{6}$")
    rotation_interval: int = Field(default=20, ge=5, le=3600)
    fullscreen_timeout: int = Field(default=600, ge=10, le=3600)


class CameraSpec(BaseModel):
    """Specification of one camera for auto-placement requests."""

    name: str = Field(pattern=r"^[a-z0-9_]+$", min_length=1, max_length=64)
    width: int = Field(default=1, ge=1, le=MAX_GRID_SIZE)
    height: int = Field(default=1, ge=1, le=MAX_GRID_SIZE)

    @property
    def area(self) -> int:
        """Cells required by this camera."""
        return self.width * self.height


class Panel(BaseModel):
    """A named layout panel (one entry of viewpie's ``panels`` section)."""

    id: str = Field(pattern=r"^[a-z0-9_]+$")
    name: str
    layout: str
    viewports: list[Viewport] = Field(default_factory=list)
    spacing: Optional[int] = Field(None, ge=0, le=20)
    background: Optional[str] = Field(None, pattern=r"^#[0-9a-fA-F]{6}$")

    @model_validator(mode="after")
    def _check_viewport_feeds(self) -> "Panel":
        """Every viewport feed must reference a label used in the layout."""
        labels = {tok for line in self.layout.splitlines() for tok in line.split()}
        for vp in self.viewports:
            for feed in vp.feeds:
                if feed not in labels:
                    raise ValueError(
                        f"viewport '{vp.slot}' references unknown feed '{feed}'"
                    )
        return self


class LayoutRequest(BaseModel):
    """Body of POST /api/layout/{validate,generate,apply}."""

    panel_id: str = Field(pattern=r"^[a-z0-9_]+$")
    panel_name: str
    layout_text: Optional[str] = None
    cameras_order: list[str] = Field(default_factory=list)
    preferred_grid: Optional[int] = Field(None, ge=MIN_GRID_SIZE, le=MAX_GRID_SIZE)
    display_settings: Optional[DisplaySettings] = None


class LayoutResponse(BaseModel):
    """Uniform response envelope for every layout operation."""

    success: bool
    panel_id: str
    grid_size: int
    layout_yaml: str = ""
    blocks: list[Block] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    applied: bool = False


class AutoLayoutRequest(BaseModel):
    """Body of POST /api/layout/auto."""

    cameras: list[CameraSpec] = Field(min_length=1)
    grid_size: Optional[int] = Field(None, ge=MIN_GRID_SIZE, le=MAX_GRID_SIZE)
    panel_id: str = Field(pattern=r"^[a-z0-9_]+$")
