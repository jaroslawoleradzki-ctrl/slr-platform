from collections.abc import Iterable
from datetime import datetime, timezone
from uuid import NAMESPACE_URL, UUID, uuid5

from app.domain.deduplication import DuplicateGroup
from app.domain.identifiers import Identifier, IdentifierType
from app.domain.publication import Publication
from app.normalization.doi import normalize_doi

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


class DuplicateGroupBuilder:
    """Build deterministic candidate groups from shared strong identifiers."""

    def build(
        self,
        publications: Iterable[Publication],
        *,
        created_at: datetime | None = None,
    ) -> list[DuplicateGroup]:
        timestamp = created_at if created_at is not None else datetime.now(timezone.utc)
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")

        publication_ids: set[UUID] = set()
        keys_by_publication: dict[UUID, set[tuple[str, str]]] = {}
        for publication in publications:
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
            groups.append(
                DuplicateGroup(
                    group_id=_group_id(members),
                    publication_ids=members,
                    created_at=timestamp,
                    updated_at=timestamp,
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
