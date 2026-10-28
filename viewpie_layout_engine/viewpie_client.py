# This file was generated with assistance from Qwen AI
# Related project: https://github.com/snoack/viewpie
# SPDX-License-Identifier: GPL-3.0-or-later
"""Async HTTP client for the modified viewpie daemon.

The upstream viewpie has no REST API; this engine targets a fork that
exposes configuration endpoints. The client is deliberately defensive:
connection failures raise :class:`ViewpieClientError` (a ``LayoutError``
subclass) so API handlers can translate them into structured JSON.

Environment variables:
    VIEWPIE_BASE_URL   – base URL of the viewpie daemon
                         (default: http://localhost:8080)
    VIEWPIE_TIMEOUT    – request timeout in seconds (default: 5)
    VIEWPIE_RETRIES    – retry count on 5xx responses (default: 3)
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Optional

import httpx

from .exceptions import LayoutError

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "http://localhost:8080"
DEFAULT_TIMEOUT = 5.0
DEFAULT_RETRIES = 3


class ViewpieClientError(LayoutError):
    """Raised when the viewpie daemon cannot be reached or returns errors."""


class ViewpieClient:
    """Thin async wrapper over the viewpie management HTTP API."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: Optional[float] = None,
        retries: Optional[int] = None,
    ) -> None:
        """Create a client.

        Args:
            base_url: Defaults to env ``VIEWPIE_BASE_URL``.
            timeout: Defaults to env ``VIEWPIE_TIMEOUT`` (seconds).
            retries: Defaults to env ``VIEWPIE_RETRIES`` — number of total
                attempts performed when the server answers 5xx.
        """
        self.base_url = (base_url or os.getenv("VIEWPIE_BASE_URL", DEFAULT_BASE_URL)).rstrip("/")
        self.timeout = timeout if timeout is not None else float(
            os.getenv("VIEWPIE_TIMEOUT", DEFAULT_TIMEOUT)
        )
        self.retries = retries if retries is not None else int(
            os.getenv("VIEWPIE_RETRIES", DEFAULT_RETRIES)
        )

    # ------------------------------------------------------------------ #
    # Internal request helper with bounded retries on 5xx / transport    #
    # ------------------------------------------------------------------ #
    async def _request(
        self,
        method: str,
        path: str,
        json_body: Any | None = None,
        *,
        allow_fail: bool = False,
    ) -> Any:
        """Perform one HTTP call with retries.

        Args:
            method: HTTP verb.
            path: Endpoint path relative to base_url.
            json_body: Optional JSON payload.
            allow_fail: When True, network/5xx errors return ``None``
                instead of raising (used by status probing).
        """
        url = f"{self.base_url}{path}"
        last_error: Exception | None = None
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for attempt in range(1, self.retries + 1):
                try:
                    response = await client.request(method, url, json=json_body)
                    if response.status_code >= 500:
                        last_error = ViewpieClientError(
                            f"viewpie returned {response.status_code}",
                            details={"url": url, "body": response.text[:200]},
                        )
                        logger.warning(
                            "viewpie %s %s -> %d (attempt %d/%d)",
                            method, path, response.status_code, attempt, self.retries,
                        )
                        await asyncio.sleep(0.2 * attempt)
                        continue
                    response.raise_for_status()
                    if not response.content:
                        return {}
                    return response.json()
                except httpx.HTTPStatusError as exc:
                    # 4xx — permanent, do not retry.
                    if allow_fail:
                        return {"error": str(exc)}
                    raise ViewpieClientError(
                        f"viewpie rejected the request: {exc.response.status_code}",
                        details={"url": url},
                    ) from exc
                except httpx.HTTPError as exc:
                    last_error = exc
                    logger.warning(
                        "viewpie connection error on %s %s: %s (attempt %d/%d)",
                        method, path, exc, attempt, self.retries,
                    )
                    await asyncio.sleep(0.2 * attempt)

        if allow_fail:
            return {"unreachable": True, "reason": str(last_error)}
        raise ViewpieClientError(
            f"viewpie unreachable after {self.retries} attempts: {last_error}",
            details={"url": url},
        )

    # ------------------------------------------------------------------ #
    # Public API                                                         #
    # ------------------------------------------------------------------ #
    async def apply_panel(self, panel_yaml: str, panel_id: str) -> dict:
        """Push a rendered YAML configuration and activate ``panel_id``."""
        return await self._request(
            "POST", "/api/config", json_body={"config": panel_yaml, "panel": panel_id}
        )

    async def update_settings(self, settings: dict) -> dict:
        """Update global display settings at runtime."""
        return await self._request("PUT", "/api/settings", json_body=settings)

    async def get_status(self) -> dict:
        """Fetch daemon status; never raises (returns error info instead)."""
        return await self._request("GET", "/api/status", allow_fail=True)

    async def reload_config(self) -> dict:
        """Ask viewpie to re-read its configuration file from disk."""
        return await self._request("POST", "/api/reload")
