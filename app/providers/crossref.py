from __future__ import annotations

import asyncio
import math
import time
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
from tenacity import AsyncRetrying, retry_if_exception, stop_after_attempt

_RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})

_USER_AGENT = (
    "slr-platform/0.1.0 "
    "(https://github.com/jaroslawoleradzki-ctrl/slr-platform)"
)


def _is_retryable_exception(exception: BaseException) -> bool:
    if isinstance(exception, httpx.HTTPStatusError):
        return exception.response.status_code in _RETRYABLE_STATUS_CODES
    return isinstance(exception, httpx.RequestError)


class CrossrefClient:
    """Low-level asynchronous client for the Crossref Works API."""

    def __init__(
        self,
        *,
        http_client: httpx.AsyncClient,
        base_url: str = "https://api.crossref.org",
        retry_attempts: int = 3,
        requests_per_second: float | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        if isinstance(retry_attempts, bool) or not isinstance(retry_attempts, int):
            raise TypeError("retry_attempts must be an integer")
        if retry_attempts < 1:
            raise ValueError("retry_attempts must be at least 1")

        if requests_per_second is not None:
            if isinstance(requests_per_second, bool) or not isinstance(
                requests_per_second, (int, float)
            ):
                raise TypeError("requests_per_second must be a number or None")
            if (
                not math.isfinite(requests_per_second)
                or requests_per_second <= 0
            ):
                raise ValueError(
                    "requests_per_second must be a finite positive number or None"
                )

        self._http_client = http_client
        self._base_url = base_url.rstrip("/")
        self._retry_attempts = retry_attempts
        self._minimum_interval = (
            None if requests_per_second is None else 1 / requests_per_second
        )
        self._clock = clock
        self._sleep = sleep
        self._rate_limit_lock = asyncio.Lock()
        self._last_request_started_at: float | None = None

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
            stop=stop_after_attempt(self._retry_attempts),
            retry=retry_if_exception(_is_retryable_exception),
            reraise=True,
        ):
            with attempt:
                await self._wait_for_rate_limit()
                response = await self._http_client.get(
                    f"{self._base_url}/works",
                    params=params,
                    headers={"User-Agent": _USER_AGENT},
                )
                response.raise_for_status()
                return response

        raise RuntimeError("retry loop completed without returning a response")

    async def search_works(
        self,
        query: str,
        *,
        rows: int = 20,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        """Fetch one page of Crossref works matching a free-text query."""

        if not isinstance(query, str):
            raise TypeError("query must be a string")
        normalized_query = query.strip()
        if not normalized_query:
            raise ValueError("query must not be blank")

        if isinstance(rows, bool) or not isinstance(rows, int):
            raise TypeError("rows must be an integer")
        if not 1 <= rows <= 1000:
            raise ValueError("rows must be between 1 and 1000")

        params: dict[str, str | int] = {
            "query": normalized_query,
            "rows": rows,
        }
        if cursor is not None:
            if not isinstance(cursor, str):
                raise TypeError("cursor must be a string or None")
            normalized_cursor = cursor.strip()
            if not normalized_cursor:
                raise ValueError("cursor must not be blank")
            params["cursor"] = normalized_cursor

        response = await self._get(params=params)

        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("Crossref response must be a JSON object")

        message = payload.get("message")
        if not isinstance(message, dict):
            raise ValueError("Crossref response message must be a JSON object")
        if not isinstance(message.get("items"), list):
            raise ValueError("Crossref response message.items must be a list")

        return payload
