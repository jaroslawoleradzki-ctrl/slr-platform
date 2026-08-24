from datetime import datetime, timezone
from typing import Any, cast
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.domain import DocumentType, IdentifierType, VenueType
from app.domain.publication import Publication
from app.domain.search import SearchQuery, SearchRun, SearchTerm
from app.providers.openalex import OpenAlexClient
from app.providers.search.crossref import CrossrefProvider
from app.providers.search.openalex import OpenAlexProvider
from app.providers.search.semantic_scholar import SemanticScholarProvider

_RETRIEVED_AT = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)


def _semantic_context() -> tuple[SearchRun, SearchQuery]:
    query = SearchQuery(
        query_id=UUID("00000000-0000-0000-0000-000000000001"),
        name="Normalization",
        expression=SearchTerm(value="normalization"),
    )
    run = SearchRun(
        run_id=UUID("00000000-0000-0000-0000-000000000002"),
        query_id=query.query_id,
        query_version=query.version,
        provider="semantic_scholar",
        rendered_query="normalization",
    )
    return run, query


def _map_openalex(**fields: Any) -> Publication:
    provider = OpenAlexProvider(client=cast(OpenAlexClient, object()))
    return provider.map_work({"title": "Test", **fields})


def _map_crossref(**fields: Any) -> Publication:
    return CrossrefProvider().map_work({"title": ["Test"], **fields})


def _map_semantic_scholar(**fields: Any) -> Publication:
    run, query = _semantic_context()
    return SemanticScholarProvider().map_paper(
        {"paperId": "S2-ID", "title": "Test", **fields},
        search_run=run,
        search_query=query,
        retrieved_at=_RETRIEVED_AT,
    )


@pytest.mark.parametrize(
    "raw_doi",
    [
        "10.1000/Example",
        " DOI:10.1000/Example ",
        "https://doi.org/10.1000/Example",
        "http://doi.org/10.1000/Example",
        "https://dx.doi.org/10.1000/Example",
    ],
)
def test_equivalent_doi_forms_normalize_identically(raw_doi: str) -> None:
    publications = [
        _map_openalex(doi=raw_doi),
        _map_crossref(DOI=raw_doi),
        _map_semantic_scholar(externalIds={"DOI": raw_doi}),
    ]

    for publication in publications:
        dois = [
            identifier.value
            for identifier in publication.identifiers
            if identifier.type is IdentifierType.DOI
        ]
        assert dois == ["10.1000/example"]


@pytest.mark.parametrize("raw_doi", [" ", None, 123])
def test_invalid_optional_doi_is_omitted_by_all_providers(raw_doi: Any) -> None:
    publications = [
        _map_openalex(doi=raw_doi),
        _map_crossref(DOI=raw_doi),
        _map_semantic_scholar(externalIds={"DOI": raw_doi}),
    ]

    assert all(
        not any(item.type is IdentifierType.DOI for item in publication.identifiers)
        for publication in publications
    )


@pytest.mark.parametrize(
    ("raw_orcid", "expected"),
    [
        ("0000-0002-1825-0097", "0000-0002-1825-0097"),
        (
            "https://orcid.org/0000-0002-1825-0097",
            "0000-0002-1825-0097",
        ),
        (
            "http://orcid.org/0000-0002-1825-009x/",
            "0000-0002-1825-009X",
        ),
    ],
)
def test_orcid_normalization_is_consistent(
    raw_orcid: str,
    expected: str,
) -> None:
    openalex = _map_openalex(
        authorships=[
            {"author": {"display_name": "Author", "orcid": raw_orcid}}
        ]
    )
    crossref = _map_crossref(
        author=[{"given": "Author", "ORCID": raw_orcid}]
    )

    assert openalex.authors[0].identifiers[0].value == expected
    assert crossref.authors[0].identifiers[0].value == expected


@pytest.mark.parametrize("raw_orcid", [" ", None, 123])
def test_invalid_optional_orcid_is_omitted(raw_orcid: Any) -> None:
    openalex = _map_openalex(
        authorships=[
            {"author": {"display_name": "Author", "orcid": raw_orcid}}
        ]
    )
    crossref = _map_crossref(
        author=[{"given": "Author", "ORCID": raw_orcid}]
    )

    assert openalex.authors[0].identifiers == []
    assert crossref.authors[0].identifiers == []


def test_issn_normalization_deduplicates_and_preserves_order() -> None:
    openalex = _map_openalex(
        primary_location={
            "source": {
                "display_name": "Venue",
                "issn_l": " 1234-567x ",
                "issn": ["1234-567X", "8765-4321", None],
            }
        }
    )
    crossref = _map_crossref(
        **{
            "container-title": ["Venue"],
            "ISSN": [" 1234-567x ", "1234-567X", "8765-4321", None],
        }
    )
    semantic = _map_semantic_scholar(
        publicationVenue={
            "name": "Venue",
            "issn": " 1234-567x ",
            "issns": ["1234-567X", "8765-4321", None],
        }
    )

    for publication in (openalex, crossref, semantic):
        assert publication.venue is not None
        assert [item.value for item in publication.venue.identifiers] == [
            "1234-567X",
            "8765-4321",
        ]


