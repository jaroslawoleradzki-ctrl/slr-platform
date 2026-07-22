from datetime import date, datetime

import pytest
from pydantic import ValidationError

from app.domain import Affiliation, Author, Identifier, IdentifierType, ProvenanceEntry, Venue
from app.domain.publication import DocumentType, Publication


def test_publication_builds_canonical_record() -> None:
    publication = Publication(
        title="  Lean manufacturing and energy efficiency  ",
        authors=[
            Author(
                display_name="Jane Doe",
                affiliations=[Affiliation(name="Example University")],
            )
        ],
        publication_year=2024,
        publication_date=date(2024, 5, 1),
        identifiers=[Identifier(type=IdentifierType.DOI, value="10.1000/example")],
        venue=Venue(name="Journal of Cleaner Production"),
        document_type=DocumentType.JOURNAL_ARTICLE,
        language="EN",
        keywords=["Lean", "energy efficiency", "lean"],
        urls=["https://example.org/article", "https://example.org/article"],
        provenance=[ProvenanceEntry(source="openalex", source_record_id="W123")],
    )

    assert publication.title == "Lean manufacturing and energy efficiency"
    assert publication.language == "en"
    assert publication.keywords == ["Lean", "energy efficiency"]
    assert publication.urls == ["https://example.org/article"]
    assert publication.authors[0].display_name == "Jane Doe"
    assert publication.provenance[0].source == "openalex"


def test_publication_rejects_blank_title() -> None:
    with pytest.raises(ValidationError):
        Publication(title="   ")


def test_publication_rejects_inconsistent_year_and_date() -> None:
    with pytest.raises(ValidationError):
        Publication(
            title="Example",
            publication_year=2023,
            publication_date=date(2024, 1, 1),
        )


def test_publication_rejects_unsupported_url_scheme() -> None:
    with pytest.raises(ValidationError):
        Publication(title="Example", urls=["ftp://example.org/article"])


def test_publication_requires_timezone_aware_created_at() -> None:
    with pytest.raises(ValidationError):
        Publication(title="Example", created_at=datetime(2026, 1, 1, 12, 0, 0))


def test_publication_is_immutable() -> None:
    publication = Publication(title="Example")

    with pytest.raises(ValidationError):
        publication.title = "Changed"
