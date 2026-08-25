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

_RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})


def _is_retryable_exception(exception: BaseException) -> bool:
    if isinstance(exception, httpx.HTTPStatusError):
        return exception.response.status_code in _RETRYABLE_STATUS_CODES
    return isinstance(exception, httpx.RequestError)


def _parse_retry_after(response: httpx.Response) -> float | None:
    retry_after_header = (
        response.headers.get("retry-after")
        or response.headers.get("Retry-After")
    )
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


class _SemanticScholarWaitStrategy:
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


@dataclass(frozen=True, slots=True)
class SemanticScholarSearchFilters:
    """Filters requested by the search strategy.

    The Semantic Scholar relevance search endpoint is not wired to apply any of
    these constraints in this version, so each active filter produces an explicit
    warning (no silent loss) and the physical query remains the canonical Boolean
    expression. Known-language result constraints are still enforced client-side
    by the router; records with an unknown language remain candidates because the
    provider cannot enforce the restriction on the physical query.
    """

    publication_year_from: int | None = None
    publication_year_to: int | None = None
    languages: tuple[str, ...] = ()
    publication_types: tuple[str, ...] = ()
    open_access: bool = False

    def to_filter_param(self) -> None:
        return None

    def get_warnings(self) -> tuple[str, ...]:
        warnings: list[str] = []
        if self.publication_year_from is not None or self.publication_year_to is not None:
            warnings.append(
                "Semantic Scholar relevance search does not support year range filtering "
                "in this version; the year filter was not applied to the physical query."
            )
        if self.languages:
            warnings.append(
                f"Semantic Scholar relevance search does not support language filtering; "
                f"language filter {list(self.languages)} was not applied to the physical query, "
                f"so the language restriction could not be enforced for records with unknown language."
            )
        if self.publication_types:
            warnings.append(
                f"Semantic Scholar relevance search does not support publication type filtering; "
                f"publication type filter {list(self.publication_types)} was not applied to the physical query."
            )
        if self.open_access:
            warnings.append(
                "Semantic Scholar relevance search does not support open access filtering; "
                "open_access filter was not applied to the physical query."
            )
        return tuple(warnings)

    @property
    def is_lossless(self) -> bool:
        return len(self.get_warnings()) == 0


@dataclass(frozen=True, slots=True)
class SemanticScholarSearchPage:
    """One parsed page of Semantic Scholar paper/search results."""

    data: list[dict[str, Any]]
    total: int | None
    offset: int
    next: int | None
    payload: dict[str, Any]


