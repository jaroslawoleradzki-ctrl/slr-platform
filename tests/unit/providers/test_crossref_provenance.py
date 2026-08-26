from datetime import datetime, timezone
from uuid import UUID, uuid4

import httpx
import pytest

from app.domain.search import SearchQuery, SearchRun, SearchTerm
from app.providers.crossref import CrossrefClient, CrossrefSearchFilters
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
                            "DOI": " https://doi.org/10.1000/ABC ",
                            "title": ["Lean Energy"],
                        }
                    ]
                }
            },
            request=request,
        )

    search_run, search_query = _search_context()
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        provider = CrossrefProvider(
            client=CrossrefClient(http_client=http_client),
            retrieval_clock=lambda: _RETRIEVED_AT,
        )
        publications = await provider.search(
            search_run=search_run,
            search_query=search_query,
        )
        repeated_publications = await provider.search(
            search_run=search_run,
            search_query=search_query,
        )

    assert len(publications) == 1
    assert publications[0].record_id == repeated_publications[0].record_id
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
async def test_search_with_raw_reuses_single_payload() -> None:
    request_count = 0
    payload = {
        "message": {
            "items": [
                {
                    "DOI": "10.1000/abc",
                    "title": ["Lean Energy"],
                }
            ]
        }
    }

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        return httpx.Response(200, json=payload, request=request)

    search_run, search_query = _search_context()
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        provider = CrossrefProvider(
            client=CrossrefClient(http_client=http_client),
            retrieval_clock=lambda: _RETRIEVED_AT,
        )
        output = await provider.search_with_raw(
            search_run=search_run,
            search_query=search_query,
        )

    assert request_count == 1
    assert output.raw_responses == [payload]
    assert [publication.title for publication in output.publications] == ["Lean Energy"]
    assert output.publications[0].provenance[0].run_id == search_run.run_id


@pytest.mark.anyio
async def test_live_provider_mode_collects_cursor_pages_with_a_bound() -> None:
    search_run, search_query = _search_context()
    requested_cursors: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        cursor = request.url.params["cursor"]
        requested_cursors.append(cursor)
        index = len(requested_cursors)
        return httpx.Response(
            200,
            json={
                "message": {
                    "items": [
                        {
                            "DOI": f"10.1000/result-{index}",
                            "title": [f"Result {index}"],
                        }
                    ],
                    "next-cursor": ("page-2" if index == 1 else "page-3"),
                }
            },
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        provider = CrossrefProvider(
            client=CrossrefClient(http_client=http_client),
            paginate=True,
            max_results=2,
        )
        output = await provider.search_with_raw(
            search_run=search_run,
            search_query=search_query,
        )

    assert requested_cursors == ["*", "page-2"]
    assert [publication.title for publication in output.publications] == [
        "Result 1",
        "Result 2",
    ]
    assert len(output.raw_responses) == 2


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
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
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
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
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
async def test_search_preserves_work_without_doi_with_deterministic_fallback_provenance() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"message": {"items": [{"title": ["No DOI Work"], "published": {"date-parts": [[2023]]}}]}},
            request=request,
        )

    search_run, search_query = _search_context()
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        provider = CrossrefProvider(
            client=CrossrefClient(http_client=http_client),
            retrieval_clock=lambda: _RETRIEVED_AT,
        )
        publications = await provider.search(
            search_run=search_run,
            search_query=search_query,
        )
        repeated_publications = await provider.search(
            search_run=search_run,
            search_query=search_query,
        )

    assert len(publications) == 1
    assert publications[0].title == "No DOI Work"
    assert publications[0].identifiers == []
    assert len(publications[0].provenance) == 1
    provenance = publications[0].provenance[0]
    assert provenance.source == "crossref"
    assert provenance.source_record_id == "fallback:no doi work:2023"
    assert publications[0].record_id == repeated_publications[0].record_id


@pytest.mark.anyio
async def test_search_preserves_work_without_abstract() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"message": {"items": [{"title": ["No Abstract Work"], "DOI": "10.1000/no-abs"}]}},
            request=request,
        )

    search_run, search_query = _search_context()
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        provider = CrossrefProvider(
            client=CrossrefClient(http_client=http_client),
            retrieval_clock=lambda: _RETRIEVED_AT,
        )
        publications = await provider.search(
            search_run=search_run,
            search_query=search_query,
        )

    assert len(publications) == 1
    assert publications[0].title == "No Abstract Work"
    assert publications[0].abstract is None
    assert publications[0].identifiers[0].value == "10.1000/no-abs"


