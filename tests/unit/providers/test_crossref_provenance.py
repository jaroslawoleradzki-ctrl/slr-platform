from datetime import datetime, timezone
from uuid import UUID, uuid4

import httpx
import pytest

from app.domain.search import SearchQuery, SearchRun, SearchTerm
from app.providers.crossref import CrossrefClient
from app.providers.search.crossref import CrossrefProvider

_RETRIEVED_AT = datetime(2026, 7, 24, 8, 30, tzinfo=timezone.utc)


def _search_context(
    *,
    provider: str = "crossref",
    run_query_id: UUID | None = None,
    query_version: int = 1,
) -> tuple[SearchRun, SearchQuery]:
    search_query = SearchQuery(
        query_id=uuid4(),
        name="Lean and energy",
        expression=SearchTerm(value="lean energy"),
        version=1,
    )
    search_run = SearchRun(
        query_id=search_query.query_id if run_query_id is None else run_query_id,
        query_version=query_version,
        provider=provider,
        rendered_query="lean energy",
    )
    return search_run, search_query


@pytest.mark.anyio
async def test_search_maps_crossref_provenance() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "message": {
                    "items": [
                        {
                            "DOI": " 10.1000/ABC ",
                            "title": ["Lean Energy"],
                        }
                    ]
                }
            },
            request=request,
        )

    search_run, search_query = _search_context()
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as http_client:
        provider = CrossrefProvider(
            client=CrossrefClient(http_client=http_client),
            retrieval_clock=lambda: _RETRIEVED_AT,
        )
        publications = await provider.search(
            search_run=search_run,
            search_query=search_query,
        )

    assert len(publications) == 1
    assert publications[0].title == "Lean Energy"
    assert len(publications[0].provenance) == 1
    provenance = publications[0].provenance[0]
    assert provenance.source == "crossref"
    assert provenance.source_record_id == "10.1000/abc"
    assert provenance.retrieved_at == _RETRIEVED_AT
    assert provenance.query_id == search_query.query_id
    assert provenance.run_id == search_run.run_id
    assert provenance.rendered_query == search_run.rendered_query


@pytest.mark.anyio
async def test_search_uses_one_retrieval_timestamp_for_page() -> None:
    clock_values = iter(
        [
            datetime(2026, 7, 24, 8, 30, tzinfo=timezone.utc),
            datetime(2026, 7, 24, 8, 31, tzinfo=timezone.utc),
        ]
    )

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "message": {
                    "items": [
                        {"DOI": "10.1000/1", "title": ["One"]},
                        {"DOI": "10.1000/2", "title": ["Two"]},
                    ]
                }
            },
            request=request,
        )

    search_run, search_query = _search_context()
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as http_client:
        provider = CrossrefProvider(
            client=CrossrefClient(http_client=http_client),
            retrieval_clock=lambda: next(clock_values),
        )
        publications = await provider.search(
            search_run=search_run,
            search_query=search_query,
        )

    assert publications[0].provenance[0].retrieved_at == _RETRIEVED_AT
    assert publications[1].provenance[0].retrieved_at == _RETRIEVED_AT


@pytest.mark.anyio
async def test_iterate_maps_provenance_for_each_work() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "message": {
                    "items": [{"DOI": "10.1000/1", "title": ["One"]}],
                    "next-cursor": None,
                }
            },
            request=request,
        )

    search_run, search_query = _search_context()
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as http_client:
        provider = CrossrefProvider(
            client=CrossrefClient(http_client=http_client),
            retrieval_clock=lambda: _RETRIEVED_AT,
        )
        publications = [
            publication
            async for publication in provider.iterate(
                search_run=search_run,
                search_query=search_query,
            )
        ]

    assert len(publications) == 1
    assert publications[0].provenance[0].source_record_id == "10.1000/1"


@pytest.mark.anyio
async def test_search_rejects_work_without_doi_for_provenance() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"message": {"items": [{"title": ["No DOI"]}]}},
            request=request,
        )

    search_run, search_query = _search_context()
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as http_client:
        provider = CrossrefProvider(client=CrossrefClient(http_client=http_client))
        with pytest.raises(
            ValueError,
            match="Crossref work DOI must be a non-blank string for provenance",
        ):
            await provider.search(
                search_run=search_run,
                search_query=search_query,
            )


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("provider_name", "run_query_id", "query_version", "message"),
    [
        ("openalex", None, 1, "search_run provider must be crossref"),
        (
            "crossref",
            uuid4(),
            1,
            "search_run and search_query must have the same query_id",
        ),
        (
            "crossref",
            None,
            2,
            "search_run query_version must match search_query version",
        ),
    ],
)
async def test_search_validates_search_context(
    provider_name: str,
    run_query_id: UUID | None,
    query_version: int,
    message: str,
) -> None:
    search_run, search_query = _search_context(
        provider=provider_name,
        run_query_id=run_query_id,
        query_version=query_version,
    )

    async with httpx.AsyncClient() as http_client:
        provider = CrossrefProvider(
            client=CrossrefClient(http_client=http_client)
        )
        with pytest.raises(ValueError, match=message):
            await provider.search(
                search_run=search_run,
                search_query=search_query,
            )


@pytest.mark.anyio
async def test_search_requires_client() -> None:
    search_run, search_query = _search_context()
    provider = CrossrefProvider()

    with pytest.raises(
        RuntimeError,
        match="CrossrefProvider requires a client for search operations",
    ):
        await provider.search(
            search_run=search_run,
            search_query=search_query,
        )
