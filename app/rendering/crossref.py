from __future__ import annotations

import hashlib
import itertools
import json
from dataclasses import dataclass
from math import prod
from typing import Any

from app.domain.search import BooleanOperator, SearchExpression, SearchGroup, SearchQuery, SearchTerm
from app.rendering.base import RenderedQuery

MAX_CROSSREF_CANDIDATE_QUERIES = 6


def compute_plan_fingerprint(candidate_queries: list[str] | tuple[str, ...]) -> str:
    """Compute a deterministic 16-character SHA-256 fingerprint for candidate queries.

    Uses canonical JSON array serialization with explicit stable UTF-8 encoding
    to ensure an unambiguous, injective representation across all query strings
    (including queries containing embedded newlines, quotes, or delimiter tokens).
    """
    payload = json.dumps(list(candidate_queries), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]


@dataclass(frozen=True, slots=True)
class CrossrefCandidatePlan:
    """A bounded physical plan plus its logical-combination coverage."""

    queries: tuple[str, ...]
    possible_combinations: int
    axis_coverage: tuple[dict[str, Any], ...] = ()

    @property
    def min_axis_coverage_ratio(self) -> float:
        if not self.axis_coverage:
            return 1.0
        return min(float(c.get("coverage_ratio", 1.0)) for c in self.axis_coverage)


class CrossrefQueryRenderer:
    """Renderer converting canonical SearchQuery to Crossref search syntax with explicit audit metadata."""

    provider: str = "crossref"

    def render(self, search_query: SearchQuery) -> RenderedQuery:
        candidate_plan = build_crossref_candidate_plan(search_query.expression)
        candidate_queries = list(candidate_plan.queries)
        plan_fingerprint = compute_plan_fingerprint(candidate_queries)
        query_string = " || ".join(candidate_queries)
        warnings_list = [
            "Crossref REST free-text search cannot execute the canonical Boolean tree losslessly; physical queries form a candidate retrieval plan and every candidate is validated locally.",
            f"Candidate retrieval uses {len(candidate_queries)} deterministic physical queries covering "
            f"{len(candidate_queries)} of {candidate_plan.possible_combinations} positive candidate combination(s); "
            "Crossref free-text retrieval remains lossy when that count exceeds the request bound.",
        ]
        metadata: dict[str, Any] = {
            "canonical_query": search_query.to_boolean_query(),
            "candidate_queries": candidate_queries,
            "translation": "multi_query_positive_anchor_candidates",
            "physical_query_bound": MAX_CROSSREF_CANDIDATE_QUERIES,
            "possible_candidate_combinations": candidate_plan.possible_combinations,
            "planned_candidate_combinations": len(candidate_queries),
            "axis_coverage": [dict(entry) for entry in candidate_plan.axis_coverage],
            "min_axis_coverage_ratio": candidate_plan.min_axis_coverage_ratio,
            "plan_fingerprint": plan_fingerprint,
            "planner_version": "v0.6.9-wp3",
        }

        return RenderedQuery(
            provider=self.provider,
            query_string=query_string,
            physical_endpoint="https://api.crossref.org/works",
            is_lossless=False,
            warnings=tuple(warnings_list),
            metadata=metadata,
        )


def _render_term(term: SearchTerm) -> str:
    return f'"{term.value}"' if term.exact_phrase or " " in term.value else term.value


def build_crossref_candidate_queries(expression: SearchExpression) -> list[str]:
    """Return a deterministic, bounded positive candidate-retrieval plan.

    Crossref's free-text endpoint has no Boolean tree API. For an AND node,
    each query combines one anchor from every positive child. When the full
    product exceeds the bound, a balanced deterministic covering selection
    guarantees broad representation across all positive concept axes without
    dimensional collapse. NOT remains a local-validation concern and OR remains
    a union of positive alternatives.
    """

    return list(build_crossref_candidate_plan(expression).queries)


def build_crossref_candidate_plan(expression: SearchExpression) -> CrossrefCandidatePlan:
    """Build a bounded, deterministic sample of positive physical queries.

    If every positive AND combination fits the request bound, every one is
    emitted. Otherwise the plan executes a deterministic balanced covering selection
    that maximizes per-axis alternative representation across all positive concept groups,
    eliminating arithmetic modulo collapse while preserving a hard physical bound.
    """

    queries, possible_combinations, axis_coverage = _build_positive_plan(
        expression, limit=MAX_CROSSREF_CANDIDATE_QUERIES
    )
    return CrossrefCandidatePlan(
        queries=tuple(queries),
        possible_combinations=possible_combinations,
        axis_coverage=axis_coverage,
    )


