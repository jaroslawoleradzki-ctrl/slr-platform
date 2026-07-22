from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import httpx


class OpenAlexClient:
    """Low-level asynchronous client for the OpenAlex Works API."""

    def __init__(
        self,
        *,
        http_client: httpx.AsyncClient,
        base_url: str = "https://api.openalex.org",
        mailto: str | None = None,
    ) -> None:
        self._http_client = http_client
        self._base_url = base_url.rstrip("/")
        self._mailto = mailto.strip() if mailto is not None else None
        if self._mailto == "":
            raise ValueError("mailto must not be blank")

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

        response = await self._http_client.get(
            f"{self._base_url}/works",
            params=params,
        )
        response.raise_for_status()

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
