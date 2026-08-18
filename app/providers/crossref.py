from __future__ import annotations

import asyncio
import math
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import httpx
from tenacity import (
    AsyncRetrying,
    RetryCallState,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from app.core.version import get_app_version

_RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})

_PUBLICATION_TYPE_FILTER_MAP = {
    "article": "journal-article",
    "conference_paper": "proceedings-article",
    "book_chapter": "book-chapter",
}


@dataclass(frozen=True, slots=True)
class CrossrefSearchFilters:
    publication_year_from: int | None = None
    publication_year_to: int | None = None
    languages: tuple[str, ...] = ()
    publication_types: tuple[str, ...] = ()
    open_access: bool = False

    def to_filter_param(self) -> str | None:
        filters: list[str] = []
        if self.publication_year_from is not None:
            filters.append(f"from-pub-date:{self.publication_year_from}-01-01")
        if self.publication_year_to is not None:
            filters.append(f"until-pub-date:{self.publication_year_to}-12-31")
        if self.publication_types:
            for pt in self.publication_types:
                if pt in _PUBLICATION_TYPE_FILTER_MAP:
                    filters.append(f"type:{_PUBLICATION_TYPE_FILTER_MAP[pt]}")
        return ",".join(filters) or None

    def get_warnings(self) -> tuple[str, ...]:
        warnings: list[str] = []
        if self.languages:
            warnings.append(
                f"Crossref REST API does not support language filtering; language filter {list(self.languages)} was not applied to the physical query."
            )
        if self.open_access:
            warnings.append(
                "Crossref REST API does not support open access filtering; open_access filter was not applied to the physical query."
            )
        if self.publication_types:
            unsupported = [pt for pt in self.publication_types if pt not in _PUBLICATION_TYPE_FILTER_MAP]
            if unsupported:
                warnings.append(
                    f"Crossref REST API does not support publication type filter for {unsupported}; unsupported types were omitted from the physical query."
                )
        return tuple(warnings)

    @property
    def is_lossless(self) -> bool:
        return len(self.get_warnings()) == 0


def _build_user_agent(mailto: str | None = None) -> str:
    version = get_app_version()
    if mailto:
        return f"slr-platform/{version} (https://github.com/jaroslawoleradzki-ctrl/slr-platform; mailto:{mailto.strip()})"
    return f"slr-platform/{version} (https://github.com/jaroslawoleradzki-ctrl/slr-platform)"


def _is_retryable_exception(exception: BaseException) -> bool:
    if isinstance(exception, httpx.HTTPStatusError):
        return exception.response.status_code in _RETRYABLE_STATUS_CODES
    return isinstance(exception, httpx.RequestError)


def _parse_retry_after(response: httpx.Response) -> float | None:
    retry_after_header = response.headers.get("retry-after") or response.headers.get("Retry-After")
    if not retry_after_header:
        return None
    cleaned = retry_after_header.strip()
    try:
        seconds = float(cleaned)
        return seconds if seconds > 0 else None
    except ValueError:
        pass
    try:
        retry_dt = parsedate_to_datetime(cleaned)
        delay = (retry_dt - datetime.now(timezone.utc)).total_seconds()
        return delay if delay > 0 else None
    except Exception:
        return None


class _CrossrefWaitStrategy:
    def __init__(self, multiplier: float, max_wait: float) -> None:
        self._exp_wait = wait_exponential(multiplier=multiplier, max=max_wait)

    def __call__(self, retry_state: RetryCallState) -> float:
        if retry_state.outcome is not None and retry_state.outcome.failed:
            exc = retry_state.outcome.exception()
            if isinstance(exc, httpx.HTTPStatusError):
                retry_after = _parse_retry_after(exc.response)
                if retry_after is not None:
                    return retry_after
        return float(self._exp_wait(retry_state))