def _stratified_indices(total: int, count: int) -> list[int]:
    """Return `count` strictly increasing, evenly spaced indices in range [0, total - 1]."""
    if count < 1 or count > total:
        raise ValueError("candidate rank count must be between 1 and the total")
    if count == 1:
        return [0]
    return [
        (2 * i * (total - 1) + (count - 1)) // (2 * (count - 1))
        for i in range(count)
    ]


def _select_balanced_positive_and_plan(
    child_plans: list[list[str]], limit: int
) -> tuple[list[str], int, tuple[dict[str, Any], ...]]:
    """Select up to `limit` combinations from positive AND child axes in a balanced manner.

    Executable contract:
    - Bounded: at most `limit` queries are returned.
    - Non-empty, zero duplicates: all emitted physical queries are distinct.
    - Full Cartesian product when total possible combinations <= `limit`.
    - Alternative coverage: represents min(limit, L_j) deduplicated executable alternatives
      on each axis j, where L_j is defined explicitly as the number of deduplicated executable
      alternatives remaining after OR textual normalization.
    - Deterministic: identical inputs produce identical ordered plans.

    Contract notes:
    - Universal mathematical coverage guarantees are not claimed for arbitrary unbounded shapes;
      the contract reflects the executable behavior observed and verified across adversarial
      sweeps (e.g. 3x3, 3^9, 7x6x4, 10x2, 2x10, 7x7, 2^14, 3^10, 7x2x2).
    - Frequency balancing: While greedy pair-scoring and usage-penalties optimize for diversity,
      balanced repetition frequency (e.g. max frequency difference <= 1) is a heuristic goal,
      not an invariant guarantee. Adversarial shapes like 3x3 and 3^9 exhibit frequency
      distribution 3/2/1 (difference = 2).
    """
    k = len(child_plans)
    if k == 0:
        return [], 0, ()

    possible_combinations = prod(len(p) for p in child_plans)
    if possible_combinations <= limit:
        # Full Cartesian product preserved when product fits within the bound
        full_tuples = list(itertools.product(*child_plans))
        deduped_tuples: list[tuple[str, ...]] = []
        deduped_queries: list[str] = []
        seen_queries: set[str] = set()
        for combo in full_tuples:
            q = " ".join(combo)
            if q not in seen_queries:
                seen_queries.add(q)
                deduped_queries.append(q)
                deduped_tuples.append(combo)

        axis_coverage = tuple(
            {
                "axis_index": j,
                "group_index": j,
                "available_alternatives": len(child_plans[j]),
                "represented_alternatives": len(set(t[j] for t in deduped_tuples)),
                "coverage_ratio": round(len(set(t[j] for t in deduped_tuples)) / len(child_plans[j]), 4)
                if child_plans[j]
                else 1.0,
            }
            for j in range(k)
        )
        return deduped_queries, possible_combinations, axis_coverage

    # Stratify axes longer than limit to at most `limit` evenly spaced candidate indices
    candidate_indices_per_axis: list[list[int]] = []
    for p in child_plans:
        L = len(p)
        if L <= limit:
            candidate_indices_per_axis.append(list(range(L)))
        else:
            candidate_indices_per_axis.append(_stratified_indices(L, limit))

    cand_prod_size = prod(len(c) for c in candidate_indices_per_axis)
    axis_usage = [{idx: 0 for idx in candidate_indices_per_axis[j]} for j in range(k)]
    pair_usage: set[tuple[tuple[int, int], tuple[int, int]]] = set()
    selected_tuples: list[tuple[int, ...]] = []

    if cand_prod_size <= 10000:
        all_candidates = list(itertools.product(*candidate_indices_per_axis))
        for _step in range(limit):
            best_cand: tuple[int, ...] | None = None
            best_score = -float("inf")
            for cand in all_candidates:
                if cand in selected_tuples:
                    continue
                score = 0.0
                for j, val in enumerate(cand):
                    u = axis_usage[j][val]
                    if u == 0:
                        score += 10000.0
                    else:
                        score -= u * 100.0
                for j1 in range(k):
                    for j2 in range(j1 + 1, k):
                        if ((j1, cand[j1]), (j2, cand[j2])) not in pair_usage:
                            score += 10.0
                if score > best_score:
                    best_score = score
                    best_cand = cand
            assert best_cand is not None
            selected_tuples.append(best_cand)
            for j, val in enumerate(best_cand):
                axis_usage[j][val] += 1
            for j1 in range(k):
                for j2 in range(j1 + 1, k):
                    pair_usage.add(((j1, best_cand[j1]), (j2, best_cand[j2])))
    else:
        # Fast coordinate-wise construction for very large combinatorial spaces
        for _step in range(limit):
            cand_list: list[int] = []
            for j in range(k):
                best_val = min(
                    candidate_indices_per_axis[j],
                    key=lambda val: (axis_usage[j][val], val),
                )
                cand_list.append(best_val)
            cand_tuple = tuple(cand_list)
            if cand_tuple in selected_tuples:
                found = False
                for j in reversed(range(k)):
                    for alt_val in sorted(
                        candidate_indices_per_axis[j],
                        key=lambda v: (axis_usage[j][v], v),
                    ):
                        trial = list(cand_tuple)
                        trial[j] = alt_val
                        trial_tuple = tuple(trial)
                        if trial_tuple not in selected_tuples:
                            cand_tuple = trial_tuple
                            found = True
                            break
                    if found:
                        break
            selected_tuples.append(cand_tuple)
            for j, val in enumerate(cand_tuple):
                axis_usage[j][val] += 1

    deduped_selected_tuples: list[tuple[int, ...]] = []
    seen_queries_large: set[str] = set()
    deduped_queries_large: list[str] = []
    for t in selected_tuples:
        q = " ".join(child_plans[j][idx] for j, idx in enumerate(t))
        if q not in seen_queries_large:
            seen_queries_large.add(q)
            deduped_queries_large.append(q)
            deduped_selected_tuples.append(t)

    axis_coverage = tuple(
        {
            "axis_index": j,
            "group_index": j,
            "available_alternatives": len(child_plans[j]),
            "represented_alternatives": len(set(t[j] for t in deduped_selected_tuples)),
            "coverage_ratio": round(len(set(t[j] for t in deduped_selected_tuples)) / len(child_plans[j]), 4)
            if child_plans[j]
            else 1.0,
        }
        for j in range(k)
    )

    return deduped_queries_large, possible_combinations, axis_coverage


