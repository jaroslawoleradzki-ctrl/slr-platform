"""Experimental uncertainty-policy layer for canonical candidates (v0.6.9 WP4).

Measurement infrastructure only.  This module classifies already-validated
candidates into uncertainty tiers and compares alternative treatments of
``INDETERMINATE`` candidates WITHOUT changing production retention:

* the canonical validator is reused, never reimplemented or altered;
* no policy deletes, rejects, or hides any uncertain candidate — the
  ``discarded_uncertain_count`` invariant is computed honestly and every
  built-in policy keeps it at zero;
* execution eligibility is tracked separately from canonical status and
  experimental uncertainty policy;
* production code paths never import this module.

Terminology (kept strictly separate):

* canonical status: ``MATCH`` / ``NON_MATCH`` / ``INDETERMINATE`` — the
  validator verdict, unchanged;
* uncertainty tier: ``MATCH`` / ``UNCERTAIN_STRONG`` / ``UNCERTAIN_WEAK`` /
  ``UNCERTAIN_NO_EVIDENCE`` / ``NON_MATCH`` — an experimental lens derived
  generically from status, positive-group evidence counts, and missing fields.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.publication import Publication
from app.domain.search import BooleanOperator, SearchGroup, SearchQuery
from app.services.canonical_query_validator import (
    CanonicalMatchStatus,
    evaluate_expression,
    validate_canonical_query,
)

ABSTRACT_FIELD = "abstract"


class UncertaintyTier(StrEnum):
    """Experimental tier of one validated candidate."""

    MATCH = "match"
    UNCERTAIN_STRONG = "uncertain_strong"
    UNCERTAIN_WEAK = "uncertain_weak"
    UNCERTAIN_NO_EVIDENCE = "uncertain_no_evidence"
    NON_MATCH = "non_match"


class ScreeningPopulation(StrEnum):
    """Experimental queue assignment under a policy scenario."""

    MAIN = "main"
    UNCERTAINTY = "uncertainty"
    REJECTED = "rejected"
    EXECUTION_INELIGIBLE = "execution_ineligible"


class PolicyScenario(StrEnum):
    """Deterministic experimental uncertainty policies."""

    CURRENT_RECALL_FIRST = "current_recall_first"
    SEPARATE_ALL_UNCERTAIN = "separate_all_uncertain"
    EVIDENCE_TIERED_UNCERTAIN = "evidence_tiered_uncertain"
    SEPARATE_UNEVIDENCED_ONLY = "separate_unevidenced_only"


ALL_POLICY_SCENARIOS: tuple[PolicyScenario, ...] = (
    PolicyScenario.CURRENT_RECALL_FIRST,
    PolicyScenario.SEPARATE_ALL_UNCERTAIN,
    PolicyScenario.EVIDENCE_TIERED_UNCERTAIN,
    PolicyScenario.SEPARATE_UNEVIDENCED_ONLY,
)


class UncertaintyCandidate(BaseModel):
    """Domain-level input for the policy engine.

    Deliberately free of provider, persistence, or WP2 types so a future
    integration can adapt WP2 replay rows into this model without rewriting
    the engine (see :func:`candidate_from_evidence_dict`).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    candidate_id: str = Field(min_length=1)
    canonical_status: CanonicalMatchStatus
    positive_group_count: int = Field(ge=0)
    evidenced_group_count: int = Field(ge=0)
    missing_fields: tuple[str, ...] = ()
    abstract_missing: bool = False
    group_statuses: tuple[CanonicalMatchStatus, ...] = ()
    execution_eligible: bool = True

    @model_validator(mode="after")
    def check_evidence_consistency(self) -> "UncertaintyCandidate":
        if self.evidenced_group_count > self.positive_group_count:
            raise ValueError("evidenced_group_count must not exceed positive_group_count")
        if self.group_statuses and len(self.group_statuses) != self.positive_group_count:
            raise ValueError("group_statuses length must match positive_group_count")
        if self.canonical_status is CanonicalMatchStatus.MATCH and (
            self.evidenced_group_count != self.positive_group_count
        ):
            raise ValueError("MATCH requires every positive group to be evidenced")
        if self.canonical_status is CanonicalMatchStatus.INDETERMINATE and (
            self.evidenced_group_count >= self.positive_group_count
        ):
            raise ValueError("INDETERMINATE requires at least one unevidenced positive group")
        return self


