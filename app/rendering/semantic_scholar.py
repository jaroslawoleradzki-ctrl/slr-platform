from __future__ import annotations

import unicodedata
from typing import Any

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
        if character.isalnum()
        or character.isspace()
        or unicodedata.category(character).startswith("M")
        else " "
        for character in value
    ]
    return " ".join("".join(characters).split())


class SemanticScholarQueryRenderer:
    """Render a canonical query for Semantic Scholar relevance search.

    The Graph API `/paper/search` endpoint accepts plain text and explicitly
    supports no special query syntax. Positive terms are therefore flattened
    in tree order, while every semantic reduction remains visible in the
    returned audit metadata.
    """

    provider: str = "semantic_scholar"

    def render(self, search_query: SearchQuery) -> RenderedQuery:
        terms: list[str] = []
        excluded_not_terms: list[str] = []
        has_and = False
        has_or = False
        has_not = False
        has_exact_phrase = False
        has_field_scope = False
        normalized_special_characters = False

        def collect_terms(expression: SearchExpression, *, excluded: bool = False) -> None:
            nonlocal has_and, has_or, has_not, has_exact_phrase
            nonlocal has_field_scope, normalized_special_characters

            if isinstance(expression, SearchTerm):
                plain_text = _to_plain_text(expression.value)
                if plain_text != expression.value.strip():
                    normalized_special_characters = True
                if expression.exact_phrase or any(
                    character.isspace() for character in expression.value
                ):
                    has_exact_phrase = True
                if expression.field is not SearchField.ANY:
                    has_field_scope = True
                if plain_text:
                    (excluded_not_terms if excluded else terms).append(plain_text)
                return

            if isinstance(expression, SearchGroup):
                if expression.operator is BooleanOperator.NOT:
                    has_not = True
                    collect_terms(expression.children[0], excluded=True)
                    return
                if expression.operator is BooleanOperator.AND:
                    has_and = True
                elif expression.operator is BooleanOperator.OR:
                    has_or = True
                for child in expression.children:
                    collect_terms(child, excluded=excluded)
                return

            raise TypeError(f"Unsupported search expression type: {type(expression)}")

        collect_terms(search_query.expression)

        warnings: list[str] = []
        if has_exact_phrase:
            warnings.append(
                "Semantic Scholar relevance search does not support exact-phrase syntax; "
                "phrase quotes were omitted from the plain-text query."
            )
        if has_and:
            warnings.append(
                "Semantic Scholar relevance search does not support AND operators; "
                "AND terms were flattened to plain-text keywords."
            )
        if has_or:
            warnings.append(
                "Semantic Scholar relevance search does not support OR operators; "
                "OR terms were flattened to plain-text keywords."
            )
        if has_not:
            warnings.append(
                "Semantic Scholar relevance search does not support NOT operators; "
                "NOT clauses were excluded from the plain-text query."
            )
        if has_field_scope:
            warnings.append(
                "Semantic Scholar relevance search does not support canonical field scopes; "
                "field-qualified terms were flattened to plain text."
            )
        if normalized_special_characters:
            warnings.append(
                "Semantic Scholar relevance search accepts plain text only; punctuation, "
                "quotes, escapes, and special query characters were converted to word boundaries."
            )

        # A NOT-only strategy has no faithful representation. Keep the request
        # executable and make the necessarily lossy fallback explicit.
        if not terms:
            terms = excluded_not_terms
            if excluded_not_terms:
                warnings.append(
                    "Semantic Scholar relevance search cannot represent a NOT-only query; "
                    "its terms were sent as plain text to keep the physical query executable."
                )

        query_string = " ".join(terms)
        if not query_string:
            query_string = _to_plain_text(search_query.name) or "search"
            warnings.append(
                "Semantic Scholar relevance search received no searchable term characters; "
                "the query name was used as a plain-text fallback."
            )

        metadata: dict[str, Any] = {
            "canonical_query": search_query.to_boolean_query(),
            "translation": "plain_text_best_effort",
        }
        return RenderedQuery(
            provider=self.provider,
            query_string=query_string,
            is_lossless=not warnings,
            warnings=tuple(warnings),
            metadata=metadata,
        )