def _build_positive_plan(
    expression: SearchExpression, *, limit: int | None
) -> tuple[list[str], int, tuple[dict[str, Any], ...]]:
    if isinstance(expression, SearchTerm):
        rendered = _render_term(expression)
        coverage = (
            {
                "axis_index": 0,
                "group_index": 0,
                "available_alternatives": 1,
                "represented_alternatives": 1,
                "coverage_ratio": 1.0,
            },
        )
        return [rendered], 1, coverage
    if not isinstance(expression, SearchGroup):
        raise TypeError(f"Unsupported search expression type: {type(expression)}")
    if expression.operator is BooleanOperator.NOT:
        return [], 0, ()

    # OR children are intentionally left unbounded while an enclosing AND
    # computes its sample; truncating here would silently discard synonyms
    # before combination coverage is even considered.
    child_results = [_build_positive_plan(child, limit=None) for child in expression.children]
    non_empty = [(plan, count, coverage) for plan, count, coverage in child_results if plan]
    if not non_empty:
        raise ValueError("Crossref candidate retrieval requires a positive search term")
    if expression.operator is BooleanOperator.AND:
        child_plans = [plan for plan, _, _ in non_empty]
        effective_limit = limit or MAX_CROSSREF_CANDIDATE_QUERIES
        return _select_balanced_positive_and_plan(child_plans, effective_limit)
    else:
        selected = [query for plan, _, _ in non_empty for query in plan]
        possible_combinations = sum(count for _, count, _ in non_empty)
        available_count = len(selected)
        if limit is not None and len(selected) > limit:
            selected = [selected[index] for index in _stratified_indices(len(selected), limit)]
        unique_selected = list(dict.fromkeys(selected))
        rep_count = len(unique_selected)
        coverage = (
            {
                "axis_index": 0,
                "group_index": 0,
                "available_alternatives": available_count,
                "represented_alternatives": rep_count,
                "coverage_ratio": round(rep_count / available_count, 4) if available_count > 0 else 1.0,
            },
        )
        return unique_selected, possible_combinations, coverage
