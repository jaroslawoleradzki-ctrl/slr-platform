from datetime import date, datetime, timezone
from typing import Any, cast
from uuid import UUID

import pytest

from app.domain import IdentifierType, VenueType
from app.domain.publication import DocumentType
from app.domain.search import SearchQuery, SearchRun, SearchTerm
from app.providers.search.semantic_scholar import SemanticScholarProvider

_QUERY_ID = UUID("00000000-0000-0000-0000-000000000001")
_RUN_ID = UUID("00000000-0000-0000-0000-000000000002")
_RETRIEVED_AT = datetime(2026, 7, 24, 12, 0, tzinfo=timezone.utc)


def build_search_context() -> tuple[SearchRun, SearchQuery]:
    search_query = SearchQuery(
        query_id=_QUERY_ID,
        name="Lean energy",
        expression=SearchTerm(value="lean energy"),
    )
    search_run = SearchRun(
        run_id=_RUN_ID,
        query_id=search_query.query_id,
        query_version=search_query.version,
        provider="semantic_scholar",
        rendered_query="lean energy",
    )
    return search_run, search_query


def test_map_paper_full_record() -> None:
    provider = SemanticScholarProvider()
    search_run, search_query = build_search_context()
    paper = {
        "paperId": "abc-123",
        "title": "  Lean Construction  ",
        "abstract": " An abstract study on lean manufacturing. ",
        "year": 2024,
        "publicationDate": "2024-05-12",
        "url": "https://www.semanticscholar.org/paper/abc-123",
        "authors": [
            {"authorId": "a1", "name": "Jane Doe"},
            {"authorId": "a2", "name": "  "},  # skipped
            {"authorId": "a3", "name": "John Smith"},
        ],
        "publicationVenue": {
            "name": "Journal of Lean Production",
            "type": "journal",
            "issn": "1234-5678",
            "issns": ["1234-5678", "8765-4321"],
        },
        "publicationTypes": ["JournalArticle", "Review"],
        "externalIds": {
            "DOI": " 10.1000/xyz-123 ",
            "PubMed": "12345",
        }
    }

    pub = provider.map_paper(
        paper,
        search_run=search_run,
        search_query=search_query,
        retrieved_at=_RETRIEVED_AT,
    )

    assert pub.title == "Lean Construction"
    assert pub.abstract == "An abstract study on lean manufacturing."
    assert pub.publication_year == 2024
    assert pub.publication_date == date(2024, 5, 12)
    assert pub.urls == ["https://www.semanticscholar.org/paper/abc-123"]

    assert len(pub.authors) == 2
    assert pub.authors[0].display_name == "Jane Doe"
    assert pub.authors[1].display_name == "John Smith"

    assert pub.venue is not None
    assert pub.venue.name == "Journal of Lean Production"
    assert pub.venue.type == VenueType.JOURNAL
    assert len(pub.venue.identifiers) == 2
    assert pub.venue.identifiers[0].type == IdentifierType.ISSN
    assert pub.venue.identifiers[0].value == "1234-5678"
    assert pub.venue.identifiers[1].value == "8765-4321"

    assert pub.document_type == DocumentType.JOURNAL_ARTICLE

    assert len(pub.identifiers) == 3
    # paperId
    assert pub.identifiers[0].type == IdentifierType.OTHER
    assert pub.identifiers[0].value == "abc-123"
    assert pub.identifiers[0].source == "semanticscholar"
    # DOI
    assert pub.identifiers[1].type == IdentifierType.DOI
    assert pub.identifiers[1].value == "10.1000/xyz-123"
    # PMID
    assert pub.identifiers[2].type == IdentifierType.PMID
    assert pub.identifiers[2].value == "12345"

    assert len(pub.provenance) == 1
    prov = pub.provenance[0]
    assert prov.source == "semantic_scholar"
    assert prov.source_record_id == "abc-123"
    assert prov.retrieved_at == _RETRIEVED_AT
    assert prov.query_id == search_query.query_id
    assert prov.run_id == search_run.run_id
    assert prov.rendered_query == search_run.rendered_query