@pytest.mark.anyio
async def test_search_with_raw_returns_total_count_next_cursor_and_has_more() -> None:
    payload = {
        "message": {
            "total-results": 1420,
            "next-cursor": "cursor-page-2",
            "items": [{"DOI": "10.1000/item1", "title": ["Item 1"]}],
        }
    }

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload, request=request)

    search_run, search_query = _search_context()
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        provider = CrossrefProvider(
            client=CrossrefClient(http_client=http_client),
            retrieval_clock=lambda: _RETRIEVED_AT,
        )
        output = await provider.search_with_raw(
            search_run=search_run,
            search_query=search_query,
            cursor="*",
        )

    assert output.total_count == 1420
    assert output.next_cursor == "cursor-page-2"
    assert output.has_more is True
    assert len(output.publications) == 1


@pytest.mark.anyio
async def test_search_with_raw_empty_page_returns_has_more_false() -> None:
    payload = {
        "message": {
            "total-results": 0,
            "next-cursor": "cursor-empty",
            "items": [],
        }
    }

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload, request=request)

    search_run, search_query = _search_context()
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        provider = CrossrefProvider(
            client=CrossrefClient(http_client=http_client),
            retrieval_clock=lambda: _RETRIEVED_AT,
        )
        output = await provider.search_with_raw(
            search_run=search_run,
            search_query=search_query,
            cursor="*",
        )

    assert output.total_count == 0
    assert output.next_cursor is None
    assert output.has_more is False
    assert output.publications == []


@pytest.mark.anyio
async def test_search_with_raw_repeating_cursor_returns_has_more_false() -> None:
    payload = {
        "message": {
            "total-results": 1,
            "next-cursor": "same-cursor",
            "items": [{"DOI": "10.1000/item1", "title": ["Item 1"]}],
        }
    }

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload, request=request)

    search_run, search_query = _search_context()
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        provider = CrossrefProvider(
            client=CrossrefClient(http_client=http_client),
            retrieval_clock=lambda: _RETRIEVED_AT,
        )
        output = await provider.search_with_raw(
            search_run=search_run,
            search_query=search_query,
            cursor="same-cursor",
        )

    assert output.total_count == 1
    assert output.next_cursor is None
    assert output.has_more is False


@pytest.mark.anyio
async def test_search_paginated_with_raw_fetches_more_than_100_records() -> None:
    search_run, search_query = _search_context()
    requested_cursors: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        cursor = request.url.params["cursor"]
        requested_cursors.append(cursor)
        page_num = len(requested_cursors)
        items = [{"DOI": f"10.1000/item-{page_num}-{i}", "title": [f"Item {page_num}-{i}"]} for i in range(50)]
        next_cursor = f"cursor-page-{page_num + 1}"
        return httpx.Response(
            200,
            json={
                "message": {
                    "total-results": 500,
                    "items": items,
                    "next-cursor": next_cursor,
                }
            },
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        provider = CrossrefProvider(
            client=CrossrefClient(http_client=http_client),
            paginate=True,
            max_results=150,
        )
        output = await provider.search_with_raw(
            search_run=search_run,
            search_query=search_query,
            rows=50,
            cursor="*",
        )

    assert requested_cursors == ["*", "cursor-page-2", "cursor-page-3"]
    assert len(output.publications) == 150
    assert len(output.raw_responses) == 3
    assert output.total_count == 500
    assert output.next_cursor == "cursor-page-4"
    assert output.has_more is True


@pytest.mark.anyio
async def test_search_with_raw_propagates_filters_and_warnings() -> None:
    payload = {
        "message": {
            "total-results": 10,
            "next-cursor": None,
            "items": [{"DOI": "10.1000/f1", "title": ["Filtered 1"]}],
        }
    }

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["filter"] == "from-pub-date:2021-01-01,until-pub-date:2025-12-31,type:journal-article"
        return httpx.Response(200, json=payload, request=request)

    search_run, search_query = _search_context()
    filters = CrossrefSearchFilters(
        publication_year_from=2021,
        publication_year_to=2025,
        languages=("en",),
        publication_types=("article", "review"),
        open_access=True,
    )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        provider = CrossrefProvider(
            client=CrossrefClient(http_client=http_client),
            filters=filters,
        )
        output = await provider.search_with_raw(
            search_run=search_run,
            search_query=search_query,
        )

    assert len(output.warnings) == 4
    assert any("canonical validation" in warning for warning in output.warnings)
    assert output.is_lossless is False
    assert output.total_count == 10
    assert len(output.publications) == 1


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
        provider = CrossrefProvider(client=CrossrefClient(http_client=http_client))
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
