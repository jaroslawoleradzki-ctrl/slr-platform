import pytest

from app.providers.import_file.bibtex.parser import parse_bibtex


def test_parse_bibtex_empty_input() -> None:
    assert parse_bibtex("") == []
    assert parse_bibtex(" \n\t ") == []


def test_parse_bibtex_single_record_with_braced_values() -> None:
    content = """@article{smith2024,
        title = {Example title},
        author = {Smith, John},
        year = {2024}
    }"""

    assert parse_bibtex(content) == [
        {
            "entry_type": "article",
            "citation_key": "smith2024",
            "fields": {
                "title": "Example title",
                "author": "Smith, John",
                "year": "2024",
            },
        }
    ]


def test_parse_bibtex_quoted_values() -> None:
    records = parse_bibtex('@article{key, title = "Example title"}')

    assert records[0]["fields"]["title"] == "Example title"


def test_parse_bibtex_multiple_records() -> None:
    content = "@article{first, title={First}} @book{second, title={Second}}"

    records = parse_bibtex(content)

    assert [record["citation_key"] for record in records] == ["first", "second"]


def test_parse_bibtex_record_without_fields() -> None:
    assert parse_bibtex("@misc{key}") == [
        {"entry_type": "misc", "citation_key": "key", "fields": {}}
    ]


def test_parse_bibtex_normalizes_entry_type_and_field_names() -> None:
    records = parse_bibtex("@ARTICLE{key, TiTle={Title}, YEAR={2024}}")

    assert records[0]["entry_type"] == "article"
    assert records[0]["fields"] == {"title": "Title", "year": "2024"}


def test_parse_bibtex_preserves_citation_key() -> None:
    records = parse_bibtex("@article{Smith_Key-2024}")

    assert records[0]["citation_key"] == "Smith_Key-2024"


def test_parse_bibtex_nested_braces() -> None:
    records = parse_bibtex(
        "@article{key, title={Lean {Manufacturing} and Energy}}"
    )

    assert records[0]["fields"]["title"] == "Lean {Manufacturing} and Energy"


def test_parse_bibtex_multiline_value_is_preserved() -> None:
    records = parse_bibtex(
        '@article{key, abstract="First line.\nSecond line.\nThird line."}'
    )

    assert records[0]["fields"]["abstract"] == (
        "First line.\nSecond line.\nThird line."
    )


def test_parse_bibtex_comma_inside_value() -> None:
    records = parse_bibtex("@article{key, title={Lean, Green, and Digital}}")

    assert records[0]["fields"]["title"] == "Lean, Green, and Digital"


def test_parse_bibtex_trailing_comma() -> None:
    records = parse_bibtex("@article{key, title={Title},}")

    assert records[0]["fields"] == {"title": "Title"}


def test_parse_bibtex_without_trailing_comma() -> None:
    records = parse_bibtex("@article{key, title={Title}}")

    assert records[0]["fields"] == {"title": "Title"}


def test_parse_bibtex_percent_comment_outside_value() -> None:
    content = """% file comment
@article{key,
    % field comment
    title = {100% preserved},
    year = {2024} % trailing comment
}"""

    records = parse_bibtex(content)

    assert records[0]["fields"] == {"title": "100% preserved", "year": "2024"}


def test_parse_bibtex_percent_comment_before_citation_key_delimiter() -> None:
    records = parse_bibtex("@article{key % comment\n, title={Title}}")

    assert records[0]["citation_key"] == "key"


def test_parse_bibtex_ignores_comment_entry() -> None:
    content = "@comment{Ignored {nested} text} @article{key, title={Kept}}"

    assert parse_bibtex(content) == [
        {
            "entry_type": "article",
            "citation_key": "key",
            "fields": {"title": "Kept"},
        }
    ]


def test_parse_bibtex_missing_record_closing_brace() -> None:
    with pytest.raises(ValueError, match="missing its closing brace"):
        parse_bibtex("@article{key, title={Title}")


def test_parse_bibtex_missing_citation_key() -> None:
    with pytest.raises(ValueError, match="missing a citation key"):
        parse_bibtex("@article{, title={Title}}")


def test_parse_bibtex_missing_equals_sign() -> None:
    with pytest.raises(ValueError, match="Missing '='"):
        parse_bibtex("@article{key, title {Title}}")


def test_parse_bibtex_unclosed_braced_value() -> None:
    with pytest.raises(ValueError, match="Unclosed braced"):
        parse_bibtex("@article{key, title={Title")


def test_parse_bibtex_unclosed_quoted_value() -> None:
    with pytest.raises(ValueError, match="Unclosed quoted"):
        parse_bibtex('@article{key, title="Title}')


def test_parse_bibtex_rejects_string() -> None:
    with pytest.raises(ValueError, match="Unsupported BibTeX construct: @string"):
        parse_bibtex("@string{journal = {Example Journal}}")


def test_parse_bibtex_rejects_preamble() -> None:
    with pytest.raises(ValueError, match="Unsupported BibTeX construct: @preamble"):
        parse_bibtex('@preamble{"Example"}')


def test_parse_bibtex_rejects_unexpected_character_after_value() -> None:
    with pytest.raises(ValueError, match="Expected another BibTeX field"):
        parse_bibtex("@article{key, title={Title} author={Smith}}")
