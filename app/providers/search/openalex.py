from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from datetime import datetime, timezone
from typing import Any

from app.domain.provenance import ProvenanceEntry
from app.domain.publication import Publication
from app.domain.search import SearchQuery, SearchRun
from app.providers.openalex import OpenAlexClient


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class OpenAlexProvider:
    """Map OpenAlex Works responses to canonical publications."""

    name = "openalex"

    def __init__(
        self,
        *,
        client: OpenAlexClient,
        retrieval_clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._client = client
        self._retrieval_clock = retrieval_clock

    async def search(
        self,
        *,
        search_run: SearchRun,
        search_query: SearchQuery,
        per_page: int = 25,
        cursor: str = "*",
    ) -> list[Publication]:
        """Fetch and map one page using explicit, auditable search context."""

        self._validate_search_context(search_run, search_query)
        payload = await self._client.search_works(
            search_run.rendered_query,
            per_page=per_page,
            cursor=cursor,
        )

        results = payload.get("results")
        if not isinstance(results, list):
            raise ValueError("OpenAlex response results must be a list")

        retrieved_at = self._retrieval_clock()
        publications: list[Publication] = []
        for work in results:
            if not isinstance(work, dict):
                raise ValueError("OpenAlex work must be a JSON object")
            publications.append(
                self._map_work(
                    work,
                    search_run=search_run,
                    search_query=search_query,
                    retrieved_at=retrieved_at,
                )
            )
        return publications

    async def iterate(
        self,
        *,
        search_run: SearchRun,
        search_query: SearchQuery,
        per_page: int = 200,
    ) -> AsyncIterator[Publication]:
        """Yield mapped publications across all cursor pages."""

        self._validate_search_context(search_run, search_query)
        async for work in self._client.iterate_works(
            search_run.rendered_query,
            per_page=per_page,
        ):
            yield self._map_work(
                work,
                search_run=search_run,
                search_query=search_query,
                retrieved_at=self._retrieval_clock(),
            )

    def _map_work(
        self,
        work: dict[str, Any],
        *,
        search_run: SearchRun,
        search_query: SearchQuery,
        retrieved_at: datetime,
    ) -> Publication:
        source_record_id = work.get("id")
        if not isinstance(source_record_id, str) or not source_record_id.strip():
            raise ValueError("OpenAlex work id must be a non-blank string")

        title = work.get("title")
        if not isinstance(title, str) or not title.strip():
            raise ValueError("OpenAlex work title must be a non-blank string")

        return Publication(
            title=title,
            provenance=[
                ProvenanceEntry(
                    source=self.name,
                    source_record_id=source_record_id,
                    retrieved_at=retrieved_at,
                    query_id=search_query.query_id,
                    run_id=search_run.run_id,
                    rendered_query=search_run.rendered_query,
                )
            ],
        )

    def _validate_search_context(
        self,
        search_run: SearchRun,
        search_query: SearchQuery,
    ) -> None:
        if search_run.provider.casefold() != self.name:
            raise ValueError("search_run provider must be openalex")
        if search_run.query_id != search_query.query_id:
            raise ValueError("search_run and search_query must have the same query_id")
        if search_run.query_version != search_query.version:
            raise ValueError(
                "search_run query_version must match search_query version"
            )
