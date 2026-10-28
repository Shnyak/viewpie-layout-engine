# This file was generated with assistance from Qwen AI
# Related project: https://github.com/snoack/viewpie
# SPDX-License-Identifier: GPL-3.0-or-later
"""FastAPI service exposing the layout engine over REST.

Endpoints
---------
POST   /api/layout/validate   – parse + normalize + validate (no YAML)
POST   /api/layout/generate   – full pipeline, return viewpie.yaml
POST   /api/layout/apply      – generate + push to viewpie daemon
POST   /api/layout/auto       – auto-place cameras into a square grid
GET    /api/cameras           – list registered cameras
POST   /api/cameras           – register a camera
DELETE /api/cameras/{name}    – remove a camera
GET    /api/panels            – list panels
POST   /api/panels            – create/update a panel (from layout text)
PUT    /api/panels/{id}       – update an existing panel
DELETE /api/panels/{id}       – delete a panel
POST   /api/panels/{id}/activate – make a panel active
GET    /api/settings          – current display settings
PUT    /api/settings          – update display settings (and viewpie)
GET    /api/status            – proxied viewpie status
GET    /health                – liveness probe

State is kept in-process (module-level registries). For production on a
single Raspberry Pi this is intentional: configuration survives via the
generated ``viewpie.yaml`` pushed through :class:`ViewpieClient`.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError as PydanticValidationError

from .auto_placer import auto_place_cameras
from .exceptions import (
    CameraNotFoundError,
    LayoutError,
    PanelNotFoundError,
)
from .viewpie_client import ViewpieClient, ViewpieClientError
from .generator import generate_viewpie_yaml
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
from .normalizer import normalize_to_square
from .parser import count_empty_cells, parse_layout_text, render_matrix
from .validator import validate_layout

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("viewpie_layout_engine.api")

app = FastAPI(
    title="viewpie Layout Engine",
    description="Validates and normalizes video-wall layouts for viewpie.",
    version="1.0.0",
)

# --------------------------------------------------------------------------- #
# In-memory state                                                             #
# --------------------------------------------------------------------------- #
CAMERAS: dict[str, Camera] = {}
PANELS: dict[str, Panel] = {}
SETTINGS: DisplaySettings = DisplaySettings()
ACTIVE_PANEL: Optional[str] = None
CLIENT = ViewpieClient()


# --------------------------------------------------------------------------- #
# Error handling                                                              #
# --------------------------------------------------------------------------- #
@app.exception_handler(LayoutError)
async def _layout_error_handler(_request: Request, exc: LayoutError) -> JSONResponse:
    """Map domain errors onto structured JSON responses."""
    status = 400
    if isinstance(exc, (CameraNotFoundError, PanelNotFoundError)):
        status = 404
    elif isinstance(exc, ViewpieClientError):
        status = 502
    logger.info("Layout error: %s (%s)", exc.message, type(exc).__name__)
    return JSONResponse(status_code=status, content={"ok": False, **exc.to_dict()})


@app.exception_handler(PydanticValidationError)
async def _pydantic_error_handler(_request: Request, exc: PydanticValidationError) -> JSONResponse:
    """Structured 422 for manually raised pydantic validation errors."""
    return JSONResponse(
        status_code=422,
        content={"ok": False, "error_type": "ValidationError", "errors": exc.errors()},
    )


# --------------------------------------------------------------------------- #
# Core pipeline                                                               #
# --------------------------------------------------------------------------- #
def _process_layout(req: LayoutRequest) -> tuple[list[list[str]], int, list[Block], list[str]]:
    """Parse → normalize → validate a layout request.

    Returns:
        ``(matrix, grid_size, blocks, warnings)``.

    Raises:
        LayoutError subclasses on any invalid input.
    """
    warnings: list[str] = []

    text = req.layout_text
    if text is None or not text.strip():
        if not req.cameras_order:
            raise LayoutError("either layout_text or cameras_order must be provided")
        # Build a default row-major placement from cameras_order.
        specs = [CameraSpec(name=name) for name in req.cameras_order]
        matrix, size, blocks = auto_place_cameras(specs, req.preferred_grid)
        warnings.append("layout auto-generated from cameras_order")
        return matrix, size, blocks, warnings

    matrix, height, width = parse_layout_text(text)

    if req.preferred_grid is not None and max(height, width) > req.preferred_grid:
        raise LayoutError(
            f"layout {height}x{width} does not fit preferred grid "
            f"{req.preferred_grid}x{req.preferred_grid}",
            details={"height": height, "width": width, "preferred": req.preferred_grid},
        )

    matrix, size = normalize_to_square(matrix, height, width)
    if (size != height or size != width):
        warnings.append(f"grid normalized from {height}x{width} to {size}x{size}")

    blocks_map = validate_layout(matrix, size)
    blocks = list(blocks_map.values())

    empties = count_empty_cells(matrix)
    if empties:
        warnings.append(f"{empties} empty cell(s) will be rendered as background")

    if req.cameras_order:
        missing = [c for c in req.cameras_order if c not in blocks_map]
        if missing:
            warnings.append(f"cameras not present in layout: {', '.join(missing)}")

    return matrix, size, blocks, warnings


def _build_response(
    req_panel_id: str,
    matrix: list[list[str]],
    size: int,
    blocks: list[Block],
    warnings: list[str],
    *,
    with_yaml: bool,
    applied: bool = False,
) -> LayoutResponse:
    """Assemble a LayoutResponse, optionally generating full viewpie YAML."""
    layout_text = render_matrix(matrix)
    yaml_text = ""
    if with_yaml:
        viewport = Viewport(slot="default", feeds=[b.label for b in blocks] or ["placeholder"]) \
            if blocks else None
        panel = Panel(
            id=req_panel_id,
            name=req_panel_id,
            layout=layout_text,
            viewports=[viewport] if viewport else [],
            spacing=SETTINGS.spacing,
            background=SETTINGS.background,
        )
        yaml_text = generate_viewpie_yaml(CAMERAS, [panel], SETTINGS, req_panel_id)

    return LayoutResponse(
        success=True,
        panel_id=req_panel_id,
        grid_size=size,
        layout_yaml=yaml_text,
        blocks=blocks,
        warnings=warnings,
        errors=[],
        applied=applied,
    )


# --------------------------------------------------------------------------- #
# Layout endpoints                                                            #
# --------------------------------------------------------------------------- #
@app.post("/api/layout/validate", response_model=LayoutResponse)
async def validate_layout_endpoint(req: LayoutRequest) -> LayoutResponse:
    """Validate a layout without generating or applying anything."""
    start = time.perf_counter()
    matrix, size, blocks, warnings = _process_layout(req)
    logger.info("validate ok: panel=%s grid=%dx%d blocks=%d (%.1f ms)",
                req.panel_id, size, size, len(blocks), (time.perf_counter() - start) * 1000)
    return _build_response(req.panel_id, matrix, size, blocks, warnings, with_yaml=False)


@app.post("/api/layout/generate", response_model=LayoutResponse)
async def generate_layout_endpoint(req: LayoutRequest) -> LayoutResponse:
    """Validate and generate viewpie.yaml, but do not apply it."""
    matrix, size, blocks, warnings = _process_layout(req)
    return _build_response(req.panel_id, matrix, size, blocks, warnings, with_yaml=True)


@app.post("/api/layout/apply", response_model=LayoutResponse)
async def apply_layout_endpoint(req: LayoutRequest) -> LayoutResponse:
    """Validate, generate and push the layout to the viewpie daemon."""
    global ACTIVE_PANEL
    matrix, size, blocks, warnings = _process_layout(req)
    response = _build_response(req.panel_id, matrix, size, blocks, warnings, with_yaml=True)

    await CLIENT.apply_panel(response.layout_yaml, req.panel_id)
    ACTIVE_PANEL = req.panel_id
    PANELS[req.panel_id] = Panel(
        id=req.panel_id,
        name=req.panel_name,
        layout=render_matrix(matrix),
        viewports=[Viewport(slot="default", feeds=[b.label for b in blocks])] if blocks else [],
    )
    response.applied = True
    logger.info("Applied panel '%s' (%dx%d)", req.panel_id, size, size)
    return response


@app.post("/api/layout/auto", response_model=LayoutResponse)
async def auto_layout_endpoint(req: AutoLayoutRequest) -> LayoutResponse:
    """Auto-generate a layout by packing camera rectangles greedily."""
    matrix, size, blocks = auto_place_cameras(req.cameras, req.grid_size)
    warnings: list[str] = []
    empties = count_empty_cells(matrix)
    if empties:
        warnings.append(f"{empties} empty cell(s) left unused")
    unknown = [b.label for b in blocks if CAMERAS and b.label not in CAMERAS]
    if unknown:
        warnings.append(f"unregistered cameras: {', '.join(sorted(unknown))}")
    return _build_response(req.panel_id, matrix, size, blocks, warnings, with_yaml=True)


# --------------------------------------------------------------------------- #
# Cameras CRUD                                                                #
# --------------------------------------------------------------------------- #
@app.get("/api/cameras", response_model=list[Camera])
async def list_cameras() -> list[Camera]:
    """Return all registered cameras."""
    return sorted(CAMERAS.values(), key=lambda c: c.name)


@app.post("/api/cameras", response_model=Camera, status_code=201)
async def create_camera(camera: Camera) -> Camera:
    """Register a new RTSP camera feed."""
    if camera.name in CAMERAS:
        raise LayoutError(f"camera '{camera.name}' already exists",
                          details={"name": camera.name})
    CAMERAS[camera.name] = camera
    logger.info("Registered camera '%s'", camera.name)
    return camera


@app.delete("/api/cameras/{name}", response_model=dict)
async def delete_camera(name: str) -> dict:
    """Remove a camera from the registry."""
    if name not in CAMERAS:
        raise CameraNotFoundError(f"camera '{name}' not found", details={"name": name})
    del CAMERAS[name]
    logger.info("Deleted camera '%s'", name)
    return {"ok": True, "deleted": name}


# --------------------------------------------------------------------------- #
# Panels CRUD                                                                 #
# --------------------------------------------------------------------------- #
@app.get("/api/panels", response_model=list[Panel])
async def list_panels() -> list[Panel]:
    """Return all stored panels."""
    return sorted(PANELS.values(), key=lambda p: p.id)


@app.post("/api/panels", response_model=Panel, status_code=201)
async def create_panel(panel: Panel) -> Panel:
    """Create (or replace) a panel; its layout is validated first."""
    matrix, height, width = parse_layout_text(panel.layout)
    norm, size = normalize_to_square(matrix, height, width)
    validate_layout(norm, size)
    stored = panel.model_copy(update={"layout": render_matrix(norm)})
    PANELS[panel.id] = stored
    logger.info("Stored panel '%s' (%dx%d)", panel.id, size, size)
    return stored


@app.put("/api/panels/{panel_id}", response_model=Panel)
async def update_panel(panel_id: str, panel: Panel) -> Panel:
    """Update an existing panel (the id in the path wins)."""
    if panel_id not in PANELS:
        raise PanelNotFoundError(f"panel '{panel_id}' not found", details={"id": panel_id})
    matrix, height, width = parse_layout_text(panel.layout)
    norm, size = normalize_to_square(matrix, height, width)
    validate_layout(norm, size)
    stored = panel.model_copy(update={"id": panel_id, "layout": render_matrix(norm)})
    PANELS[panel_id] = stored
    return stored


@app.delete("/api/panels/{panel_id}", response_model=dict)
async def delete_panel(panel_id: str) -> dict:
    """Delete a panel; the active panel cannot be deleted."""
    global ACTIVE_PANEL
    if panel_id not in PANELS:
        raise PanelNotFoundError(f"panel '{panel_id}' not found", details={"id": panel_id})
    if ACTIVE_PANEL == panel_id:
        raise LayoutError(f"panel '{panel_id}' is active and cannot be deleted",
                          details={"id": panel_id})
    del PANELS[panel_id]
    return {"ok": True, "deleted": panel_id}


@app.post("/api/panels/{panel_id}/activate", response_model=dict)
async def activate_panel(panel_id: str) -> dict:
    """Activate a stored panel and push the full config to viewpie."""
    global ACTIVE_PANEL
    if panel_id not in PANELS:
        raise PanelNotFoundError(f"panel '{panel_id}' not found", details={"id": panel_id})
    yaml_text = generate_viewpie_yaml(CAMERAS, list(PANELS.values()), SETTINGS, panel_id)
    await CLIENT.apply_panel(yaml_text, panel_id)
    ACTIVE_PANEL = panel_id
    logger.info("Activated panel '%s'", panel_id)
    return {"ok": True, "active_panel": panel_id}


# --------------------------------------------------------------------------- #
# Settings & status                                                           #
# --------------------------------------------------------------------------- #
@app.get("/api/settings", response_model=DisplaySettings)
async def get_settings() -> DisplaySettings:
    """Return current display settings."""
    return SETTINGS


@app.put("/api/settings", response_model=DisplaySettings)
async def put_settings(settings: DisplaySettings) -> DisplaySettings:
    """Update display settings and propagate them to viewpie."""
    global SETTINGS
    SETTINGS = settings
    await CLIENT.update_settings(settings.model_dump())
    logger.info("Updated display settings")
    return SETTINGS


@app.get("/api/status", response_model=dict)
async def get_status() -> dict:
    """Proxy the viewpie daemon status plus engine state."""
    upstream = await CLIENT.get_status()
    return {
        "engine": {
            "cameras": len(CAMERAS),
            "panels": len(PANELS),
            "active_panel": ACTIVE_PANEL,
            "settings": SETTINGS.model_dump(),
        },
        "viewpie": upstream,
    }


@app.get("/health", response_model=dict)
async def health() -> dict:
    """Liveness probe used by the Docker HEALTHCHECK."""
    return {"status": "ok"}


def run() -> None:  # pragma: no cover - console entry point
    """Start the server programmatically (``python -m viewpie_layout_engine.api_server``)."""
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":  # pragma: no cover
    run()
