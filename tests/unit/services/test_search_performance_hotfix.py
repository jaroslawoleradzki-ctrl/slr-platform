from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import patch
from uuid import uuid4

import httpx
import pytest

from app.api.dto.search_strategy import ConceptGroupRequest, SearchStrategyExecutionRequest
from app.domain.identifiers import Identifier, IdentifierType
from app.domain.provenance import ProvenanceEntry
from app.domain.publication import DocumentType, Publication
from app.domain.search import BooleanOperator, SearchGroup, SearchQuery, SearchTerm
from app.providers.search.base import ProviderSearchOutput
from app.repositories.project_publication_repository import default_project_publication_repository
from app.services.canonical_query_validator import CanonicalMatchStatus, validate_canonical_query
from app.services.fetch_all_search import FetchAllSearchService
from app.services.live_search import LiveSearchService, build_search_query
from app.services.metadata_enrichment import MetadataEnrichmentService
from app.services.search_engine import SearchEngine


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _sample_strategy() -> SearchStrategyExecutionRequest:
    return SearchStrategyExecutionRequest(
        publication_year_from=2020,
        publication_year_to=2025,
        providers=["crossref"],
        concept_groups=[
            ConceptGroupRequest(
                id="g1",
                name="Lean",
                terms=["lean production", "lean manufacturing"],
            ),
            ConceptGroupRequest(
                id="g2",
                name="Energy",
                terms=["energy efficiency"],
            ),
        ],
        languages=["en"],
        publication_types=["article"],
        open_access=False,
    )


def _canonical_query() -> SearchQuery:
    return SearchQuery(
        name="Test canonical query",
        expression=SearchGroup(
            operator=BooleanOperator.AND,
            children=[
                SearchGroup(
                    operator=BooleanOperator.OR,
                    children=[
                        SearchTerm(value="lean production", exact_phrase=True),
                        SearchTerm(value="lean manufacturing", exact_phrase=True),
                    ],
                ),
                SearchTerm(value="energy efficiency", exact_phrase=True),
            ],
        ),
        created_at=datetime.now(timezone.utc),
    )


class ScriptedProvider:
    def __init__(self, name: str, publications: list[Publication]) -> None:
        self.name = name
        self.publications = publications

    async def search_with_raw(self, **kwargs: Any) -> ProviderSearchOutput:
        return ProviderSearchOutput(
            publications=self.publications,
            raw_responses=[{"items": len(self.publications)}],
            next_cursor=None,
            total_count=len(self.publications),
        )


@pytest.mark.anyio
async def test_live_search_crossref_without_abstract_issues_zero_external_enrichment_calls() -> None:
    """Requirement A & B: LiveSearchService executes Crossref with missing abstracts without external HTTP enrichment."""
    strategy = _sample_strategy()

    http_calls: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        http_calls.append(str(request.url))
        if "api.crossref.org" in request.url.host:
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "message-type": "work-list",
                    "message": {
                        "total-results": 2,
                        "items": [
                            {
                                "DOI": "10.1000/cr_test_1",
                                "title": ["Lean manufacturing implementation in industry"],
                                "type": "journal-article",
                                "created": {"date-parts": [[2024, 1, 1]]},
                                # No abstract provided by Crossref
                            },
                            {
                                "DOI": "10.1000/cr_test_2",
                                "title": ["Unrelated robotics paper"],
                                "type": "journal-article",
                                "created": {"date-parts": [[2024, 1, 1]]},
                                # No abstract provided by Crossref
                            },
                        ],
                    },
                },
                request=request,
            )
        # If any external enrichment lookup is attempted, fail or record
        if "api.openalex.org" in request.url.host or "api.semanticscholar.org" in request.url.host:
            raise AssertionError(f"Unexpected external enrichment HTTP call during Search: {request.url}")

        return httpx.Response(404, request=request)

    repo = default_project_publication_repository()
    service = LiveSearchService(repository=repo)

    original_async_client = httpx.AsyncClient

    def mock_async_client(**kwargs: Any) -> httpx.AsyncClient:
        kwargs["transport"] = httpx.MockTransport(handler)
        return original_async_client(**kwargs)

    with patch("httpx.AsyncClient", side_effect=mock_async_client):
        execution = await service.execute("lean_energy", strategy)

    # 1. Assert exactly Crossref was called and 0 OpenAlex / Semantic Scholar calls were made
    assert len(http_calls) == 1
    assert "api.crossref.org" in http_calls[0]
    assert not any("openalex" in url for url in http_calls)
    assert not any("semanticscholar" in url for url in http_calls)

    # 2. Assert recall-first INDETERMINATE semantics
    assert len(execution.provider_results) == 1
    cr_result = execution.provider_results[0]
    assert cr_result.search_run.records_retrieved == 2

    # Both records missing abstracts are evaluated:
    # Under 3-valued Kleene logic, missing abstract cannot be ruled out as NON_MATCH,
    # so both are INDETERMINATE and retained to protect recall.
    assert len(execution.normalized_publications) == 2
    for pub in execution.normalized_publications:
        assert pub.abstract is None
        validation = validate_canonical_query(build_search_query(strategy), pub)
        assert validation.status is CanonicalMatchStatus.INDETERMINATE


