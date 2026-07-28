_ORCID_PREFIXES = (
    "https://orcid.org/",
    "http://orcid.org/",
)


class OrcidNormalizer:
    """Normalize one ORCID value without validation or identity resolution."""

    def normalize(self, value: object) -> str | None:
        if not isinstance(value, str):
            return None

        orcid = value.strip()
        if not orcid:
            return None

        lowered = orcid.casefold()
        for prefix in _ORCID_PREFIXES:
            if lowered.startswith(prefix):
                orcid = orcid[len(prefix) :]
                break

        orcid = orcid.rstrip("/").strip()
        if not orcid:
            return None
        return orcid[:-1] + "X" if orcid.casefold().endswith("x") else orcid


orcid_normalizer = OrcidNormalizer()


def normalize_orcid(value: object) -> str | None:
    return orcid_normalizer.normalize(value)
