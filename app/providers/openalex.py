from __future__ import annotations

import asyncio
import math
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

import httpx
from tenacity import AsyncRetrying, retry_if_exception, stop_after_attempt, wait_exponential

_RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})


def _is_retryable_exception(exception: BaseException) -> bool:
    if isinstance(exception, httpx.HTTPStatusError):
        return exception.response.status_code in _RETRYABLE_STATUS_CODES
    return isinstance(exception, httpx.RequestError)


class OpenAlexClient:
    """Low-level asynchronous client for the OpenAlex Works API."""

    def __init__(
        self,
        *,
        http_client: httpx.AsyncClient,
        base_url: str = "https://api.openalex.org",
        mailto: str | None = None,
        max_attempts: int = 3,
        retry_wait_multiplier: float = 1.0,
        retry_wait_max: float = 10.0,
        requests_per_second: float | None = 10.0,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if retry_wait_multiplier < 0:
            raise ValueError("retry_wait_multiplier must not be negative")
        if retry_wait_max < 0:
            raise ValueError("retry_wait_max must not be negative")
        if requests_per_second is not None and (
            not math.isfinite(requests_per_second) or requests_per_second <= 0
        ):
            raise ValueError(
                "requests_per_second must be a finite positive number or None"
            )

        self._http_client = http_client
        self._base_url = base_url.rstrip("/")
        self._mailto = mailto.strip() if mailto is not None else None
        self._max_attempts = max_attempts
        self._retry_wait_multiplier = retry_wait_multiplier
        self._retry_wait_max = retry_wait_max
        self._minimum_interval = (
            None if requests_per_second is None else 1 / requests_per_second
        )
        self._clock = clock
        self._sleep = sleep
        self._rate_limit_lock = asyncio.Lock()
        self._last_request_started_at: float | None = None
        if self._mailto == "":
            raise ValueError("mailto must not be blank")

    async def _wait_for_rate_limit(self) -> None:
        if self._minimum_interval is None:
            return

        async with self._rate_limit_lock:
            now = self._clock()
            if self._last_request_started_at is not None:
                delay = self._minimum_interval - (
                    now - self._last_request_started_at
                )
                if delay > 0:
                    await self._sleep(delay)
            self._last_request_started_at = self._clock()

    async def _get(self, *, params: dict[str, str | int]) -> httpx.Response:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(self._max_attempts),
            wait=wait_exponential(
                multiplier=self._retry_wait_multiplier,
                max=self._retry_wait_max,
            ),
            retry=retry_if_exception(_is_retryable_exception),
            reraise=True,
        ):
            with attempt:
                await self._wait_for_rate_limit()
                response = await self._http_client.get(
                    f"{self._base_url}/works",
                    params=params,
                )
                response.raise_for_status()
                return response

        raise RuntimeError("retry loop completed without returning a response")

    async def search_works(
        self,
        query: str,
        *,
        per_page: int = 25,
        cursor: str = "*",
    ) -> dict[str, Any]:
        """Fetch one cursor page of works matching a free-text query."""

        normalized_query = query.strip()
        if not normalized_query:
            raise ValueError("query must not be blank")
        if not 1 <= per_page <= 200:
            raise ValueError("per_page must be between 1 and 200")
        if not cursor.strip():
            raise ValueError("cursor must not be blank")

        params: dict[str, str | int] = {
            "search": normalized_query,
            "per-page": per_page,
            "cursor": cursor,
        }
        if self._mailto is not None:
            params["mailto"] = self._mailto

        response = await self._get(params=params)

        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("OpenAlex response must be a JSON object")
        return payload

    async def iterate_works(
        self,
        query: str,
        *,
        per_page: int = 200,
    ) -> AsyncIterator[dict[str, Any]]:
        """Yield all works by following OpenAlex cursor pagination."""

        cursor = "*"
        while True:
            payload = await self.search_works(
                query,
                per_page=per_page,
                cursor=cursor,
            )

            results = payload.get("results")
            if not isinstance(results, list):
                raise ValueError("OpenAlex response results must be a list")

            for work in results:
                if not isinstance(work, dict):
                    raise ValueError("OpenAlex work must be a JSON object")
                yield work

            meta = payload.get("meta")
            if not isinstance(meta, dict):
                raise ValueError("OpenAlex response meta must be a JSON object")

            next_cursor = meta.get("next_cursor")
            if next_cursor is None:
                return
            if not isinstance(next_cursor, str) or not next_cursor.strip():
                raise ValueError("OpenAlex next_cursor must be a non-blank string or null")

            cursor = next_cursor
