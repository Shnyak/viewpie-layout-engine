# This file was generated with assistance from Qwen AI
# Related project: https://github.com/snoack/viewpie
# SPDX-License-Identifier: GPL-3.0-or-later
"""viewpie-layout-engine — video-wall layout processing for viewpie.

Pipeline: ``parser`` → ``normalizer`` → ``validator`` → ``generator``,
with ``auto_placer`` producing layouts from camera rectangles and
``api_server`` exposing everything over REST.
"""

from __future__ import annotations

from .exceptions import (
    CameraNotFoundError,
    InvalidBlockError,
    LayoutError,
    NonSquareError,
    OutOfBoundsError,
    PanelNotFoundError,
    TooManyCamerasError,
    ValidationError,
)
from .models import (
    AutoLayoutRequest,
    Block,
    Camera,
    CameraSpec,
    DisplaySettings,
    LayoutRequest,
    LayoutResponse,
    Panel,
    Viewport,
)

__version__ = "1.0.0"

__all__ = [
    "AutoLayoutRequest",
    "Block",
    "Camera",
    "CameraNotFoundError",
    "CameraSpec",
    "DisplaySettings",
    "InvalidBlockError",
    "LayoutError",
    "LayoutRequest",
    "LayoutResponse",
    "NonSquareError",
    "OutOfBoundsError",
    "Panel",
    "PanelNotFoundError",
    "TooManyCamerasError",
    "ValidationError",
    "Viewport",
    "__version__",
]