class ClassifiedCandidate(BaseModel):
    """A candidate with its experimental tier attached."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    candidate: UncertaintyCandidate
    tier: UncertaintyTier


def classify_tier(candidate: UncertaintyCandidate) -> UncertaintyTier:
    """Derive the experimental tier generically (no hard-coded terms).

    ``STRONG`` means all-but-one positive groups are evidenced; ``WEAK``
    means at least one group is evidenced but more than one is not;
    ``NO_EVIDENCE`` means no group is evidenced.
    """
    if candidate.canonical_status is CanonicalMatchStatus.MATCH:
        return UncertaintyTier.MATCH
    if candidate.canonical_status is CanonicalMatchStatus.NON_MATCH:
        return UncertaintyTier.NON_MATCH
    if candidate.evidenced_group_count <= 0:
        return UncertaintyTier.UNCERTAIN_NO_EVIDENCE
    if candidate.evidenced_group_count == candidate.positive_group_count - 1:
        return UncertaintyTier.UNCERTAIN_STRONG
    return UncertaintyTier.UNCERTAIN_WEAK


def _is_exclusion(child: Any) -> bool:
    """Whether a top-level AND child is a NOT exclusion rather than a positive group.

    Mirrors the canonical positive-group definition in
    ``app.domain.crossref_diagnostics.group_evidence_for`` without rerunning
    WP2 persistence logic.
    """
    return isinstance(child, SearchGroup) and child.operator is BooleanOperator.NOT


def _positive_groups(query: SearchQuery) -> list[Any]:
    """Split a canonical query into its positive concept groups, generically.

    Consistent with the corrected canonical definition: top-level NOT children
    of an AND are exclusions, not evidence groups; a pure NOT query yields no
    positive groups.
    """
    expression = query.expression
    if isinstance(expression, SearchGroup) and expression.operator is BooleanOperator.AND:
        return [child for child in expression.children if not _is_exclusion(child)]
    if _is_exclusion(expression):
        return []
    return [expression]


def classify_candidate(
    query: SearchQuery,
    publication: Publication,
    *,
    candidate_id: str,
    execution_eligible: bool = True,
) -> ClassifiedCandidate:
    """Validate with the real validator and classify, without duplicating logic."""
    status = validate_canonical_query(query, publication).status
    groups = _positive_groups(query)
    group_statuses = tuple(evaluate_expression(child, publication).status for child in groups)
    evidenced = sum(1 for group_status in group_statuses if group_status is CanonicalMatchStatus.MATCH)
    missing: list[str] = []
    for child in groups:
        for field in evaluate_expression(child, publication).missing_fields:
            if field not in missing:
                missing.append(field)
    candidate = UncertaintyCandidate(
        candidate_id=candidate_id,
        canonical_status=status,
        positive_group_count=len(groups),
        evidenced_group_count=evidenced,
        missing_fields=tuple(missing),
        abstract_missing=ABSTRACT_FIELD in missing,
        group_statuses=group_statuses,
        execution_eligible=execution_eligible,
    )
    return ClassifiedCandidate(candidate=candidate, tier=classify_tier(candidate))


def candidate_from_evidence_dict(data: Mapping[str, Any]) -> UncertaintyCandidate:
    """Adapt a plain evidence mapping (e.g. a future WP2 replay row) to the engine.

    Expected shape (all values plain JSON types)::

        {
            "candidate_id": str,
            "canonical_status": "match" | "non_match" | "indeterminate",
            "positive_group_count": int,
            "evidenced_group_count": int,
            "missing_fields": [str, ...],          # optional
            "abstract_missing": bool,              # optional
            "group_statuses": [...]                # optional, same vocabulary
        }

    This is the documented WP2 integration boundary: WP2 owns persistence and
    row shape; this function owns validation of the adapted input.  Keys beyond
    the documented shape (subquery, rank, score, …) are ignored by the engine.
    """
    raw_status = data["canonical_status"]
    status = raw_status if isinstance(raw_status, CanonicalMatchStatus) else CanonicalMatchStatus(str(raw_status))
    raw_groups = data.get("group_statuses", ())
    group_statuses = tuple(
        item if isinstance(item, CanonicalMatchStatus) else CanonicalMatchStatus(str(item)) for item in raw_groups
    )
    return UncertaintyCandidate(
        candidate_id=str(data["candidate_id"]),
        canonical_status=status,
        positive_group_count=int(data["positive_group_count"]),
        evidenced_group_count=int(data["evidenced_group_count"]),
        missing_fields=tuple(str(field) for field in data.get("missing_fields", ())),
        abstract_missing=bool(data.get("abstract_missing", False)),
        group_statuses=group_statuses,
        execution_eligible=bool(data.get("execution_eligible", True)),
    )


def assign_population(
    tier: UncertaintyTier,
    scenario: PolicyScenario,
    *,
    execution_eligible: bool = True,
) -> ScreeningPopulation:
    """Queue assignment for one tier under one scenario (total function)."""
    if tier is UncertaintyTier.NON_MATCH:
        return ScreeningPopulation.REJECTED
    if not execution_eligible:
        return ScreeningPopulation.EXECUTION_INELIGIBLE
    if tier is UncertaintyTier.MATCH:
        return ScreeningPopulation.MAIN
    if scenario is PolicyScenario.CURRENT_RECALL_FIRST:
        return ScreeningPopulation.MAIN
    if scenario is PolicyScenario.SEPARATE_ALL_UNCERTAIN:
        return ScreeningPopulation.UNCERTAINTY
    if scenario is PolicyScenario.EVIDENCE_TIERED_UNCERTAIN:
        return ScreeningPopulation.UNCERTAINTY
    # SEPARATE_UNEVIDENCED_ONLY
    return (
        ScreeningPopulation.UNCERTAINTY
        if tier is UncertaintyTier.UNCERTAIN_NO_EVIDENCE
        else ScreeningPopulation.MAIN
    )


class CandidateAssignment(BaseModel):
    """Per-candidate policy outcome, suitable for later inspection."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    candidate_id: str
    canonical_status: CanonicalMatchStatus
    tier: UncertaintyTier
    population: ScreeningPopulation
    positive_group_count: int
    evidenced_group_count: int
    missing_fields: tuple[str, ...] = ()
    abstract_missing: bool = False
    execution_eligible: bool = True


