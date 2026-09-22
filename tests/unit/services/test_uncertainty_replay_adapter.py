"""WP4.1 integration tests using the real WP2.1 replay-row schema."""

from __future__ import annotations

from app.domain.crossref_diagnostics import (
    CanonicalGroupEvidence,
    CrossrefMetadataCompleteness,
    CrossrefRecordDiagnostic,
    CrossrefRetrievalPath,
    RetentionOutcome,
    build_crossref_replay_dataset,
    group_evidence_for,
)
from app.domain.publication import Publication
from app.domain.search import BooleanOperator, SearchGroup, SearchQuery, SearchTerm
from app.services.canonical_query_validator import CanonicalMatchStatus
from app.services.uncertainty_experiment import (
    ClassifiedCandidate,
    PolicyScenario,
    UncertaintyTier,
    classify_tier,
    run_experiment,
)
from app.services.uncertainty_replay_adapter import (
    WP2ReplayDataIntegrityError,
    adapt_wp2_replay_rows,
)


def _evidence(*statuses: CanonicalMatchStatus, missing_abstract: bool = False) -> tuple[CanonicalGroupEvidence, ...]:
    return tuple(
        CanonicalGroupEvidence(
            group_index=index,
            group_query=f'"Group {index}"',
            status=status,
            matched_terms=(f'"Group {index}"',) if status is CanonicalMatchStatus.MATCH else (),
            missing_fields=("abstract",) if missing_abstract and status is CanonicalMatchStatus.INDETERMINATE else (),
        )
        for index, status in enumerate(statuses)
    )


def _diagnostic(
    source_id: str,
    status: CanonicalMatchStatus,
    outcome: RetentionOutcome,
    evidence: tuple[CanonicalGroupEvidence, ...],
    *,
    abstract_present: bool = True,
    paths: int = 1,
) -> CrossrefRecordDiagnostic:
    return CrossrefRecordDiagnostic(
        source_record_id=source_id,
        doi=source_id,
        title=f"Title {source_id}",
        retrieval_paths=tuple(
            CrossrefRetrievalPath(
                physical_query=f'"path {index}"',
                physical_query_index=index,
                physical_cursor="*",
                result_rank=index,
                provider_score=float(index),
            )
            for index in range(paths)
        ),
        completeness=CrossrefMetadataCompleteness(
            title_present=True,
            abstract_present=abstract_present,
            doi_present=True,
        ),
        canonical_status=status,
        group_evidence=evidence,
        retention_outcome=outcome,
    )


def _rows(*diagnostics: CrossrefRecordDiagnostic) -> list[dict[str, object]]:
    return build_crossref_replay_dataset(list(diagnostics), job_id="job-1")


def test_path_rows_become_one_candidate_with_real_wp2_schema() -> None:
    rows = _rows(
        _diagnostic(
            "10.1/match",
            CanonicalMatchStatus.MATCH,
            RetentionOutcome.RETAINED,
            _evidence(CanonicalMatchStatus.MATCH, CanonicalMatchStatus.MATCH),
            paths=2,
        )
    )
    assert len(rows) == 2

    adapted = adapt_wp2_replay_rows(rows)
    assert len(adapted) == 1
    assert adapted[0].source_record_id == "10.1/match"
    assert adapted[0].retrieval_path_count == 2
    assert adapted[0].candidate.canonical_status is CanonicalMatchStatus.MATCH
    assert adapted[0].candidate.execution_eligible is True


def test_replay_population_reconciles_without_path_inflation() -> None:
    rows = _rows(
        _diagnostic(
            "10.1/match",
            CanonicalMatchStatus.MATCH,
            RetentionOutcome.RETAINED,
            _evidence(CanonicalMatchStatus.MATCH, CanonicalMatchStatus.MATCH),
            paths=2,
        ),
        _diagnostic(
            "10.1/zero",
            CanonicalMatchStatus.INDETERMINATE,
            RetentionOutcome.RETAINED,
            _evidence(CanonicalMatchStatus.INDETERMINATE, CanonicalMatchStatus.INDETERMINATE, missing_abstract=True),
            abstract_present=False,
        ),
        _diagnostic(
            "10.1/nonmatch",
            CanonicalMatchStatus.NON_MATCH,
            RetentionOutcome.REJECTED_CANONICAL,
            _evidence(CanonicalMatchStatus.NON_MATCH, CanonicalMatchStatus.NON_MATCH),
        ),
        _diagnostic(
            "10.1/constrained-match",
            CanonicalMatchStatus.MATCH,
            RetentionOutcome.REJECTED_CONSTRAINTS,
            _evidence(CanonicalMatchStatus.MATCH, CanonicalMatchStatus.MATCH),
        ),
        _diagnostic(
            "10.1/constrained-indeterminate",
            CanonicalMatchStatus.INDETERMINATE,
            RetentionOutcome.REJECTED_CONSTRAINTS,
            _evidence(CanonicalMatchStatus.MATCH, CanonicalMatchStatus.INDETERMINATE, missing_abstract=True),
            abstract_present=False,
        ),
    )
    adapted = adapt_wp2_replay_rows(rows)
    assert len(rows) == 6
    assert len(adapted) == 5
    assert sum(item.retrieval_path_count for item in adapted) == 6

    result = run_experiment(
        [ClassifiedCandidate(candidate=item.candidate, tier=classify_tier(item.candidate)) for item in adapted]
    )
    assert (result.match_count, result.non_match_count, result.indeterminate_count) == (2, 1, 2)
    current = result.policies[PolicyScenario.CURRENT_RECALL_FIRST]
    assert (current.main_count, current.uncertainty_count, current.rejected_count, current.execution_ineligible_count) == (2, 0, 1, 2)
    separated = result.policies[PolicyScenario.SEPARATE_ALL_UNCERTAIN]
    assert (separated.main_count, separated.uncertainty_count, separated.rejected_count, separated.execution_ineligible_count) == (1, 1, 1, 2)


