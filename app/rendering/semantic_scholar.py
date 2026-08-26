from __future__ import annotations

import unicodedata

from app.domain.search import (
    BooleanOperator,
    SearchExpression,
    SearchField,
    SearchGroup,
    SearchQuery,
    SearchTerm,
)
from app.rendering.base import RenderedQuery


def _to_plain_text(value: str) -> str:
    """Convert one canonical term to words accepted by relevance search.

    `/paper/search` has no query language. Keep Unicode letters, marks, and
    numbers, and treat syntax/punctuation (including quotes, escapes, and
    hyphens) as word boundaries. This is deliberately applied to term nodes,
    not to a serialized Boolean query.
    """

    characters = [
        character
        if character.isalnum() or character.isspace() or unicodedata.category(character).startswith("M")
        else " "
        for character in value
    ]
    return " ".join("".join(characters).split())


class SemanticScholarQueryRenderer:
    """Render canonical Boolean syntax for Semantic Scholar bulk search."""

    provider: str = "semantic_scholar"

    def render(self, search_query: SearchQuery) -> RenderedQuery:
        warnings: list[str] = []

        def render_expression(expression: SearchExpression) -> str:
            if isinstance(expression, SearchTerm):
                value = _to_plain_text(expression.value)
                if value != expression.value.strip():
                    warnings.append(
                        f"Semantic Scholar bulk search normalized punctuation in '{expression.value}' to '{value}'; physical query may differ from canonical term."
                    )
                if expression.field is not SearchField.ANY:
                    warnings.append(
                        "Semantic Scholar bulk search cannot preserve canonical field scopes; local canonical validation is required."
                    )
                if expression.exact_phrase or " " in value:
                    return f'"{value}"'
                return value
            if isinstance(expression, SearchGroup):
                if expression.operator is BooleanOperator.NOT:
                    return f"-({render_expression(expression.children[0])})"
                operator = " + " if expression.operator is BooleanOperator.AND else " | "
                return f"({operator.join(render_expression(child) for child in expression.children)})"
            raise TypeError(f"Unsupported search expression type: {type(expression)}")


        query_string = render_expression(search_query.expression)
        return RenderedQuery(
            provider=self.provider,
            query_string=query_string,
            physical_endpoint="https://api.semanticscholar.org/graph/v1/paper/search/bulk",
            is_lossless=not warnings,
            warnings=tuple(dict.fromkeys(warnings)),
            metadata={
                "canonical_query": search_query.to_boolean_query(),
                "translation": "semantic_scholar_bulk_boolean",
            },
        )
