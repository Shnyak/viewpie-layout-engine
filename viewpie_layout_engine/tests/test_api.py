# This file was generated with assistance from Qwen AI
# Related project: https://github.com/snoack/viewpie
# SPDX-License-Identifier: GPL-3.0-or-later
"""End-to-end tests for the FastAPI server (TestClient, mocked viewpie)."""

from __future__ import annotations

import time
from typing import Any

import pytest
from fastapi.testclient import TestClient

from viewpie_layout_engine import api_server
from viewpie_layout_engine.api_server import app


class FakeClient:
    """Stand-in for ViewpieClient that records calls and never touches net."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []

    async def apply_panel(self, panel_yaml: str, panel_id: str) -> dict:
        self.calls.append(("apply_panel", (panel_id, len(panel_yaml))))
        return {"ok": True}

    async def update_settings(self, settings: dict) -> dict:
        self.calls.append(("update_settings", settings))
        return {"ok": True}

    async def get_status(self) -> dict:
        self.calls.append(("get_status", None))
        return {"state": "running"}

    async def reload_config(self) -> dict:
        self.calls.append(("reload_config", None))
        return {"ok": True}


@pytest.fixture()
def client() -> TestClient:
    """Fresh app state + faked viewpie client per test."""
    api_server.CAMERAS.clear()
    api_server.PANELS.clear()
    api_server.SETTINGS = api_server.DisplaySettings()
    api_server.ACTIVE_PANEL = None
    api_server.CLIENT = FakeClient()  # type: ignore[assignment]
    with TestClient(app) as c:
        yield c


VALID_4X4 = "1 1 2 3\n1 1 4 5\n6 7 8 9\n10 11 12 13"


def test_health(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_validate_ok(client: TestClient) -> None:
    r = client.post(
        "/api/layout/validate",
        json={"panel_id": "main", "panel_name": "Main", "layout_text": VALID_4X4},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["success"] is True
    assert body["grid_size"] == 4
    assert len(body["blocks"]) == 13
    assert body["errors"] == []
    assert body["applied"] is False


def test_validate_l_shape_returns_structured_error(client: TestClient) -> None:
    r = client.post(
        "/api/layout/validate",
        json={"panel_id": "main", "panel_name": "M", "layout_text": "1 1 2\n1 2 2\n3 4 5"},
    )
    assert r.status_code == 400
    body = r.json()
    assert body["ok"] is False
    assert body["error_type"] == "InvalidBlockError"
    assert "не прямоугольник" in body["message"]
    assert body["details"]["label"] == "1"


def test_validate_non_square_normalizes_with_warning(client: TestClient) -> None:
    r = client.post(
        "/api/layout/validate",
        json={"panel_id": "p", "panel_name": "P", "layout_text": "1 1 2 3\n4 5 6 7"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["grid_size"] == 4
    assert any("normalized" in w for w in body["warnings"])


def test_generate_returns_yaml(client: TestClient) -> None:
    r = client.post(
        "/api/layout/generate",
        json={"panel_id": "wall", "panel_name": "Wall", "layout_text": VALID_4X4},
    )
    assert r.status_code == 200
    yaml_text = r.json()["layout_yaml"]
    for section in ("display:", "feeds:", "panels:", "defaults:"):
        assert section in yaml_text


def test_apply_marks_applied_true(client: TestClient) -> None:
    r = client.post(
        "/api/layout/apply",
        json={"panel_id": "wall", "panel_name": "Wall", "layout_text": VALID_4X4},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["applied"] is True
    assert ("apply_panel" in [c[0] for c in api_server.CLIENT.calls])  # type: ignore[attr-defined]


def test_auto_endpoint(client: TestClient) -> None:
    cameras = [{"name": f"cam{i}", "width": 1, "height": 1} for i in range(9)]
    r = client.post("/api/layout/auto", json={"cameras": cameras, "panel_id": "auto"})
    assert r.status_code == 200
    body = r.json()
    assert body["grid_size"] == 3
    assert len(body["blocks"]) == 9


def test_auto_too_many_cameras(client: TestClient) -> None:
    cameras = [{"name": f"cam{i}"} for i in range(20)]
    r = client.post("/api/layout/auto", json={"cameras": cameras, "grid_size": 3, "panel_id": "a"})
    assert r.status_code == 400
    assert r.json()["error_type"] == "TooManyCamerasError"


def test_performance_8x8_under_500ms(client: TestClient) -> None:
    """Acceptance criterion: 8×8 request handled in ≤ 500 ms."""
    layout = "\n".join(" ".join(str(y * 8 + x + 1) for x in range(8)) for y in range(8))
    start = time.perf_counter()
    r = client.post(
        "/api/layout/validate",
        json={"panel_id": "big", "panel_name": "Big", "layout_text": layout},
    )
    elapsed_ms = (time.perf_counter() - start) * 1000
    assert r.status_code == 200
    assert len(r.json()["blocks"]) == 64
    assert elapsed_ms < 500, f"took {elapsed_ms:.1f} ms"


def test_cameras_crud(client: TestClient) -> None:
    cam = {"name": "front", "url": "rtsp://10.0.0.1/stream"}
    assert client.post("/api/cameras", json=cam).status_code == 201
    # duplicate → 400 structured error
    dup = client.post("/api/cameras", json=cam)
    assert dup.status_code == 400
    listing = client.get("/api/cameras").json()
    assert len(listing) == 1
    assert client.delete("/api/cameras/front").status_code == 200
    missing = client.delete("/api/cameras/front")
    assert missing.status_code == 404
    assert missing.json()["error_type"] == "CameraNotFoundError"


def test_camera_invalid_url_rejected_by_pydantic(client: TestClient) -> None:
    r = client.post("/api/cameras", json={"name": "x", "url": "http://not-rtsp"})
    assert r.status_code == 422


def test_panels_crud_and_activation(client: TestClient) -> None:
    panel = {"id": "p1", "name": "Panel 1", "layout": VALID_4X4, "viewports": []}
    assert client.post("/api/panels", json=panel).status_code == 201
    # stored layout is normalized square text
    got = client.get("/api/panels").json()[0]
    assert got["layout"].count("\n") == 3

    updated = dict(panel, name="Renamed")
    assert client.put("/api/panels/p1", json=updated).status_code == 200

    assert client.post("/api/panels/p1/activate").status_code == 200
    # active panel cannot be deleted
    blocked = client.delete("/api/panels/p1")
    assert blocked.status_code == 400

    assert client.delete("/api/panels/nope").status_code == 404


def test_panel_invalid_layout_stored_normalized(client: TestClient) -> None:
    bad = {"id": "b", "name": "B", "layout": "1 1 2\n1 2 2\n3 4 5", "viewports": []}
    r = client.post("/api/panels", json=bad)
    assert r.status_code == 400
    assert r.json()["error_type"] == "InvalidBlockError"


def test_settings_roundtrip(client: TestClient) -> None:
    s = client.get("/api/settings").json()
    assert s["spacing"] == 1
    new = dict(s, spacing=7, background="#ff00aa")
    r = client.put("/api/settings", json=new)
    assert r.status_code == 200
    assert r.json()["spacing"] == 7
    assert ("update_settings" in [c[0] for c in api_server.CLIENT.calls])  # type: ignore[attr-defined]


def test_status_proxies_viewpie(client: TestClient) -> None:
    r = client.get("/api/status")
    assert r.status_code == 200
    body = r.json()
    assert body["viewpie"]["state"] == "running"
    assert "engine" in body


def test_layout_requires_text_or_order(client: TestClient) -> None:
    r = client.post("/api/layout/validate", json={"panel_id": "p", "panel_name": "P"})
    assert r.status_code == 400
    assert r.json()["error_type"] == "LayoutError"


def test_layout_from_cameras_order(client: TestClient) -> None:
    r = client.post(
        "/api/layout/validate",
        json={"panel_id": "p", "panel_name": "P", "cameras_order": ["a", "b", "c", "d"]},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["grid_size"] == 3  # min grid even for 4 cameras
    assert len(body["blocks"]) == 4


def test_preferred_grid_too_small_rejected(client: TestClient) -> None:
    """A layout bigger than the requested square is refused with 400."""
    layout = "\n".join(" ".join(str(i + 1) for _ in range(5)) for i in range(5))
    r = client.post(
        "/api/layout/validate",
        json={
            "panel_id": "p",
            "panel_name": "P",
            "layout_text": layout,
            "preferred_grid": 4,
        },
    )
    assert r.status_code == 400
    assert r.json()["error_type"] == "LayoutError"


def test_cameras_order_warning_for_missing_labels(client: TestClient) -> None:
    """cameras_order entries absent from the layout produce a warning."""
    r = client.post(
        "/api/layout/validate",
        json={
            "panel_id": "p",
            "panel_name": "P",
            "layout_text": "1 2 3\n4 5 6\n7 8 9",
            "cameras_order": ["1", "ghost"],
        },
    )
    assert r.status_code == 200
    assert any("not present" in w for w in r.json()["warnings"])


def test_auto_unregistered_camera_warning(client: TestClient) -> None:
    """Auto-placement of unknown camera names warns but still succeeds."""
    api_server.CAMERAS["known"] = api_server.Camera(
        name="known", url="rtsp://h/s"
    )
    r = client.post(
        "/api/layout/auto",
        json={"cameras": [{"name": "known"}, {"name": "mystery"}], "panel_id": "a"},
    )
    assert r.status_code == 200
    assert any("unregistered" in w for w in r.json()["warnings"])


def test_delete_panel_success_when_inactive(client: TestClient) -> None:
    panel = {"id": "gone", "name": "Gone", "layout": "1 2 3\n4 5 6\n7 8 9", "viewports": []}
    assert client.post("/api/panels", json=panel).status_code == 201
    assert client.delete("/api/panels/gone").status_code == 200
    assert client.get("/api/panels").json() == []


def test_activate_unknown_panel_404(client: TestClient) -> None:
    r = client.post("/api/panels/nope/activate")
    assert r.status_code == 404
    assert r.json()["error_type"] == "PanelNotFoundError"


def test_update_unknown_panel_404(client: TestClient) -> None:
    body = {"id": "nope", "name": "N", "layout": "1 2 3\n4 5 6\n7 8 9", "viewports": []}
    r = client.put("/api/panels/nope", json=body)
    assert r.status_code == 404


def test_apply_unreachable_viewpie_returns_502(client: TestClient) -> None:
    """A real ViewpieClient with no daemon behind it maps to HTTP 502."""
    from viewpie_layout_engine.viewpie_client import ViewpieClient

    api_server.CLIENT = ViewpieClient(base_url="http://127.0.0.1:1", retries=1, timeout=0.2)
    r = client.post(
        "/api/layout/apply",
        json={"panel_id": "w", "panel_name": "W", "layout_text": "1 2 3\n4 5 6\n7 8 9"},
    )
    assert r.status_code == 502
    assert r.json()["error_type"] == "ViewpieClientError"
