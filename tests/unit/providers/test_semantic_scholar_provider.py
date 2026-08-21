from datetime import datetime, timezone
from uuid import UUID

import httpx
import pytest

from app.domain import IdentifierType
from app.domain.search import SearchQuery, SearchRun, SearchTerm
from app.providers.search.semantic_scholar import SemanticScholarProvider
from app.providers.semantic_scholar import (
    SemanticScholarClient,
    SemanticScholarSearchFilters,
)

_QUERY_ID = UUID("00000000-0000-0000-0000-000000000001")
_RUN_ID = UUID("00000000-0000-0000-0000-000000000002")
_RETRIEVED_AT = datetime(2026, 7, 24, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def build_search_context() -> tuple[SearchRun, SearchQuery]:
    search_query = SearchQuery(
        query_id=_QUERY_ID,
        name="Lean energy",
        expression=SearchTerm(value="lean energy"),
    )
    search_run = SearchRun(
        run_id=_RUN_ID,
        query_id=search_query.query_id,
        query_version=search_query.version,
        provider="semantic_scholar",
        rendered_query="lean energy",
    )
    return search_run, search_query


def _paper(paper_id: str, title: str, *, doi: str | None = None) -> dict[str, object]:
    paper: dict[str, object] = {"paperId": paper_id, "title": title}
    if doi is not None:
        paper["externalIds"] = {"DOI": doi}
    return paper


@pytest.mark.anyio
async def test_search_with_raw_single_page() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["query"] == "lean energy"
        assert request.url.params["offset"] == "0"
        return httpx.Response(
            200,
            json={
                "total": 2,
                "offset": 0,
                "next": None,
                "data": [
                    _paper("p1", "Lean Paper One", doi="10.1000/p1"),
                    _paper("p2", "Lean Paper Two"),
                ],
            },
            request=request,
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = SemanticScholarClient(
            http_client=http_client,
            requests_per_second=None,
        )
        provider = SemanticScholarProvider(
            client=client,
            retrieval_clock=lambda: _RETRIEVED_AT,
        )
        search_run, search_query = build_search_context()
        output = await provider.search_with_raw(
            search_run=search_run,
            search_query=search_query,
            per_page=25,
        )

    assert len(output.publications) == 2
    assert output.total_count == 2
    assert output.next_cursor is None
    assert output.has_more is False
    assert len(output.raw_responses) == 1
    assert output.warnings == ()
    assert output.is_lossless is None or output.is_lossless is True

    pub = output.publications[0]
    assert pub.title == "Lean Paper One"
    assert pub.provenance[0].source == "semantic_scholar"
    assert pub.provenance[0].source_record_id == "p1"
    assert pub.identifiers[0].type == IdentifierType.OTHER
    assert pub.identifiers[0].value == "p1"
    assert pub.identifiers[1].type == IdentifierType.DOI
    assert pub.identifiers[1].value == "10.1000/p1"


@pytest.mark.anyio
async def test_search_with_raw_record_ids_are_deterministic() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "total": 1,
                "offset": 0,
                "next": None,
                "data": [_paper("p1", "Lean Paper One", doi="10.1000/p1")],
            },
            request=request,
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = SemanticScholarClient(
            http_client=http_client,
            requests_per_second=None,
        )
        provider = SemanticScholarProvider(
            client=client,
            retrieval_clock=lambda: _RETRIEVED_AT,
        )
        search_run, search_query = build_search_context()
        first = await provider.search_with_raw(
            search_run=search_run,
            search_query=search_query,
        )
        second = await provider.search_with_raw(
            search_run=search_run,
            search_query=search_query,
        )

    assert first.publications[0].record_id == second.publications[0].record_id


@pytest.mark.anyio
async def test_search_with_raw_paginated_multiple_pages() -> None:
    pages = {
        0: {
            "total": 3,
            "offset": 0,
            "next": 1,
            "data": [_paper("p1", "P1")],
        },
        1: {
            "total": 3,
            "offset": 1,
            "next": 2,
            "data": [_paper("p2", "P2")],
        },
        2: {
            "total": 3,
            "offset": 2,
            "next": None,
            "data": [_paper("p3", "P3")],
        },
    }

    async def handler(request: httpx.Request) -> httpx.Response:
        offset = int(request.url.params["offset"])
        return httpx.Response(200, json=pages[offset], request=request)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = SemanticScholarClient(
            http_client=http_client,
            requests_per_second=None,
        )
        provider = SemanticScholarProvider(
            client=client,
            retrieval_clock=lambda: _RETRIEVED_AT,
            paginate=True,
            max_results=100,
        )
        search_run, search_query = build_search_context()
        output = await provider.search_with_raw(
            search_run=search_run,
            search_query=search_query,
            per_page=1,
        )

    assert len(output.publications) == 3
    assert [p.provenance[0].source_record_id for p in output.publications] == [
        "p1",
        "p2",
        "p3",
    ]
    assert output.total_count == 3
    assert output.next_cursor is None
    assert output.has_more is False
    assert len(output.raw_responses) == 3


@pytest.mark.anyio
async def test_search_with_raw_stops_at_max_results_mid_page() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        offset = int(request.url.params["offset"])
        data = [_paper(f"p{i}", f"P{i}") for i in range(offset, offset + 10)]
        return httpx.Response(
            200,
            json={"total": 100, "offset": offset, "next": offset + 10, "data": data},
            request=request,
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = SemanticScholarClient(
            http_client=http_client,
            requests_per_second=None,
        )
        provider = SemanticScholarProvider(
            client=client,
            retrieval_clock=lambda: _RETRIEVED_AT,
            paginate=True,
            max_results=3,
        )
        search_run, search_query = build_search_context()
        output = await provider.search_with_raw(
            search_run=search_run,
            search_query=search_query,
            per_page=10,
        )

    assert len(output.publications) == 3
    assert output.total_count == 100
    assert output.next_cursor == "3"
    assert output.has_more is True
    assert output.warnings == ()


@pytest.mark.anyio
async def test_search_with_raw_resumes_from_cursor_offset() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["offset"] == "5"
        return httpx.Response(
            200,
            json={
                "total": 6,
                "offset": 5,
                "next": None,
                "data": [_paper("p5", "P5")],
            },
            request=request,
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = SemanticScholarClient(
            http_client=http_client,
            requests_per_second=None,
        )
        provider = SemanticScholarProvider(
            client=client,
            retrieval_clock=lambda: _RETRIEVED_AT,
        )
        search_run, search_query = build_search_context()
        output = await provider.search_with_raw(
            search_run=search_run,
            search_query=search_query,
            cursor="5",
        )

    assert output.publications[0].provenance[0].source_record_id == "p5"


@pytest.mark.anyio
async def test_search_with_raw_next_cursor_when_more_pages_exist() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "total": 50,
                "offset": 0,
                "next": 25,
                "data": [_paper("p1", "P1")],
            },
            request=request,
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = SemanticScholarClient(
            http_client=http_client,
            requests_per_second=None,
        )
        provider = SemanticScholarProvider(
            client=client,
            retrieval_clock=lambda: _RETRIEVED_AT,
        )
        search_run, search_query = build_search_context()
        output = await provider.search_with_raw(
            search_run=search_run,
            search_query=search_query,
            per_page=25,
        )

    assert output.next_cursor == "25"
    assert output.has_more is True


@pytest.mark.anyio
async def test_search_with_raw_truncation_warning_when_api_returns_fewer() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "total": 10,
                "offset": 0,
                "next": None,
                "data": [_paper("p1", "P1"), _paper("p2", "P2")],
            },
            request=request,
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = SemanticScholarClient(
            http_client=http_client,
            requests_per_second=None,
        )
        provider = SemanticScholarProvider(
            client=client,
            retrieval_clock=lambda: _RETRIEVED_AT,
            paginate=True,
            max_results=100,
        )
        search_run, search_query = build_search_context()
        output = await provider.search_with_raw(
            search_run=search_run,
            search_query=search_query,
        )

    assert len(output.publications) == 2
    assert output.next_cursor is None
    assert any("returned only 2 of 10" in warning for warning in output.warnings)


@pytest.mark.anyio
async def test_search_with_raw_no_truncation_warning_when_complete() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "total": 2,
                "offset": 0,
                "next": None,
                "data": [_paper("p1", "P1"), _paper("p2", "P2")],
            },
            request=request,
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = SemanticScholarClient(
            http_client=http_client,
            requests_per_second=None,
        )
        provider = SemanticScholarProvider(
            client=client,
            retrieval_clock=lambda: _RETRIEVED_AT,
        )
        search_run, search_query = build_search_context()
        output = await provider.search_with_raw(
            search_run=search_run,
            search_query=search_query,
        )

    assert output.warnings == ()


