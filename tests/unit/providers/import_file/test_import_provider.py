from dataclasses import dataclass
from typing import Any

import pytest

from app.domain.publication import Publication
from app.providers.import_file.base import ImportProvider
from app.providers.import_file.bibtex.provider import BibTeXImportProvider
from app.providers.import_file.ris.google_scholar import GoogleScholarImportProvider


@dataclass(frozen=True)
class ImportProviderCase:
    name: str
    provider: ImportProvider
    single_record_content: str
    second_record_content: str
    multiple_records_content: str
    invalid_content: str
    expected_single_title: str
    expected_second_title: str
    expected_multiple_titles: tuple[str, ...]


_CASES = [
    ImportProviderCase(
        name="google_scholar_ris",
        provider=GoogleScholarImportProvider(),
        single_record_content=(
            "TY  - JOUR\n"
            "TI  - First RIS Publication\n"
            "AU  - Smith, John\n"
            "PY  - 2024\n"
            "DO  - 10.1000/ris-first\n"
            "ER  - "
        ),
        second_record_content=(
            "TY  - BOOK\n"
            "TI  - Second RIS Publication\n"
            "ER  - "
        ),
        multiple_records_content=(
            "TY  - JOUR\n"
            "TI  - First RIS Publication\n"
            "ER  - \n\n"
            "TY  - BOOK\n"
            "TI  - Second RIS Publication\n"
            "ER  - "
        ),
        invalid_content=(
            "TY  - JOUR\n"
            "TI  - Valid RIS Publication\n"
            "ER  - \n\n"
            "TY  - JOUR\n"
            "AU  - Missing, Title\n"
            "ER  - "
        ),
        expected_single_title="First RIS Publication",
        expected_second_title="Second RIS Publication",
        expected_multiple_titles=(
            "First RIS Publication",
            "Second RIS Publication",
        ),
    ),
    ImportProviderCase(
        name="bibtex",
        provider=BibTeXImportProvider(),
        single_record_content=(
            "@article{first,"
            " title={First BibTeX Publication},"
            " author={Smith, John},"
            " year={2024},"
            " doi={10.1000/bibtex-first}"
            "}"
        ),
        second_record_content=(
            "@book{second, title={Second BibTeX Publication}}"
        ),
        multiple_records_content=(
            "@article{first, title={First BibTeX Publication}}\n"
            "@book{second, title={Second BibTeX Publication}}"
        ),
        invalid_content=(
            "@article{valid, title={Valid BibTeX Publication}}\n"
            "@article{invalid, year={2024}}"
        ),
        expected_single_title="First BibTeX Publication",
        expected_second_title="Second BibTeX Publication",
        expected_multiple_titles=(
            "First BibTeX Publication",
            "Second BibTeX Publication",
        ),
    ),
]


@pytest.fixture(params=_CASES, ids=lambda case: case.name)
def provider_case(request: pytest.FixtureRequest) -> ImportProviderCase:
    return request.param


def _accept_import_provider(provider: ImportProvider) -> ImportProvider:
    return provider


def _stable_publication_data(publication: Publication) -> dict[str, Any]:
    return {
        "title": publication.title,
        "abstract": publication.abstract,
        "authors": publication.authors,
        "publication_year": publication.publication_year,
        "document_type": publication.document_type,
        "identifiers": publication.identifiers,
        "venue": publication.venue,
        "provenance": [
            {
                "source": entry.source,
                "source_record_id": entry.source_record_id,
                "transformation": entry.transformation,
            }
            for entry in publication.provenance
        ],
    }


def test_provider_structurally_satisfies_import_provider(
    provider_case: ImportProviderCase,
) -> None:
    assert _accept_import_provider(provider_case.provider) is provider_case.provider


@pytest.mark.parametrize("content", ["", " \n\t "], ids=["empty", "whitespace"])
def test_provider_empty_content_returns_list(
    provider_case: ImportProviderCase,
    content: str,
) -> None:
    result = provider_case.provider.import_publications(content)

    assert isinstance(result, list)
    assert result == []


def test_provider_imports_single_publication(
    provider_case: ImportProviderCase,
) -> None:
    result = provider_case.provider.import_publications(
        provider_case.single_record_content
    )

    assert isinstance(result, list)
    assert len(result) == 1
    assert isinstance(result[0], Publication)
    assert result[0].title == provider_case.expected_single_title


def test_provider_imports_all_publications_in_order(
    provider_case: ImportProviderCase,
) -> None:
    result = provider_case.provider.import_publications(
        provider_case.multiple_records_content
    )

    assert isinstance(result, list)
    assert len(result) == len(provider_case.expected_multiple_titles)
    assert all(isinstance(publication, Publication) for publication in result)
    assert tuple(publication.title for publication in result) == (
        provider_case.expected_multiple_titles
    )


def test_provider_does_not_share_state_between_calls(
    provider_case: ImportProviderCase,
) -> None:
    first_result = provider_case.provider.import_publications(
        provider_case.single_record_content
    )
    second_result = provider_case.provider.import_publications(
        provider_case.second_record_content
    )

    assert [publication.title for publication in first_result] == [
        provider_case.expected_single_title
    ]
    assert [publication.title for publication in second_result] == [
        provider_case.expected_second_title
    ]


def test_provider_propagates_errors_without_partial_success(
    provider_case: ImportProviderCase,
) -> None:
    with pytest.raises(ValueError):
        provider_case.provider.import_publications(provider_case.invalid_content)


def test_provider_repeated_import_has_equivalent_stable_domain_data(
    provider_case: ImportProviderCase,
) -> None:
    first_result = provider_case.provider.import_publications(
        provider_case.single_record_content
    )
    second_result = provider_case.provider.import_publications(
        provider_case.single_record_content
    )

    assert [_stable_publication_data(item) for item in first_result] == [
        _stable_publication_data(item) for item in second_result
    ]