def test_map_paper_minimal_record() -> None:
    provider = SemanticScholarProvider()
    search_run, search_query = build_search_context()
    paper = {
        "paperId": "abc-123",
        "title": "Minimal title"
    }
    pub = provider.map_paper(
        paper,
        search_run=search_run,
        search_query=search_query,
        retrieved_at=_RETRIEVED_AT,
    )
    assert pub.title == "Minimal title"
    assert pub.abstract is None
    assert pub.authors == []
    assert pub.publication_year is None
    assert pub.publication_date is None
    assert pub.venue is None
    assert pub.document_type is None
    assert len(pub.identifiers) == 1
    assert pub.identifiers[0].value == "abc-123"
    assert pub.urls == []


def test_map_paper_missing_title_raises_value_error() -> None:
    provider = SemanticScholarProvider()
    search_run, search_query = build_search_context()
    with pytest.raises(ValueError, match="Semantic Scholar paper title is missing or blank"):
        provider.map_paper(
            {"paperId": "abc-123", "title": "   "},
            search_run=search_run,
            search_query=search_query,
            retrieved_at=_RETRIEVED_AT,
        )
    with pytest.raises(ValueError, match="Semantic Scholar paper title is missing or blank"):
        provider.map_paper(
            {"paperId": "abc-123"},
            search_run=search_run,
            search_query=search_query,
            retrieved_at=_RETRIEVED_AT,
        )


def test_map_paper_external_ids_handling() -> None:
    provider = SemanticScholarProvider()
    search_run, search_query = build_search_context()

    # externalIds missing
    pub1 = provider.map_paper(
        {"paperId": "abc-123", "title": "Test"},
        search_run=search_run,
        search_query=search_query,
        retrieved_at=_RETRIEVED_AT,
    )
    assert len(pub1.identifiers) == 1
    assert pub1.identifiers[0].value == "abc-123"

    # externalIds is None
    pub2 = provider.map_paper(
        {"paperId": "abc-123", "title": "Test", "externalIds": None},
        search_run=search_run,
        search_query=search_query,
        retrieved_at=_RETRIEVED_AT,
    )
    assert len(pub2.identifiers) == 1
    assert pub2.identifiers[0].value == "abc-123"

    # externalIds empty or missing specific keys
    pub3 = provider.map_paper(
        {"paperId": "abc-123", "title": "Test", "externalIds": {"ArXiv": "123"}},
        search_run=search_run,
        search_query=search_query,
        retrieved_at=_RETRIEVED_AT,
    )
    assert len(pub3.identifiers) == 1
    assert pub3.identifiers[0].value == "abc-123"


def test_map_paper_authors_handling() -> None:
    provider = SemanticScholarProvider()
    search_run, search_query = build_search_context()

    # empty list
    pub1 = provider.map_paper(
        {"paperId": "abc-123", "title": "Test", "authors": []},
        search_run=search_run,
        search_query=search_query,
        retrieved_at=_RETRIEVED_AT,
    )
    assert pub1.authors == []

    # authors contains invalid format
    pub2 = provider.map_paper(
        {
            "paperId": "abc-123",
            "title": "Test",
            "authors": [
                "Jane Doe",  # not a dict, should be skipped
                {"name": "John Smith"}
            ]
        },
        search_run=search_run,
        search_query=search_query,
        retrieved_at=_RETRIEVED_AT,
    )
    assert len(pub2.authors) == 1
    assert pub2.authors[0].display_name == "John Smith"


def test_map_paper_venue_handling() -> None:
    provider = SemanticScholarProvider()
    search_run, search_query = build_search_context()

    # publicationVenue dict with fallback to venue string
    pub1 = provider.map_paper(
        {
            "paperId": "abc-123",
            "title": "Test",
            "publicationVenue": {"type": "journal"},
            "venue": "Venue String"
        },
        search_run=search_run,
        search_query=search_query,
        retrieved_at=_RETRIEVED_AT,
    )
    assert pub1.venue is not None
    assert pub1.venue.name == "Venue String"
    assert pub1.venue.type == VenueType.JOURNAL

    # Top-level venue string only
    pub2 = provider.map_paper(
        {
            "paperId": "abc-123",
            "title": "Test",
            "venue": "Top-level Venue"
        },
        search_run=search_run,
        search_query=search_query,
        retrieved_at=_RETRIEVED_AT,
    )
    assert pub2.venue is not None
    assert pub2.venue.name == "Top-level Venue"
    assert pub2.venue.type is None


