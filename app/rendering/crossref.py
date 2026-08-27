from __future__ import annotations

from dataclasses import dataclass
from math import prod
from typing import Any

from app.domain.search import BooleanOperator, SearchExpression, SearchGroup, SearchQuery, SearchTerm
from app.rendering.base import RenderedQuery

MAX_CROSSREF_CANDIDATE_QUERIES = 6


@dataclass(frozen=True, slots=True)
class CrossrefCandidatePlan:
    """A bounded physical plan plus its logical-combination coverage."""

    queries: tuple[str, ...]
    possible_combinations: int


class CrossrefQueryRenderer:
    """Renderer converting canonical SearchQuery to Crossref search syntax with explicit audit metadata."""

    provider: str = "crossref"

    def render(self, search_query: SearchQuery) -> RenderedQuery:
        candidate_plan = build_crossref_candidate_plan(search_query.expression)
        candidate_queries = list(candidate_plan.queries)
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

    Crossref's free-text endpoint has no Boolean tree API.  For an AND node,
    each query combines one anchor from every positive child.  When the full
    product exceeds the bound, evenly spaced mixed-radix combinations provide
    measurable, deterministic coverage rather than a claim of losslessness.
    NOT remains a local-validation concern and OR remains a union of positive
    alternatives.
    """

    return list(build_crossref_candidate_plan(expression).queries)


def build_crossref_candidate_plan(expression: SearchExpression) -> CrossrefCandidatePlan:
    """Build a bounded, deterministic sample of positive physical queries.

    If every positive AND combination fits the request bound, every one is
    emitted.  Otherwise the plan selects evenly spaced mixed-radix ranks from
    the logical Cartesian space without materialising that space.  It is thus
    intentionally *not* a lossless candidate superset above the bound; the
    metadata makes its coverage explicit rather than claiming otherwise.
    """

    queries, possible_combinations = _build_positive_plan(
        expression, limit=MAX_CROSSREF_CANDIDATE_QUERIES
    )
    return CrossrefCandidatePlan(tuple(queries), possible_combinations)


def _build_positive_plan(expression: SearchExpression, *, limit: int | None) -> tuple[list[str], int]:
    if isinstance(expression, SearchTerm):
        return [_render_term(expression)], 1
    if not isinstance(expression, SearchGroup):
        raise TypeError(f"Unsupported search expression type: {type(expression)}")
    if expression.operator is BooleanOperator.NOT:
        return [], 0

    # OR children are intentionally left unbounded while an enclosing AND
    # computes its sample; truncating here would silently discard synonyms
    # before combination coverage is even considered.
    child_results = [_build_positive_plan(child, limit=None) for child in expression.children]
    non_empty = [(plan, count) for plan, count in child_results if plan]
    if not non_empty:
        raise ValueError("Crossref candidate retrieval requires a positive search term")
    if expression.operator is BooleanOperator.AND:
        child_plans = [plan for plan, _ in non_empty]
        possible_combinations = prod(len(plan) for plan in child_plans)
        query_count = min(limit or MAX_CROSSREF_CANDIDATE_QUERIES, possible_combinations)
        # Evenly spaced ranks cover the logical product more broadly than the
        # former diagonal/cyclic alignment while retaining a strict bound.
        selected = [
            " ".join(_mixed_radix_choice(rank, child_plans))
            for rank in _evenly_spaced_ranks(possible_combinations, query_count)
        ]
    else:
        selected = [query for plan, _ in non_empty for query in plan]
        possible_combinations = sum(count for _, count in non_empty)
        if limit is not None and len(selected) > limit:
            selected = [selected[index] for index in _evenly_spaced_ranks(len(selected), limit)]
    return list(dict.fromkeys(selected)), possible_combinations


def _evenly_spaced_ranks(total: int, count: int) -> list[int]:
    if count < 1 or count > total:
        raise ValueError("candidate rank count must be between 1 and the total")
    return [(index * total) // count for index in range(count)]


def _mixed_radix_choice(rank: int, plans: list[list[str]]) -> list[str]:
    selected: list[str] = []
    for plan in reversed(plans):
        rank, index = divmod(rank, len(plan))
        selected.append(plan[index])
    return list(reversed(selected))
