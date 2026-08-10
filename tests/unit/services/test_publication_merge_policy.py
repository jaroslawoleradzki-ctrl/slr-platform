from copy import deepcopy
from datetime import date, datetime, timezone
from uuid import UUID

import pytest

from app.domain import (
    Author,
    Identifier,
    IdentifierType,
    ProvenanceEntry,
    Venue,
)
from app.domain.publication import DocumentType, Publication
from app.services.publication_merge_policy import (
    PublicationMergeConflict,
    PublicationMergePolicy,
)
from app.services.result_merger import ResultMerger

_EARLY_ID = UUID("00000000-0000-0000-0000-000000000001")
_LATE_ID = UUID("00000000-0000-0000-0000-000000000002")
_EARLY_TIME = datetime(2026, 7, 28, 8, 0, tzinfo=timezone.utc)
_LATE_TIME = datetime(2026, 7, 29, 8, 0, tzinfo=timezone.utc)


def _doi(value: str) -> Identifier:
    return Identifier(type=IdentifierType.DOI, value=value)


def _provenance(source: str, record_id: str) -> ProvenanceEntry:
    return ProvenanceEntry(
        source=source,
        source_record_id=record_id,
        retrieved_at=_EARLY_TIME,
    )


def _publication(
    *,
    record_id: UUID = _EARLY_ID,
    title: str = "Study",
    abstract: str | None = None,
    authors: list[Author] | None = None,
    identifiers: list[Identifier] | None = None,
    provenance: list[ProvenanceEntry] | None = None,
    publication_year: int | None = None,
    publication_date: date | None = None,
    venue: Venue | None = None,
    publisher: str | None = None,
    document_type: DocumentType | None = None,
    schema_version: str = "1.0",
    language: str | None = None,
    keywords: list[str] | None = None,
    urls: list[str] | None = None,
    open_access: bool | None = None,
) -> Publication:
    return Publication(
        record_id=record_id,
        schema_version=schema_version,
        title=title,
        abstract=abstract,
        authors=authors or [],
        identifiers=identifiers or [],
        provenance=provenance or [],
        publication_year=publication_year,
        publication_date=publication_date,
        venue=venue,
        publisher=publisher,
        document_type=document_type,
        language=language,
        keywords=keywords or [],
        urls=urls or [],
        open_access=open_access,
        created_at=_EARLY_TIME if record_id == _EARLY_ID else _LATE_TIME,
    )


def test_merge_publications_with_same_doi_preserves_available_values() -> None:
    first = _publication(
        identifiers=[_doi("10.1000/example")],
        publisher="Publisher",
    )
    second = _publication(
        record_id=_LATE_ID,
        identifiers=[_doi("HTTPS://DOI.ORG/10.1000/EXAMPLE")],
        abstract="Available abstract",
    )

    result = PublicationMergePolicy().merge(first, second)

    assert result.record_id == _EARLY_ID
    assert result.publisher == "Publisher"
    assert result.abstract == "Available abstract"
    assert result.identifiers == [_doi("10.1000/example")]


def test_longer_title_and_abstract_win_deterministically() -> None:
    short = _publication(title="Short title", abstract="Short")
    complete = _publication(
        record_id=_LATE_ID,
        title="A substantially more complete title",
        abstract="A substantially more complete abstract.",
    )

    result = PublicationMergePolicy().merge(short, complete)

    assert result.title == complete.title
    assert result.title_normalized == "a substantially more complete title"
    assert result.abstract == complete.abstract


def test_merge_is_commutative_and_deterministic() -> None:
    first = _publication(
        title="Alpha title",
        identifiers=[
            _doi("10.1000/example"),
            Identifier(type=IdentifierType.ISSN, value="2222-2222"),
        ],
        keywords=["Beta"],
        provenance=[_provenance("openalex", "W1")],
    )
    second = _publication(
        record_id=_LATE_ID,
        title="Omega title",
        identifiers=[
            Identifier(type=IdentifierType.PMID, value="123"),
            _doi("10.1000/example"),
        ],
        keywords=["Alpha"],
        provenance=[_provenance("crossref", "C1")],
    )
    policy = PublicationMergePolicy()

    assert policy.merge(first, second) == policy.merge(second, first)
    assert policy.merge(first, second) == policy.merge(first, second)


