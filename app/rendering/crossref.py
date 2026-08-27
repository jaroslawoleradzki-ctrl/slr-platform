from __future__ import annotations

from typing import Any

from app.domain.search import BooleanOperator, SearchExpression, SearchGroup, SearchQuery, SearchTerm
from app.rendering.base import RenderedQuery

MAX_CROSSREF_CANDIDATE_QUERIES = 6


class CrossrefQueryRenderer:
    """Renderer converting canonical SearchQuery to Crossref search syntax with explicit audit metadata."""

    provider: str = "crossref"

    def render(self, search_query: SearchQuery) -> RenderedQuery:
        candidate_queries = build_crossref_candidate_queries(search_query.expression)
        query_string = " || ".join(candidate_queries)
        warnings_list = [
            "Crossref REST free-text search cannot execute the canonical Boolean tree losslessly; physical queries form a candidate retrieval plan and every candidate is validated locally.",
            f"Candidate retrieval uses {len(candidate_queries)} bounded composite physical queries; each positive AND branch is represented without a Cartesian product.",
        ]
        metadata: dict[str, Any] = {
            "canonical_query": search_query.to_boolean_query(),
            "candidate_queries": candidate_queries,
            "translation": "multi_query_positive_anchor_candidates",
            "physical_query_bound": MAX_CROSSREF_CANDIDATE_QUERIES,
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
    each query therefore combines one cyclically selected anchor from *every*
    positive child.  This retains the AND structure in physical retrieval
    while avoiding the full product of synonym alternatives.  NOT remains a
    local-validation concern and OR remains a union of positive alternatives.
    """

    if isinstance(expression, SearchTerm):
        return [_render_term(expression)]
    if not isinstance(expression, SearchGroup):
        raise TypeError(f"Unsupported search expression type: {type(expression)}")
    if expression.operator is BooleanOperator.NOT:
        return []
    child_plans = [build_crossref_candidate_queries(child) for child in expression.children]
    non_empty = [plan for plan in child_plans if plan]
    if not non_empty:
        raise ValueError("Crossref candidate retrieval requires a positive search term")
    if expression.operator is BooleanOperator.AND:
        # The longest child plan determines how many aligned alternatives we
        # need to represent.  Cycling shorter plans means every generated
        # physical query still contains every required positive branch.
        query_count = min(MAX_CROSSREF_CANDIDATE_QUERIES, max(map(len, non_empty)))
        selected = [
            " ".join(plan[index % len(plan)] for plan in non_empty)
            for index in range(query_count)
        ]
    else:
        selected = [query for plan in non_empty for query in plan]
    return list(dict.fromkeys(selected))[:MAX_CROSSREF_CANDIDATE_QUERIES]
