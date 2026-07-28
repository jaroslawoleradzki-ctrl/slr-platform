_DOI_PREFIXES = (
    "https://doi.org/",
    "http://doi.org/",
    "https://dx.doi.org/",
    "http://dx.doi.org/",
    "doi:",
)


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
    return doi_normalizer.normalize(value)