@pytest.mark.anyio
async def test_fetch_all_search_issues_zero_external_enrichment_calls() -> None:
    """Requirement C: FetchAllSearchService does not invoke external enrichment lookups."""
    # 5 publications without abstract with DOIs
    pubs = [
        Publication(
            record_id=uuid4(),
            title=f"Lean manufacturing study {i}",
            abstract=None,
            identifiers=[Identifier(type=IdentifierType.DOI, value=f"10.1000/cr_fetch_{i}")],
            provenance=[
                ProvenanceEntry(
                    source="crossref",
                    source_record_id=f"10.1000/cr_fetch_{i}",
                    retrieved_at=datetime.now(timezone.utc),
                )
            ],
            publication_year=2024,
            document_type=DocumentType.JOURNAL_ARTICLE,
        )
        for i in range(5)
    ]

    provider = ScriptedProvider("crossref", pubs)

    http_calls: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        http_calls.append(str(request.url))
        return httpx.Response(404, request=request)

    service = FetchAllSearchService(
        provider_factory=lambda strategy, client: [provider],
    )

    original_async_client = httpx.AsyncClient

    def mock_async_client(**kwargs: Any) -> httpx.AsyncClient:
        kwargs["transport"] = httpx.MockTransport(handler)
        return original_async_client(**kwargs)

    with patch("httpx.AsyncClient", side_effect=mock_async_client):
        start = service.start("proj_fetch_perf", _sample_strategy())
        job = await service.wait(start.job_id)

    assert job.status == "completed"
    assert len(job.providers) == 1
    state = job.providers[0]

    # No external HTTP calls made during fetch-all
    assert len(http_calls) == 0
    assert state.fetched_count == 5
    assert state.canonical_indeterminate_count == 5
    assert state.kept_count == 5


@pytest.mark.anyio
async def test_internal_in_memory_abstract_reuse_without_network_calls() -> None:
    """Requirement 3: In-memory abstract reuse across providers works with 0 network calls."""
    doi = "10.1000/shared_doi_1"

    # Provider 1 (e.g. OpenAlex) returned abstract
    pub_with_abstract = Publication(
        record_id=uuid4(),
        title="Lean production and energy efficiency in manufacturing",
        abstract="Comprehensive analysis of energy efficiency methods in lean production factories.",
        identifiers=[Identifier(type=IdentifierType.DOI, value=doi)],
        provenance=[
            ProvenanceEntry(
                source="openalex",
                source_record_id="W12345",
                retrieved_at=datetime.now(timezone.utc),
            )
        ],
    )

    # Provider 2 (e.g. Crossref) returned candidate without abstract
    pub_without_abstract = Publication(
        record_id=uuid4(),
        title="Lean production and energy efficiency in manufacturing",
        abstract=None,
        identifiers=[Identifier(type=IdentifierType.DOI, value=doi)],
        provenance=[
            ProvenanceEntry(
                source="crossref",
                source_record_id=doi,
                retrieved_at=datetime.now(timezone.utc),
            )
        ],
    )

    p1 = ScriptedProvider("openalex", [pub_with_abstract])
    p2 = ScriptedProvider("crossref", [pub_without_abstract])

    from app.storage.raw_response_archive import RawResponseArchiveEntry

    class MockArchive:
        async def save(self, entry: RawResponseArchiveEntry) -> None:
            pass

    enricher = LiveSearchService._build_enricher(enable_external_lookups=False)
    engine = SearchEngine(
        providers=[p1, p2],
        raw_response_archive=MockArchive(),  # type: ignore[arg-type]
        metadata_enricher=enricher,
    )

    execution = await engine.execute(_canonical_query())

    # Provider 2 publication reused Provider 1's abstract in memory
    assert len(execution.provider_results) == 2
    assert enricher.stats.reused_internal == 1
    assert enricher.stats.attempted == 1
    assert enricher.stats.succeeded == 1


@pytest.mark.anyio
async def test_standalone_metadata_enrichment_service_with_external_clients_still_supported() -> None:
    """Requirement F: MetadataEnrichmentService remains functional when explicitly provided with external clients."""
    doi = "10.1000/standalone_doi"
    pub = Publication(
        record_id=uuid4(),
        title="Lean energy standalone test",
        abstract=None,
        identifiers=[Identifier(type=IdentifierType.DOI, value=doi)],
        provenance=[
            ProvenanceEntry(
                source="crossref",
                source_record_id=doi,
                retrieved_at=datetime.now(timezone.utc),
            )
        ],
    )

    async def handler(request: httpx.Request) -> httpx.Response:
        if "api.openalex.org" in request.url.host:
            return httpx.Response(
                200,
                json={
                    "id": "https://openalex.org/W999",
                    "abstract_inverted_index": {
                        "Energy": [0],
                        "efficiency": [1],
                        "in": [2],
                        "lean": [3],
                        "manufacturing.": [4],
                    },
                },
                request=request,
            )
        return httpx.Response(404, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        from app.providers.openalex import OpenAlexClient
        oa_client = OpenAlexClient(http_client=client)
        enricher = MetadataEnrichmentService(openalex_client=oa_client)

        enriched, was_enriched = await enricher.enrich_single(pub)
        assert was_enriched is True
        assert enriched.abstract == "Energy efficiency in lean manufacturing."
        assert enricher.stats.succeeded == 1