@pytest.mark.anyio
async def test_search_with_raw_filter_warnings_and_is_lossless() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"total": 0, "offset": 0, "next": None, "data": []},
            request=request,
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = SemanticScholarClient(
            http_client=http_client,
            requests_per_second=None,
        )
        provider = SemanticScholarProvider(
            client=client,
            retrieval_clock=lambda: _RETRIEVED_AT,
            filters=SemanticScholarSearchFilters(
                publication_year_from=2020,
                publication_year_to=2025,
                languages=("en",),
                publication_types=("article",),
                open_access=True,
            ),
        )
        search_run, search_query = build_search_context()
        output = await provider.search_with_raw(
            search_run=search_run,
            search_query=search_query,
        )

    joined = "\n".join(output.warnings)
    assert "year range filtering" in joined
    assert "language filtering" in joined
    assert "publication type filtering" in joined
    assert "open access filtering" in joined
    assert output.is_lossless is False


@pytest.mark.anyio
async def test_search_with_raw_requires_client() -> None:
    provider = SemanticScholarProvider(retrieval_clock=lambda: _RETRIEVED_AT)
    search_run, search_query = build_search_context()
    with pytest.raises(
        RuntimeError, match="SemanticScholarProvider requires a client"
    ):
        await provider.search_with_raw(
            search_run=search_run,
            search_query=search_query,
        )


