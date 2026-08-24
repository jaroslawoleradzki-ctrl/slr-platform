import json
from collections.abc import Iterable
from datetime import date
from enum import StrEnum
from typing import Any, TypeVar

from app.domain.author import Author
from app.domain.identifiers import Identifier, IdentifierType
from app.domain.publication import Publication
from app.domain.venue import Venue
from app.normalization.doi import normalize_doi
from app.normalization.language import normalize_language
from app.normalization.title import normalize_title

_ValueT = TypeVar("_ValueT")
_UNIQUE_IDENTIFIER_TYPES = {
    IdentifierType.DOI,
    IdentifierType.PMID,
    IdentifierType.OPENALEX,
}


class PublicationMergeConflict(ValueError):
    """Raised when two publications contain values that cannot be safely merged."""


def _stable_key(value: Any) -> str:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, date):
        return value.isoformat()
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _choose_optional(first: _ValueT | None, second: _ValueT | None) -> _ValueT | None:
    available = [value for value in (first, second) if value is not None]
    return max(available, key=_stable_key) if available else None


def _choose_text(first: str | None, second: str | None) -> str | None:
    available = [value for value in (first, second) if value is not None]
    return (
        max(available, key=lambda value: (len(value), value.casefold(), value))
        if available
        else None
    )


def _unique_sorted(values: Iterable[_ValueT]) -> list[_ValueT]:
    by_key: dict[str, _ValueT] = {}
    for value in values:
        by_key.setdefault(_stable_key(value), value)
    return [by_key[key] for key in sorted(by_key)]


def _identifier_value(identifier: Identifier) -> str:
    if identifier.type is IdentifierType.DOI:
        normalized = normalize_doi(identifier.value)
        if normalized is not None:
            return normalized
    return identifier.value.casefold()


def _merge_identifiers(
    first: Publication,
    second: Publication,
) -> list[Identifier]:
    identifiers = [*first.identifiers, *second.identifiers]
    for identifier_type in _UNIQUE_IDENTIFIER_TYPES:
        values = {
            _identifier_value(identifier)
            for identifier in identifiers
            if identifier.type is identifier_type
        }
        if len(values) > 1:
            raise PublicationMergeConflict(
                f"conflicting {identifier_type.value} identifiers"
            )

    by_identity: dict[tuple[str, str, str], Identifier] = {}
    for identifier in identifiers:
        identity = (
            identifier.type.value,
            _identifier_value(identifier),
            identifier.source or "",
        )
        candidate = identifier
        if identifier.type is IdentifierType.DOI:
            candidate = identifier.model_copy(update={"value": identity[1]}, deep=True)
        by_identity.setdefault(identity, candidate)
    return [by_identity[key] for key in sorted(by_identity)]


def _author_list_key(authors: list[Author]) -> tuple[int, int, str]:
    completeness = sum(
        1
        + (author.given_name is not None)
        + (author.family_name is not None)
        + len(author.identifiers)
        + len(author.affiliations)
        for author in authors
    )
    return len(authors), completeness, _stable_key(authors)


def _choose_authors(first: list[Author], second: list[Author]) -> list[Author]:
    selected = first if _author_list_key(first) >= _author_list_key(second) else second
    return list(selected)


def _venue_key(venue: Venue) -> tuple[int, str]:
    completeness = (
        1
        + (venue.type is not None)
        + (venue.publisher is not None)
        + len(venue.identifiers)
    )
    return completeness, _stable_key(venue)


def _choose_venue(first: Venue | None, second: Venue | None) -> Venue | None:
    available = [venue for venue in (first, second) if venue is not None]
    return max(available, key=_venue_key) if available else None


def _bibliographic_date_key(
    value: tuple[date | None, int | None],
) -> tuple[bool, bool, str, int]:
    publication_date, publication_year = value
    return (
        publication_date is not None,
        publication_year is not None,
        publication_date.isoformat() if publication_date is not None else "",
        publication_year if publication_year is not None else 0,
    )


class PublicationMergePolicy:
    """Merge two publications already known to represent the same work."""

    def merge(self, first: Publication, second: Publication) -> Publication:
        if first == second:
            return Publication.model_validate(first.model_dump())

        if first.schema_version != second.schema_version:
            raise PublicationMergeConflict("conflicting schema_version values")

        first_lang = normalize_language(first.language)
        second_lang = normalize_language(second.language)
        if (
            first_lang is not None
            and second_lang is not None
            and first_lang != second_lang
        ):
            raise PublicationMergeConflict("conflicting language values")
        if (
            first.open_access is not None
            and second.open_access is not None
            and first.open_access is not second.open_access
        ):
            raise PublicationMergeConflict("conflicting open_access values")

        title = _choose_text(first.title, second.title)
        if title is None:  # Publication validation makes this defensive only.
            raise PublicationMergeConflict("merged publication requires a title")

        publication_date, publication_year = max(
            (
                (first.publication_date, first.publication_year),
                (second.publication_date, second.publication_year),
            ),
            key=_bibliographic_date_key,
        )
        values = {
            "record_id": min(first.record_id, second.record_id),
            "schema_version": first.schema_version,
            "title": title,
            "title_normalized": normalize_title(title),
            "abstract": _choose_text(first.abstract, second.abstract),
            "authors": _choose_authors(first.authors, second.authors),
            "publication_year": publication_year,
            "publication_date": publication_date,
            "identifiers": _merge_identifiers(first, second),
            "venue": _choose_venue(first.venue, second.venue),
            "publisher": _choose_text(first.publisher, second.publisher),
            "document_type": _choose_optional(
                first.document_type,
                second.document_type,
            ),
            "language": _choose_optional(first_lang, second_lang),
            "keywords": _unique_sorted([*first.keywords, *second.keywords]),
            "urls": _unique_sorted([*first.urls, *second.urls]),
            "open_access": _choose_optional(first.open_access, second.open_access),
            "provenance": _unique_sorted([*first.provenance, *second.provenance]),
            "created_at": min(first.created_at, second.created_at),
        }
        return Publication.model_validate(values)


publication_merge_policy = PublicationMergePolicy()


def merge_publications(first: Publication, second: Publication) -> Publication:
    return publication_merge_policy.merge(first, second)
