from uuid import UUID

import httpx
import pytest

from app.domain.publication import Publication
from app.domain.search import BooleanOperator, SearchGroup, SearchQuery, SearchRun, SearchTerm
from app.providers.crossref import CrossrefClient
from app.providers.openalex import OpenAlexClient
from app.providers.search.crossref import CrossrefProvider
from app.rendering.crossref import CrossrefQueryRenderer
from app.rendering.openalex import OpenAlexQueryRenderer
from app.rendering.semantic_scholar import SemanticScholarQueryRenderer
from app.services.canonical_query_validator import (
    CanonicalMatchStatus,
    validate_canonical_query,
)


def canonical_regression_query() -> SearchQuery:
    blocks = [
        [
            "Lean Management",
            "Lean Manufacturing",
            "Lean Production",
            "Kaizen",
            "Continuous Improvement",
        ],
        [
            "Energy Efficiency",
            "Energy Consumption",
            "Energy Performance",
            "Energy Saving",
            "Energy Savings",
            "Energy Management",
            "Energy Use",
        ],
        [
            "Manufacturing",
            "Production",
            "Industrial",
            "Factory",
            "Factories",
            "Manufacturing Industry",
            "Manufacturing Industries",
        ],
    ]
    return SearchQuery(
        query_id=UUID("11111111-1111-4111-8111-111111111111"),
        name="Lean energy manufacturing regression",
        version=1,
        expression=SearchGroup(
            operator=BooleanOperator.AND,
            children=[
                SearchGroup(
                    operator=BooleanOperator.OR,
                    children=[SearchTerm(value=value, exact_phrase=True) for value in block],
                )
                for block in blocks
            ],
        ),
    )


def test_canonical_hash_is_stable_and_version_sensitive() -> None:
    query = canonical_regression_query()
    equivalent = query.model_copy(update={"query_id": UUID("22222222-2222-4222-8222-222222222222")})
    next_version = query.model_copy(update={"version": 2})

    assert len(query.canonical_hash) == 64
    assert equivalent.canonical_hash == query.canonical_hash
    assert next_version.canonical_hash != query.canonical_hash


@pytest.mark.parametrize(
    "title,abstract,expected",
    [
        (
            "KAIZEN in industrial plants",
            "A case study of energy efficiency.",
            CanonicalMatchStatus.MATCH,
        ),
        (
            "Lean management and energy consumption",
            "A healthcare case study.",
            CanonicalMatchStatus.NON_MATCH,
        ),
        (
            "Lean production in a factory",
            "A productivity case study.",
            CanonicalMatchStatus.NON_MATCH,
        ),
        (
            "Energy savings in manufacturing",
            "A productivity case study.",
            CanonicalMatchStatus.NON_MATCH,
        ),
    ],
)
def test_canonical_three_block_truth_table(
    title: str,
    abstract: str,
    expected: CanonicalMatchStatus,
) -> None:
    result = validate_canonical_query(canonical_regression_query(), Publication(title=title, abstract=abstract))
    assert result.status is expected


def test_phrase_matching_requires_order_and_contiguous_tokens() -> None:
    query = SearchQuery(
        name="Phrase",
        expression=SearchTerm(value="continuous improvement", exact_phrase=True),
    )
    assert (
        validate_canonical_query(
            query,
            Publication(title="Continuous process improvement", abstract="Unrelated."),
        ).status
        is CanonicalMatchStatus.NON_MATCH
    )


def test_missing_abstract_accepts_when_title_proves_all_blocks() -> None:
    publication = Publication(title="Lean Manufacturing for ENERGY EFFICIENCY in an Industrial Factory")
    assert validate_canonical_query(canonical_regression_query(), publication).status is CanonicalMatchStatus.MATCH


def test_missing_abstract_is_auditable_as_indeterminate_when_title_cannot_prove_query() -> None:
    result = validate_canonical_query(canonical_regression_query(), Publication(title="An unrelated title"))
    assert result.status is CanonicalMatchStatus.INDETERMINATE
    assert "abstract" in result.missing_fields


