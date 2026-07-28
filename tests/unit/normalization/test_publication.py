from copy import deepcopy
from datetime import datetime, timezone
from uuid import UUID

from app.domain import (
    Affiliation,
    Author,
    Identifier,
    IdentifierType,
    ProvenanceEntry,
    Venue,
)
from app.domain.publication import DocumentType, Publication
from app.normalization import (
    Normalizer,
    PublicationNormalizer,
    normalize_publication,
)


def _publication() -> Publication:
    return Publication(
        record_id=UUID("11111111-1111-1111-1111-111111111111"),
        schema_version="1.0",
        title="Lean-Manufacturing: Energy",
        abstract="Original abstract",
        authors=[
            Author(
                display_name="Jane   O’Connor-Smith",
                given_name="Jane",
                family_name="O’Connor-Smith",
                identifiers=[
                    Identifier(
                        type=IdentifierType.ORCID,
                        value="https://orcid.org/0000-0002-1825-009x/",
                    ),
                    Identifier(type=IdentifierType.OTHER, value="A1"),
                ],
                affiliations=[Affiliation(name="Example Institute")],
            ),
            Author(display_name="Second   Author"),
        ],
        publication_year=2024,
        identifiers=[
            Identifier(
                type=IdentifierType.DOI,
                value="HTTPS://DOI.ORG/10.1000/Example",
            ),
            Identifier(type=IdentifierType.PMID, value="12345"),
            Identifier(
                type=IdentifierType.DOI,
                value="https://doi.org/10.1000/example",
            ),
        ],
        venue=Venue(name="Example Journal"),
        publisher="Example Publisher",
        document_type=DocumentType.JOURNAL_ARTICLE,
        language="en",
        keywords=["Lean", "Energy"],
        urls=["https://example.org/article"],
        provenance=[
            ProvenanceEntry(source="provider", source_record_id="record-1")
        ],
        created_at=datetime(2026, 7, 28, 12, 0, tzinfo=timezone.utc),
    )


def test_publication_normalizer_satisfies_structural_contract() -> None:
    normalizer: Normalizer[Publication, Publication] = PublicationNormalizer()

    assert normalizer.normalize(_publication()).title_normalized == (
        "lean manufacturing energy"
    )


def test_returns_new_deep_copy_without_mutating_input() -> None:
    publication = _publication()
    original = deepcopy(publication)

    result = normalize_publication(publication)

    assert result is not publication
    assert publication == original
    assert result.authors is not publication.authors
    assert result.identifiers is not publication.identifiers
    assert result.provenance is not publication.provenance
    assert result.keywords is not publication.keywords
    assert result.urls is not publication.urls


def test_preserves_title_and_calculates_normalized_title() -> None:
    result = normalize_publication(_publication())

    assert result.title == "Lean-Manufacturing: Energy"
    assert result.title_normalized == "lean manufacturing energy"


def test_normalizes_doi_without_deduplicating_or_reordering_identifiers() -> None:
    result = normalize_publication(_publication())

    assert [
        (identifier.type, identifier.value)
        for identifier in result.identifiers
    ] == [
        (IdentifierType.DOI, "10.1000/example"),
        (IdentifierType.PMID, "12345"),
        (IdentifierType.DOI, "10.1000/example"),
    ]


def test_normalizes_authors_and_only_their_orcid_identifiers() -> None:
    result = normalize_publication(_publication())

    assert [author.display_name for author in result.authors] == [
        "Jane O’Connor-Smith",
        "Second Author",
    ]
    assert [
        (identifier.type, identifier.value)
        for identifier in result.authors[0].identifiers
    ] == [
        (IdentifierType.ORCID, "0000-0002-1825-009X"),
        (IdentifierType.OTHER, "A1"),
    ]


def test_preserves_identity_metadata_and_unchanged_fields() -> None:
    publication = _publication()
    result = normalize_publication(publication)

    assert result.record_id == publication.record_id
    assert result.schema_version == publication.schema_version
    assert result.created_at == publication.created_at
    assert result.provenance == publication.provenance
    assert result.abstract == publication.abstract
    assert result.publication_year == publication.publication_year
    assert result.venue == publication.venue
    assert result.publisher == publication.publisher
    assert result.document_type == publication.document_type
    assert result.language == publication.language
    assert result.keywords == publication.keywords
    assert result.urls == publication.urls
    assert result.authors[0].affiliations == publication.authors[0].affiliations


def test_normalization_is_idempotent() -> None:
    publication = _publication()

    assert normalize_publication(normalize_publication(publication)) == (
        normalize_publication(publication)
    )


def test_normalization_is_deterministic() -> None:
    publication = _publication()

    assert normalize_publication(publication) == normalize_publication(publication)
