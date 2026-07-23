from __future__ import annotations

from typing import Any

import httpx

_USER_AGENT = (
    "slr-platform/0.1.0 "
    "(https://github.com/jaroslawoleradzki-ctrl/slr-platform)"
)


class CrossrefClient:
    """Low-level asynchronous client for the Crossref Works API."""

    def __init__(
        self,
        *,
        http_client: httpx.AsyncClient,
        base_url: str = "https://api.crossref.org",
    ) -> None:
        self._http_client = http_client
        self._base_url = base_url.rstrip("/")

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

        response = await self._http_client.get(
            f"{self._base_url}/works",
            params=params,
            headers={"User-Agent": _USER_AGENT},
        )
        response.raise_for_status()

        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("Crossref response must be a JSON object")

        message = payload.get("message")
        if not isinstance(message, dict):
            raise ValueError("Crossref response message must be a JSON object")
        if not isinstance(message.get("items"), list):
            raise ValueError("Crossref response message.items must be a list")

        return payload