class PolicyEvaluation(BaseModel):
    """Aggregate outcome of one policy scenario over a candidate set."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    scenario: PolicyScenario
    main_count: int = Field(ge=0)
    uncertainty_count: int = Field(ge=0)
    uncertainty_by_tier: dict[str, int] = Field(default_factory=dict)
    rejected_count: int = Field(ge=0)
    execution_ineligible_count: int = Field(ge=0)
    discarded_uncertain_count: int = Field(ge=0)
    assignments: tuple[CandidateAssignment, ...] = ()


def evaluate_policy(
    classified: list[ClassifiedCandidate],
    scenario: PolicyScenario,
) -> PolicyEvaluation:
    """Apply one scenario; every candidate lands in exactly one population."""
    assignments: list[CandidateAssignment] = []
    uncertainty_by_tier: dict[str, int] = {}
    main_count = 0
    uncertainty_count = 0
    rejected_count = 0
    execution_ineligible_count = 0
    discarded = 0
    for item in classified:
        population = assign_population(
            item.tier,
            scenario,
            execution_eligible=item.candidate.execution_eligible,
        )
        if population is ScreeningPopulation.MAIN:
            main_count += 1
        elif population is ScreeningPopulation.UNCERTAINTY:
            uncertainty_count += 1
            uncertainty_by_tier[item.tier.value] = uncertainty_by_tier.get(item.tier.value, 0) + 1
        else:
            if population is ScreeningPopulation.REJECTED:
                rejected_count += 1
            else:
                execution_ineligible_count += 1
        if (
            item.candidate.canonical_status is CanonicalMatchStatus.INDETERMINATE
            and population is ScreeningPopulation.REJECTED
        ):
            discarded += 1
        assignments.append(
            CandidateAssignment(
                candidate_id=item.candidate.candidate_id,
                canonical_status=item.candidate.canonical_status,
                tier=item.tier,
                population=population,
                positive_group_count=item.candidate.positive_group_count,
                evidenced_group_count=item.candidate.evidenced_group_count,
                missing_fields=item.candidate.missing_fields,
                abstract_missing=item.candidate.abstract_missing,
                execution_eligible=item.candidate.execution_eligible,
            )
        )
    return PolicyEvaluation(
        scenario=scenario,
        main_count=main_count,
        uncertainty_count=uncertainty_count,
        uncertainty_by_tier=dict(sorted(uncertainty_by_tier.items())),
        rejected_count=rejected_count,
        execution_ineligible_count=execution_ineligible_count,
        discarded_uncertain_count=discarded,
        assignments=tuple(assignments),
    )


class UncertaintyExperimentResult(BaseModel):
    """Deterministic comparison of policy scenarios over one candidate set."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    total_candidates: int = Field(ge=0)
    match_count: int = Field(ge=0)
    non_match_count: int = Field(ge=0)
    indeterminate_count: int = Field(ge=0)
    evidence_distribution: dict[int, int] = Field(default_factory=dict)
    missing_fields_distribution: dict[str, int] = Field(default_factory=dict)
    missing_abstract_count: int = Field(ge=0)
    policies: dict[PolicyScenario, PolicyEvaluation] = Field(default_factory=dict)


