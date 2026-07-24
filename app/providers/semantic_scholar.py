from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import httpx


class SemanticScholarClient:
    """Low-level asynchronous client for the Semantic Scholar Graph API."""

    def __init__(
        self,
        *,
        http_client: httpx.AsyncClient,
        base_url: str = "https://api.semanticscholar.org/graph/v1",
        api_key: str | None = None,
    ) -> None:
        self._http_client = http_client
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key.strip() if api_key is not None else None

        if api_key is not None and not api_key.strip():
            raise ValueError("api_key must not be blank")

    async def search_papers(
        self,
        query: str,
        *,
        limit: int = 20,
        offset: int = 0,
        fields: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch one page of papers matching a free-text query from Semantic Scholar."""
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

        headers: dict[str, str] = {}
        if self._api_key is not None:
            headers["x-api-key"] = self._api_key

        url = f"{self._base_url}/paper/search"
        response = await self._http_client.get(
            url,
            params=params,
            headers=headers,
        )
        response.raise_for_status()

        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("Semantic Scholar response must be a JSON object")

        data = payload.get("data")
        if data is None:
            return []
        if not isinstance(data, list):
            raise ValueError("Semantic Scholar response data must be a list")

        for item in data:
            if not isinstance(item, dict):
                raise ValueError("Semantic Scholar paper record must be a JSON object")

        return data

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
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must not be blank")
        if not isinstance(limit, int) or isinstance(limit, bool) or limit <= 0:
            raise ValueError("limit must be positive")
        if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
            raise ValueError("offset must not be negative")
        if max_results is not None:
            if not isinstance(max_results, int) or isinstance(max_results, bool) or max_results <= 0:
                raise ValueError("max_results must be positive")

        seen_offsets: set[int] = set()
        current_offset = offset
        yielded = 0

        while True:
            if max_results is not None and yielded >= max_results:
                break

            params: dict[str, Any] = {
                "query": query.strip(),
                "limit": limit,
                "offset": current_offset,
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

            headers: dict[str, str] = {}
            if self._api_key is not None:
                headers["x-api-key"] = self._api_key

            url = f"{self._base_url}/paper/search"
            response = await self._http_client.get(
                url,
                params=params,
                headers=headers,
            )
            response.raise_for_status()

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