def test_provider_native_identifiers_use_canonical_sources_and_preserve_values() -> None:
    openalex = _map_openalex(id=" OpenAlex-WORK ")
    semantic = _map_semantic_scholar(paperId=" Semantic-ID ")
    crossref = _map_crossref(DOI="10.1000/Example")

    assert (
        openalex.identifiers[0].type,
        openalex.identifiers[0].value,
        openalex.identifiers[0].source,
    ) == (IdentifierType.OTHER, "OpenAlex-WORK", "openalex")
    assert (
        semantic.identifiers[0].type,
        semantic.identifiers[0].value,
        semantic.identifiers[0].source,
    ) == (IdentifierType.OTHER, "Semantic-ID", "semantic_scholar")
    assert [item.type for item in crossref.identifiers] == [IdentifierType.DOI]


@pytest.mark.parametrize(
    ("raw_url", "expected"),
    [
        (" HTTP://Example.com/Path ", "http://Example.com/Path"),
        ("HTTPS://Example.com/Path", "https://Example.com/Path"),
        ("ftp://example.org/file", None),
        (" ", None),
        (123, None),
    ],
)
def test_url_boundary_behavior_is_consistent(
    raw_url: Any,
    expected: str | None,
) -> None:
    publications = [
        _map_openalex(primary_location={"landing_page_url": raw_url}),
        _map_crossref(URL=raw_url),
        _map_semantic_scholar(url=raw_url),
    ]

    assert [publication.urls for publication in publications] == [
        [] if expected is None else [expected],
    ] * 3


@pytest.mark.parametrize(
    "invalid_url",
    [
        "http:example.com",
        "https:example.com",
        "HTTP:test",
        "ftp://example.com",
    ],
)
def test_urls_without_supported_scheme_delimiter_are_rejected(
    invalid_url: str,
) -> None:
    publications = [
        _map_openalex(primary_location={"landing_page_url": invalid_url}),
        _map_crossref(URL=invalid_url),
        _map_semantic_scholar(url=invalid_url),
    ]

    assert all(publication.urls == [] for publication in publications)


@pytest.mark.parametrize("language", [" EN ", "pl"])
def test_language_is_trimmed_and_preserves_case_in_canonical_model(
    language: str,
) -> None:
    publications = [
        _map_openalex(language=language),
        _map_crossref(language=language),
        _map_semantic_scholar(language=language),
    ]

    assert {publication.language for publication in publications} == {language.strip()}


@pytest.mark.parametrize("language", ["x", " "])
def test_language_uses_canonical_validation_consistently(language: str) -> None:
    if language.strip():
        for mapper in (_map_openalex, _map_crossref, _map_semantic_scholar):
            with pytest.raises(ValidationError, match="language"):
                mapper(language=language)
    else:
        assert _map_openalex(language=language).language is None
        assert _map_crossref(language=language).language is None
        assert _map_semantic_scholar(language=language).language is None


@pytest.mark.parametrize(
    ("raw_type", "expected"),
    [
        (" Journal-Article ", DocumentType.JOURNAL_ARTICLE),
        ("BOOK", DocumentType.BOOK),
        ("review", DocumentType.REVIEW),
        ("unknown", DocumentType.OTHER),
        (" ", None),
        (123, None),
    ],
)
def test_document_type_fallback_contract(
    raw_type: Any,
    expected: DocumentType | None,
) -> None:
    openalex = _map_openalex(type=raw_type)
    crossref = _map_crossref(type=raw_type)
    semantic = _map_semantic_scholar(publicationTypes=[raw_type])

    assert openalex.document_type is expected
    assert crossref.document_type is expected
    assert semantic.document_type is expected


@pytest.mark.parametrize(
    ("raw_type", "expected"),
    [
        (" Journal ", VenueType.JOURNAL),
        ("conference", VenueType.CONFERENCE),
        ("BOOK", VenueType.BOOK),
        ("repository", VenueType.REPOSITORY),
        ("unknown", VenueType.OTHER),
        (" ", None),
    ],
)
def test_venue_type_fallback_contract(
    raw_type: str,
    expected: VenueType | None,
) -> None:
    openalex = _map_openalex(
        primary_location={
            "source": {"display_name": "Venue", "type": raw_type}
        }
    )
    semantic = _map_semantic_scholar(
        publicationVenue={"name": "Venue", "type": raw_type}
    )

    assert openalex.venue is not None
    assert semantic.venue is not None
    assert openalex.venue.type is expected
    assert semantic.venue.type is expected


def test_malformed_optional_values_do_not_reject_valid_records() -> None:
    openalex = _map_openalex(
        abstract_inverted_index=[],
        authorships={},
        publication_year=True,
        publication_date=[],
        primary_location=[],
        doi={},
        type=[],
        language={},
        open_access={"is_oa": "yes"},
    )
    crossref = _map_crossref(
        abstract=[],
        author={},
        issued={"date-parts": [[True]]},
        **{
            "container-title": {},
            "ISSN": {},
            "publisher": [],
            "type": [],
            "language": {},
            "URL": [],
        },
    )
    semantic = _map_semantic_scholar(
        abstract=[],
        authors={},
        year=True,
        publicationDate=[],
        publicationVenue=[],
        publicationTypes={},
        externalIds=[],
        language={},
        url=[],
    )

    for publication in (openalex, crossref, semantic):
        assert publication.title == "Test"
        assert publication.abstract is None
        assert publication.authors == []
        assert publication.publication_year is None
        assert publication.publication_date is None
        assert publication.venue is None
        assert publication.document_type is None
        assert publication.language is None
        assert publication.urls == []
