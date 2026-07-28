import pytest

from app.domain.publication import DocumentType
from app.providers.import_file.base import ImportProvider
from app.providers.import_file.bibtex.provider import BibTeXImportProvider


def _import_with(provider: ImportProvider, content: str) -> list[str]:
    return [
        publication.title
        for publication in provider.import_publications(content)
    ]


def test_bibtex_provider_implements_import_provider_contract() -> None:
    content = "@article{key, title={Contract Test}}"

    assert _import_with(BibTeXImportProvider(), content) == ["Contract Test"]


def test_bibtex_provider_empty_input_returns_empty_list() -> None:
    provider = BibTeXImportProvider()

    assert provider.import_publications("") == []
    assert provider.import_publications(" \n\t ") == []


def test_bibtex_provider_imports_single_record() -> None:
    publications = BibTeXImportProvider().import_publications(
        "@article{key, title={Single Record}}"
    )

    assert len(publications) == 1
    assert publications[0].title == "Single Record"
    assert publications[0].title_normalized == "single record"


def test_bibtex_provider_preserves_record_order() -> None:
    content = (
        "@article{first, title={First}}"
        "@book{second, title={Second}}"
        "@misc{third, title={Third}}"
    )

    publications = BibTeXImportProvider().import_publications(content)

    assert [publication.title for publication in publications] == [
        "First",
        "Second",
        "Third",
    ]


def test_bibtex_provider_assigns_source_to_every_publication() -> None:
    content = "@article{first, title={First}} @book{second, title={Second}}"

    publications = BibTeXImportProvider(source="library").import_publications(
        content
    )

    assert [
        publication.provenance[0].source for publication in publications
    ] == ["library", "library"]


def test_bibtex_provider_default_source_is_bibtex() -> None:
    publications = BibTeXImportProvider().import_publications(
        "@article{key, title={Title}}"
    )

    assert publications[0].provenance[0].source == "bibtex"


def test_bibtex_provider_custom_source_reaches_provenance() -> None:
    publications = BibTeXImportProvider(
        source="uploaded_bibliography"
    ).import_publications("@article{key, title={Title}}")

    assert (
        publications[0].provenance[0].source
        == "uploaded_bibliography"
    )


def test_bibtex_provider_maps_doi() -> None:
    publications = BibTeXImportProvider().import_publications(
        "@article{key, title={Title}, "
        "doi={https://doi.org/10.1000/EXAMPLE}}"
    )

    assert publications[0].identifiers[0].value == "10.1000/example"


def test_bibtex_provider_uses_citation_key_without_doi() -> None:
    publications = BibTeXImportProvider().import_publications(
        "@article{Smith2024, title={Title}}"
    )

    assert publications[0].provenance[0].source_record_id == "Smith2024"


def test_bibtex_provider_propagates_parser_error() -> None:
    with pytest.raises(ValueError, match="Unclosed braced"):
        BibTeXImportProvider().import_publications(
            "@article{key, title={Unclosed"
        )


def test_bibtex_provider_propagates_mapper_error() -> None:
    with pytest.raises(ValueError, match="missing a title"):
        BibTeXImportProvider().import_publications(
            "@article{key, year={2024}}"
        )


def test_bibtex_provider_does_not_modify_content() -> None:
    content = "@article{key, title={Original {LaTeX} text}}"

    BibTeXImportProvider().import_publications(content)

    assert content == "@article{key, title={Original {LaTeX} text}}"


def test_bibtex_provider_does_not_share_state_between_calls() -> None:
    provider = BibTeXImportProvider()

    first = provider.import_publications(
        "@article{first, title={First}}"
    )
    second = provider.import_publications(
        "@article{second, title={Second}}"
    )

    assert [publication.title for publication in first] == ["First"]
    assert [publication.title for publication in second] == ["Second"]


def test_bibtex_provider_ignores_comment_entries() -> None:
    content = (
        "@comment{Ignored text}"
        "@article{key, title={Included}}"
    )

    publications = BibTeXImportProvider().import_publications(content)

    assert [publication.title for publication in publications] == ["Included"]


@pytest.mark.parametrize("construct", ["string", "preamble"])
def test_bibtex_provider_rejects_unsupported_constructs(
    construct: str,
) -> None:
    with pytest.raises(
        ValueError,
        match=f"Unsupported BibTeX construct: @{construct}",
    ):
        BibTeXImportProvider().import_publications(
            f"@{construct}{{value={{Unsupported}}}}"
        )


def test_bibtex_provider_preserves_latex_text() -> None:
    publications = BibTeXImportProvider().import_publications(
        r'@article{key, title={Energy in M{\"u}nchen}}'
    )

    assert publications[0].title == r'Energy in M{\"u}nchen'


def test_bibtex_provider_uses_mapper_document_type_mapping() -> None:
    publications = BibTeXImportProvider().import_publications(
        "@inproceedings{key, title={Conference Paper}}"
    )

    assert publications[0].document_type == DocumentType.CONFERENCE_PAPER


def test_bibtex_provider_uses_mapper_author_mapping() -> None:
    publications = BibTeXImportProvider().import_publications(
        "@article{key, title={Title}, "
        "author={Smith, John and Jane Doe}}"
    )

    assert [author.display_name for author in publications[0].authors] == [
        "Smith, John",
        "Jane Doe",
    ]
