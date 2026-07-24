import pytest

from app.providers.import_file.ris.parser import parse_ris


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------


def test_parse_ris_empty_input() -> None:
    assert parse_ris("") == []
    assert parse_ris("   \n\n   ") == []


def test_parse_ris_single_record() -> None:
    content = """TY  - JOUR
TI  - A Lean Study
AU  - Smith, John
ER  - """
    expected = [
        {
            "TY": ["JOUR"],
            "TI": ["A Lean Study"],
            "AU": ["Smith, John"],
        }
    ]
    assert parse_ris(content) == expected


def test_parse_ris_multiple_records() -> None:
    content = """TY  - JOUR
TI  - First Record
ER  - 

TY  - CONF
TI  - Second Record
ER  - """
    expected = [
        {
            "TY": ["JOUR"],
            "TI": ["First Record"],
        },
        {
            "TY": ["CONF"],
            "TI": ["Second Record"],
        },
    ]
    assert parse_ris(content) == expected


def test_parse_ris_repeated_au_tags() -> None:
    content = """TY  - JOUR
TI  - Test Paper
AU  - Smith, John
AU  - Doe, Jane
ER  - """
    expected = [
        {
            "TY": ["JOUR"],
            "TI": ["Test Paper"],
            "AU": ["Smith, John", "Doe, Jane"],
        }
    ]
    assert parse_ris(content) == expected


def test_parse_ris_repeated_kw_tags() -> None:
    content = """TY  - JOUR
TI  - Test Paper
KW  - Lean
KW  - Energy
KW  - Manufacturing
ER  - """
    expected = [
        {
            "TY": ["JOUR"],
            "TI": ["Test Paper"],
            "KW": ["Lean", "Energy", "Manufacturing"],
        }
    ]
    assert parse_ris(content) == expected


def test_parse_ris_whitespace_trimming() -> None:
    content = """TY  - JOUR   
TI  -    Lean Production   
ER  -    """
    expected = [
        {
            "TY": ["JOUR"],
            "TI": ["Lean Production"],
        }
    ]
    assert parse_ris(content) == expected


def test_parse_ris_utf8_characters() -> None:
    content = """TY  - JOUR
TI  - Prace naukowe w języku polskim zażółć gęślą jaźń
AU  - Kowalski, Janusz
ER  - """
    expected = [
        {
            "TY": ["JOUR"],
            "TI": ["Prace naukowe w języku polskim zażółć gęślą jaźń"],
            "AU": ["Kowalski, Janusz"],
        }
    ]
    assert parse_ris(content) == expected


def test_parse_ris_multiline_abstract() -> None:
    """A continuation line is appended (space-separated) to the previous field value."""
    content = """TY  - JOUR
AB  - First line of abstract.
Second line of abstract.
Third line.
ER  - """
    expected = [
        {
            "TY": ["JOUR"],
            "AB": ["First line of abstract. Second line of abstract. Third line."],
        }
    ]
    assert parse_ris(content) == expected


def test_parse_ris_hyphenated_continuation_lines() -> None:
    """Ordinary text containing hyphens is valid continuation — not a malformed tag.

    Regression test: the previous broad regex incorrectly rejected lines such as
    'ISO-50001 ...', 'AI-based ...', 'CO2-related ...' as malformed RIS tags.
    """
    content = """TY  - JOUR
AB  - This study focuses on energy management.
ISO-50001 improves energy management.
AI-based methods were analysed.
CO2-related emissions were measured.
ER  - """
    expected = [
        {
            "TY": ["JOUR"],
            "AB": [
                "This study focuses on energy management."
                " ISO-50001 improves energy management."
                " AI-based methods were analysed."
                " CO2-related emissions were measured."
            ],
        }
    ]
    assert parse_ris(content) == expected


def test_parse_ris_multiple_continuation_lines() -> None:
    """Multiple consecutive continuation lines all fold into the same field value."""
    content = """TY  - JOUR
TI  - First Part of Title
And Second Part
And Third Part
AU  - Smith, John
ER  - """
    expected = [
        {
            "TY": ["JOUR"],
            "TI": ["First Part of Title And Second Part And Third Part"],
            "AU": ["Smith, John"],
        }
    ]
    assert parse_ris(content) == expected


# ---------------------------------------------------------------------------
# Error-path tests
# ---------------------------------------------------------------------------


def test_parse_ris_malformed_line_raises_value_error() -> None:
    # Single space before hyphen instead of two spaces
    with pytest.raises(ValueError, match="Malformed RIS line"):
        parse_ris("TY - JOUR\nER  - ")

    # Tag-like prefix with no spaces at all
    with pytest.raises(ValueError, match="Malformed RIS line"):
        parse_ris("TY  - JOUR\nTI-Title here\nER  - ")

    # Three-character tag — not a valid 2-char tag
    with pytest.raises(ValueError, match="Malformed RIS line"):
        parse_ris("TYY  - JOUR\nER  - ")


def test_parse_ris_missing_er_raises_value_error() -> None:
    content = """TY  - JOUR
TI  - Test Paper"""
    with pytest.raises(ValueError, match="EOF reached before last record was closed"):
        parse_ris(content)


def test_parse_ris_er_before_ty_raises_value_error() -> None:
    with pytest.raises(ValueError, match="ER tag found .* before any TY tag"):
        parse_ris("ER  - ")

    with pytest.raises(ValueError, match="Tag TI found .* before any TY tag"):
        parse_ris("TI  - Test\nTY  - JOUR\nER  - ")


def test_parse_ris_nested_ty_raises_value_error() -> None:
    content = """TY  - JOUR
TY  - BOOK
ER  - """
    with pytest.raises(ValueError, match="Nested TY tag found"):
        parse_ris(content)


def test_parse_ris_continuation_outside_record_raises_value_error() -> None:
    """A plain-text line before the first TY is a continuation outside a record."""
    content = """Continuation outside a record.
TY  - JOUR
TI  - Test
ER  - """
    with pytest.raises(ValueError, match="Continuation line found outside a record"):
        parse_ris(content)


def test_parse_ris_continuation_outside_record_between_records_raises_value_error() -> None:
    """A plain-text line after ER (record closed) is also outside a record."""
    content = """TY  - JOUR
TI  - Test
ER  - 
Orphan continuation line between records.
TY  - CONF
TI  - Second
ER  - """
    with pytest.raises(ValueError, match="Continuation line found outside a record"):
        parse_ris(content)
