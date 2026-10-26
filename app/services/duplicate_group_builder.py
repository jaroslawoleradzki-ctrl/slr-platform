from collections.abc import Iterable
from datetime import datetime, timezone
from uuid import NAMESPACE_URL, UUID, uuid5

from app.domain.deduplication import DuplicateGroup
from app.domain.identifiers import Identifier, IdentifierType
from app.domain.publication import Publication
from app.normalization.doi import normalize_doi
from app.normalization.title import normalize_title, titles_are_similar

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
    return titles_are_similar(
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
        publication_ids: set[UUID] = set()
        keys_by_publication: dict[UUID, set[tuple[str, str]]] = {}
        for publication in publication_list:
            publication_ids.add(publication.record_id)
            # Repeated representations of one record contribute identifier keys
            # only; Phase 5.3 does not select or reconcile their metadata.
            keys_by_publication.setdefault(publication.record_id, set()).update(
                key
                for identifier in publication.identifiers
                if (key := _identifier_key(identifier)) is not None
            )

        parent = {
            publication_id: publication_id
            for publication_id in publication_ids
        }

        def find(publication_id: UUID) -> UUID:
            while parent[publication_id] != publication_id:
                parent[publication_id] = parent[parent[publication_id]]
                publication_id = parent[publication_id]
            return publication_id

        def union(first: UUID, second: UUID) -> None:
            first_root = find(first)
            second_root = find(second)
            if first_root == second_root:
                return
            lower, higher = sorted((first_root, second_root))
            parent[higher] = lower

        owner_by_key: dict[tuple[str, str], UUID] = {}
        for publication_id in sorted(publication_ids):
            for key in sorted(keys_by_publication[publication_id]):
                owner = owner_by_key.setdefault(key, publication_id)
                union(owner, publication_id)

        if include_title_candidates:
            # File-import (RIS/BibTeX) candidates feed the existing manual
            # duplicate-review workflow.  Exact title grouping includes
            # DOI-bearing counterparts; similar-title grouping is deliberately
            # conservative and never auto-merges.
            title_buckets: dict[str, list[Publication]] = {}
            for publication in publication_list:
                title_key = _normalized_title(publication)
                if title_key is None:
                    continue
                title_buckets.setdefault(title_key, []).append(publication)
            for bucket in title_buckets.values():
                if len(bucket) < 2 or not any(_is_file_import(pub) for pub in bucket):
                    continue
                owner = bucket[0].record_id
                for publication in bucket[1:]:
                    union(owner, publication.record_id)

            file_origin = [
                publication
                for publication in publication_list
                if _is_file_import(publication) and _normalized_title(publication)
            ]
            for first in file_origin:
                first_title = _normalized_title(first)
                assert first_title is not None  # guarded above
                for second in publication_list:
                    if second.record_id == first.record_id:
                        continue
                    second_title = _normalized_title(second)
                    if second_title is None or second_title == first_title:
                        continue
                    if abs(len(first_title) - len(second_title)) > 25:
                        continue
                    if _similar_title(first_title, second_title):
                        union(first.record_id, second.record_id)

        members_by_root: dict[UUID, list[UUID]] = {}
        for publication_id in sorted(publication_ids):
            members_by_root.setdefault(find(publication_id), []).append(
                publication_id
            )

        groups: list[DuplicateGroup] = []
        for members in sorted(
            (
                tuple(sorted(publication_ids))
                for publication_ids in members_by_root.values()
                if len(publication_ids) >= 2
            )
        ):
            member_publications = [
                publication
                for publication in publication_list
                if publication.record_id in set(members)
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
