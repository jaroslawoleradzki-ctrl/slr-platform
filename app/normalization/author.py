import re

from app.domain.author import Author


def _normalize_whitespace(value: str | None) -> str | None:
    if value is None:
        return None
    return re.sub(r"\s+", " ", value).strip()


class AuthorNormalizer:
    """Normalize whitespace in one canonical author without parsing its name."""

    def normalize(self, value: Author) -> Author:
        return value.model_copy(
            update={
                "display_name": _normalize_whitespace(value.display_name),
                "given_name": _normalize_whitespace(value.given_name),
                "family_name": _normalize_whitespace(value.family_name),
            },
            deep=True,
        )


author_normalizer = AuthorNormalizer()


def normalize_author(value: Author) -> Author:
    return author_normalizer.normalize(value)