def test_map_paper_publication_types() -> None:
    provider = SemanticScholarProvider()
    search_run, search_query = build_search_context()

    # Recognized type
    pub1 = provider.map_paper(
        {
            "paperId": "abc-123",
            "title": "Test",
            "publicationTypes": ["Conference", "Book"]
        },
        search_run=search_run,
        search_query=search_query,
        retrieved_at=_RETRIEVED_AT,
    )
    assert pub1.document_type == DocumentType.CONFERENCE_PAPER

    # Unrecognized type
    pub2 = provider.map_paper(
        {
            "paperId": "abc-123",
            "title": "Test",
            "publicationTypes": ["UnknownType"]
        },
        search_run=search_run,
        search_query=search_query,
        retrieved_at=_RETRIEVED_AT,
    )
    assert pub2.document_type == DocumentType.OTHER

    # Missing types
    pub3 = provider.map_paper(
        {
            "paperId": "abc-123",
            "title": "Test",
            "publicationTypes": []
        },
        search_run=search_run,
        search_query=search_query,
        retrieved_at=_RETRIEVED_AT,
    )
    assert pub3.document_type is None


def test_map_paper_date_alignment() -> None:
    provider = SemanticScholarProvider()
    search_run, search_query = build_search_context()

    # Conflicting date and year: year kept, date cleared
    pub1 = provider.map_paper(
        {
            "paperId": "abc-123",
            "title": "Test",
            "year": 2024,
            "publicationDate": "2023-12-15"
        },
        search_run=search_run,
        search_query=search_query,
        retrieved_at=_RETRIEVED_AT,
    )
    assert pub1.publication_year == 2024
    assert pub1.publication_date is None

    # Correct date and year: both kept
    pub2 = provider.map_paper(
        {
            "paperId": "abc-123",
            "title": "Test",
            "year": 2024,
            "publicationDate": "2024-05-12"
        },
        search_run=search_run,
        search_query=search_query,
        retrieved_at=_RETRIEVED_AT,
    )
    assert pub2.publication_year == 2024
    assert pub2.publication_date == date(2024, 5, 12)

    # Missing year: inferred from date
    pub3 = provider.map_paper(
        {
            "paperId": "abc-123",
            "title": "Test",
            "publicationDate": "2024-05-12"
        },
        search_run=search_run,
        search_query=search_query,
        retrieved_at=_RETRIEVED_AT,
    )
    assert pub3.publication_year == 2024
    assert pub3.publication_date == date(2024, 5, 12)


def test_map_paper_non_dictionary_raises_type_error() -> None:
    provider = SemanticScholarProvider()
    search_run, search_query = build_search_context()
    with pytest.raises(TypeError, match="paper must be a dictionary"):
        provider.map_paper(
            cast(Any, "not-a-dict"),
            search_run=search_run,
            search_query=search_query,
            retrieved_at=_RETRIEVED_AT,
        )


@pytest.mark.parametrize(
    "paper_data",
    [
        {"title": "Test"},  # missing paperId
        {"paperId": None, "title": "Test"},  # paperId=None
        {"paperId": "   ", "title": "Test"},  # paperId="   "
    ],
    ids=["missing", "none", "blank"]
)
def test_map_paper_invalid_paper_id_raises_value_error(paper_data: dict[str, Any]) -> None:
    provider = SemanticScholarProvider()
    search_run, search_query = build_search_context()
    with pytest.raises(ValueError, match="Semantic Scholar paper must have a valid paperId for provenance"):
        provider.map_paper(
            paper_data,
            search_run=search_run,
            search_query=search_query,
            retrieved_at=_RETRIEVED_AT,
        )