class SemanticScholarClient:
    """Low-level asynchronous client for the Semantic Scholar Graph API.

    The client retries transient failures (HTTP 429/500/502/503/504 and
    transport errors) with exponential backoff, honors the `Retry-After`
    header, and throttles requests to the documented Semantic Scholar rate
    limit (1 request per second with an API key) when rate limiting is enabled.
    """

    def __init__(
        self,
        *,
        http_client: httpx.AsyncClient,
        base_url: str = "https://api.semanticscholar.org/graph/v1",
        api_key: str | None = None,
        retry_attempts: int = 3,
        retry_wait_multiplier: float = 1.0,
        retry_wait_max: float = 10.0,
        requests_per_second: float | None = 1.0,
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
            if not math.isfinite(requests_per_second) or requests_per_second <= 0:
                raise ValueError(
                    "requests_per_second must be a finite positive number or None"
                )

        self._http_client = http_client
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key.strip() if api_key is not None else None

        if api_key is not None and not api_key.strip():
            raise ValueError("api_key must not be blank")

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
        self._wait_strategy = _SemanticScholarWaitStrategy(
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

    def _headers(self) -> dict[str, str]:
        if self._api_key is not None:
            return {"x-api-key": self._api_key}
        return {}

    async def _get(
        self,
        *,
        url: str,
        params: dict[str, Any],
        headers: dict[str, str],
    ) -> httpx.Response:
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
                    url,
                    params=params,
                    headers=headers,
                )
                response.raise_for_status()
                return response

        raise RuntimeError("retry loop completed without returning a response")

    @staticmethod
    def _search_params(
        query: Any,
        limit: Any,
        offset: Any,
        fields: Any,
    ) -> dict[str, Any]:
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must not be blank")
        if not isinstance(limit, int) or isinstance(limit, bool) or limit <= 0:
            raise ValueError("limit must be positive")
        if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
            raise ValueError("offset must not be negative")

        params: dict[str, Any] = {
            "query": query.strip(),
            "limit": limit,
            "offset": offset,
        }

        if fields is not None:
            if not isinstance(fields, list) or not fields:
                raise ValueError("fields must not be empty")
            cleaned_fields: list[str] = []
            for f in fields:
                if not isinstance(f, str) or not f.strip():
                    raise ValueError("fields must contain non-blank strings")
                cleaned_fields.append(f.strip())
            params["fields"] = ",".join(cleaned_fields)

        return params

    def _parse_payload(self, payload: Any) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError("Semantic Scholar response must be a JSON object")
        return payload

    def _parse_data(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        data = payload.get("data")
        if data is None:
            return []
        if not isinstance(data, list):
            raise ValueError("Semantic Scholar response data must be a list")
        for item in data:
            if not isinstance(item, dict):
                raise ValueError("Semantic Scholar paper record must be a JSON object")
        return data

    async def search_papers(
        self,
        query: str,
        *,
        limit: int = 20,
        offset: int = 0,
        fields: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch one page of papers matching a free-text query from Semantic Scholar."""
        params = self._search_params(query, limit, offset, fields)
        url = f"{self._base_url}/paper/search"
        response = await self._get(
            url=url,
            params=params,
            headers=self._headers(),
        )
        payload = self._parse_payload(response.json())
        return self._parse_data(payload)

    async def search_papers_page(
        self,
        query: str,
        *,
        limit: int = 20,
        offset: int = 0,
        fields: list[str] | None = None,
    ) -> SemanticScholarSearchPage:
        """Fetch one page and expose pagination metadata alongside the raw payload."""
        params = self._search_params(query, limit, offset, fields)
        url = f"{self._base_url}/paper/search"
        response = await self._get(
            url=url,
            params=params,
            headers=self._headers(),
        )
        payload = self._parse_payload(response.json())
        data = self._parse_data(payload)

        total = payload.get("total")
        if total is not None and (
            not isinstance(total, int)
            or isinstance(total, bool)
            or total < 0
        ):
            raise ValueError(
                "Semantic Scholar response total must be a non-negative integer"
            )

        page_offset = payload.get("offset", offset)
        if not isinstance(page_offset, int) or isinstance(page_offset, bool) or page_offset < 0:
            raise ValueError(
                "Semantic Scholar response offset must be a non-negative integer"
            )

        next_offset = payload.get("next")
        if next_offset is not None and (
            not isinstance(next_offset, int)
            or isinstance(next_offset, bool)
            or next_offset < 0
        ):
            raise ValueError(
                "Semantic Scholar response next must be a non-negative integer or null"
            )

        return SemanticScholarSearchPage(
            data=data,
            total=total,
            offset=page_offset,
            next=next_offset,
            payload=payload,
        )

    async def iterate_papers(
        self,
        query: str,
        *,
        limit: int = 20,
        offset: int = 0,
        fields: list[str] | None = None,
        max_results: int | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Yield all papers matching a query by following Semantic Scholar offset pagination."""
        if max_results is not None:
            if not isinstance(max_results, int) or isinstance(max_results, bool) or max_results <= 0:
                raise ValueError("max_results must be positive")

        seen_offsets: set[int] = set()
        current_offset = offset
        yielded = 0

        while True:
            if max_results is not None and yielded >= max_results:
                break

            params = self._search_params(query, limit, current_offset, fields)
            url = f"{self._base_url}/paper/search"
            response = await self._get(
                url=url,
                params=params,
                headers=self._headers(),
            )
            payload = response.json()
            if not isinstance(payload, dict):
                raise RuntimeError("Semantic Scholar response must be a JSON object")

            data = payload.get("data")
            if data is None:
                break
            if not isinstance(data, list):
                raise RuntimeError("Semantic Scholar response data must be a list")
            if not data:
                break

            for item in data:
                if not isinstance(item, dict):
                    raise RuntimeError("Semantic Scholar paper record must be a JSON object")
                yield item
                yielded += 1
                if max_results is not None and yielded >= max_results:
                    return

            next_offset = payload.get("next")
            if next_offset is None:
                break

            if not isinstance(next_offset, int) or isinstance(next_offset, bool):
                raise RuntimeError("Semantic Scholar next offset must be an integer")

            if next_offset == current_offset or next_offset in seen_offsets:
                raise RuntimeError("Pagination loop detected")

            seen_offsets.add(current_offset)
            current_offset = next_offset
