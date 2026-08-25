from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, cast
from uuid import UUID

import pytest

from app.domain import Publication
from app.domain.search import SearchQuery, SearchRun, SearchTerm
from app.providers.openalex import OpenAlexClient
from app.providers.search.crossref import CrossrefProvider
from app.providers.search.openalex import OpenAlexProvider
from app.providers.search.semantic_scholar import SemanticScholarProvider

_QUERY_ID = UUID("00000000-0000-0000-0000-000000000001")
_RUN_ID = UUID("00000000-0000-0000-0000-000000000002")
_RETRIEVED_AT = datetime(2026, 7, 28, 12, 0, tzinfo=timezone.utc)
_RENDERED_QUERY = "lean energy"


@dataclass(frozen=True)
class ProviderMappingCase:
    name: str
    map_record: Callable[[dict[str, Any]], Publication]
    rich_record: dict[str, Any]
    minimal_record: dict[str, Any]
    invalid_title_record: dict[str, Any]
    malformed_optional_record: dict[str, Any]
    expected_rich_snapshot: dict[str, Any]


def _context(provider: str) -> tuple[SearchRun, SearchQuery]:
    query = SearchQuery(
        query_id=_QUERY_ID,
        name="Lean energy",
        expression=SearchTerm(value="lean energy"),
    )
    run = SearchRun(
        run_id=_RUN_ID,
        query_id=query.query_id,
        query_version=query.version,
        provider=provider,
        rendered_query=_RENDERED_QUERY,
    )
    return run, query


def _map_openalex(record: dict[str, Any]) -> Publication:
    run, query = _context("openalex")
    provider = OpenAlexProvider(client=cast(OpenAlexClient, object()))
    return provider._map_work_with_provenance(
        record,
        search_run=run,
        search_query=query,
        retrieved_at=_RETRIEVED_AT,
    )


def _map_crossref(record: dict[str, Any]) -> Publication:
    run, query = _context("crossref")
    return CrossrefProvider()._map_work_with_provenance(
        record,
        search_run=run,
        search_query=query,
        retrieved_at=_RETRIEVED_AT,
    )


def _map_semantic_scholar(record: dict[str, Any]) -> Publication:
    run, query = _context("semantic_scholar")
    return SemanticScholarProvider().map_paper(
        record,
        search_run=run,
        search_query=query,
        retrieved_at=_RETRIEVED_AT,
    )


def _identifier_snapshot(identifier: Any) -> tuple[str, str, str | None]:
    return identifier.type.value, identifier.value, identifier.source


def _contract_snapshot(publication: Publication) -> dict[str, Any]:
    return {
        "title": publication.title,
        "abstract": publication.abstract,
        "authors": [
            {
                "display_name": author.display_name,
                "given_name": author.given_name,
                "family_name": author.family_name,
                "identifiers": [
                    _identifier_snapshot(identifier)
                    for identifier in author.identifiers
                ],
                "affiliations": [
                    {
                        "name": affiliation.name,
                        "identifiers": [
                            _identifier_snapshot(identifier)
                            for identifier in affiliation.identifiers
                        ],
                    }
                    for affiliation in author.affiliations
                ],
            }
            for author in publication.authors
        ],
        "publication_year": publication.publication_year,
        "publication_date": (
            publication.publication_date.isoformat()
            if publication.publication_date is not None
            else None
        ),
        "identifiers": [
            _identifier_snapshot(identifier)
            for identifier in publication.identifiers
        ],
        "venue": (
            {
                "name": publication.venue.name,
                "type": (
                    publication.venue.type.value
                    if publication.venue.type is not None
                    else None
                ),
                "identifiers": [
                    _identifier_snapshot(identifier)
                    for identifier in publication.venue.identifiers
                ],
            }
            if publication.venue is not None
            else None
        ),
        "publisher": publication.publisher,
        "document_type": (
            publication.document_type.value
            if publication.document_type is not None
            else None
        ),
        "language": publication.language,
        "urls": publication.urls,
        "keywords": publication.keywords,
        "open_access": publication.open_access,
        "provenance": [
            {
                "source": entry.source,
                "source_record_id": entry.source_record_id,
                "retrieved_at": entry.retrieved_at,
                "query_id": entry.query_id,
                "run_id": entry.run_id,
                "rendered_query": entry.rendered_query,
            }
            for entry in publication.provenance
        ],
    }


