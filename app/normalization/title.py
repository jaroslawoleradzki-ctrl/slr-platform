import re
import unicodedata
from collections import Counter
from difflib import SequenceMatcher


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


def title_tokens(value: object) -> tuple[str, ...]:
    normalized = normalize_title(value)
    return tuple(normalized.split()) if normalized else ()


def titles_are_similar(
    first: object,
    second: object,
    *,
    threshold: float = 0.92,
    max_differing_tokens: int = 4,
) -> bool:
    """Conservative similarity for manual-review candidates.

    Sequential record titles (``Study 201`` vs ``Study 202``) and titles that
    differ only by numbers are deliberately rejected: they are far more often
    distinct works than duplicates.  The rule is intentionally asymmetric with
    conservative import: a positive result only creates a candidate, never an
    automatic merge.
    """

    first_normalized = normalize_title(first)
    second_normalized = normalize_title(second)
    if not first_normalized or not second_normalized:
        return False
    if first_normalized == second_normalized:
        return True
    if abs(len(first_normalized) - len(second_normalized)) > 25:
        return False
    if SequenceMatcher(None, first_normalized, second_normalized).ratio() < threshold:
        return False
    first_counts = Counter(title_tokens(first))
    second_counts = Counter(title_tokens(second))
    differing = tuple((first_counts - second_counts).elements()) + tuple(
        (second_counts - first_counts).elements()
    )
    if not differing:
        return True
    if all(token.isdigit() for token in differing):
        return False
    return len(differing) <= max_differing_tokens
