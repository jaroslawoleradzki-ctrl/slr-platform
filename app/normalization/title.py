import re
import unicodedata


class TitleNormalizer:
    """Normalize one title without language-specific or matching behavior."""

    def normalize(self, value: object) -> str | None:
        if not isinstance(value, str):
            return None

        normalized = unicodedata.normalize("NFKC", value).casefold()
        normalized = re.sub(r"[^\w\s]", " ", normalized)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return normalized or None


title_normalizer = TitleNormalizer()


def normalize_title(value: object) -> str | None:
    return title_normalizer.normalize(value)
