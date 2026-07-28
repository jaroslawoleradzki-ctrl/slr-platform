from typing import Any

import pytest

from app.normalization import (
    normalize_doi as normalize_canonical_doi,
    normalize_orcid as normalize_canonical_orcid,
)
from app.providers.search.mapping_utils import (
    clean_string,
    normalize_doi,
    normalize_issn,
    normalize_orcid,
    normalize_url,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("  value  ", "value"),
        ("two  internal\tspaces", "two  internal\tspaces"),
        (" ", None),
        ("", None),
        (None, None),
        (123, None),
    ],
)
def test_clean_string(value: Any, expected: str | None) -> None:
    assert clean_string(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("10.1000/Example", "10.1000/example"),
        (" https://doi.org/10.1000/Example ", "10.1000/example"),
        ("http://doi.org/10.1000/Example", "10.1000/example"),
        ("https://dx.doi.org/10.1000/Example", "10.1000/example"),
        ("http://dx.doi.org/10.1000/Example", "10.1000/example"),
        (" DOI: 10.1000/Example ", "10.1000/example"),
        ("HTTPS://DOI.ORG/10.1000/Example", "10.1000/example"),
        ("prefix-doi:10.1000/Example", "prefix-doi:10.1000/example"),
        ("https://doi.org/", None),
        ("doi:", None),
        (" ", None),
        (None, None),
        (123, None),
    ],
)
def test_normalize_doi(value: Any, expected: str | None) -> None:
    assert normalize_doi(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "10.1000/Example",
        " HTTPS://DOI.ORG/10.1000/Example ",
        "doi:",
        "prefix-doi:10.1000/Example",
        None,
        123,
    ],
)
def test_provider_normalize_doi_reexport_matches_canonical_api(value: Any) -> None:
    assert normalize_doi(value) == normalize_canonical_doi(value)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("0000-0002-1825-0097", "0000-0002-1825-0097"),
        (
            " https://orcid.org/0000-0002-1825-0097/ ",
            "0000-0002-1825-0097",
        ),
        (
            "http://orcid.org/0000-0002-1825-009x/",
            "0000-0002-1825-009X",
        ),
        (
            "HTTPS://ORCID.ORG/0000-0002-1825-0097",
            "0000-0002-1825-0097",
        ),
        (
            "prefix-https://orcid.org/0000-0002-1825-0097",
            "prefix-https://orcid.org/0000-0002-1825-0097",
        ),
        ("https://orcid.org/", None),
        (" ", None),
        (None, None),
        (123, None),
    ],
)
def test_normalize_orcid(value: Any, expected: str | None) -> None:
    assert normalize_orcid(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "0000-0002-1825-0097",
        " HTTPS://ORCID.ORG/0000-0002-1825-0097/ ",
        "http://orcid.org/0000-0002-1825-009x/",
        "https://orcid.org/",
        None,
        123,
    ],
)
def test_provider_normalize_orcid_reexport_matches_canonical_api(
    value: Any,
) -> None:
    assert normalize_orcid(value) == normalize_canonical_orcid(value)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (" 1234-567x ", "1234-567X"),
        ("AbCd-1234", "AbCd-1234"),
        (" ", None),
        (None, None),
        (123, None),
    ],
)
def test_normalize_issn(value: Any, expected: str | None) -> None:
    assert normalize_issn(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (" http://Example.com/Path?Query=Yes#Fragment ", "http://Example.com/Path?Query=Yes#Fragment"),
        ("HTTPS://Example.com:8443/Path", "https://Example.com:8443/Path"),
        ("http:example.com", None),
        ("https:example.com", None),
        ("HTTP:test", None),
        ("ftp://example.com", None),
        (" ", None),
        (None, None),
        (123, None),
    ],
)
def test_normalize_url(value: Any, expected: str | None) -> None:
    assert normalize_url(value) == expected