def run_experiment(
    classified: list[ClassifiedCandidate],
    scenarios: tuple[PolicyScenario, ...] = ALL_POLICY_SCENARIOS,
) -> UncertaintyExperimentResult:
    """Compare scenarios over pre-classified candidates (input order preserved)."""
    evidence_distribution: dict[int, int] = {}
    missing_fields_distribution: dict[str, int] = {}
    match_count = 0
    non_match_count = 0
    indeterminate_count = 0
    missing_abstract_count = 0
    for item in classified:
        candidate = item.candidate
        if candidate.canonical_status is CanonicalMatchStatus.MATCH:
            match_count += 1
        elif candidate.canonical_status is CanonicalMatchStatus.NON_MATCH:
            non_match_count += 1
        else:
            indeterminate_count += 1
            evidence_distribution[candidate.evidenced_group_count] = (
                evidence_distribution.get(candidate.evidenced_group_count, 0) + 1
            )
            for field in candidate.missing_fields:
                missing_fields_distribution[field] = missing_fields_distribution.get(field, 0) + 1
            if candidate.abstract_missing:
                missing_abstract_count += 1
    return UncertaintyExperimentResult(
        total_candidates=len(classified),
        match_count=match_count,
        non_match_count=non_match_count,
        indeterminate_count=indeterminate_count,
        evidence_distribution=dict(sorted(evidence_distribution.items())),
        missing_fields_distribution=dict(sorted(missing_fields_distribution.items())),
        missing_abstract_count=missing_abstract_count,
        policies={scenario: evaluate_policy(classified, scenario) for scenario in scenarios},
    )