class CrossrefClient:
    """Low-level asynchronous client for the Crossref Works API."""

    def __init__(
        self,
        *,
        http_client: httpx.AsyncClient,
        base_url: str = "https://api.crossref.org",
        mailto: str | None = None,
        retry_attempts: int = 3,
        retry_wait_multiplier: float = 1.0,
        retry_wait_max: float = 10.0,
        requests_per_second: float | None = 20.0,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        if isinstance(retry_attempts, bool) or not isinstance(retry_attempts, int):
            raise TypeError("retry_attempts must be an integer")
        if retry_attempts < 1:
            raise ValueError("retry_attempts must be at least 1")

        if retry_wait_multiplier < 0:
            raise ValueError("retry_wait_multiplier must not be negative")
        if retry_wait_max < 0:
            raise ValueError("retry_wait_max must not be negative")

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
        self._mailto = mailto.strip() if mailto is not None else None
        if self._mailto == "":
            raise ValueError("mailto must not be blank")
        self._retry_attempts = retry_attempts
        self._retry_wait_multiplier = retry_wait_multiplier
        self._retry_wait_max = retry_wait_max
        self._minimum_interval = (
            None if requests_per_second is None else 1 / requests_per_second
        )
        self._clock = clock
        self._sleep = sleep
        self._rate_limit_lock = asyncio.Lock()
        self._last_request_started_at: float | None = None
        self._wait_strategy = _CrossrefWaitStrategy(
            multiplier=retry_wait_multiplier,
            max_wait=retry_wait_max,
        )

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
        user_agent = _build_user_agent(self._mailto)
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(self._retry_attempts),
            wait=self._wait_strategy,
            retry=retry_if_exception(_is_retryable_exception),
            sleep=self._sleep,
            reraise=True,
        ):
            with attempt:
                await self._wait_for_rate_limit()
                response = await self._http_client.get(
                    f"{self._base_url}/works",
                    params=params,
                    headers={"User-Agent": user_agent},
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
        filters: CrossrefSearchFilters | None = None,
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

        if filters is not None:
            filter_param = filters.to_filter_param()
            if filter_param is not None:
                params["filter"] = filter_param

        if self._mailto is not None:
            params["mailto"] = self._mailto

        response = await self._get(params=params)

        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("Crossref response must be a JSON object")

        message = payload.get("message")
        if not isinstance(message, dict):
            raise ValueError("Crossref response message must be a JSON object")
        if not isinstance(message.get("items"), list):
            raise ValueError("Crossref response message.items must be a list")

        if cursor is not None:
            if "next-cursor" in message:
                next_cursor = message["next-cursor"]
                if next_cursor is not None:
                    if not isinstance(next_cursor, str):
                        raise ValueError("Crossref response message.next-cursor must be a string")
                    if not next_cursor.strip():
                        raise ValueError("Crossref response message.next-cursor must not be blank")

        return payload

    async def iterate_works(
        self,
        query: str,
        *,
        rows: int = 20,
        limit: int | None = None,
        filters: CrossrefSearchFilters | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Yield all works matching a query by following Crossref cursor pagination."""
        if limit is not None:
            if isinstance(limit, bool) or not isinstance(limit, int):
                raise TypeError("limit must be an integer or None")
            if limit < 1:
                raise ValueError("limit must be at least 1")

        cursor = "*"
        seen_cursors: set[str] = set()
        yielded = 0

        while True:
            if limit is not None and yielded >= limit:
                break

            current_rows = min(rows, limit - yielded) if limit is not None else rows
            payload = await self.search_works(
                query,
                rows=current_rows,
                cursor=cursor,
                filters=filters,
            )

            message = payload["message"]
            items = message["items"]

            if not items:
                break

            for item in items:
                if not isinstance(item, dict):
                    raise ValueError("Crossref work must be a JSON object")
                yield item
                yielded += 1
                if limit is not None and yielded >= limit:
                    return

            next_cursor = message.get("next-cursor")
            if next_cursor is None:
                break

            if next_cursor == cursor or next_cursor in seen_cursors:
                break

            seen_cursors.add(cursor)
            cursor = next_cursor
