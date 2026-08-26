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
    query = SearchQuery(
        query_id=_QUERY_ID,
        name="Lean energy",
        expression=SearchTerm(value="lean energy", exact_phrase=True),
    )
    run = SearchRun(
        run_id=_RUN_ID,
        query_id=query.query_id,
        query_version=query.version,
        provider="semantic_scholar",
        rendered_query='"lean energy"',
    )
    return run, query


def _paper(paper_id: str, title: str, *, doi: str | None = None) -> dict[str, object]:
    paper: dict[str, object] = {"paperId": paper_id, "title": title}
    if doi is not None:
        paper["externalIds"] = {"DOI": doi}
    return paper


@pytest.mark.anyio
async def test_search_with_raw_uses_bulk_endpoint_and_maps_provenance() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/graph/v1/paper/search/bulk"
        assert request.url.params["query"] == '"lean energy"'
        assert "offset" not in request.url.params
        assert "token" not in request.url.params
        assert "language" not in request.url.params["fields"].split(",")
        return httpx.Response(
            200,
            json={
                "total": 2,
                "token": "next-token",
                "data": [
                    _paper("p1", "Lean energy paper", doi="10.1000/p1"),
                    _paper("p2", "Second paper"),
                ],
            },
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        provider = SemanticScholarProvider(
            client=SemanticScholarClient(http_client=http_client, requests_per_second=None),
            retrieval_clock=lambda: _RETRIEVED_AT,
        )
        run, query = build_search_context()
        output = await provider.search_with_raw(search_run=run, search_query=query)

    assert len(output.publications) == 2
    assert output.total_count == 2
    assert output.next_cursor == "next-token"
    assert output.has_more is True
    assert output.publications[0].provenance[0].source == "semantic_scholar"
    assert output.publications[0].provenance[0].source_record_id == "p1"
    assert [identifier.type for identifier in output.publications[0].identifiers] == [
        IdentifierType.OTHER,
        IdentifierType.DOI,
    ]


@pytest.mark.anyio
async def test_search_with_raw_resumes_with_opaque_bulk_token() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["token"] == "opaque:token/2"
        return httpx.Response(
            200,
            json={"total": 1, "data": [_paper("p2", "Lean energy result")]},
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        provider = SemanticScholarProvider(
            client=SemanticScholarClient(http_client=http_client, requests_per_second=None),
            retrieval_clock=lambda: _RETRIEVED_AT,
        )
        run, query = build_search_context()
        output = await provider.search_with_raw(
            search_run=run,
            search_query=query,
            cursor="opaque:token/2",
        )
    assert output.publications[0].provenance[0].source_record_id == "p2"


@pytest.mark.anyio
async def test_search_with_raw_propagates_supported_filters() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["publicationDateOrYear"] == "2020:2025"
        assert request.url.params["publicationTypes"] == "JournalArticle,Review"
        assert request.url.params["openAccessPdf"] == ""
        return httpx.Response(200, json={"total": 0, "data": []}, request=request)

    filters = SemanticScholarSearchFilters(
        publication_year_from=2020,
        publication_year_to=2025,
        languages=("en",),
        publication_types=("article", "review"),
        open_access=True,
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        provider = SemanticScholarProvider(
            client=SemanticScholarClient(http_client=http_client, requests_per_second=None),
            filters=filters,
        )
        run, query = build_search_context()
        output = await provider.search_with_raw(search_run=run, search_query=query)
    assert output.is_lossless is False
    assert len(output.warnings) == 1
    assert "language filtering" in output.warnings[0]


@pytest.mark.anyio
async def test_search_with_raw_record_ids_are_deterministic() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"total": 1, "data": [_paper("p1", "Lean energy paper")]},
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        provider = SemanticScholarProvider(
            client=SemanticScholarClient(http_client=http_client, requests_per_second=None),
            retrieval_clock=lambda: _RETRIEVED_AT,
        )
        run, query = build_search_context()
        first = await provider.search_with_raw(search_run=run, search_query=query)
        second = await provider.search_with_raw(search_run=run, search_query=query)
    assert first.publications[0].record_id == second.publications[0].record_id


@pytest.mark.anyio
async def test_search_convenience_returns_publications() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"total": 1, "data": [_paper("p1", "Lean energy paper")]},
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        provider = SemanticScholarProvider(
            client=SemanticScholarClient(http_client=http_client, requests_per_second=None)
        )
        run, query = build_search_context()
        publications = await provider.search(search_run=run, search_query=query)
    assert [publication.title for publication in publications] == ["Lean energy paper"]


@pytest.mark.anyio
async def test_search_with_raw_requires_client() -> None:
    run, query = build_search_context()
    with pytest.raises(RuntimeError, match="requires a client"):
        await SemanticScholarProvider().search_with_raw(search_run=run, search_query=query)


@pytest.mark.anyio
async def test_search_with_raw_validates_context() -> None:
    run, query = build_search_context()
    bad_run = run.model_copy(update={"provider": "crossref"})
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200))) as client:
        provider = SemanticScholarProvider(client=SemanticScholarClient(http_client=client))
        with pytest.raises(ValueError, match="provider must be semantic_scholar"):
            await provider.search_with_raw(search_run=bad_run, search_query=query)
