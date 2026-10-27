import re

_DOI_PREFIXES = (
    "https://doi.org/",
    "http://doi.org/",
    "https://dx.doi.org/",
    "http://dx.doi.org/",
    "doi:",
)

# A DOI is a registrant prefix (10.<4-9 digits>) followed by a non-empty,
# non-whitespace suffix.  This deliberately does not verify that the DOI is
# registered; it only rejects values that cannot be DOIs.
_DOI_PATTERN = re.compile(r"^10\.\d{4,9}/\S+$", re.IGNORECASE)


class DoiNormalizer:
    """Normalize a single DOI value without validating its existence or syntax."""

    def normalize(self, value: object) -> str | None:
        if not isinstance(value, str):
            return None

        doi = value.strip()
        if not doi:
            return None

        lowered = doi.casefold()
        for prefix in _DOI_PREFIXES:
            if lowered.startswith(prefix):
                doi = doi[len(prefix) :].strip()
                break

        return doi.lower() or None


doi_normalizer = DoiNormalizer()


def normalize_doi(value: object) -> str | None:
    """Backward-compatible permissive DOI normalizer.

    Existing providers and stored rows may contain DOI-shaped values that do
    not satisfy the strict syntax check.  New import deduplication code must
    use :func:`normalize_doi_strict` so that malformed values never become
    automatic duplicate keys.
    """

    return doi_normalizer.normalize(value)


def is_valid_doi(value: object) -> bool:
    """Return True only for a syntactically plausible DOI value."""

    normalized = normalize_doi(value)
    return bool(normalized and _DOI_PATTERN.fullmatch(normalized))


def normalize_doi_strict(value: object) -> str | None:
    """Normalize *value* and return it only when it is a valid DOI shape.

    URL prefixes and case are normalized exactly like :func:`normalize_doi`.
    Invalid strings (for example ``not-a-doi``), blank strings and non-string
    values return ``None`` and therefore must never participate in automatic
    duplicate removal.
    """

    normalized = normalize_doi(value)
    if not normalized or not _DOI_PATTERN.fullmatch(normalized):
        return None
    return normalized
