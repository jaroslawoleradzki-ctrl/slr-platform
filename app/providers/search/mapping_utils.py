from typing import Any

from app.normalization.doi import normalize_doi as normalize_doi
from app.normalization.orcid import normalize_orcid as normalize_orcid


def clean_string(value: Any) -> str | None:
    """Return a trimmed non-blank string without coercing other values."""

    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None

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
