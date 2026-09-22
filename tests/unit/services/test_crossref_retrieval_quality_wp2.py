"""WP2 — Crossref retrieval quality and medical noise diagnostic regressions.

This test suite formalizes and verifies the diagnostic findings of v0.7.0 WP2:
1. When full metadata (title + abstract) is present, the canonical validator correctly
   rejects out-of-domain medical records, lean healthcare records, energy-only medical records,
   and manufacturing-only records as NON_MATCH.
2. When abstract metadata is missing from Crossref, the three-valued logic (PRISMA-S / recall-first)
   classifies unproven terms as INDETERMINATE, which allows 0-evidence and partial-evidence
   records to enter the candidate corpus.
3. Group evidence correctly reflects per-group matching status (0/3, 1/3, 2/3, 3/3).
4. NOT exclusions correctly invert MATCH/NON_MATCH while preserving INDETERMINATE.
5. Deterministic replay and provenance structures are preserved.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from app.api.dto.search_strategy import ConceptGroupRequest, SearchStrategyExecutionRequest
from app.domain.crossref_diagnostics import (
    RetentionOutcome,
    group_evidence_for,
)
from app.domain.publication import Publication
from app.domain.search import BooleanOperator, SearchField, SearchGroup, SearchQuery, SearchTerm
from app.providers.crossref import CrossrefClient
from app.providers.search.crossref import CrossrefProvider
from app.repositories.search_result_snapshot_repository import SqliteSearchResultSnapshotRepository
from app.repositories.search_run_checkpoint_repository import SqliteSearchRunCheckpointRepository
from app.services.canonical_query_validator import (
    CanonicalMatchStatus,
    validate_canonical_query,
)
from app.services.fetch_all_search import FetchAllSearchService


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _lean_energy_mfg_query() -> SearchQuery:
    lean_terms = [
        "Lean Management",
        "Lean Manufacturing",
        "Lean Production",
        "Toyota Production System",
        "Kaizen",
        "Continuous Improvement",
        "Just-in-Time",
    ]
    energy_terms = [
        "Energy Efficiency",
        "Energy Consumption",
        "Energy Performance",
        "Energy Saving",
        "Energy Management",
        "Energy Use",
    ]
    mfg_terms = [
        "Manufacturing",
        "Production",
        "Industrial",
        "Factory",
    ]

    lean_group = SearchGroup(
        operator=BooleanOperator.OR,
        children=[SearchTerm(value=t, exact_phrase=True, field=SearchField.ANY) for t in lean_terms],
    )
    energy_group = SearchGroup(
        operator=BooleanOperator.OR,
        children=[SearchTerm(value=t, exact_phrase=True, field=SearchField.ANY) for t in energy_terms],
    )
    mfg_group = SearchGroup(
        operator=BooleanOperator.OR,
        children=[SearchTerm(value=t, exact_phrase=True, field=SearchField.ANY) for t in mfg_terms],
    )

    return SearchQuery(
        name="Lean Energy Manufacturing SLR Strategy",
        expression=SearchGroup(operator=BooleanOperator.AND, children=[lean_group, energy_group, mfg_group]),
    )


class TestMedicalNoiseReproductionAndSemantics:
    """Test suite reproducing and explaining medical noise cases with and without abstracts."""

    @pytest.mark.parametrize(
        ("case_name", "title", "abstract", "expected_status", "expected_evidences"),
        [
            (
                "A. Clinical energy expenditure",
                "Energy expenditure and clinical outcomes in intensive care patients",
                "We measured resting energy expenditure in 50 intensive care patients.",
                CanonicalMatchStatus.NON_MATCH,
                (CanonicalMatchStatus.NON_MATCH, CanonicalMatchStatus.NON_MATCH, CanonicalMatchStatus.NON_MATCH),
            ),
            (
                "B. Lean management in hospital",
                "Lean management in hospital emergency departments",
                "Implementing lean management principles reduced emergency department wait times.",
                CanonicalMatchStatus.NON_MATCH,
                (CanonicalMatchStatus.MATCH, CanonicalMatchStatus.NON_MATCH, CanonicalMatchStatus.NON_MATCH),
            ),
            (
                "C. Cancer cell energy metabolism",
                "Energy metabolism in cancer cells",
                "Glycolysis and energy metabolism pathways were studied in cancer cell lines.",
                CanonicalMatchStatus.NON_MATCH,
                (CanonicalMatchStatus.NON_MATCH, CanonicalMatchStatus.NON_MATCH, CanonicalMatchStatus.NON_MATCH),
            ),
            (
                "D. Pharmaceutical manufacturing",
                "Manufacturing of pharmaceutical tablets",
                "Continuous manufacturing processes for oral solid dosage pharmaceutical tablets.",
                CanonicalMatchStatus.NON_MATCH,
                (CanonicalMatchStatus.NON_MATCH, CanonicalMatchStatus.NON_MATCH, CanonicalMatchStatus.MATCH),
            ),
            (
                "F. Lean + Energy in healthcare (2/3 groups)",
                "Lean management and energy efficiency in hospital operating rooms",
                "Applying lean management to optimize energy efficiency and thermal comfort in hospital operating rooms.",
                CanonicalMatchStatus.NON_MATCH,
                (CanonicalMatchStatus.MATCH, CanonicalMatchStatus.MATCH, CanonicalMatchStatus.NON_MATCH),
            ),
            (
                "G. Energy + Manufacturing without Lean (2/3 groups)",
                "Energy efficiency in automobile manufacturing plants",
                "Assessment of energy efficiency measures across automotive manufacturing assembly plants.",
                CanonicalMatchStatus.NON_MATCH,
                (CanonicalMatchStatus.NON_MATCH, CanonicalMatchStatus.MATCH, CanonicalMatchStatus.MATCH),
            ),
            (
                "H. True Positive: Lean + Energy + Manufacturing (3/3 groups)",
                "Lean manufacturing and energy efficiency in automotive assembly plants",
                "A framework combining lean manufacturing tools with energy efficiency assessments in industrial factory settings.",
                CanonicalMatchStatus.MATCH,
                (CanonicalMatchStatus.MATCH, CanonicalMatchStatus.MATCH, CanonicalMatchStatus.MATCH),
            ),
        ],
    )
    def test_complete_metadata_evaluates_exact_canonical_truth_table(
        self,
        case_name: str,
        title: str,
        abstract: str,
        expected_status: CanonicalMatchStatus,
        expected_evidences: tuple[CanonicalMatchStatus, ...],
    ) -> None:
        """When abstract is present, any missing concept group triggers NON_MATCH under AND.

        Methodological rationale: When full text metadata (title + abstract) is available,
        the closed-world assumption holds for the abstract-level screening: if a required
        concept axis is not mentioned anywhere in title or abstract, the publication fails
        the conjunction.
        """
        query = _lean_energy_mfg_query()
        pub = Publication(title=title, abstract=abstract)
        res = validate_canonical_query(query, pub)
        assert res.status is expected_status, f"Failed for {case_name}"

        evidence = group_evidence_for(query, pub)
        actual_group_statuses = tuple(e.status for e in evidence)
        assert actual_group_statuses == expected_evidences, f"Group evidence mismatch for {case_name}"

    @pytest.mark.parametrize(
        ("case_name", "title", "expected_status", "expected_evidences"),
        [
            (
                "A. Clinical energy expenditure (no abstract)",
                "Energy expenditure and clinical outcomes in intensive care patients",
                CanonicalMatchStatus.INDETERMINATE,
                (CanonicalMatchStatus.INDETERMINATE, CanonicalMatchStatus.INDETERMINATE, CanonicalMatchStatus.INDETERMINATE),
            ),
            (
                "B. Lean management in hospital (no abstract)",
                "Lean management in hospital emergency departments",
                CanonicalMatchStatus.INDETERMINATE,
                (CanonicalMatchStatus.MATCH, CanonicalMatchStatus.INDETERMINATE, CanonicalMatchStatus.INDETERMINATE),
            ),
            (
                "C. Cancer cell energy metabolism (no abstract)",
                "Energy metabolism in cancer cells",
                CanonicalMatchStatus.INDETERMINATE,
                (CanonicalMatchStatus.INDETERMINATE, CanonicalMatchStatus.INDETERMINATE, CanonicalMatchStatus.INDETERMINATE),
            ),
            (
                "D. Pharmaceutical manufacturing (no abstract)",
                "Manufacturing of pharmaceutical tablets",
                CanonicalMatchStatus.INDETERMINATE,
                (CanonicalMatchStatus.INDETERMINATE, CanonicalMatchStatus.INDETERMINATE, CanonicalMatchStatus.MATCH),
            ),
            (
                "E. Cardiovascular title with no abstract (0/3 groups)",
                "Endovascular management of arterial intimal defects",
                CanonicalMatchStatus.INDETERMINATE,
                (CanonicalMatchStatus.INDETERMINATE, CanonicalMatchStatus.INDETERMINATE, CanonicalMatchStatus.INDETERMINATE),
            ),
            (
                "F. Lean + Energy in healthcare (no abstract - 2/3 groups in title)",
                "Lean management and energy efficiency in hospital operating rooms",
                CanonicalMatchStatus.INDETERMINATE,
                (CanonicalMatchStatus.MATCH, CanonicalMatchStatus.MATCH, CanonicalMatchStatus.INDETERMINATE),
            ),
            (
                "G. Energy + Manufacturing without Lean (no abstract - 2/3 groups in title)",
                "Energy efficiency in automobile manufacturing plants",
                CanonicalMatchStatus.INDETERMINATE,
                (CanonicalMatchStatus.INDETERMINATE, CanonicalMatchStatus.MATCH, CanonicalMatchStatus.MATCH),
            ),
            (
                "H. True Positive with all 3 groups in title (no abstract)",
                "Lean manufacturing and energy efficiency in industrial factory settings",
                CanonicalMatchStatus.MATCH,
                (CanonicalMatchStatus.MATCH, CanonicalMatchStatus.MATCH, CanonicalMatchStatus.MATCH),
            ),
        ],
    )
    def test_missing_abstract_yields_indeterminate_unless_all_groups_proven_in_title(
        self,
        case_name: str,
        title: str,
        expected_status: CanonicalMatchStatus,
        expected_evidences: tuple[CanonicalMatchStatus, ...],
    ) -> None:
        """When abstract is missing, unproven terms cannot be declared false.

        Methodological rationale: PRISMA-S / SLR protocol safety dictates that
        if an unproven term was scoped to ANY (title OR abstract), and abstract is missing,
        the proposition cannot be disproven from title alone. The status is therefore
        INDETERMINATE, preserving recall.
        """
        query = _lean_energy_mfg_query()
        pub = Publication(title=title, abstract=None)
        res = validate_canonical_query(query, pub)
        assert res.status is expected_status, f"Failed for {case_name}"

        evidence = group_evidence_for(query, pub)
        actual_group_statuses = tuple(e.status for e in evidence)
        assert actual_group_statuses == expected_evidences, f"Group evidence mismatch for {case_name}"


class TestThreeValuedLogicAndNotOperators:
    """Test three-valued Kleene logic interactions including NOT and nested expressions."""

    def test_not_inverts_match_and_non_match_preserving_indeterminate(self) -> None:
        """NOT operator in 3-valued logic: NOT(MATCH)=NON_MATCH, NOT(NON_MATCH)=MATCH, NOT(INDETERMINATE)=INDETERMINATE."""
        term_health = SearchTerm(value="Healthcare", field=SearchField.ANY)
        not_health = SearchGroup(operator=BooleanOperator.NOT, children=[term_health])

        # Case 1: abstract present, contains Healthcare -> MATCH -> inverted to NON_MATCH
        pub_match = Publication(title="Lean in hospital", abstract="Healthcare processes.")
        assert validate_canonical_query(SearchQuery(name="NOT test", expression=not_health), pub_match).status is CanonicalMatchStatus.NON_MATCH

        # Case 2: abstract present, does not contain Healthcare -> NON_MATCH -> inverted to MATCH
        pub_non_match = Publication(title="Lean in factory", abstract="Automotive plant.")
        assert validate_canonical_query(SearchQuery(name="NOT test", expression=not_health), pub_non_match).status is CanonicalMatchStatus.MATCH

        # Case 3: abstract missing, title does not contain Healthcare -> INDETERMINATE -> inverted to INDETERMINATE
        pub_indet = Publication(title="Lean in factory", abstract=None)
        assert validate_canonical_query(SearchQuery(name="NOT test", expression=not_health), pub_indet).status is CanonicalMatchStatus.INDETERMINATE


@pytest.mark.anyio
class TestFetchAllRetentionAndDiagnosticsIntegration:
    """Integration test verifying fetch-all accounting and diagnostic capture for medical noise."""

    async def test_fetch_all_retains_indeterminate_and_rejects_non_match(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test_retrieval_quality.db"

        strategy_req = SearchStrategyExecutionRequest(
            publication_year_from=2020,
            publication_year_to=2025,
            providers=["crossref"],
            concept_groups=[
                ConceptGroupRequest(id="g1", name="Lean", terms=["Lean Management", "Lean Manufacturing"]),
                ConceptGroupRequest(id="g2", name="Energy", terms=["Energy Efficiency", "Energy Consumption"]),
                ConceptGroupRequest(id="g3", name="Manufacturing", terms=["Manufacturing", "Factory"]),
            ],
            languages=["en"],
            publication_types=["article"],
            open_access=False,
        )

        # Mock items returned by Crossref:
        # 1. Medical noise with abstract -> NON_MATCH -> REJECTED_CANONICAL
        item_medical_with_abs = {
            "DOI": "10.1000/medical-1",
            "title": ["Energy expenditure and clinical outcomes in intensive care patients"],
            "abstract": "We measured resting energy expenditure in 50 intensive care patients.",
            "type": "journal-article",
            "published": {"date-parts": [[2024, 1, 1]]},
            "language": "en",
            "score": 12.5,
        }
        # 2. Medical noise without abstract -> INDETERMINATE (0/3 evidence) -> RETAINED (recall-first)
        item_medical_no_abs = {
            "DOI": "10.1000/medical-2",
            "title": ["Endovascular management of arterial intimal defects"],
            "type": "journal-article",
            "published": {"date-parts": [[2024, 1, 1]]},
            "language": "en",
            "score": 10.0,
        }
        # 3. Relevant paper with abstract -> MATCH (3/3 evidence) -> RETAINED
        item_relevant = {
            "DOI": "10.1000/relevant-1",
            "title": ["Lean manufacturing and energy efficiency in factory operations"],
            "abstract": "Applying lean manufacturing and energy efficiency to factory assembly lines.",
            "type": "journal-article",
            "published": {"date-parts": [[2024, 1, 1]]},
            "language": "en",
            "score": 15.0,
        }

        async def handler(request: httpx.Request) -> httpx.Response:
            cursor = request.url.params.get("cursor", "*")
            if cursor == "*":
                return httpx.Response(
                    200,
                    json={
                        "message": {
                            "total-results": 3,
                            "items": [item_medical_with_abs, item_medical_no_abs, item_relevant],
                            "next-cursor": None,
                        }
                    },
                    request=request,
                )
            return httpx.Response(200, json={"message": {"total-results": 3, "items": [], "next-cursor": None}}, request=request)

        snapshot_repository = SqliteSearchResultSnapshotRepository(db_path)
        checkpoint_repository = SqliteSearchRunCheckpointRepository(db_path)

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
            def provider_factory(strategy: SearchStrategyExecutionRequest, client: httpx.AsyncClient) -> list[CrossrefProvider]:
                return [
                    CrossrefProvider(
                        client=CrossrefClient(http_client=http_client, requests_per_second=None),
                        paginate=True,
                    )
                ]

            service = FetchAllSearchService(
                provider_factory=provider_factory,
                snapshot_repository=snapshot_repository,
                checkpoint_repository=checkpoint_repository,
                max_pages_per_provider=20,
            )

            started = service.start("test_project", strategy_req)
            job = await service.wait(started.job_id)

        assert job is not None
        assert job.result is not None
        result = job.result
        assert result.retrieved_count == 3
        assert result.canonical_accepted_count == 1  # item_relevant
        assert result.canonical_indeterminate_count == 1  # item_medical_no_abs
        assert result.canonical_rejected_count == 1  # item_medical_with_abs
        assert result.returned_count == 2  # item_relevant (MATCH) + item_medical_no_abs (INDETERMINATE)

        # Check diagnostics recorded in service state
        assert job.job_id in service._jobs
        active_job = service._jobs[job.job_id]
        crossref_state = next(p for p in active_job.providers if p.name == "crossref")
        diagnostics = {d.doi: d for d in crossref_state.record_diagnostics}
        assert len(diagnostics) == 3

        assert diagnostics["10.1000/medical-1"].canonical_status is CanonicalMatchStatus.NON_MATCH
        assert diagnostics["10.1000/medical-1"].retention_outcome is RetentionOutcome.REJECTED_CANONICAL

        assert diagnostics["10.1000/medical-2"].canonical_status is CanonicalMatchStatus.INDETERMINATE
        assert diagnostics["10.1000/medical-2"].retention_outcome is RetentionOutcome.RETAINED

        assert diagnostics["10.1000/relevant-1"].canonical_status is CanonicalMatchStatus.MATCH
        assert diagnostics["10.1000/relevant-1"].retention_outcome is RetentionOutcome.RETAINED
