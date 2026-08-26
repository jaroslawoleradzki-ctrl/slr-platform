"""Provider-independent evaluation of canonical search expressions.

Canonical ``ANY`` terms are evaluated against title and abstract.  Keywords
remain available through an explicit ``SearchField.KEYWORDS`` term; author and
venue scopes likewise require an explicit field in the canonical AST.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from enum import StrEnum

from app.domain.publication import Publication
from app.domain.search import (
    BooleanOperator,
    SearchExpression,
    SearchField,
    SearchGroup,
    SearchQuery,
    SearchTerm,
)

_TOKEN = re.compile(r"\w+", flags=re.UNICODE)


class CanonicalMatchStatus(StrEnum):
    MATCH = "match"
    NON_MATCH = "non_match"
    INDETERMINATE = "indeterminate"


@dataclass(frozen=True, slots=True)
class CanonicalValidationResult:
    status: CanonicalMatchStatus
    matched_terms: tuple[str, ...] = ()
    missing_fields: tuple[str, ...] = ()


def _tokens(value: str) -> tuple[str, ...]:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return tuple(_TOKEN.findall(normalized))


def _contains_phrase(haystack: tuple[str, ...], needle: tuple[str, ...]) -> bool:
    if not needle or len(needle) > len(haystack):
        return False
    width = len(needle)
    return any(haystack[index : index + width] == needle for index in range(len(haystack) - width + 1))


def _field_values(publication: Publication, field: SearchField) -> tuple[list[str], list[str]]:
    missing: list[str] = []
    if field is SearchField.ANY:
        values = [publication.title]
        if publication.abstract is None:
            missing.append(SearchField.ABSTRACT.value)
        else:
            values.append(publication.abstract)
        return values, missing
    if field is SearchField.TITLE:
        return [publication.title], missing
    if field is SearchField.ABSTRACT:
        if publication.abstract is None:
            return [], [field.value]
        return [publication.abstract], missing
    if field is SearchField.KEYWORDS:
        if not publication.keywords:
            return [], [field.value]
        return list(publication.keywords), missing
    if field is SearchField.AUTHOR:
        if not publication.authors:
            return [], [field.value]
        return [author.display_name for author in publication.authors], missing
    if field is SearchField.VENUE:
        if publication.venue is None:
            return [], [field.value]
        return [publication.venue.name], missing
    raise ValueError(f"Unsupported canonical search field: {field}")


def _evaluate_term(term: SearchTerm, publication: Publication) -> CanonicalValidationResult:
    values, missing = _field_values(publication, term.field)
    needle = _tokens(term.value)
    matched = any(_contains_phrase(_tokens(value), needle) for value in values)
    if matched:
        return CanonicalValidationResult(
            CanonicalMatchStatus.MATCH,
            matched_terms=(term.to_boolean_query(),),
            missing_fields=tuple(missing),
        )
    if missing:
        return CanonicalValidationResult(
            CanonicalMatchStatus.INDETERMINATE,
            missing_fields=tuple(missing),
        )
    return CanonicalValidationResult(
        CanonicalMatchStatus.NON_MATCH,
        missing_fields=tuple(missing),
    )


def _combine(results: list[CanonicalValidationResult], operator: BooleanOperator) -> CanonicalValidationResult:
    matched_terms = tuple(term for result in results for term in result.matched_terms)
    missing_fields = tuple(dict.fromkeys(field for result in results for field in result.missing_fields))
    statuses = {result.status for result in results}

    if operator is BooleanOperator.AND:
        if CanonicalMatchStatus.NON_MATCH in statuses:
            status = CanonicalMatchStatus.NON_MATCH
        elif CanonicalMatchStatus.INDETERMINATE in statuses:
            status = CanonicalMatchStatus.INDETERMINATE
        else:
            status = CanonicalMatchStatus.MATCH
    elif operator is BooleanOperator.OR:
        if CanonicalMatchStatus.MATCH in statuses:
            status = CanonicalMatchStatus.MATCH
        elif CanonicalMatchStatus.INDETERMINATE in statuses:
            status = CanonicalMatchStatus.INDETERMINATE
        else:
            status = CanonicalMatchStatus.NON_MATCH
    else:
        child = results[0]
        status = {
            CanonicalMatchStatus.MATCH: CanonicalMatchStatus.NON_MATCH,
            CanonicalMatchStatus.NON_MATCH: CanonicalMatchStatus.MATCH,
            CanonicalMatchStatus.INDETERMINATE: CanonicalMatchStatus.INDETERMINATE,
        }[child.status]
        matched_terms = ()

    return CanonicalValidationResult(status, matched_terms, missing_fields)


def evaluate_expression(expression: SearchExpression, publication: Publication) -> CanonicalValidationResult:
    if isinstance(expression, SearchTerm):
        return _evaluate_term(expression, publication)
    if isinstance(expression, SearchGroup):
        return _combine(
            [evaluate_expression(child, publication) for child in expression.children],
            expression.operator,
        )
    raise TypeError(f"Unsupported canonical search expression: {type(expression)}")


def validate_canonical_query(query: SearchQuery, publication: Publication) -> CanonicalValidationResult:
    return evaluate_expression(query.expression, publication)