@pytest.mark.anyio
async def test_search_with_raw_validation_context() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": []}, request=request)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = SemanticScholarClient(
            http_client=http_client,
            requests_per_second=None,
        )
        provider = SemanticScholarProvider(
            client=client,
            retrieval_clock=lambda: _RETRIEVED_AT,
        )
        search_query = SearchQuery(
            query_id=_QUERY_ID,
            name="Lean energy",
            expression=SearchTerm(value="lean energy"),
        )
        search_run = SearchRun(
            run_id=_RUN_ID,
            query_id=search_query.query_id,
            query_version=search_query.version,
            provider="crossref",
            rendered_query="lean energy",
        )
        with pytest.raises(
            ValueError, match="search_run provider must be semantic_scholar"
        ):
            await provider.search_with_raw(
                search_run=search_run,
                search_query=search_query,
            )


@pytest.mark.anyio
async def test_search_with_raw_invalid_cursor() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": []}, request=request)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = SemanticScholarClient(
            http_client=http_client,
            requests_per_second=None,
        )
        provider = SemanticScholarProvider(
            client=client,
            retrieval_clock=lambda: _RETRIEVED_AT,
        )
        search_run, search_query = build_search_context()
        with pytest.raises(
            ValueError, match="must be an offset integer string or '\\*'"
        ):
            await provider.search_with_raw(
                search_run=search_run,
                search_query=search_query,
                cursor="not-an-offset",
            )


@pytest.mark.anyio
async def test_search_convenience_returns_publications() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "total": 1,
                "offset": 0,
                "next": None,
                "data": [_paper("p1", "P1")],
            },
            request=request,
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = SemanticScholarClient(
            http_client=http_client,
            requests_per_second=None,
        )
        provider = SemanticScholarProvider(
            client=client,
            retrieval_clock=lambda: _RETRIEVED_AT,
        )
        search_run, search_query = build_search_context()
        publications = await provider.search(
            search_run=search_run,
            search_query=search_query,
        )

    assert len(publications) == 1
    assert publications[0].title == "P1"


@pytest.mark.anyio
async def test_iterate_yields_all_pages() -> None:
    pages = {
        0: {"total": 2, "offset": 0, "next": 1, "data": [_paper("p1", "P1")]},
        1: {"total": 2, "offset": 1, "next": None, "data": [_paper("p2", "P2")]},
    }

    async def handler(request: httpx.Request) -> httpx.Response:
        offset = int(request.url.params["offset"])
        return httpx.Response(200, json=pages[offset], request=request)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = SemanticScholarClient(
            http_client=http_client,
            requests_per_second=None,
        )
        provider = SemanticScholarProvider(
            client=client,
            retrieval_clock=lambda: _RETRIEVED_AT,
        )
        search_run, search_query = build_search_context()
        collected = [
            publication
            async for publication in provider.iterate(
                search_run=search_run,
                search_query=search_query,
            )
        ]

    assert len(collected) == 2
    assert [p.provenance[0].source_record_id for p in collected] == ["p1", "p2"]


@pytest.mark.anyio
async def test_max_results_validation() -> None:
    async with httpx.AsyncClient() as http_client:
        client = SemanticScholarClient(
            http_client=http_client,
            requests_per_second=None,
        )
        with pytest.raises(ValueError, match="max_results must be at least 1"):
            SemanticScholarProvider(client=client, max_results=0)
