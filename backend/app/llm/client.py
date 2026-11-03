"""The single entry point for every model call.

Responsibilities: tier routing, caching, concurrency limiting, retry on rate
limits, token accounting, and tolerant JSON parsing. Callers pass a stage name
and a tier; they never see a provider.
"""
from __future__ import annotations

import asyncio
import json
import random
import re
import time
from typing import Any, Literal

import httpx

from app.core.config import settings
from app.core.exceptions import LLMUnavailable
from app.core.logging import get_logger
from app.db.session import session_scope
from app.llm import cache
from app.llm.providers import Completion, build_provider
from app.utils.dates import utcnow

log = get_logger(__name__)

Tier = Literal["cheap", "strong"]

# Free tiers sit around 10-15 requests/minute. Firing 20 extractions in a
# gather() would burn the quota in two seconds and fail most of them.
_SEMAPHORE = asyncio.Semaphore(4)
_RATE_LIMIT_STATUSES = {429, 503}
_MAX_ATTEMPTS = 4


class LLMClient:
    def __init__(self) -> None:
        self._provider = build_provider()

    def model_for(self, tier: Tier) -> str:
        return settings.llm_model_strong if tier == "strong" else settings.llm_model_cheap

    async def complete(
        self,
        *,
        stage: str,
        system: str,
        prompt: str,
        tier: Tier = "cheap",
        json_mode: bool = True,
        max_tokens: int | None = None,
    ) -> str:
        model = self.model_for(tier)
        key = cache.make_key(stage, model, system, prompt)

        hit = cache.get(key)
        if hit is not None:
            self._record(stage, tier, model, Completion(text=hit), cached=True, ms=0)
            return hit

        started = time.perf_counter()
        async with _SEMAPHORE:
            completion = await self._call_with_backoff(
                system=system,
                prompt=prompt,
                model=model,
                max_tokens=max_tokens or settings.llm_max_tokens,
                json_mode=json_mode,
            )
        elapsed_ms = int((time.perf_counter() - started) * 1000)

        if completion.text:
            cache.put(key, completion.text)
        self._record(stage, tier, model, completion, cached=False, ms=elapsed_ms)
        return completion.text

    async def complete_json(
        self, *, stage: str, system: str, prompt: str, tier: Tier = "cheap", **kwargs: Any
    ) -> Any:
        """Completion parsed as JSON, returning None rather than raising.

        Every caller of this already has a 'could not extract' path. Letting a
        malformed completion take down an ingest run would be the wrong
        trade: one unparseable filing should not cost the other nineteen.
        """
        raw = await self.complete(
            stage=stage, system=system, prompt=prompt, tier=tier, json_mode=True, **kwargs
        )
        return parse_json_loose(raw)

    async def _call_with_backoff(self, **kwargs: Any) -> Completion:
        last: Exception | None = None
        for attempt in range(_MAX_ATTEMPTS):
            try:
                return await self._provider.complete(**kwargs)
            except LLMUnavailable:
                raise
            except httpx.HTTPStatusError as exc:
                last = exc
                status = exc.response.status_code
                if status not in _RATE_LIMIT_STATUSES and status < 500:
                    log.warning("llm call rejected (%s): %s", status, exc.response.text[:200])
                    break
                delay = self._retry_after(exc) or (2.0 * (2**attempt) + random.random())
                log.info("llm rate limited, sleeping %.1fs", delay)
                await asyncio.sleep(delay)
            except (httpx.HTTPError, asyncio.TimeoutError) as exc:
                last = exc
                await asyncio.sleep(1.5 * (2**attempt))
        log.error("llm call failed after %d attempts: %s", _MAX_ATTEMPTS, last)
        return Completion(text="", model=kwargs.get("model", ""), provider="failed")

    @staticmethod
    def _retry_after(exc: httpx.HTTPStatusError) -> float | None:
        raw = exc.response.headers.get("retry-after")
        if not raw:
            return None
        try:
            return min(float(raw), 30.0)
        except ValueError:
            return None

    @staticmethod
    def _record(stage, tier, model, completion: Completion, *, cached: bool, ms: int) -> None:
        from app.db.models import LLMUsage

        try:
            with session_scope() as session:
                session.add(
                    LLMUsage(
                        created_at=utcnow(),
                        stage=stage,
                        tier=tier,
                        provider=completion.provider or settings.llm_provider,
                        model=model,
                        input_tokens=completion.input_tokens,
                        output_tokens=completion.output_tokens,
                        cached=cached,
                        latency_ms=ms,
                    )
                )
        except Exception as exc:  # noqa: BLE001 - telemetry must never break work
            log.debug("usage logging failed: %s", exc)


_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.S)


def parse_json_loose(raw: str) -> Any:
    """Parse JSON that a model produced, with the usual damage repaired.

    Handles: markdown fences, leading prose, trailing commentary, and a
    trailing comma before a closing brace. Returns None when nothing usable
    is recoverable.
    """
    if not raw or not raw.strip():
        return None
    text = raw.strip()

    fenced = _FENCE_RE.search(text)
    if fenced:
        text = fenced.group(1).strip()

    try:
        return json.loads(text)
    except ValueError:
        pass

    start = min((i for i in (text.find("{"), text.find("[")) if i != -1), default=-1)
    if start == -1:
        return None
    closer = "}" if text[start] == "{" else "]"
    end = text.rfind(closer)
    if end <= start:
        return None
    candidate = text[start : end + 1]
    candidate = re.sub(r",\s*([}\]])", r"\1", candidate)
    try:
        return json.loads(candidate)
    except ValueError:
        log.debug("unparseable model output: %s", candidate[:200])
        return None


_client: LLMClient | None = None


def get_llm() -> LLMClient:
    global _client
    if _client is None:
        _client = LLMClient()
    return _client