@pytest.mark.anyio
async def test_openalex_request_contains_full_canonical_boolean_in_search() -> None:
    canonical = canonical_regression_query()
    rendered = OpenAlexQueryRenderer().render(canonical)

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/works"
        assert request.url.params["search"] == canonical.to_boolean_query()
        return httpx.Response(
            200,
            json={"meta": {"count": 0, "next_cursor": None}, "results": []},
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        await OpenAlexClient(http_client=client).search_works(rendered.query_string)

    assert rendered.physical_endpoint == "https://api.openalex.org/works"
    assert rendered.query_string == canonical.to_boolean_query()
    assert rendered.is_lossless is False
    assert rendered.warnings


def test_crossref_uses_bounded_lossy_candidate_plan_not_flattened_query() -> None:
    rendered = CrossrefQueryRenderer().render(canonical_regression_query())
    assert rendered.is_lossless is False
    assert rendered.metadata["candidate_queries"] == [
        '"Lean Management" "Energy Efficiency" "Manufacturing"',
        '"Lean Manufacturing" "Energy Consumption" "Production"',
        '"Lean Production" "Energy Performance" "Industrial"',
        '"Kaizen" "Energy Saving" "Factory"',
        '"Continuous Improvement" "Energy Savings" "Factories"',
        '"Lean Management" "Energy Management" "Manufacturing Industry"',
    ]
    assert len(rendered.metadata["candidate_queries"]) == 6
    assert all(
        "Energy" in query
        and any(
            term in query
            for term in ("Manufact", "Production", "Industrial", "Factor")
        )
        for query in rendered.metadata["candidate_queries"]
    )
    assert "candidate" in " ".join(rendered.warnings).casefold()


@pytest.mark.anyio
async def test_crossref_provider_executes_bounded_composite_plan_without_cartesian_product() -> None:
    canonical = canonical_regression_query()
    rendered = CrossrefQueryRenderer().render(canonical)
    requested_queries: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requested_queries.append(request.url.params["query"])
        return httpx.Response(
            200,
            json={
                "status": "ok",
                "message": {
                    "total-results": 0,
                    "next-cursor": None,
                    "items": [],
                },
            },
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = CrossrefProvider(
            client=CrossrefClient(http_client=client, requests_per_second=None),
            paginate=True,
        )
        output = await provider.search_with_raw(
            search_run=SearchRun(
                query_id=canonical.query_id,
                query_version=canonical.version,
                provider="crossref",
                rendered_query=rendered.query_string,
            ),
            search_query=canonical,
        )

    assert requested_queries == rendered.metadata["candidate_queries"]
    assert len(requested_queries) == 6
    assert output.total_count is None
    assert output.is_lossless is False
    assert output.next_cursor is None


@pytest.mark.anyio
async def test_crossref_composite_retrieval_keeps_known_positive_and_excludes_medical_management_noise() -> None:
    canonical = canonical_regression_query()
    rendered = CrossrefQueryRenderer().render(canonical)
    medical_titles = {
        "Management of side effects and complications in medical abortion",
        "Endovascular management of arterial intimal defects",
        "Optimizing the management of blunt splenic injury",
    }

    async def handler(request: httpx.Request) -> httpx.Response:
        physical_query = request.url.params["query"]
        # The fixture emulates Crossref's physical matching: broad medical
        # 'management' records never match a query retaining all AND anchors.
        assert "Energy" in physical_query
        assert any(
            term in physical_query
            for term in ("Manufact", "Production", "Industrial", "Factor")
        )
        items = (
            [
                {
                    "DOI": "10.1000/known-positive",
                    "title": ["Kaizen principles for improving energy efficiency in industrial plants"],
                }
            ]
            if physical_query == rendered.metadata["candidate_queries"][3]
            else []
        )
        return httpx.Response(
            200,
            json={"message": {"total-results": len(items), "next-cursor": None, "items": items}},
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = CrossrefProvider(
            client=CrossrefClient(http_client=client, requests_per_second=None), paginate=True
        )
        output = await provider.search_with_raw(
            search_run=SearchRun(
                query_id=canonical.query_id,
                query_version=canonical.version,
                provider="crossref",
                rendered_query=rendered.query_string,
            ),
            search_query=canonical,
        )

    assert [publication.title for publication in output.publications] == [
        "Kaizen principles for improving energy efficiency in industrial plants"
    ]
    assert not medical_titles.intersection(publication.title for publication in output.publications)


def test_semantic_scholar_regression_query_uses_bulk_boolean_operators() -> None:
    rendered = SemanticScholarQueryRenderer().render(canonical_regression_query())
    assert rendered.physical_endpoint.endswith("/paper/search/bulk")
    assert rendered.is_lossless is True
    assert " + " in rendered.query_string
    assert " | " in rendered.query_string
    assert '"Lean Management"' in rendered.query_string
    assert rendered.query_string.startswith("((")