_COMMON_PROVENANCE = {
    "retrieved_at": _RETRIEVED_AT,
    "query_id": _QUERY_ID,
    "run_id": _RUN_ID,
    "rendered_query": _RENDERED_QUERY,
}

CASES = (
    ProviderMappingCase(
        name="openalex",
        map_record=_map_openalex,
        rich_record={
            "id": "https://openalex.org/W123",
            "title": "  Lean energy  ",
            "abstract_inverted_index": {
                "Lean": [0],
                "energy": [1],
                "abstract": [2],
            },
            "authorships": [
                {
                    "author": {
                        "id": "https://openalex.org/A1",
                        "display_name": " Alice Example ",
                        "orcid": "https://orcid.org/0000-0001-2345-6789",
                    },
                    "institutions": [
                        {
                            "id": "https://openalex.org/I1",
                            "display_name": "First Institute",
                        },
                        {"display_name": "Second Institute"},
                    ],
                },
                {"author": {"display_name": "Bob Example"}},
            ],
            "publication_year": 2024,
            "publication_date": "2024-05-12",
            "doi": "https://doi.org/10.1000/Example",
            "primary_location": {
                "landing_page_url": "https://example.org/article",
                "pdf_url": "https://example.org/article.pdf",
                "source": {
                    "display_name": "Journal of Energy",
                    "type": "journal",
                    "issn_l": "1234-5678",
                    "issn": ["1234-5678", "8765-4321"],
                },
            },
            "type": "article",
            "language": "EN",
            "open_access": {"is_oa": True},
        },
        minimal_record={"id": "OA-Minimal", "title": " Minimal "},
        invalid_title_record={"id": "OA-Invalid", "title": " "},
        malformed_optional_record={
            "id": "OA-Malformed",
            "title": "Valid title",
            "abstract_inverted_index": [],
            "authorships": {},
            "publication_year": True,
            "publication_date": [],
            "doi": {},
            "primary_location": [],
            "type": [],
            "language": {},
            "open_access": {"is_oa": "yes"},
        },
        expected_rich_snapshot={
            "title": "Lean energy",
            "abstract": "Lean energy abstract",
            "authors": [
                {
                    "display_name": "Alice Example",
                    "given_name": None,
                    "family_name": None,
                    "identifiers": [
                        ("other", "https://openalex.org/A1", "openalex"),
                        ("orcid", "0000-0001-2345-6789", None),
                    ],
                    "affiliations": [
                        {
                            "name": "First Institute",
                            "identifiers": [
                                (
                                    "other",
                                    "https://openalex.org/I1",
                                    "openalex",
                                )
                            ],
                        },
                        {"name": "Second Institute", "identifiers": []},
                    ],
                },
                {
                    "display_name": "Bob Example",
                    "given_name": None,
                    "family_name": None,
                    "identifiers": [],
                    "affiliations": [],
                },
            ],
            "publication_year": 2024,
            "publication_date": "2024-05-12",
            "identifiers": [
                ("doi", "10.1000/example", None),
                ("other", "https://openalex.org/W123", "openalex"),
            ],
            "venue": {
                "name": "Journal of Energy",
                "type": "journal",
                "identifiers": [
                    ("issn", "1234-5678", None),
                    ("issn", "8765-4321", None),
                ],
            },
            "publisher": None,
            "document_type": "journal_article",
            "language": "EN",
            "urls": [
                "https://example.org/article",
                "https://example.org/article.pdf",
            ],
            "keywords": [],
            "open_access": True,
            "provenance": [
                {
                    "source": "openalex",
                    "source_record_id": "https://openalex.org/W123",
                    **_COMMON_PROVENANCE,
                }
            ],
        },
    ),
    ProviderMappingCase(
        name="crossref",
        map_record=_map_crossref,
        rich_record={
            "title": ["  Lean energy  "],
            "abstract": "<jats:p>Lean energy abstract</jats:p>",
            "author": [
                {
                    "given": " Alice ",
                    "family": " Example ",
                    "ORCID": "https://orcid.org/0000-0001-2345-6789",
                    "affiliation": [
                        {"name": " First Institute "},
                        {"name": "Second Institute"},
                    ],
                },
                {"given": "Bob", "family": "Example"},
            ],
            "issued": {"date-parts": [[2024, 5, 12]]},
            "DOI": "https://doi.org/10.1000/Example",
            "container-title": [" Journal of Energy "],
            "ISSN": ["1234-5678", "8765-4321"],
            "publisher": " Example Publisher ",
            "type": "journal-article",
            "language": "EN",
            "URL": "https://example.org/article",
        },
        minimal_record={
            "title": [" Minimal "],
            "DOI": "10.1000/minimal",
        },
        invalid_title_record={
            "title": [" "],
            "DOI": "10.1000/invalid",
        },
        malformed_optional_record={
            "title": ["Valid title"],
            "DOI": "10.1000/malformed",
            "abstract": [],
            "author": {},
            "issued": {"date-parts": [[True]]},
            "container-title": {},
            "ISSN": {},
            "publisher": [],
            "type": [],
            "language": {},
            "URL": [],
        },
        expected_rich_snapshot={
            "title": "Lean energy",
            "abstract": "Lean energy abstract",
            "authors": [
                {
                    "display_name": "Alice Example",
                    "given_name": "Alice",
                    "family_name": "Example",
                    "identifiers": [
                        ("orcid", "0000-0001-2345-6789", None)
                    ],
                    "affiliations": [
                        {"name": "First Institute", "identifiers": []},
                        {"name": "Second Institute", "identifiers": []},
                    ],
                },
                {
                    "display_name": "Bob Example",
                    "given_name": "Bob",
                    "family_name": "Example",
                    "identifiers": [],
                    "affiliations": [],
                },
            ],
            "publication_year": 2024,
            "publication_date": "2024-05-12",
            "identifiers": [("doi", "10.1000/example", None)],
            "venue": {
                "name": "Journal of Energy",
                "type": None,
                "identifiers": [
                    ("issn", "1234-5678", None),
                    ("issn", "8765-4321", None),
                ],
            },
            "publisher": "Example Publisher",
            "document_type": "journal_article",
            "language": "EN",
            "urls": ["https://example.org/article"],
            "keywords": [],
            "open_access": None,
            "provenance": [
                {
                    "source": "crossref",
                    "source_record_id": "10.1000/example",
                    **_COMMON_PROVENANCE,
                }
            ],
        },
    ),
    ProviderMappingCase(
        name="semantic_scholar",
        map_record=_map_semantic_scholar,
        rich_record={
            "paperId": "S2-123",
            "title": "  Lean energy  ",
            "abstract": " Lean energy abstract ",
            "authors": [
                {"name": " Alice Example "},
                {"name": "Bob Example"},
            ],
            "year": 2024,
            "publicationDate": "2024-05-12",
            "externalIds": {
                "DOI": "https://doi.org/10.1000/Example",
                "PubMed": "123456",
            },
            "publicationVenue": {
                "name": " Journal of Energy ",
                "type": "journal",
                "issn": "1234-5678",
                "issns": ["1234-5678", "8765-4321"],
            },
            "publicationTypes": ["JournalArticle"],
            "url": "https://example.org/article",
        },
        minimal_record={"paperId": "S2-Minimal", "title": " Minimal "},
        invalid_title_record={"paperId": "S2-Invalid", "title": " "},
        malformed_optional_record={
            "paperId": "S2-Malformed",
            "title": "Valid title",
            "abstract": [],
            "authors": {},
            "year": True,
            "publicationDate": [],
            "externalIds": [],
            "publicationVenue": [],
            "publicationTypes": {},
            "url": [],
        },
        expected_rich_snapshot={
            "title": "Lean energy",
            "abstract": "Lean energy abstract",
            "authors": [
                {
                    "display_name": "Alice Example",
                    "given_name": None,
                    "family_name": None,
                    "identifiers": [],
                    "affiliations": [],
                },
                {
                    "display_name": "Bob Example",
                    "given_name": None,
                    "family_name": None,
                    "identifiers": [],
                    "affiliations": [],
                },
            ],
            "publication_year": 2024,
            "publication_date": "2024-05-12",
            "identifiers": [
                ("other", "S2-123", "semantic_scholar"),
                ("doi", "10.1000/example", None),
                ("pmid", "123456", None),
            ],
            "venue": {
                "name": "Journal of Energy",
                "type": "journal",
                "identifiers": [
                    ("issn", "1234-5678", None),
                    ("issn", "8765-4321", None),
                ],
            },
            "publisher": None,
            "document_type": "journal_article",
            "language": None,
            "urls": ["https://example.org/article"],
            "keywords": [],
            "open_access": None,
            "provenance": [
                {
                    "source": "semantic_scholar",
                    "source_record_id": "S2-123",
                    **_COMMON_PROVENANCE,
                }
            ],
        },
    ),
)


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.name)
def test_rich_provider_record_matches_canonical_snapshot(
    case: ProviderMappingCase,
) -> None:
    publication = case.map_record(case.rich_record)

    assert isinstance(publication, Publication)
    assert _contract_snapshot(publication) == case.expected_rich_snapshot


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.name)
def test_minimal_record_preserves_canonical_optional_defaults(
    case: ProviderMappingCase,
) -> None:
    publication = case.map_record(case.minimal_record)

    assert isinstance(publication, Publication)
    assert publication.title == "Minimal"
    assert publication.abstract is None
    assert publication.authors == []
    assert publication.venue is None
    assert publication.publisher is None
    assert publication.document_type is None
    assert publication.language is None
    assert publication.urls == []
    assert publication.keywords == []
    assert publication.open_access is None
    assert len(publication.provenance) == 1


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.name)
def test_missing_valid_title_raises_provider_error(
    case: ProviderMappingCase,
) -> None:
    with pytest.raises(ValueError, match="title"):
        case.map_record(case.invalid_title_record)


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.name)
def test_malformed_optional_fields_do_not_escape_into_canonical_model(
    case: ProviderMappingCase,
) -> None:
    publication = case.map_record(case.malformed_optional_record)

    assert isinstance(publication, Publication)
    assert publication.title == "Valid title"
    assert publication.abstract is None
    assert publication.authors == []
    assert publication.publication_year is None
    assert publication.publication_date is None
    assert publication.venue is None
    assert publication.publisher is None
    assert publication.document_type is None
    assert publication.language is None
    assert publication.urls == []
    assert publication.open_access is None


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.name)
def test_provenance_is_complete_and_provider_specific(
    case: ProviderMappingCase,
) -> None:
    publication = case.map_record(case.rich_record)
    provenance = publication.provenance

    assert len(provenance) == 1
    assert provenance[0].source == case.name
    assert provenance[0].retrieved_at == _RETRIEVED_AT
    assert provenance[0].query_id == _QUERY_ID
    assert provenance[0].run_id == _RUN_ID
    assert provenance[0].rendered_query == _RENDERED_QUERY
    assert provenance[0].source_record_id == {
        "openalex": "https://openalex.org/W123",
        "crossref": "10.1000/example",
        "semantic_scholar": "S2-123",
    }[case.name]


def test_provider_data_dependent_differences_remain_explicit() -> None:
    publications = {
        case.name: case.map_record(case.rich_record)
        for case in CASES
    }
    openalex = publications["openalex"]
    crossref = publications["crossref"]
    semantic = publications["semantic_scholar"]

    assert openalex.authors[0].given_name is None
    assert openalex.authors[0].family_name is None
    assert openalex.publisher is None
    assert openalex.keywords == []

    assert crossref.authors[0].given_name == "Alice"
    assert crossref.authors[0].family_name == "Example"
    assert crossref.publisher == "Example Publisher"
    assert crossref.venue is not None
    assert crossref.venue.type is None
    assert all(identifier.type.value != "other" for identifier in crossref.identifiers)

    assert semantic.authors[0].given_name is None
    assert semantic.authors[0].family_name is None
    assert semantic.authors[0].identifiers == []
    assert semantic.authors[0].affiliations == []
    assert semantic.publisher is None
    assert any(identifier.type.value == "pmid" for identifier in semantic.identifiers)
