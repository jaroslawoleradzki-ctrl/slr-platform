from typing import Any
from uuid import UUID, uuid5

from app.normalization.doi import normalize_doi as normalize_doi
from app.normalization.orcid import normalize_orcid as normalize_orcid

_SEARCH_RESULT_NAMESPACE = UUID("4eb84216-6a9f-5340-8982-1ec47a5eb478")


def deterministic_search_record_id(
    *,
    provider: str,
    source_id: str | None,
    doi: str | None,
    title: str,
    publication_year: int | None,
) -> UUID:
    """Build stable source-record identity without changing Publication defaults."""

    normalized_provider = provider.strip().casefold()
    normalized_source_id = source_id.strip() if source_id is not None else ""
    if normalized_source_id:
        key = f"{normalized_provider}:{normalized_source_id}"
    else:
        normalized_title = " ".join(title.split()).casefold()
        normalized_doi = normalize_doi(doi) or ""
        key = (
            f"{normalized_provider}:fallback:{normalized_doi}:"
            f"{normalized_title}:{publication_year or ''}"
        )
    return uuid5(_SEARCH_RESULT_NAMESPACE, key)


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