def test_merged_record_id_is_smallest_existing_member_id() -> None:
    smallest = _publication(record_id=_EARLY_ID)
    largest = _publication(record_id=_LATE_ID)
    policy = PublicationMergePolicy()

    assert policy.merge(largest, smallest).record_id == _EARLY_ID
    assert policy.merge(smallest, largest).record_id == _EARLY_ID


def test_merge_is_idempotent_and_returns_valid_new_publication() -> None:
    publication = _publication(
        title="Complete title",
        identifiers=[_doi("10.1000/example")],
        publication_year=2024,
        publication_date=date(2024, 1, 2),
    )

    result = PublicationMergePolicy().merge(publication, publication)

    assert result == publication
    assert result is not publication
    assert Publication.model_validate(result.model_dump()) == result


def test_merge_does_not_mutate_inputs() -> None:
    first = _publication(keywords=["First"])
    second = _publication(record_id=_LATE_ID, keywords=["Second"])
    first_before = deepcopy(first)
    second_before = deepcopy(second)

    PublicationMergePolicy().merge(first, second)

    assert first == first_before
    assert second == second_before


def test_identifiers_are_complete_unique_and_stably_ordered() -> None:
    first = _publication(
        identifiers=[
            Identifier(type=IdentifierType.ISSN, value="2222-2222"),
            _doi("10.1000/example"),
        ]
    )
    second = _publication(
        record_id=_LATE_ID,
        identifiers=[
            Identifier(type=IdentifierType.PMID, value="123"),
            _doi("doi:10.1000/EXAMPLE"),
            Identifier(type=IdentifierType.ISSN, value="1111-1111"),
        ],
    )

    result = PublicationMergePolicy().merge(first, second)

    assert [(item.type, item.value) for item in result.identifiers] == [
        (IdentifierType.DOI, "10.1000/example"),
        (IdentifierType.ISSN, "1111-1111"),
        (IdentifierType.ISSN, "2222-2222"),
        (IdentifierType.PMID, "123"),
    ]


def test_same_identifier_from_different_sources_preserves_both_attributions() -> None:
    first = _publication(
        identifiers=[
            Identifier(
                type=IdentifierType.DOI,
                value="10.1000/example",
                source="openalex",
            )
        ]
    )
    second = _publication(
        record_id=_LATE_ID,
        identifiers=[
            Identifier(
                type=IdentifierType.DOI,
                value="doi:10.1000/EXAMPLE",
                source="crossref",
            )
        ],
    )

    result = PublicationMergePolicy().merge(first, second)

    assert [(item.value, item.source) for item in result.identifiers] == [
        ("10.1000/example", "crossref"),
        ("10.1000/example", "openalex"),
    ]


@pytest.mark.parametrize(
    "identifier_type",
    [IdentifierType.DOI, IdentifierType.PMID, IdentifierType.OPENALEX],
)
def test_conflicting_unique_identifiers_are_explicit(
    identifier_type: IdentifierType,
) -> None:
    first = _publication(identifiers=[Identifier(type=identifier_type, value="first")])
    second = _publication(
        record_id=_LATE_ID,
        identifiers=[Identifier(type=identifier_type, value="second")],
    )

    with pytest.raises(PublicationMergeConflict, match="conflicting"):
        PublicationMergePolicy().merge(first, second)


def test_provenance_is_complete_unique_and_stably_ordered() -> None:
    duplicate = _provenance("openalex", "W1")
    crossref = _provenance("crossref", "C1")
    first = _publication(provenance=[duplicate])
    second = _publication(
        record_id=_LATE_ID,
        provenance=[duplicate, crossref],
    )

    result = PublicationMergePolicy().merge(first, second)

    assert result.provenance == [crossref, duplicate]


def test_more_complete_ordered_author_list_is_selected_whole() -> None:
    short = _publication(authors=[Author(display_name="Jane Doe")])
    complete_authors = [
        Author(
            display_name="Jane Doe",
            given_name="Jane",
            family_name="Doe",
        ),
        Author(display_name="John Smith"),
    ]
    complete = _publication(record_id=_LATE_ID, authors=complete_authors)

    result = PublicationMergePolicy().merge(short, complete)

    assert result.authors == complete_authors


