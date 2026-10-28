# This file was generated with assistance from Qwen AI
# Related project: https://github.com/snoack/viewpie
# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for viewpie_layout_engine.viewpie_client (respx-free, monkeypatched transport)."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
import pytest

from viewpie_layout_engine.exceptions import LayoutError
from viewpie_layout_engine.viewpie_client import ViewpieClient, ViewpieClientError


def _handler(responses: list[Any]):
    """Build an AsyncHTTPTransport handler serving queued responses/errors."""
    state = {"i": 0}

    async def handler(request: httpx.Request) -> httpx.Response:
        idx = min(state["i"], len(responses) - 1)
        state["i"] += 1
        item = responses[idx]
        if isinstance(item, Exception):
            raise item
        return item

    return handler, state


def _patch_transport(monkeypatch: pytest.MonkeyPatch, responses: list[Any]) -> dict:
    handler, state = _handler(responses)
    real_client = httpx.AsyncClient

    class Patched(real_client):  # type: ignore[misc,valid-type]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            kwargs["transport"] = httpx.MockTransport(handler)
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", Patched)
    return state


def test_apply_panel_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Happy path: POST /api/config returns JSON."""
    _patch_transport(monkeypatch, [httpx.Response(200, json={"ok": True})])
    client = ViewpieClient(base_url="http://vp:1", retries=1)
    result = asyncio.run(client.apply_panel("yaml-text", "main"))
    assert result == {"ok": True}


def test_retry_on_5xx_then_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Two 500s followed by 200 → success within 3 attempts."""
    _patch_transport(
        monkeypatch,
        [
            httpx.Response(500, text="boom"),
            httpx.Response(500, text="boom"),
            httpx.Response(200, json={"recovered": True}),
        ],
    )
    client = ViewpieClient(base_url="http://vp:1", retries=3, timeout=1.0)
    result = asyncio.run(client.reload_config())
    assert result == {"recovered": True}


def test_exhausted_retries_raise(monkeypatch: pytest.MonkeyPatch) -> None:
    """Persistent 5xx exhausts retries and raises ViewpieClientError."""
    _patch_transport(monkeypatch, [httpx.Response(500, text="down")])
    client = ViewpieClient(base_url="http://vp:1", retries=2, timeout=1.0)
    with pytest.raises(LayoutError):
        asyncio.run(client.update_settings({"spacing": 3}))


def test_connection_error_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """Transport failures bubble up as LayoutError after retries."""
    _patch_transport(monkeypatch, [httpx.ConnectError("refused")])
    client = ViewpieClient(base_url="http://vp:1", retries=1, timeout=1.0)
    with pytest.raises(ViewpieClientError):
        asyncio.run(client.apply_panel("y", "p"))


def test_get_status_never_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """Status probing degrades gracefully to an 'unreachable' payload."""
    _patch_transport(monkeypatch, [httpx.ConnectTimeout("slow")])
    client = ViewpieClient(base_url="http://vp:1", retries=1, timeout=0.5)
    status = asyncio.run(client.get_status())
    assert status["unreachable"] is True


def test_4xx_is_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    """A 400 answer fails immediately (permanent client error)."""
    state = _patch_transport(monkeypatch, [httpx.Response(400, json={"err": "bad"})])
    client = ViewpieClient(base_url="http://vp:1", retries=3, timeout=1.0)
    with pytest.raises(ViewpieClientError):
        asyncio.run(client.reload_config())
    assert state["i"] == 1  # exactly one attempt


def test_empty_body_returns_dict(monkeypatch: pytest.MonkeyPatch) -> None:
    """204-style empty responses normalize to {}."""
    _patch_transport(monkeypatch, [httpx.Response(200, content=b"")])
    client = ViewpieClient(base_url="http://vp:1/", retries=1)
    assert asyncio.run(client.reload_config()) == {}


def test_env_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    """Base URL / timeout / retries come from environment variables."""
    monkeypatch.setenv("VIEWPIE_BASE_URL", "http://pi.local:9999/")
    monkeypatch.setenv("VIEWPIE_TIMEOUT", "2.5")
    monkeypatch.setenv("VIEWPIE_RETRIES", "7")
    client = ViewpieClient()
    assert client.base_url == "http://pi.local:9999"
    assert client.timeout == 2.5
    assert client.retries == 7


def test_payload_serialization(monkeypatch: pytest.MonkeyPatch) -> None:
    """apply_panel sends config+panel keys in the JSON body."""
    captured: dict[str, Any] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={})

    handler_obj = handler

    class Patched(httpx.AsyncClient):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            kwargs["transport"] = httpx.MockTransport(handler_obj)
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", Patched)
    client = ViewpieClient(base_url="http://vp", retries=1)
    asyncio.run(client.apply_panel("cfg", "wall"))
    assert captured["path"] == "/api/config"
    assert captured["body"] == {"config": "cfg", "panel": "wall"}
