from __future__ import annotations

from typing import Any

from app.domain.search import BooleanOperator, SearchExpression, SearchGroup, SearchQuery, SearchTerm
from app.rendering.base import RenderedQuery


class CrossrefQueryRenderer:
    """Renderer converting canonical SearchQuery to Crossref search syntax with explicit audit metadata."""

    provider: str = "crossref"

    def render(self, search_query: SearchQuery) -> RenderedQuery:
        has_not = False
        has_or = False
        terms: list[str] = []

        def collect_terms(expr: SearchExpression) -> None:
            nonlocal has_not, has_or
            if isinstance(expr, SearchTerm):
                val = expr.value
                if expr.exact_phrase or " " in val:
                    terms.append(f'"{val}"')
                else:
                    terms.append(val)
            elif isinstance(expr, SearchGroup):
                if expr.operator is BooleanOperator.NOT:
                    has_not = True
                    # NOT clauses cannot be expressed in Crossref query parameter.
                    # We omit them from physical keywords to avoid matching them.
                    return
                if expr.operator is BooleanOperator.OR:
                    has_or = True
                for child in expr.children:
                    collect_terms(child)

        collect_terms(search_query.expression)

        query_string = " ".join(terms) if terms else search_query.to_boolean_query()

        warnings_list: list[str] = []
        if has_not:
            warnings_list.append(
                "Crossref free-text query parameter does not support NOT operators; NOT clauses were excluded from the physical query string."
            )
        if has_or:
            warnings_list.append(
                "Crossref free-text query parameter does not support OR operators; OR terms were flattened to space-separated keywords."
            )

        is_lossless = not (has_not or has_or)
        metadata: dict[str, Any] = {
            "canonical_query": search_query.to_boolean_query(),
        }

        return RenderedQuery(
            provider=self.provider,
            query_string=query_string,
            is_lossless=is_lossless,
            warnings=tuple(warnings_list),
            metadata=metadata,
        )
