"""HTTP client with the quirks of Indian exchange endpoints handled once.

NSE rejects requests without a browser UA and a cookie obtained by first
hitting the site root. The cookie expires silently and the endpoint then
returns 401/403 with an HTML body, so we refresh and retry rather than
treating it as a hard failure.
"""
from __future__ import annotations

import asyncio
import random
from typing import Any

import httpx

from app.core.config import settings
from app.core.exceptions import UpstreamUnavailable
from app.core.logging import get_logger

log = get_logger(__name__)

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-GB,en;q=0.9",
    "Connection": "keep-alive",
}

_COOKIE_REFRESH_STATUSES = {401, 403}


class SessionClient:
    """A cookie-bearing async client bound to one host.

    Instances are cheap but the cookie handshake is not, so ingest jobs should
    create one and reuse it for the whole run.
    """

    def __init__(self, base_url: str, warmup_paths: list[str] | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.warmup_paths = warmup_paths or ["/"]
        self._client: httpx.AsyncClient | None = None
        self._warm = False
        self._lock = asyncio.Lock()

    async def __aenter__(self) -> "SessionClient":
        self._client = httpx.AsyncClient(
            headers=BROWSER_HEADERS,
            timeout=settings.http_timeout_seconds,
            follow_redirects=True,
        )
        return self

    async def __aexit__(self, *_: object) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _warmup(self) -> None:
        assert self._client is not None
        async with self._lock:
            for path in self.warmup_paths:
                try:
                    await self._client.get(f"{self.base_url}{path}")
                    await asyncio.sleep(0.4)
                except httpx.HTTPError as exc:  # pragma: no cover - network
                    log.debug("warmup failed for %s: %s", path, exc)
            self._warm = True

    async def get_json(self, path: str, **params: Any) -> Any:
        """GET returning parsed JSON, with cookie refresh and backoff."""
        if self._client is None:
            raise RuntimeError("SessionClient used outside its context manager")
        if not self._warm:
            await self._warmup()

        url = path if path.startswith("http") else f"{self.base_url}{path}"
        last_error: str = "unknown"

        for attempt in range(settings.http_max_retries):
            try:
                response = await self._client.get(url, params=params or None)
            except httpx.HTTPError as exc:
                last_error = str(exc)
            else:
                if response.status_code in _COOKIE_REFRESH_STATUSES:
                    log.info("cookie expired on %s, refreshing", self.base_url)
                    self._warm = False
                    await self._warmup()
                    last_error = f"status {response.status_code}"
                elif response.status_code >= 500:
                    last_error = f"status {response.status_code}"
                elif response.status_code >= 400:
                    # 404 and friends are not retryable; surface immediately.
                    raise UpstreamUnavailable(
                        f"{url} returned {response.status_code}"
                    )
                else:
                    try:
                        return response.json()
                    except ValueError:
                        # NSE serves an HTML interstitial when it throttles.
                        last_error = "non-JSON body"
                        self._warm = False

            await asyncio.sleep(0.8 * (2**attempt) + random.random() * 0.3)

        raise UpstreamUnavailable(f"{url} failed after retries: {last_error}")

    async def get_bytes(self, url: str) -> bytes:
        if self._client is None:
            raise RuntimeError("SessionClient used outside its context manager")
        if not self._warm:
            await self._warmup()
        try:
            response = await self._client.get(url)
            response.raise_for_status()
            return response.content
        except httpx.HTTPError as exc:
            raise UpstreamUnavailable(f"download failed: {url}") from exc
