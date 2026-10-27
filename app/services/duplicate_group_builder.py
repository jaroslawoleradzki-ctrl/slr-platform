from collections import Counter
from collections.abc import Iterable
from datetime import datetime, timezone
from uuid import NAMESPACE_URL, UUID, uuid5

from app.domain.deduplication import DuplicateGroup
from app.domain.identifiers import Identifier, IdentifierType
from app.domain.publication import Publication
from app.normalization.doi import normalize_doi
from app.normalization.title import (
    normalize_title,
    normalized_titles_are_similar,
    prepared_titles_are_similar,
)

_FILE_IMPORT_TRANSFORMATIONS = {"ris_to_publication", "bibtex_to_publication"}
_FILE_IMPORT_SOURCES = {
    "ris",
    "bibtex",
    "google_scholar",
    "google_scholar_pop",
    "scopus",
    "web_of_science",
    "pubmed",
    "ebsco",
    "proquest",
}
_SIMILAR_TITLE_THRESHOLD = 0.92

_STRONG_IDENTIFIER_TYPES = {
    IdentifierType.DOI,
    IdentifierType.PMID,
    IdentifierType.OPENALEX,
}


def _identifier_key(identifier: Identifier) -> tuple[str, str] | None:
    is_provider_openalex_id = (
        identifier.type is IdentifierType.OTHER
        and identifier.source is not None
        and identifier.source.casefold() == "openalex"
    )
    if identifier.type not in _STRONG_IDENTIFIER_TYPES and not is_provider_openalex_id:
        return None
    value = normalize_doi(identifier.value) if identifier.type is IdentifierType.DOI else identifier.value
    if value is None:
        return None
    identifier_type = (
        IdentifierType.OPENALEX.value
        if is_provider_openalex_id
        else identifier.type.value
    )
    return identifier_type, value


def _group_id(publication_ids: tuple[UUID, ...]) -> UUID:
    member_key = ",".join(str(publication_id) for publication_id in publication_ids)
    return uuid5(NAMESPACE_URL, f"slr-platform:duplicate-group:{member_key}")


def _is_file_import(publication: Publication) -> bool:
    for provenance in publication.provenance:
        if (provenance.transformation or "") in _FILE_IMPORT_TRANSFORMATIONS:
            return True
        if provenance.source.strip().casefold() in _FILE_IMPORT_SOURCES:
            return True
    return False


def _normalized_title(publication: Publication) -> str | None:
    return normalize_title(publication.title)


def _similar_title(first: str, second: str) -> bool:
    return normalized_titles_are_similar(
        first, second, threshold=_SIMILAR_TITLE_THRESHOLD
    )


def _group_evidence(
    publications: list[Publication],
    keys_by_publication: dict[UUID, set[tuple[str, str]]],
) -> tuple[str | None, str | None]:
    """Return ``(match_type, reason)`` from actual member evidence."""

    shared: set[tuple[str, str]] = set()
    sets = [keys_by_publication.get(pub.record_id, set()) for pub in publications]
    for index, keys in enumerate(sets):
        for other in sets[index + 1 :]:
            shared.update(keys & other)
    if shared:
        types = sorted({identifier_type for identifier_type, _ in shared})
        if "doi" in types:
            return "exact_doi", "Exact normalized DOI match"
        if "pmid" in types:
            return "shared_identifier", "Shared PMID"
        if "openalex" in types:
            return "shared_identifier", "Shared OpenAlex identifier"
        return "shared_identifier", f"Shared strong identifier ({', '.join(types)})"

    titles = [title for pub in publications if (title := _normalized_title(pub))]
    if len(titles) >= 2 and len(set(titles)) == 1:
        any_doi = any(
            identifier.type is IdentifierType.DOI
            for pub in publications
            for identifier in pub.identifiers
        )
        if any_doi:
            return (
                "conflicting_identifiers",
                "Identical normalized title with conflicting DOI evidence",
            )
        return "identical_title", "Identical normalized title without DOI"
    for index, first in enumerate(titles):
        for second in titles[index + 1 :]:
            if _similar_title(first, second):
                return (
                    "similar_title",
                    "Similar normalized title; insufficient bibliographic evidence",
                )
    return None, None