def test_collections_are_unique_and_stably_ordered() -> None:
    first = _publication(
        keywords=["Zulu", "Alpha"],
        urls=["https://example.org/z", "https://example.org/a"],
    )
    second = _publication(
        record_id=_LATE_ID,
        keywords=["Alpha", "Beta"],
        urls=["https://example.org/a", "https://example.org/b"],
    )

    result = PublicationMergePolicy().merge(first, second)

    assert result.keywords == ["Alpha", "Beta", "Zulu"]
    assert result.urls == [
        "https://example.org/a",
        "https://example.org/b",
        "https://example.org/z",
    ]


def test_more_complete_venue_and_bibliographic_date_are_selected() -> None:
    first = _publication(
        publication_year=2024,
        venue=Venue(name="Journal"),
    )
    second = _publication(
        record_id=_LATE_ID,
        publication_year=2023,
        publication_date=date(2023, 2, 1),
        venue=Venue(
            name="Journal",
            publisher="Publisher",
            identifiers=[Identifier(type=IdentifierType.ISSN, value="1234-5678")],
        ),
        document_type=DocumentType.JOURNAL_ARTICLE,
    )

    result = PublicationMergePolicy().merge(first, second)

    assert result.publication_year == 2023
    assert result.publication_date == date(2023, 2, 1)
    assert result.venue == second.venue
    assert result.document_type is DocumentType.JOURNAL_ARTICLE


def test_conflicting_open_access_values_are_explicit() -> None:
    first = _publication(open_access=True)
    second = _publication(record_id=_LATE_ID, open_access=False)

    with pytest.raises(PublicationMergeConflict, match="open_access"):
        PublicationMergePolicy().merge(first, second)


@pytest.mark.parametrize(
    ("first_version", "second_version"),
    [("1.0", "2.0"), ("2.0", "10.0")],
)
def test_different_schema_versions_are_an_explicit_conflict(
    first_version: str,
    second_version: str,
) -> None:
    first = _publication(schema_version=first_version)
    second = _publication(record_id=_LATE_ID, schema_version=second_version)

    with pytest.raises(PublicationMergeConflict, match="schema_version"):
        PublicationMergePolicy().merge(first, second)


def test_language_is_not_selected_by_text_length() -> None:
    first = _publication(language="en")
    second = _publication(record_id=_LATE_ID, language="eng")

    with pytest.raises(PublicationMergeConflict, match="language"):
        PublicationMergePolicy().merge(first, second)


def test_later_full_publication_date_wins_explicitly() -> None:
    first = _publication(
        publication_year=2023,
        publication_date=date(2023, 12, 31),
    )
    second = _publication(
        record_id=_LATE_ID,
        publication_year=2024,
        publication_date=date(2024, 1, 1),
    )

    result = PublicationMergePolicy().merge(first, second)

    assert result.publication_date == date(2024, 1, 1)
    assert result.publication_year == 2024


def test_result_merger_keeps_existing_doi_only_first_record_behavior() -> None:
    first = _publication(
        title="First",
        identifiers=[_doi("10.1000/example")],
    )
    duplicate = _publication(
        record_id=_LATE_ID,
        title="Richer duplicate title",
        identifiers=[_doi("10.1000/example")],
    )
    same_title_different_doi = _publication(
        title="First",
        identifiers=[_doi("10.1000/other")],
    )

    result = ResultMerger().merge([first, duplicate, same_title_different_doi])

    assert result == [first, same_title_different_doi]
    assert result[0] is first


def test_repeated_merge_does_not_accumulate_collection_duplicates() -> None:
    first = _publication(
        authors=[Author(display_name="Jane Doe")],
        identifiers=[_doi("10.1000/example")],
        provenance=[_provenance("openalex", "W1")],
        keywords=["Lean"],
    )
    second = _publication(
        record_id=_LATE_ID,
        authors=[
            Author(display_name="Jane Doe"),
            Author(display_name="John Smith"),
        ],
        identifiers=[
            _doi("10.1000/example"),
            Identifier(type=IdentifierType.PMID, value="123"),
        ],
        provenance=[_provenance("crossref", "C1")],
        keywords=["Energy"],
    )
    policy = PublicationMergePolicy()

    merged = policy.merge(first, second)
    repeated = policy.merge(merged, second)

    assert repeated == merged
    assert len(repeated.identifiers) == 2
    assert len(repeated.authors) == 2
    assert len(repeated.provenance) == 2
