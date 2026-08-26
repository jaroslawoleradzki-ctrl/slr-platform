from __future__ import annotations

from typing import Any

from app.domain.search import BooleanOperator, SearchExpression, SearchGroup, SearchQuery, SearchTerm
from app.rendering.base import RenderedQuery


class CrossrefQueryRenderer:
    """Renderer converting canonical SearchQuery to Crossref search syntax with explicit audit metadata."""

    provider: str = "crossref"

    def render(self, search_query: SearchQuery) -> RenderedQuery:
        candidate_queries = build_crossref_candidate_queries(search_query.expression)
        query_string = " || ".join(candidate_queries)
        warnings_list = [
            "Crossref REST free-text search cannot execute the canonical Boolean tree losslessly; physical queries form a candidate retrieval plan and every candidate is validated locally.",
            f"Candidate retrieval uses {len(candidate_queries)} physical queries from the smallest required positive branch to avoid a Cartesian product.",
        ]
        metadata: dict[str, Any] = {
            "canonical_query": search_query.to_boolean_query(),
            "candidate_queries": candidate_queries,
            "translation": "multi_query_positive_anchor_candidates",
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
    """Return a bounded positive-anchor plan without a Cartesian product.

    For an AND expression every canonical match must satisfy every child, so
    querying the child with the fewest positive alternatives is sufficient to
    obtain a candidate superset.  OR expressions require the union of their
    child plans.  Final Boolean semantics are enforced locally.
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
    selected = (
        min(non_empty, key=len)
        if expression.operator is BooleanOperator.AND
        else [query for plan in non_empty for query in plan]
    )
    return list(dict.fromkeys(selected))