def test_zero_evidence_missing_abstract_is_retained_by_every_safe_policy() -> None:
    adapted = adapt_wp2_replay_rows(
        _rows(
            _diagnostic(
                "10.1/zero",
                CanonicalMatchStatus.INDETERMINATE,
                RetentionOutcome.RETAINED,
                _evidence(
                    CanonicalMatchStatus.INDETERMINATE,
                    CanonicalMatchStatus.INDETERMINATE,
                    CanonicalMatchStatus.INDETERMINATE,
                    missing_abstract=True,
                ),
                abstract_present=False,
            )
        )
    )
    candidate = adapted[0].candidate
    assert candidate.abstract_missing is True
    assert candidate.evidenced_group_count == 0
    assert classify_tier(candidate) is UncertaintyTier.UNCERTAIN_NO_EVIDENCE
    result = run_experiment([ClassifiedCandidate(candidate=candidate, tier=classify_tier(candidate))])
    assert result.policies[PolicyScenario.CURRENT_RECALL_FIRST].main_count == 1
    assert result.policies[PolicyScenario.SEPARATE_ALL_UNCERTAIN].uncertainty_count == 1
    assert result.policies[PolicyScenario.EVIDENCE_TIERED_UNCERTAIN].uncertainty_count == 1
    assert all(item.discarded_uncertain_count == 0 for item in result.policies.values())


def test_adapter_consumes_wp21_not_aware_evidence() -> None:
    query = SearchQuery(
        name="AND with NOT",
        expression=SearchGroup(
            operator=BooleanOperator.AND,
            children=[
                SearchTerm(value="Alpha"),
                SearchTerm(value="Gamma"),
                SearchGroup(operator=BooleanOperator.NOT, children=[SearchTerm(value="Beta")]),
            ],
        ),
    )
    evidence = group_evidence_for(query, Publication(title="Alpha Gamma", abstract="Alpha Gamma"))
    assert len(evidence) == 2
    adapted = adapt_wp2_replay_rows(
        _rows(_diagnostic("10.1/not", CanonicalMatchStatus.MATCH, RetentionOutcome.RETAINED, evidence))
    )
    assert adapted[0].candidate.positive_group_count == 2


def test_adapter_supports_wp21_pure_not_empty_evidence() -> None:
    query = SearchQuery(
        name="Pure NOT",
        expression=SearchGroup(operator=BooleanOperator.NOT, children=[SearchTerm(value="Beta")]),
    )
    evidence = group_evidence_for(query, Publication(title="Alpha", abstract="Alpha"))
    assert evidence == ()
    adapted = adapt_wp2_replay_rows(
        _rows(_diagnostic("10.1/pure-not", CanonicalMatchStatus.MATCH, RetentionOutcome.RETAINED, evidence))
    )
    assert adapted[0].candidate.positive_group_count == 0


def test_contradictory_path_rows_fail_deterministically() -> None:
    rows = _rows(
        _diagnostic(
            "10.1/conflict",
            CanonicalMatchStatus.MATCH,
            RetentionOutcome.RETAINED,
            _evidence(CanonicalMatchStatus.MATCH),
            paths=2,
        )
    )
    rows[1]["canonical_status"] = CanonicalMatchStatus.INDETERMINATE.value
    try:
        adapt_wp2_replay_rows(rows)
    except WP2ReplayDataIntegrityError as error:
        assert "conflicting candidate facts" in str(error)
    else:
        raise AssertionError("contradictory WP2 path rows must fail")
