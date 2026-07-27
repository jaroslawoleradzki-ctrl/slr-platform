from typing import Any, cast

import pytest
from pydantic import ValidationError

from app.domain import DocumentType, IdentifierType, VenueType
from app.providers.openalex import OpenAlexClient
from app.providers.search.openalex import OpenAlexProvider


def build_provider() -> OpenAlexProvider:
    return OpenAlexProvider(client=cast(OpenAlexClient, object()))


def representative_work() -> dict[str, Any]:
    return {
        "id": "https://openalex.org/W123",
        "title": "  Lean energy efficiency  ",
        "abstract_inverted_index": {
            "Lean": [0],
            "improves": [1],
            "energy": [2],
            "efficiency": [3],
        },
        "publication_year": 2024,
        "publication_date": "2024-05-12",
        "doi": "https://doi.org/10.1000/Example",
        "type": "article",
        "language": "EN",
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
                        "ror": "https://ror.org/012345678",
                        "display_name": " Example University ",
                    }
                ],
            },
            {
                "author": {
                    "id": "https://openalex.org/A2",
                    "display_name": "Bob Example",
                },
                "institutions": [],
            },
        ],
        "primary_location": {
            "landing_page_url": " https://example.org/article ",
            "pdf_url": "https://example.org/article.pdf",
            "source": {
                "display_name": " Journal of Efficient Systems ",
                "type": "journal",
                "issn_l": "1234-5678",
                "issn": ["1234-5678", "8765-4321"],
                "host_organization_name": "Hosting Organization",
            },
        },
        "best_oa_location": {
            "landing_page_url": "https://example.org/article",
            "pdf_url": "https://repository.example.org/article.pdf",
        },
        "open_access": {"is_oa": True},
        "topics": [{"display_name": "Energy efficiency"}],
    }


def test_map_work_maps_representative_record_without_provenance() -> None:
    publication = build_provider().map_work(representative_work())

    assert publication.title == "Lean energy efficiency"
    assert publication.abstract == "Lean improves energy efficiency"
    assert [author.display_name for author in publication.authors] == [
        "Alice Example",
        "Bob Example",
    ]
    assert publication.authors[0].given_name is None
    assert publication.authors[0].family_name is None
    assert [
        (identifier.type, identifier.value, identifier.source)
        for identifier in publication.authors[0].identifiers
    ] == [
        (
            IdentifierType.OTHER,
            "https://openalex.org/A1",
            "openalex",
        ),
        (
            IdentifierType.ORCID,
            "0000-0001-2345-6789",
            None,
        ),
    ]
    affiliation = publication.authors[0].affiliations[0]
    assert affiliation.name == "Example University"
    assert [(item.value, item.source) for item in affiliation.identifiers] == [
        ("https://openalex.org/I1", "openalex"),
        ("https://ror.org/012345678", "ror"),
    ]
    assert publication.publication_year == 2024
    assert publication.publication_date is not None
    assert publication.publication_date.isoformat() == "2024-05-12"
    assert [
        (identifier.type, identifier.value, identifier.source)
        for identifier in publication.identifiers
    ] == [
        (
            IdentifierType.DOI,
            "10.1000/example",
            None,
        ),
        (
            IdentifierType.OTHER,
            "https://openalex.org/W123",
            "openalex",
        ),
    ]
    assert publication.venue is not None
    assert publication.venue.name == "Journal of Efficient Systems"
    assert publication.venue.type is VenueType.JOURNAL
    assert [item.value for item in publication.venue.identifiers] == [
        "1234-5678",
        "8765-4321",
    ]
    assert publication.document_type is DocumentType.JOURNAL_ARTICLE
    assert publication.language == "en"
    assert publication.urls == [
        "https://example.org/article",
        "https://example.org/article.pdf",
        "https://repository.example.org/article.pdf",
    ]
    assert publication.open_access is True
    assert publication.publisher is None
    assert publication.keywords == []
    assert publication.provenance == []


def test_map_work_maps_minimal_record() -> None:
    publication = build_provider().map_work({"title": "Minimal"})

    assert publication.title == "Minimal"
    assert publication.abstract is None
    assert publication.authors == []
    assert publication.identifiers == []
    assert publication.venue is None
    assert publication.urls == []


def test_map_work_rejects_non_dictionary() -> None:
    with pytest.raises(TypeError, match="OpenAlex work must be a dictionary"):
        build_provider().map_work(cast(dict[str, Any], ["not", "a", "dict"]))


@pytest.mark.parametrize("work", [{}, {"title": "   "}, {"title": 42}])
def test_map_work_rejects_missing_or_invalid_title(work: dict[str, Any]) -> None:
    with pytest.raises(
        ValueError,
        match="OpenAlex work title must be a non-blank string",
    ):
        build_provider().map_work(work)


def test_map_work_uses_display_name_as_title_fallback() -> None:
    publication = build_provider().map_work(
        {"title": " ", "display_name": " Fallback title "}
    )

    assert publication.title == "Fallback title"


def test_abstract_reconstruction_handles_repetition_order_and_collisions() -> None:
    publication = build_provider().map_work(
        {
            "title": "Abstract",
            "abstract_inverted_index": {
                "repeat": [2, 0],
                "zeta": [1],
                "alpha": [1],
            },
        }
    )

    assert publication.abstract == "repeat alpha repeat"


