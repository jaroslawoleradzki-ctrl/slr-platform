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
    return normalized_titles_are_similar(
        first_normalized,
        second_normalized,
        threshold=threshold,
        max_differing_tokens=max_differing_tokens,
    )


def _common_prefix_length(first: str, second: str) -> int:
    low, high = 0, min(len(first), len(second))
    while low < high:
        middle = (low + high + 1) // 2
        if first[:middle] == second[:middle]:
            low = middle
        else:
            high = middle - 1
    return low


def _common_suffix_length(first: str, second: str, limit: int) -> int:
    low, high = 0, limit
    while low < high:
        middle = (low + high + 1) // 2
        if first[len(first) - middle :] == second[len(second) - middle :]:
            low = middle
        else:
            high = middle - 1
    return low


def _matching_character_bound(first: str, second: str) -> float:
    """Upper bound for ``SequenceMatcher.ratio()`` after removing common edges.

    ``SequenceMatcher`` cannot place a matching block across the maximal common
    prefix/suffix boundary, so every matching character lies in the prefix, the
    suffix, or the differing middles.  Characters in the middles can match at
    most as often as their multiset intersection.  The resulting fraction is a
    valid upper bound and is usually much tighter than ``quick_ratio()`` for
    long titles that share a template but differ in their middle section.
    """

    total = len(first) + len(second)
    if total == 0:
        return 1.0
    prefix = _common_prefix_length(first, second)
    suffix = _common_suffix_length(
        first, second, min(len(first), len(second)) - prefix
    )
    first_middle = first[prefix : len(first) - suffix]
    second_middle = second[prefix : len(second) - suffix]
    middle_matches = sum(
        (Counter(first_middle) & Counter(second_middle)).values()
    )
    return 2.0 * (prefix + suffix + middle_matches) / total


def prepared_titles_are_similar(
    first_normalized: str,
    second_normalized: str,
    first_counts: Counter[str],
    second_counts: Counter[str],
    first_tokens: frozenset[str],
    second_tokens: frozenset[str],
    *,
    threshold: float = 0.92,
    max_differing_tokens: int = 4,
) -> bool:
    """Apply the similarity rule with precomputed token data.

    Callers that cache per-title token sets and counters (the duplicate-group
    builder) avoid rebuilding them for every comparison.  The decision is
    identical to :func:`normalized_titles_are_similar`.
    """

    if not first_normalized or not second_normalized:
        return False
    if first_normalized == second_normalized:
        return True
    if abs(len(first_normalized) - len(second_normalized)) > 25:
        return False
    # Distinct-token symmetric difference is a cheap lower bound for the
    # multiset difference; reject before touching the counters when it already
    # exceeds the budget.
    if len(first_tokens ^ second_tokens) > max_differing_tokens:
        return False
    first_only = first_counts - second_counts
    second_only = second_counts - first_counts
    differing_count = sum(first_only.values()) + sum(second_only.values())
    if differing_count == 0:
        return True
    if all(token.isdigit() for token in (*first_only, *second_only)):
        return False
    if differing_count > max_differing_tokens:
        return False
    matcher = SequenceMatcher(None, first_normalized, second_normalized)
    # real_quick_ratio() is a cheap length upper bound; the prefix/suffix bound
    # is tighter than quick_ratio() for template-like titles.  Skipping the
    # full ratio when either bound is below the threshold is exact.
    if matcher.real_quick_ratio() < threshold:
        return False
    if _matching_character_bound(first_normalized, second_normalized) < threshold:
        return False
    return matcher.ratio() >= threshold


def normalized_titles_are_similar(
    first_normalized: str,
    second_normalized: str,
    *,
    threshold: float = 0.92,
    max_differing_tokens: int = 4,
) -> bool:
    """Apply :func:`titles_are_similar` to already-normalized titles.

    ``normalize_title`` is idempotent, so callers that cache normalized titles
    can avoid re-running Unicode and regex normalization for every comparison
    without changing the match decision.
    """

    if not first_normalized or not second_normalized:
        return False
    if first_normalized == second_normalized:
        return True
    first_tokens = first_normalized.split()
    second_tokens = second_normalized.split()
    return prepared_titles_are_similar(
        first_normalized,
        second_normalized,
        Counter(first_tokens),
        Counter(second_tokens),
        frozenset(first_tokens),
        frozenset(second_tokens),
        threshold=threshold,
        max_differing_tokens=max_differing_tokens,
    )
