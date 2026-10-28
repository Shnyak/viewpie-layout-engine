# This file was generated with assistance from Qwen AI
# Related project: https://github.com/snoack/viewpie
# SPDX-License-Identifier: GPL-3.0-or-later
"""Custom exception hierarchy for the viewpie layout engine.

The hierarchy is intentionally flat and semantic so that API handlers can
map every failure mode to a structured JSON error response::

    LayoutError (base)
    ├── NonSquareError        – grid cannot be normalized to N×N
    ├── InvalidBlockError     – block is not a rectangle (L-shape, hole…)
    ├── OutOfBoundsError      – block outside grid / overlapping blocks
    ├── TooManyCamerasError   – cameras do not fit into the grid
    ├── CameraNotFoundError   – unknown camera referenced
    ├── PanelNotFoundError    – unknown panel referenced
    └── ValidationError       – generic validation failure
"""

from __future__ import annotations


class LayoutError(Exception):
    """Base class for all layout-engine errors.

    Args:
        message: Human readable error description.
        details: Optional machine-readable context (dict of arbitrary keys).
    """

    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details: dict = details or {}

    def to_dict(self) -> dict:
        """Serialize the error into a JSON-friendly dictionary."""
        return {
            "error_type": type(self).__name__,
            "message": self.message,
            "details": self.details,
        }

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"{type(self).__name__}({self.message!r})"


class NonSquareError(LayoutError):
    """Raised when a grid cannot be normalized into a valid square N×N grid.

    Valid squares are N ∈ {3, 4, 5, 6, 7, 8}.
    """


class InvalidBlockError(LayoutError):
    """Raised when a labelled block is not a perfect rectangle.

    L-shapes, holes and protrusions produce a bounding-box area that does
    not match the number of cells actually occupied by the label.
    """


class OutOfBoundsError(LayoutError):
    """Raised when a block exceeds grid bounds or overlaps another block."""


class TooManyCamerasError(LayoutError):
    """Raised when the requested cameras cannot be placed into the grid."""


class CameraNotFoundError(LayoutError):
    """Raised when a referenced camera does not exist in the registry."""


class PanelNotFoundError(LayoutError):
    """Raised when a referenced panel does not exist in the registry."""


class ValidationError(LayoutError):
    """Generic validation failure (malformed input, bad configuration…)."""