@pytest.mark.parametrize(
    "abstract",
    [
        "not a dictionary",
        {"token": "not a list"},
        {"token": [True]},
        {"token": [-1]},
        {1: [0]},
        {"token": ["0"]},
        {" ": [0]},
        {},
    ],
)
def test_malformed_abstract_is_omitted(abstract: Any) -> None:
    publication = build_provider().map_work(
        {"title": "Malformed abstract", "abstract_inverted_index": abstract}
    )

    assert publication.abstract is None


def test_malformed_authorships_are_skipped_and_order_is_preserved() -> None:
    publication = build_provider().map_work(
        {
            "title": "Authors",
            "authorships": [
                None,
                {},
                {"author": {"display_name": " "}},
                {"author": {"display_name": "First"}},
                {"author": {"display_name": "Second"}},
            ],
        }
    )

    assert [author.display_name for author in publication.authors] == [
        "First",
        "Second",
    ]


@pytest.mark.parametrize("year", [True, 999, 10000, "2024"])
def test_invalid_publication_year_is_omitted(year: Any) -> None:
    publication = build_provider().map_work(
        {"title": "Year", "publication_year": year}
    )

    assert publication.publication_year is None


def test_publication_year_is_inferred_from_valid_date() -> None:
    publication = build_provider().map_work(
        {"title": "Date", "publication_date": "2024-05-12"}
    )

    assert publication.publication_year == 2024
    assert publication.publication_date is not None


def test_conflicting_date_is_omitted_and_explicit_year_is_preserved() -> None:
    publication = build_provider().map_work(
        {
            "title": "Date conflict",
            "publication_year": 2023,
            "publication_date": "2024-05-12",
        }
    )

    assert publication.publication_year == 2023
    assert publication.publication_date is None


@pytest.mark.parametrize(
    "publication_date",
    ["2024", "2024-05", "2024-02-30", "", None, 20240512],
)
def test_invalid_publication_date_is_omitted(publication_date: Any) -> None:
    publication = build_provider().map_work(
        {"title": "Date", "publication_date": publication_date}
    )

    assert publication.publication_date is None


@pytest.mark.parametrize(
    "doi",
    [
        "https://doi.org/10.1000/MixedCase",
        "http://doi.org/10.1000/MixedCase",
        "doi:10.1000/MixedCase",
    ],
)
def test_doi_uses_phase_5_3_canonical_normalization(doi: str) -> None:
    publication = build_provider().map_work({"title": "DOI", "doi": f" {doi} "})

    assert publication.identifiers[0].value == "10.1000/mixedcase"


@pytest.mark.parametrize(
    ("raw_type", "expected"),
    [
        ("journal-article", DocumentType.JOURNAL_ARTICLE),
        ("book", DocumentType.BOOK),
        ("book-chapter", DocumentType.BOOK_CHAPTER),
        ("dissertation", DocumentType.DISSERTATION),
        ("report", DocumentType.REPORT),
        ("preprint", DocumentType.PREPRINT),
        ("dataset", DocumentType.DATASET),
        ("review", DocumentType.REVIEW),
        ("proceedings-article", DocumentType.CONFERENCE_PAPER),
        ("new-openalex-type", DocumentType.OTHER),
    ],
)
def test_document_type_mapping(
    raw_type: str,
    expected: DocumentType,
) -> None:
    publication = build_provider().map_work({"title": "Type", "type": raw_type})

    assert publication.document_type is expected


def test_invalid_urls_are_omitted_and_valid_urls_are_deduplicated() -> None:
    publication = build_provider().map_work(
        {
            "title": "URLs",
            "primary_location": {
                "landing_page_url": "ftp://invalid.example/article",
                "pdf_url": " https://example.org/article.pdf ",
            },
            "best_oa_location": {
                "landing_page_url": "https://example.org/article.pdf",
                "pdf_url": " ",
            },
        }
    )

    assert publication.urls == ["https://example.org/article.pdf"]


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [(True, True), (False, False), (None, None), ("true", None), (1, None)],
)
def test_open_access_requires_real_boolean(raw_value: Any, expected: bool | None) -> None:
    publication = build_provider().map_work(
        {"title": "Open access", "open_access": {"is_oa": raw_value}}
    )

    assert publication.open_access is expected


def test_optional_malformed_structures_do_not_reject_publication() -> None:
    publication = build_provider().map_work(
        {
            "title": "Still valid",
            "authorships": "invalid",
            "primary_location": {"source": {"display_name": None}},
            "doi": [],
            "language": {},
            "open_access": [],
        }
    )

    assert publication.authors == []
    assert publication.venue is None
    assert publication.identifiers == []
    assert publication.language is None
    assert publication.open_access is None


def test_language_is_cleaned_and_canonical_model_applies_its_contract() -> None:
    publication = build_provider().map_work(
        {"title": "Language", "language": " EN "}
    )

    assert publication.language == "en"


def test_language_length_is_validated_by_canonical_model_not_mapper() -> None:
    with pytest.raises(ValidationError, match="language"):
        build_provider().map_work({"title": "Language", "language": "x"})
