from typing import Any


def clean_string(value: Any) -> str | None:
    """Return a trimmed non-blank string without coercing other values."""

    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def normalize_doi(value: Any) -> str | None:
    """Normalize supported DOI prefixes and casing at the provider boundary."""

    doi = clean_string(value)
    if doi is None:
        return None
    lowered = doi.casefold()
    for prefix in (
        "https://doi.org/",
        "http://doi.org/",
        "https://dx.doi.org/",
        "http://dx.doi.org/",
        "doi:",
    ):
        if lowered.startswith(prefix):
            doi = doi[len(prefix) :].strip()
            break
    return doi.lower() or None


def normalize_orcid(value: Any) -> str | None:
    """Normalize supported ORCID prefixes, trailing slash, and final X."""

    orcid = clean_string(value)
    if orcid is None:
        return None
    lowered = orcid.casefold()
    for prefix in ("https://orcid.org/", "http://orcid.org/"):
        if lowered.startswith(prefix):
            orcid = orcid[len(prefix) :]
            break
    orcid = orcid.rstrip("/").strip()
    return orcid[:-1] + "X" if orcid.casefold().endswith("x") else orcid or None


def normalize_issn(value: Any) -> str | None:
    """Trim an ISSN and uppercase only a final X."""

    issn = clean_string(value)
    if issn is None:
        return None
    return issn[:-1] + "X" if issn.casefold().endswith("x") else issn


def normalize_url(value: Any) -> str | None:
    """Accept HTTP(S) URLs and lowercase only their scheme."""

    url = clean_string(value)
    if url is None:
        return None
    lowered = url.casefold()
    if lowered.startswith("http://"):
        return f"http://{url[7:]}"
    if lowered.startswith("https://"):
        return f"https://{url[8:]}"
    return None
