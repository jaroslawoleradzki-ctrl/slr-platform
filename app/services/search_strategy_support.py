"""Shared helpers for search strategy execution and fetch-all jobs.

Introduced in v0.6.5 so the synchronous execution endpoint and background
"fetch all available results" jobs apply exactly the same local constraint
semantics (including the v0.6.4 unknown-language rule) and result mapping.
"""

from __future__ import annotations

from typing import Literal, cast

from app.api.dto.search_strategy import (
    SearchResultRecordResponse,
    SearchStrategyExecutionRequest,
)
from app.domain.identifiers import IdentifierType
from app.domain.publication import DocumentType, Publication
from app.normalization.doi import normalize_doi

PUBLICATION_TYPE_DOMAIN_MAP = {
    "article": DocumentType.JOURNAL_ARTICLE,
    "review": DocumentType.REVIEW,
    "conference_paper": DocumentType.CONFERENCE_PAPER,
    "book_chapter": DocumentType.BOOK_CHAPTER,
}


def matches_execution_constraints(
    publication: Publication,
    payload: SearchStrategyExecutionRequest,
) -> bool:
    if (
        publication.publication_year is None
        or publication.publication_year < payload.publication_year_from
        or publication.publication_year > payload.publication_year_to
    ):
        return False
    # An unknown language (None, e.g. Semantic Scholar since v0.6.3) is not a
    # known non-match: providers that cannot enforce the language filter on the
    # physical query must not have their records silently discarded locally.
    if (
        payload.languages
        and publication.language is not None
        and publication.language not in payload.languages
    ):
        return False
    if payload.publication_types and publication.document_type not in {
        PUBLICATION_TYPE_DOMAIN_MAP[value] for value in payload.publication_types
    }:
        return False
    if payload.open_access and publication.open_access is not True:
        return False
    return True


def publication_source_id(publication: Publication) -> str:
    if publication.provenance:
        return publication.provenance[0].source_record_id
    return str(publication.record_id)


def publication_doi(publication: Publication) -> str | None:
    for identifier in publication.identifiers:
        if identifier.type is IdentifierType.DOI:
            return normalize_doi(identifier.value) or identifier.value
    return None


def map_search_result_record(
    publication: Publication,
    *,
    provider: str,
    result_id: str | None = None,
) -> SearchResultRecordResponse:
    return SearchResultRecordResponse(
        id=result_id or str(publication.record_id),
        title=publication.title,
        authors=[author.display_name for author in publication.authors],
        year=cast(int, publication.publication_year),
        provider=cast(Literal["openalex", "crossref", "semantic_scholar"], provider),
        source_id=publication_source_id(publication),
        doi=publication_doi(publication),
    )
