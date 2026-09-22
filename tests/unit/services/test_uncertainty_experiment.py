"""WP4 — uncertainty policy experiment regressions (local fixtures only)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from app.api.dto.search_strategy import ConceptGroupRequest, SearchStrategyExecutionRequest
from app.domain.provenance import ProvenanceEntry
from app.domain.publication import Publication
from app.domain.search import BooleanOperator, SearchField, SearchGroup, SearchQuery, SearchTerm
from app.providers.search.base import ProviderSearchOutput
from app.repositories.search_result_snapshot_repository import SqliteSearchResultSnapshotRepository
from app.repositories.search_run_checkpoint_repository import SqliteSearchRunCheckpointRepository
from app.services.canonical_query_validator import CanonicalMatchStatus
from app.services.fetch_all_search import FetchAllSearchService
from app.services.live_search import build_search_query
from app.services.uncertainty_experiment import (
    PolicyScenario,
    ScreeningPopulation,
    UncertaintyCandidate,
    UncertaintyTier,
    assign_population,
    candidate_from_evidence_dict,
    classify_candidate,
    classify_tier,
    evaluate_policy,
    run_experiment,
)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _three_group_query() -> SearchQuery:
    return SearchQuery(
        name="Neutral three-group query",
        expression=SearchGroup(
            operator=BooleanOperator.AND,
            children=[
                SearchGroup(
                    operator=BooleanOperator.OR,
                    children=[
                        SearchTerm(value="Alpha", exact_phrase=True),
                        SearchTerm(value="Beta", exact_phrase=True),
                    ],
                ),
                SearchTerm(value="Gamma", exact_phrase=True),
                SearchTerm(value="Delta", exact_phrase=True),
            ],
        ),
    )


def _pub(title: str, abstract: str | None, *, doi_suffix: str) -> Publication:
    return Publication(
        title=title,
        abstract=abstract,
        publication_year=2024,
        identifiers=[],
        provenance=[
            ProvenanceEntry(
                source="crossref",
                source_record_id=f"10.1000/{doi_suffix}",
                run_id=uuid4(),
                retrieved_at=datetime.now(timezone.utc),
            )
        ],
    )


_MATCH_PUB = _pub("Alpha Gamma Delta breakthrough", "Alpha Gamma Delta research.", doi_suffix="match")
_NON_MATCH_PUB = _pub("Unrelated ceramics overview", "Kiln temperature survey.", doi_suffix="nonmatch")
_NO_EVIDENCE_PUB = _pub("Unrelated robotics paper", None, doi_suffix="noevidence")
_WEAK_PUB = _pub("Alpha rotor dynamics", None, doi_suffix="weak")
_STRONG_PUB = _pub("Alpha Gamma turbine study", None, doi_suffix="strong")


def test_match_classification() -> None:
    classified = classify_candidate(_three_group_query(), _MATCH_PUB, candidate_id="m")
    assert classified.candidate.canonical_status is CanonicalMatchStatus.MATCH
    assert classified.candidate.positive_group_count == 3
    assert classified.candidate.evidenced_group_count == 3
    assert classified.tier is UncertaintyTier.MATCH


def test_non_match_classification() -> None:
    classified = classify_candidate(_three_group_query(), _NON_MATCH_PUB, candidate_id="n")
    assert classified.candidate.canonical_status is CanonicalMatchStatus.NON_MATCH
    assert classified.tier is UncertaintyTier.NON_MATCH


def test_indeterminate_with_zero_evidence() -> None:
    classified = classify_candidate(_three_group_query(), _NO_EVIDENCE_PUB, candidate_id="z")
    assert classified.candidate.canonical_status is CanonicalMatchStatus.INDETERMINATE
    assert classified.candidate.evidenced_group_count == 0
    assert classified.candidate.abstract_missing is True
    assert classified.tier is UncertaintyTier.UNCERTAIN_NO_EVIDENCE


def test_indeterminate_with_partial_evidence() -> None:
    weak = classify_candidate(_three_group_query(), _WEAK_PUB, candidate_id="w")
    assert weak.candidate.canonical_status is CanonicalMatchStatus.INDETERMINATE
    assert weak.candidate.evidenced_group_count == 1
    assert weak.tier is UncertaintyTier.UNCERTAIN_WEAK
    strong = classify_candidate(_three_group_query(), _STRONG_PUB, candidate_id="s")
    assert strong.candidate.canonical_status is CanonicalMatchStatus.INDETERMINATE
    assert strong.candidate.evidenced_group_count == 2
    assert strong.tier is UncertaintyTier.UNCERTAIN_STRONG


def test_indeterminate_with_full_observable_evidence_but_missing_field() -> None:
    classified = classify_candidate(_three_group_query(), _STRONG_PUB, candidate_id="s")
    assert classified.candidate.evidenced_group_count == 2
    assert classified.candidate.positive_group_count == 3
    assert classified.candidate.abstract_missing is True
    assert "abstract" in classified.candidate.missing_fields
    assert classified.tier is UncertaintyTier.UNCERTAIN_STRONG


def test_missing_abstract_is_measurable() -> None:
    query = _three_group_query()
    classified = [
        classify_candidate(query, pub, candidate_id=str(index))
        for index, pub in enumerate([_MATCH_PUB, _NO_EVIDENCE_PUB, _WEAK_PUB, _STRONG_PUB])
    ]
    result = run_experiment(classified, scenarios=(PolicyScenario.CURRENT_RECALL_FIRST,))
    assert result.missing_abstract_count == 3
    assert result.missing_fields_distribution == {"abstract": 3}


def test_multiple_missing_fields() -> None:
    query = SearchQuery(
        name="Scoped fields query",
        expression=SearchGroup(
            operator=BooleanOperator.AND,
            children=[
                SearchTerm(value="Alpha", exact_phrase=True),
                SearchTerm(value="Gamma", exact_phrase=True, field=SearchField.KEYWORDS),
                SearchTerm(value="Delta", exact_phrase=True, field=SearchField.AUTHOR),
            ],
        ),
    )
    classified = classify_candidate(query, _pub("Alpha study", None, doi_suffix="scoped"), candidate_id="scoped")
    assert classified.candidate.canonical_status is CanonicalMatchStatus.INDETERMINATE
    assert classified.candidate.evidenced_group_count == 1
    assert set(classified.candidate.missing_fields) == {"abstract", "keywords", "author"}
    assert classified.tier is UncertaintyTier.UNCERTAIN_WEAK


class _ScriptedProvider:
    name = "crossref"

    def __init__(self, publications: list[Publication]) -> None:
        self._publications = publications

    async def search_with_raw(self, **kwargs: Any) -> ProviderSearchOutput:
        search_run = kwargs["search_run"]
        search_query = kwargs["search_query"]
        mapped = [
            publication.model_copy(
                update={
                    "provenance": [
                        ProvenanceEntry(
                            source="crossref",
                            source_record_id=publication.provenance[0].source_record_id,
                            run_id=search_run.run_id,
                            query_id=search_query.query_id,
                            retrieved_at=datetime.now(timezone.utc),
                        )
                    ]
                }
            )
            for publication in self._publications
        ]
        return ProviderSearchOutput(publications=mapped, raw_responses=[{}], next_cursor=None)


def _strategy_request() -> SearchStrategyExecutionRequest:
    return SearchStrategyExecutionRequest(
        publication_year_from=2020,
        publication_year_to=2025,
        providers=["crossref"],
        concept_groups=[
            ConceptGroupRequest(id="g1", name="First", terms=["Alpha", "Beta"]),
            ConceptGroupRequest(id="g2", name="Second", terms=["Gamma"]),
            ConceptGroupRequest(id="g3", name="Third", terms=["Delta"]),
        ],
    )


@pytest.mark.anyio
async def test_current_recall_first_reproduces_retention(tmp_path: Path) -> None:
    inputs = [_MATCH_PUB, _NO_EVIDENCE_PUB, _WEAK_PUB, _STRONG_PUB, _NON_MATCH_PUB]
    service = FetchAllSearchService(
        provider_factory=lambda strategy, client: [_ScriptedProvider(inputs)],
        snapshot_repository=SqliteSearchResultSnapshotRepository(tmp_path / "wp4.db"),
        checkpoint_repository=SqliteSearchRunCheckpointRepository(tmp_path / "wp4.db"),
    )
    job = await service.wait(service.start("wp4-recall", _strategy_request()).job_id)
    assert job.status == "completed"
    kept_ids = {publication.provenance[0].source_record_id for state in job.providers for publication in state.kept_records}

    classified = [
        classify_candidate(job.query, publication, candidate_id=publication.provenance[0].source_record_id)
        for publication in inputs
    ]
    evaluation = evaluate_policy(classified, PolicyScenario.CURRENT_RECALL_FIRST)
    main_ids = {
        assignment.candidate_id for assignment in evaluation.assignments if assignment.population is ScreeningPopulation.MAIN
    }
    rejected_ids = {
        assignment.candidate_id
        for assignment in evaluation.assignments
        if assignment.population is ScreeningPopulation.REJECTED
    }
    assert main_ids == kept_ids
    assert rejected_ids == {"10.1000/nonmatch"}
    assert evaluation.discarded_uncertain_count == 0


def test_execution_ineligible_match_is_not_in_main_population() -> None:
    classified = classify_candidate(
        _three_group_query(),
        _MATCH_PUB,
        candidate_id="constraint-match",
        execution_eligible=False,
    )
    assert classified.candidate.canonical_status is CanonicalMatchStatus.MATCH
    result = run_experiment([classified])
    for evaluation in result.policies.values():
        assert evaluation.main_count == 0
        assert evaluation.execution_ineligible_count == 1
        assert evaluation.rejected_count == 0


def test_execution_ineligible_indeterminate_is_not_silently_discarded() -> None:
    classified = classify_candidate(
        _three_group_query(),
        _NO_EVIDENCE_PUB,
        candidate_id="constraint-indeterminate",
        execution_eligible=False,
    )
    assert classified.candidate.canonical_status is CanonicalMatchStatus.INDETERMINATE
    result = run_experiment([classified])
    for evaluation in result.policies.values():
        assert evaluation.main_count == 0
        assert evaluation.uncertainty_count == 0
        assert evaluation.execution_ineligible_count == 1
        assert evaluation.discarded_uncertain_count == 0


def test_separate_all_uncertain_moves_but_deletes_nothing() -> None:
    query = _three_group_query()
    pubs = [_MATCH_PUB, _NO_EVIDENCE_PUB, _WEAK_PUB, _STRONG_PUB, _NON_MATCH_PUB]
    classified = [classify_candidate(query, pub, candidate_id=f"c{index}") for index, pub in enumerate(pubs)]
    evaluation = evaluate_policy(classified, PolicyScenario.SEPARATE_ALL_UNCERTAIN)
    assert evaluation.main_count == 1
    assert evaluation.uncertainty_count == 3
    assert evaluation.rejected_count == 1
    assert evaluation.discarded_uncertain_count == 0
    assert set(evaluation.uncertainty_by_tier) == {
        UncertaintyTier.UNCERTAIN_NO_EVIDENCE.value,
        UncertaintyTier.UNCERTAIN_WEAK.value,
        UncertaintyTier.UNCERTAIN_STRONG.value,
    }


def test_evidence_tiered_scenario_separates_strengths() -> None:
    query = _three_group_query()
    pubs = [_MATCH_PUB, _NO_EVIDENCE_PUB, _WEAK_PUB, _STRONG_PUB, _NON_MATCH_PUB]
    classified = [classify_candidate(query, pub, candidate_id=f"c{index}") for index, pub in enumerate(pubs)]
    evaluation = evaluate_policy(classified, PolicyScenario.EVIDENCE_TIERED_UNCERTAIN)
    assert evaluation.main_count == 1
    assert evaluation.uncertainty_count == 3
    assert evaluation.uncertainty_by_tier == {
        UncertaintyTier.UNCERTAIN_NO_EVIDENCE.value: 1,
        UncertaintyTier.UNCERTAIN_STRONG.value: 1,
        UncertaintyTier.UNCERTAIN_WEAK.value: 1,
    }
    assert evaluation.rejected_count == 1
    assert evaluation.discarded_uncertain_count == 0


def test_no_policy_silently_discards_indeterminate() -> None:
    query = _three_group_query()
    pubs = [_MATCH_PUB, _NO_EVIDENCE_PUB, _WEAK_PUB, _STRONG_PUB, _NON_MATCH_PUB]
    classified = [classify_candidate(query, pub, candidate_id=f"c{index}") for index, pub in enumerate(pubs)]
    result = run_experiment(classified)
    assert result.total_candidates == 5
    for scenario, evaluation in result.policies.items():
        accounted = evaluation.main_count + evaluation.uncertainty_count + evaluation.rejected_count
        assert accounted == 5, scenario
        assert evaluation.discarded_uncertain_count == 0, scenario


def test_deterministic_output() -> None:
    query = _three_group_query()
    pubs = [_STRONG_PUB, _MATCH_PUB, _NO_EVIDENCE_PUB, _NON_MATCH_PUB, _WEAK_PUB]
    first = run_experiment([classify_candidate(query, pub, candidate_id=f"c{index}") for index, pub in enumerate(pubs)])
    second = run_experiment([classify_candidate(query, pub, candidate_id=f"c{index}") for index, pub in enumerate(pubs)])
    assert first == second
    reordered = run_experiment(
        [classify_candidate(query, pub, candidate_id=f"r{index}") for index, pub in enumerate(reversed(pubs))]
    )
    assert reordered.evidence_distribution == first.evidence_distribution
    assert reordered.missing_fields_distribution == first.missing_fields_distribution
    assert {scenario: evaluation.main_count for scenario, evaluation in reordered.policies.items()} == {
        scenario: evaluation.main_count for scenario, evaluation in first.policies.items()
    }


def test_generic_behavior_with_different_group_counts() -> None:
    two_group = SearchQuery(
        name="Two groups",
        expression=SearchGroup(
            operator=BooleanOperator.AND,
            children=[
                SearchGroup(
                    operator=BooleanOperator.OR,
                    children=[
                        SearchTerm(value="Epsilon", exact_phrase=True),
                        SearchTerm(value="Zeta", exact_phrase=True),
                    ],
                ),
                SearchTerm(value="Eta", exact_phrase=True),
            ],
        ),
    )
    one_of_two = classify_candidate(two_group, _pub("Epsilon apparatus", None, doi_suffix="g2"), candidate_id="g2")
    assert one_of_two.candidate.positive_group_count == 2
    assert one_of_two.candidate.evidenced_group_count == 1
    assert one_of_two.tier is UncertaintyTier.UNCERTAIN_STRONG

    four_group = SearchQuery(
        name="Four groups",
        expression=SearchGroup(
            operator=BooleanOperator.AND,
            children=[SearchTerm(value=term, exact_phrase=True) for term in ("A", "B", "C", "D")],
        ),
    )
    two_of_four = classify_candidate(
        four_group, _pub("A B apparatus", None, doi_suffix="g4"), candidate_id="g4"
    )
    assert two_of_four.candidate.positive_group_count == 4
    assert two_of_four.candidate.evidenced_group_count == 2
    assert two_of_four.tier is UncertaintyTier.UNCERTAIN_WEAK
    three_of_four = classify_candidate(
        four_group, _pub("A B C device", None, doi_suffix="g4b"), candidate_id="g4b"
    )
    assert three_of_four.tier is UncertaintyTier.UNCERTAIN_STRONG


def test_evidence_dict_adapter_boundary() -> None:
    candidate = candidate_from_evidence_dict(
        {
            "candidate_id": "wp2-row-1",
            "canonical_status": "indeterminate",
            "positive_group_count": 3,
            "evidenced_group_count": 1,
            "missing_fields": ["abstract"],
            "abstract_missing": True,
            "group_statuses": ["match", "indeterminate", "indeterminate"],
            # Unknown future keys must not break the engine.
            "physical_query": '"Alpha" "Gamma"',
            "provider_score": 7.5,
        }
    )
    assert classify_tier(candidate) is UncertaintyTier.UNCERTAIN_WEAK
    assert candidate.abstract_missing is True


def test_diagnosis_style_example_comparison() -> None:
    """Fixture modeled on the diagnosis sample (not a population claim)."""
    query = _three_group_query()
    dataset = [
        ("match-1", _MATCH_PUB),
        ("nonmatch-1", _NON_MATCH_PUB),
        ("indet-0", _NO_EVIDENCE_PUB),
        ("indet-1", _WEAK_PUB),
        ("indet-2", _STRONG_PUB),
    ]
    classified = [classify_candidate(query, pub, candidate_id=name) for name, pub in dataset]
    result = run_experiment(classified)
    assert (result.match_count, result.non_match_count, result.indeterminate_count) == (1, 1, 3)
    assert result.evidence_distribution == {0: 1, 1: 1, 2: 1}
    assert result.missing_abstract_count == 3
    recall_first = result.policies[PolicyScenario.CURRENT_RECALL_FIRST]
    assert (recall_first.main_count, recall_first.uncertainty_count, recall_first.rejected_count) == (4, 0, 1)
    separate = result.policies[PolicyScenario.SEPARATE_ALL_UNCERTAIN]
    assert (separate.main_count, separate.uncertainty_count, separate.rejected_count) == (1, 3, 1)
    tiered = result.policies[PolicyScenario.EVIDENCE_TIERED_UNCERTAIN]
    assert tiered.uncertainty_by_tier == {
        "uncertain_no_evidence": 1,
        "uncertain_strong": 1,
        "uncertain_weak": 1,
    }
    unevidenced_only = result.policies[PolicyScenario.SEPARATE_UNEVIDENCED_ONLY]
    assert (unevidenced_only.main_count, unevidenced_only.uncertainty_count) == (3, 1)
    assert all(evaluation.discarded_uncertain_count == 0 for evaluation in result.policies.values())


def test_tier_assignment_table() -> None:
    query = _three_group_query()
    by_id = {
        name: classify_candidate(query, pub, candidate_id=name)
        for name, pub in [
            ("m", _MATCH_PUB),
            ("n", _NON_MATCH_PUB),
            ("z", _NO_EVIDENCE_PUB),
            ("w", _WEAK_PUB),
            ("s", _STRONG_PUB),
        ]
    }
    assert assign_population(by_id["m"].tier, PolicyScenario.SEPARATE_UNEVIDENCED_ONLY) is ScreeningPopulation.MAIN
    assert assign_population(by_id["w"].tier, PolicyScenario.SEPARATE_UNEVIDENCED_ONLY) is ScreeningPopulation.MAIN
    assert (
        assign_population(by_id["z"].tier, PolicyScenario.SEPARATE_UNEVIDENCED_ONLY) is ScreeningPopulation.UNCERTAINTY
    )
    assert assign_population(by_id["n"].tier, PolicyScenario.SEPARATE_UNEVIDENCED_ONLY) is ScreeningPopulation.REJECTED


def test_invalid_evidence_rejected() -> None:
    base: dict[str, object] = {
        "candidate_id": "m",
        "canonical_status": "match",
        "positive_group_count": 3,
        "evidenced_group_count": 3,
    }
    with pytest.raises(ValueError):
        UncertaintyCandidate.model_validate({**base, "evidenced_group_count": 9})
    with pytest.raises(ValueError):
        UncertaintyCandidate.model_validate({**base, "evidenced_group_count": 1})
    with pytest.raises(ValueError):
        UncertaintyCandidate.model_validate(
            {**base, "canonical_status": "indeterminate", "evidenced_group_count": 3}
        )


def test_strategy_built_query_classifies() -> None:
    query = build_search_query(_strategy_request())
    classified = classify_candidate(
        query, _pub("Alpha Gamma Delta trial", "Alpha Gamma Delta methods.", doi_suffix="live"), candidate_id="live"
    )
    assert classified.tier is UncertaintyTier.MATCH


def _and_not_query() -> SearchQuery:
    return SearchQuery(
        name="AND with NOT",
        expression=SearchGroup(
            operator=BooleanOperator.AND,
            children=[
                SearchTerm(value="Alpha", exact_phrase=True),
                SearchTerm(value="Gamma", exact_phrase=True),
                SearchGroup(operator=BooleanOperator.NOT, children=[SearchTerm(value="Beta", exact_phrase=True)]),
            ],
        ),
    )


def test_direct_and_not_counts_two_positive_groups() -> None:
    query = _and_not_query()
    classified = classify_candidate(
        query,
        _pub("Alpha Gamma study", "Alpha Gamma methods.", doi_suffix="and-not"),
        candidate_id="and-not",
    )
    assert classified.candidate.positive_group_count == 2
    assert classified.candidate.evidenced_group_count == 2
    assert classified.candidate.canonical_status is CanonicalMatchStatus.MATCH
    assert classified.tier is UncertaintyTier.MATCH


def test_direct_pure_not_counts_zero_positive_groups() -> None:
    query = SearchQuery(
        name="Pure NOT",
        expression=SearchGroup(operator=BooleanOperator.NOT, children=[SearchTerm(value="Beta", exact_phrase=True)]),
    )
    matched = classify_candidate(
        query,
        _pub("Alpha study", "Alpha methods.", doi_suffix="pure-not-match"),
        candidate_id="pure-not-match",
    )
    assert matched.candidate.positive_group_count == 0
    assert matched.candidate.evidenced_group_count == 0
    assert matched.candidate.canonical_status is CanonicalMatchStatus.MATCH
    non_matched = classify_candidate(
        query,
        _pub("Beta study", "Beta methods.", doi_suffix="pure-not-nonmatch"),
        candidate_id="pure-not-nonmatch",
    )
    assert non_matched.candidate.positive_group_count == 0
    assert non_matched.candidate.evidenced_group_count == 0
    assert non_matched.candidate.canonical_status is CanonicalMatchStatus.NON_MATCH


def test_direct_normal_positive_and_unchanged() -> None:
    classified = classify_candidate(_three_group_query(), _MATCH_PUB, candidate_id="normal-and")
    assert classified.candidate.positive_group_count == 3
    assert classified.candidate.evidenced_group_count == 3
    assert classified.candidate.canonical_status is CanonicalMatchStatus.MATCH


def test_direct_nested_not_consistent_with_canonical_definition() -> None:
    nested = SearchQuery(
        name="Nested NOT inside OR",
        expression=SearchGroup(
            operator=BooleanOperator.AND,
            children=[
                SearchTerm(value="Alpha", exact_phrase=True),
                SearchGroup(
                    operator=BooleanOperator.OR,
                    children=[
                        SearchTerm(value="Gamma", exact_phrase=True),
                        SearchGroup(
                            operator=BooleanOperator.NOT,
                            children=[SearchTerm(value="Beta", exact_phrase=True)],
                        ),
                    ],
                ),
            ],
        ),
    )
    classified = classify_candidate(
        nested,
        _pub("Alpha Gamma study", "Alpha Gamma methods.", doi_suffix="nested-not"),
        candidate_id="nested-not",
    )
    assert classified.candidate.positive_group_count == 2
    pure_nested = SearchQuery(
        name="Pure NOT over AND",
        expression=SearchGroup(
            operator=BooleanOperator.NOT,
            children=[
                SearchGroup(
                    operator=BooleanOperator.AND,
                    children=[
                        SearchTerm(value="Alpha", exact_phrase=True),
                        SearchTerm(value="Gamma", exact_phrase=True),
                    ],
                )
            ],
        ),
    )
    pure_classified = classify_candidate(
        pure_nested,
        _pub("Alpha Gamma study", "Alpha Gamma methods.", doi_suffix="pure-nested"),
        candidate_id="pure-nested",
    )
    assert pure_classified.candidate.positive_group_count == 0


def test_direct_zero_evidence_indeterminate_unchanged() -> None:
    classified = classify_candidate(_three_group_query(), _NO_EVIDENCE_PUB, candidate_id="zero-ev")
    assert classified.candidate.positive_group_count == 3
    assert classified.candidate.evidenced_group_count == 0
    assert classified.candidate.canonical_status is CanonicalMatchStatus.INDETERMINATE
    assert classified.tier is UncertaintyTier.UNCERTAIN_NO_EVIDENCE


def test_direct_and_not_execution_eligibility_unchanged() -> None:
    classified = classify_candidate(
        _and_not_query(),
        _pub("Alpha Gamma study", "Alpha Gamma methods.", doi_suffix="and-not-inelig"),
        candidate_id="and-not-inelig",
        execution_eligible=False,
    )
    assert classified.candidate.positive_group_count == 2
    assert classified.candidate.execution_eligible is False
    result = run_experiment([classified])
    for evaluation in result.policies.values():
        assert evaluation.execution_ineligible_count == 1
        assert evaluation.main_count == 0
        assert evaluation.discarded_uncertain_count == 0