class DuplicateGroupBuilder:
    """Build deterministic candidate groups from shared strong identifiers."""

    def build(
        self,
        publications: Iterable[Publication],
        *,
        created_at: datetime | None = None,
        include_title_candidates: bool = False,
    ) -> list[DuplicateGroup]:
        timestamp = created_at if created_at is not None else datetime.now(timezone.utc)
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")

        publication_list = list(publications)
        # Union-find runs on dense integer indexes so that the candidate hot
        # loop does not pay UUID hashing/comparison costs.  Index order is the
        # deterministic UUID order and every public identifier is mapped back
        # before a group is emitted.
        ordered_ids = sorted({publication.record_id for publication in publication_list})
        index_by_id = {
            publication_id: index for index, publication_id in enumerate(ordered_ids)
        }
        publication_count = len(ordered_ids)
        publications_by_index: dict[int, list[Publication]] = {}
        keys_by_publication: dict[UUID, set[tuple[str, str]]] = {}
        keys_by_index: list[set[tuple[str, str]]] = [
            set() for _ in range(publication_count)
        ]
        file_import_indices: set[int] = set()
        for publication in publication_list:
            index = index_by_id[publication.record_id]
            publications_by_index.setdefault(index, []).append(publication)
            # Repeated representations of one record contribute identifier keys
            # only; Phase 5.3 does not select or reconcile their metadata.
            keys = keys_by_publication.setdefault(publication.record_id, set())
            for identifier in publication.identifiers:
                key = _identifier_key(identifier)
                if key is not None:
                    keys.add(key)
                    keys_by_index[index].add(key)
            if _is_file_import(publication):
                file_import_indices.add(index)

        parent = list(range(publication_count))
        # Bit i of component_bits[root] marks record i as a member of that
        # component.  Bitsets keep candidate filtering and already-connected
        # checks in C for high-collision datasets.
        component_bits = [1 << index for index in range(publication_count)]
        # Number of file-origin records in each union-find root.  Populated
        # after identifier/exact-title unions and maintained by union(); once
        # one root contains every file-origin record, no remaining similarity
        # comparison can change group membership.
        root_file_count = [0] * publication_count

        def find(index: int) -> int:
            while parent[index] != index:
                parent[index] = parent[parent[index]]
                index = parent[index]
            return index

        def union(first: int, second: int) -> None:
            first_root = find(first)
            second_root = find(second)
            if first_root == second_root:
                return
            lower, higher = sorted((first_root, second_root))
            parent[higher] = lower
            component_bits[lower] |= component_bits[higher]
            component_bits[higher] = 0
            root_file_count[lower] += root_file_count[higher]
            root_file_count[higher] = 0

        owner_by_key: dict[tuple[str, str], int] = {}
        for index in range(publication_count):
            for key in sorted(keys_by_index[index]):
                owner = owner_by_key.setdefault(key, index)
                union(owner, index)

        if include_title_candidates:
            # File-import (RIS/BibTeX) candidates feed the existing manual
            # duplicate-review workflow.  Exact title grouping includes
            # DOI-bearing counterparts; similar-title grouping is deliberately
            # conservative and never auto-merges.
            normalized_titles: dict[int, str | None] = {}
            for publication in publication_list:
                normalized_titles[index_by_id[publication.record_id]] = (
                    _normalized_title(publication)
                )
            title_buckets: dict[str, list[int]] = {}
            for publication in publication_list:
                index = index_by_id[publication.record_id]
                title_key = normalized_titles[index]
                if title_key is None:
                    continue
                title_buckets.setdefault(title_key, []).append(index)
            for bucket in title_buckets.values():
                if len(bucket) < 2 or not any(
                    index in file_import_indices for index in bucket
                ):
                    continue
                owner = bucket[0]
                for index in bucket[1:]:
                    union(owner, index)

            # Similar-title candidate generation is deliberately conservative
            # and exact with respect to the previous all-pairs comparison:
            #
            # * titles_are_similar() rejects pairs whose token counts differ by
            #   more than four (the differing-token budget);
            # * when both titles have at least five tokens, any accepted pair
            #   must share a token.  Ordering each title's first five *unique*
            #   tokens by global rarity and indexing that prefix guarantees a
            #   shared token for every accepted pair with five or more tokens
            #   on both sides;
            # * pairs involving titles with fewer than five tokens are covered
            #   by an explicit short-title bucket, including typo pairs that
            #   share no token at all.
            #
            # The old implementation compared every file-import record against
            # the whole collection.  This index only removes comparisons that
            # provably cannot satisfy titles_are_similar(); it does not cap the
            # candidate set or discard high-collision groups.
            tokens_by_index: dict[int, tuple[str, ...]] = {
                index: tuple(title.split())
                for index, title in normalized_titles.items()
                if title is not None
            }
            token_counter_by_index = {
                index: Counter(tokens) for index, tokens in tokens_by_index.items()
            }
            token_set_by_index = {
                index: frozenset(tokens) for index, tokens in tokens_by_index.items()
            }
            token_counts = {
                index: len(tokens) for index, tokens in tokens_by_index.items()
            }
            # Titles that share a digit-masked token multiset differ only by
            # numeric tokens, which titles_are_similar() rejects unconditionally.
            # Precomputing the shape makes that rejection O(1) per pair instead
            # of tokenizing and counting both titles.
            title_shapes: dict[int, tuple[tuple[str, int], ...]] = {
                index: tuple(
                    sorted(
                        Counter(
                            "#" if token.isdigit() else token for token in tokens
                        ).items()
                    )
                )
                for index, tokens in tokens_by_index.items()
            }
            token_frequency: Counter[str] = Counter()
            for tokens in tokens_by_index.values():
                token_frequency.update(set(tokens))
            prefix_tokens_by_index: dict[int, tuple[str, ...]] = {
                index: tuple(
                    sorted(set(tokens), key=lambda token: (token_frequency[token], token))[
                        :5
                    ]
                )
                for index, tokens in tokens_by_index.items()
            }
            postings: dict[str, int] = {}
            shape_bits: dict[tuple[tuple[str, int], ...], int] = {}
            for index in sorted(prefix_tokens_by_index):
                shape = title_shapes[index]
                index_bit = 1 << index
                shape_bits[shape] = shape_bits.get(shape, 0) | index_bit
                for token in prefix_tokens_by_index[index]:
                    postings[token] = postings.get(token, 0) | index_bit
            short_bits = 0
            for index, count in token_counts.items():
                if count <= 4:
                    short_bits |= 1 << index

            file_origin = sorted(
                index
                for index in file_import_indices
                if normalized_titles.get(index) is not None
            )
            for index in file_origin:
                root_file_count[find(index)] += 1
            for first_id in file_origin:
                if root_file_count[find(first_id)] == len(file_origin):
                    # Every file-origin record is already in one component;
                    # further similarity edges cannot split or extend it.
                    break
                first_title = normalized_titles[first_id]
                assert first_title is not None  # guarded above
                first_tokens = tokens_by_index.get(first_id, ())
                first_shape = title_shapes[first_id]
                candidate_bits = 0
                if len(first_tokens) <= 4:
                    # Short titles may pass on a typo-only difference with no
                    # shared token; compare them with the short-title bucket.
                    candidate_bits |= short_bits
                for token in prefix_tokens_by_index.get(first_id, ()):
                    candidate_bits |= postings.get(token, 0)
                # Same-shape titles differ only by numeric tokens, which
                # titles_are_similar() rejects; removing them here is exact and
                # avoids high-collision numeric families such as "Study 201" /
                # "Study 202".
                candidate_bits &= ~shape_bits.get(first_shape, 0)
                candidate_bits &= ~(1 << first_id)
                pending = candidate_bits & ~component_bits[find(first_id)]

                while pending:
                    lowest_bit = pending & -pending
                    second_id = lowest_bit.bit_length() - 1
                    pending ^= lowest_bit
                    if second_id in file_import_indices and second_id < first_id:
                        # Both directions of an unordered file/file pair are
                        # equivalent; process the pair once.
                        continue
                    if find(first_id) == find(second_id):
                        continue
                    second_title = normalized_titles.get(second_id)
                    if second_title is None or second_title == first_title:
                        continue
                    if abs(token_counts[first_id] - token_counts.get(second_id, 0)) > 4:
                        continue
                    if abs(len(first_title) - len(second_title)) > 25:
                        continue
                    if prepared_titles_are_similar(
                        first_title,
                        second_title,
                        token_counter_by_index[first_id],
                        token_counter_by_index[second_id],
                        token_set_by_index[first_id],
                        token_set_by_index[second_id],
                        threshold=_SIMILAR_TITLE_THRESHOLD,
                    ):
                        union(first_id, second_id)
                        pending &= ~component_bits[find(first_id)]

        members_by_root: dict[int, list[int]] = {}
        for index in range(publication_count):
            members_by_root.setdefault(find(index), []).append(index)

        groups: list[DuplicateGroup] = []
        for member_indices in sorted(
            (
                tuple(sorted(indices))
                for indices in members_by_root.values()
                if len(indices) >= 2
            ),
            key=lambda indices: tuple(ordered_ids[index] for index in indices),
        ):
            members = tuple(ordered_ids[index] for index in member_indices)
            member_publications = [
                publication
                for index in member_indices
                for publication in publications_by_index[index]
            ]
            match_type, match_reason = _group_evidence(
                member_publications, keys_by_publication
            )
            groups.append(
                DuplicateGroup(
                    group_id=_group_id(members),
                    publication_ids=members,
                    created_at=timestamp,
                    updated_at=timestamp,
                    match_type=match_type,
                    match_reason=match_reason,
                )
            )
        return groups


duplicate_group_builder = DuplicateGroupBuilder()


def build_duplicate_groups(
    publications: Iterable[Publication],
    *,
    created_at: datetime | None = None,
) -> list[DuplicateGroup]:
    return duplicate_group_builder.build(publications, created_at=created_at)
