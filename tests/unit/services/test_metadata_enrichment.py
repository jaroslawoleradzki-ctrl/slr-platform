from datetime import datetime, timezone
from uuid import uuid4

import httpx
import pytest

from app.domain.identifiers import Identifier, IdentifierType
from app.domain.provenance import ProvenanceEntry
from app.domain.publication import Publication
from app.domain.search import BooleanOperator, SearchGroup, SearchQuery, SearchTerm
from app.providers.openalex import OpenAlexClient
from app.providers.semantic_scholar import SemanticScholarClient
from app.services.canonical_query_validator import (
    CanonicalMatchStatus,
    validate_canonical_query,
)
from app.services.metadata_enrichment import MetadataEnrichmentService
from app.services.result_merger import ResultMerger
from tests.unit.services.test_search_canonical_regression import canonical_regression_query


def make_test_publication(
    title: str,
    abstract: str | None = None,
    doi: str | None = "10.1016/j.test.2026.01",
    source: str = "crossref",
) -> Publication:
    identifiers = [Identifier(type=IdentifierType.DOI, value=doi)] if doi else []
    provenance = [
        ProvenanceEntry(
            source=source,
            source_record_id=doi or "rec-1",
            retrieved_at=datetime.now(timezone.utc),
            rendered_query=f'query="{title}"',
        )
    ]
    return Publication(
        record_id=uuid4(),
        title=title,
        abstract=abstract,
        identifiers=identifiers,
        provenance=provenance,
    )


@pytest.mark.anyio
async def test_scenario_1_internal_merge_reuses_existing_abstract_without_http() -> None:
    """Scenario 1: Crossref (no abstract) + OpenAlex (with abstract) with same DOI.
    
    Internal merge reuses OpenAlex abstract without issuing any external HTTP lookups.
    """
    doi = "10.1016/j.lean.energy.2026.100"
    crossref_pub = make_test_publication(
        title="Lean Manufacturing implementation in industry",
        abstract=None,
        doi=doi,
        source="crossref",
    )
    openalex_pub = make_test_publication(
        title="Lean Manufacturing implementation in industry",
        abstract="A case study of energy efficiency and energy management in manufacturing factories.",
        doi=doi,
        source="openalex",
    )

    known_abstracts = {doi: (openalex_pub.abstract, "openalex")}
    enricher = MetadataEnrichmentService()

    enriched, was_enriched = await enricher.enrich_single(crossref_pub, known_abstracts=known_abstracts)
    assert was_enriched is True
    assert enriched.abstract == openalex_pub.abstract
    assert enriched.discovered_by == "crossref"
    assert enriched.abstract_source == "openalex"
    assert enricher.stats.reused_internal == 1
    assert enricher.stats.attempted == 1

    validation = validate_canonical_query(canonical_regression_query(), enriched)
    assert validation.status is CanonicalMatchStatus.MATCH


@pytest.mark.anyio
async def test_scenario_2_openalex_doi_lookup_enriches_abstract_for_canonical_match() -> None:
    """Scenario 2: Crossref-only record (no abstract) -> OpenAlex DOI lookup succeeds -> MATCH."""
    doi = "10.1016/j.lean.energy.2026.200"
    crossref_pub = make_test_publication(
        title="Kaizen and continuous improvement in production",
        abstract=None,
        doi=doi,
        source="crossref",
    )

    # Inverted index for "A case study of energy efficiency in manufacturing plants."
    # positions: 0: A, 1: case, 2: study, 3: of, 4: energy, 5: efficiency, 6: in, 7: manufacturing, 8: plants.
    inverted_index = {
        "A": [0],
        "case": [1],
        "study": [2],
        "of": [3],
        "energy": [4],
        "efficiency": [5],
        "in": [6],
        "manufacturing": [7],
        "plants.": [8],
    }

    async def handler(request: httpx.Request) -> httpx.Response:
        assert f"/works/https://doi.org/{doi}" in str(request.url)
        return httpx.Response(
            200,
            json={
                "id": "https://openalex.org/W123456",
                "title": "Kaizen and continuous improvement in production",
                "abstract_inverted_index": inverted_index,
            },
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        oa_client = OpenAlexClient(http_client=client)
        enricher = MetadataEnrichmentService(openalex_client=oa_client)

        enriched, was_enriched = await enricher.enrich_single(crossref_pub)
        assert was_enriched is True
        assert enriched.abstract is not None
        assert "energy efficiency" in enriched.abstract.lower()
        assert enriched.discovered_by == "crossref"
        assert enriched.abstract_source == "openalex"
        assert "openalex" in enriched.enrichment_sources

        validation = validate_canonical_query(canonical_regression_query(), enriched)
        assert validation.status is CanonicalMatchStatus.MATCH


@pytest.mark.anyio
async def test_scenario_3_openalex_404_failover_to_semantic_scholar_doi_lookup() -> None:
    """Scenario 3: Crossref-only record (no abstract) -> OpenAlex 404 -> Semantic Scholar 200 with abstract -> MATCH."""
    doi = "10.1016/j.lean.energy.2026.300"
    crossref_pub = make_test_publication(
        title="Lean Production and continuous improvement",
        abstract=None,
        doi=doi,
        source="crossref",
    )

    async def handler(request: httpx.Request) -> httpx.Response:
        if "openalex" in str(request.url):
            return httpx.Response(404, json={"error": "not found"}, request=request)
        if "semanticscholar" in str(request.url):
            assert f"DOI:{doi}" in str(request.url)
            return httpx.Response(
                200,
                json={
                    "paperId": "s2_paper_123",
                    "title": "Lean Production and continuous improvement",
                    "abstract": "Analysis of energy consumption and energy savings in the manufacturing industry.",
                },
                request=request,
            )
        return httpx.Response(500, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        oa_client = OpenAlexClient(http_client=client)
        s2_client = SemanticScholarClient(http_client=client, requests_per_second=None)
        enricher = MetadataEnrichmentService(
            openalex_client=oa_client,
            semantic_scholar_client=s2_client,
        )

        enriched, was_enriched = await enricher.enrich_single(crossref_pub)
        assert was_enriched is True
        assert enriched.abstract is not None
        assert "energy consumption" in enriched.abstract.lower()
        assert enriched.discovered_by == "crossref"
        assert enriched.abstract_source == "semantic_scholar"
        assert "semantic_scholar" in enriched.enrichment_sources

        validation = validate_canonical_query(canonical_regression_query(), enriched)
        assert validation.status is CanonicalMatchStatus.MATCH


@pytest.mark.anyio
async def test_scenario_4_lookup_fails_leaves_indeterminate_to_protect_recall() -> None:
    """Scenario 4: Crossref-only record with missing abstract -> lookup fails -> remains INDETERMINATE."""
    doi = "10.1016/j.lean.energy.2026.400"
    crossref_pub = make_test_publication(
        title="Lean Management strategies",  # Title only has LEAN, not Energy or Context
        abstract=None,
        doi=doi,
        source="crossref",
    )

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "not found"}, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        oa_client = OpenAlexClient(http_client=client)
        s2_client = SemanticScholarClient(http_client=client, requests_per_second=None)
        enricher = MetadataEnrichmentService(
            openalex_client=oa_client,
            semantic_scholar_client=s2_client,
        )

        enriched, was_enriched = await enricher.enrich_single(crossref_pub)
        assert was_enriched is False
        assert enriched.abstract is None
        assert enricher.stats.failed == 1

        validation = validate_canonical_query(canonical_regression_query(), enriched)
        assert validation.status is CanonicalMatchStatus.INDETERMINATE
        assert "abstract" in validation.missing_fields


@pytest.mark.anyio
async def test_scenario_5_enriched_abstract_permits_definitive_non_match() -> None:
    """Scenario 5: Title has Lean, abstract has Energy, but no Context block anywhere -> definitive NON_MATCH."""
    doi = "10.1016/j.lean.energy.2026.500"
    crossref_pub = make_test_publication(
        title="Kaizen and Lean Management principles",
        abstract=None,
        doi=doi,
        source="crossref",
    )

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "id": "https://openalex.org/W555",
                "title": "Kaizen and Lean Management principles",
                "abstract_inverted_index": {
                    "Energy": [0],
                    "efficiency": [1],
                    "in": [2],
                    "hospital": [3],
                    "healthcare": [4],
                    "wards.": [5],
                },
            },
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        oa_client = OpenAlexClient(http_client=client)
        enricher = MetadataEnrichmentService(openalex_client=oa_client)

        enriched, was_enriched = await enricher.enrich_single(crossref_pub)
        assert was_enriched is True
        assert enriched.abstract == "Energy efficiency in hospital healthcare wards."

        validation = validate_canonical_query(canonical_regression_query(), enriched)
        assert validation.status is CanonicalMatchStatus.NON_MATCH


@pytest.mark.anyio
async def test_scenario_6_safety_limits_bound_lookup_budget() -> None:
    """Scenario 6: Max lookups limit prevents runaway network requests."""
    pubs = [
        make_test_publication(
            title=f"Lean Production item {i}",
            abstract=None,
            doi=f"10.1016/j.item.{i}",
            source="crossref",
        )
        for i in range(10)
    ]

    requested_urls: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requested_urls.append(str(request.url))
        return httpx.Response(404, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        oa_client = OpenAlexClient(http_client=client)
        enricher = MetadataEnrichmentService(openalex_client=oa_client, max_lookups=3)

        enriched_list = await enricher.enrich_batch(pubs)
        assert len(enriched_list) == 10
        assert len(requested_urls) == 3  # Strictly capped at max_lookups=3
        assert enricher.stats.attempted == 3
        assert enricher.stats.failed == 3


def test_result_merger_consolidates_abstract_and_provenance() -> None:
    """ResultMerger correctly adopts abstract from richer publication and merges provenance."""
    doi = "10.1016/j.merge.test.1"
    pub_crossref = make_test_publication(
        title="Lean Manufacturing for Energy Efficiency in Factories",
        abstract=None,
        doi=doi,
        source="crossref",
    )
    pub_oa = make_test_publication(
        title="Lean Manufacturing for Energy Efficiency in Factories",
        abstract="Complete abstract text with detailed manufacturing findings.",
        doi=doi,
        source="openalex",
    )

    merger = ResultMerger()
    merged = merger.merge([pub_crossref, pub_oa])
    assert len(merged) == 1
    assert merged[0].abstract == "Complete abstract text with detailed manufacturing findings."
    assert len(merged[0].provenance) == 2
    sources = {p.source for p in merged[0].provenance}
    assert sources == {"crossref", "openalex"}
