from dataclasses import dataclass
from functools import reduce
from uuid import UUID

from app.api.dto.deduplication import (
    DuplicateDecisionStatus,
    DuplicateDecisionType,
    DuplicateGroupDecisionResponse,
    DuplicateGroupListResponse,
    DuplicateGroupMergeResponse,
    DuplicateGroupResponse,
    DuplicateGroupStatus,
    DuplicateRecordPreviewResponse,
    ProvenanceEntryResponse,
    SharedIdentifierResponse,
)
from app.domain.deduplication import DuplicateGroup, DuplicateGroupMergeRecord
from app.domain.duplicate_review import DuplicateDecision, DuplicateGroupReviewDecision
from app.domain.identifiers import IdentifierType
from app.domain.publication import Publication
from app.normalization.doi import normalize_doi
from app.repositories.duplicate_merge_repository import (
    DuplicateMergeRepository,
    InMemoryDuplicateMergeRepository,
    default_duplicate_merge_repository,
)
from app.repositories.duplicate_review_decision_repository import (
    DuplicateReviewDecisionRepository,
    GroupNotFoundError,
    default_duplicate_review_decision_repository,
)
from app.repositories.project_publication_repository import (
    ProjectPublicationRepository,
    default_project_publication_repository,
)
from app.repositories.transaction_manager import SqliteTransactionManager
from app.services.active_publication_filter import (
    provides_active_corpus,
    provides_removed_record_listing,
    repository_provides_method,
)
from app.services.duplicate_group_builder import DuplicateGroupBuilder, duplicate_group_builder
from app.services.publication_merge_policy import publication_merge_policy


def _shared(records: list[Publication]) -> list[SharedIdentifierResponse]:
    counts: dict[tuple[str, str], int] = {}
    for pub in records:
        for ident in pub.identifiers:
            value = normalize_doi(ident.value) if ident.type is IdentifierType.DOI else ident.value.strip()
            if value:
                key = (ident.type.value.lower(), value)
                counts[key] = counts.get(key, 0) + 1
    return [SharedIdentifierResponse(identifier_type=k[0], value=k[1]) for k, n in sorted(counts.items()) if n >= 2]


def _preview(pub: Publication) -> DuplicateRecordPreviewResponse:
    ids = {i.type: i.value for i in pub.identifiers}
    return DuplicateRecordPreviewResponse(
        id=str(pub.record_id),
        title=pub.title,
        authors=", ".join(a.display_name for a in pub.authors) or "Unknown Authors",
        year=pub.publication_year,
        source=pub.provenance[0].source if pub.provenance else "Unknown Source",
        venue=pub.venue.name if pub.venue else None,
        doi=normalize_doi(ids.get(IdentifierType.DOI, "")) or None,
        pmid=ids.get(IdentifierType.PMID),
        openalex_id=ids.get(IdentifierType.OPENALEX),
        provenance=[
            ProvenanceEntryResponse(
                source=p.source,
                source_record_id=p.source_record_id,
                retrieved_at=p.retrieved_at.isoformat() if p.retrieved_at else None,
            )
            for p in pub.provenance
        ],
    )


@dataclass(frozen=True, slots=True)
class DuplicateReconciliationReport:
    """Outcome of reconciling persisted duplicate state with the Active Corpus."""

    project_id: str
    active_records_count: int
    removed_merge_group_ids: tuple[str, ...] = ()
    removed_decision_group_ids: tuple[str, ...] = ()

    @property
    def removed_merges_count(self) -> int:
        return len(self.removed_merge_group_ids)

    @property
    def removed_decisions_count(self) -> int:
        return len(self.removed_decision_group_ids)


class ProjectDuplicateService:
    def __init__(
        self,
        repository: ProjectPublicationRepository | None = None,
        decision_repository: DuplicateReviewDecisionRepository | None = None,
        builder: DuplicateGroupBuilder = duplicate_group_builder,
        merge_repository: DuplicateMergeRepository | None = None,
        transaction_manager: SqliteTransactionManager | None = None,
    ) -> None:
        self._repository = repository or default_project_publication_repository()
        self._decision_repository = decision_repository or default_duplicate_review_decision_repository()
        self._merge_repository = merge_repository or (
            default_duplicate_merge_repository()
            if hasattr(self._repository, "_database_path")
            else InMemoryDuplicateMergeRepository()
        )
        self._transaction_manager = transaction_manager or SqliteTransactionManager(
            getattr(self._repository, "_database_path", "data/slr-platform.db")
        )
        self._builder = builder

    def _active_publications(self, project_id: str, *, connection=None) -> list[Publication]:
        """Return the authoritative Active Project Corpus for deduplication.

        The WP1 Active Corpus excludes ``pre_screening_status='removed'``
        records, physically archived records, and superseded duplicate members,
        uniformly across providers (Crossref / OpenAlex / Semantic Scholar).
        Repositories without the WP1 ``get_active_publications`` accessor fall
        back to their whole collection (legacy projects without pre-screening
        decisions remain compatible).
        """
        if provides_active_corpus(self._repository):
            get_active = getattr(self._repository, "get_active_publications")
            if connection is None:
                return list(get_active(project_id))
            try:
                return list(get_active(project_id, connection=connection))
            except TypeError:
                return list(get_active(project_id))
        if connection is None:
            publications = (
                self._repository.get_all_publications(project_id)
                if hasattr(self._repository, "get_all_publications")
                else self._repository.get_publications(project_id)
            )
        else:
            publications = (
                self._repository.get_all_publications(project_id, connection=connection)
                if hasattr(self._repository, "get_all_publications")
                else self._repository.get_publications(project_id, connection=connection)
            )
        return list(publications)

    def _find_group(self, project_id: str, group_id: str, *, connection=None):
        publications = self._active_publications(project_id, connection=connection)
        group = next((g for g in self._builder.build(publications) if str(g.group_id) == group_id), None)
        if group is None:
            merge = self._merge_repository.get_merge(project_id, group_id, connection=connection)
            if merge is None:
                raise GroupNotFoundError(group_id, project_id)
            group = DuplicateGroup(
                group_id=UUID(group_id),
                publication_ids=merge.merged_publication_ids,
                created_at=merge.merged_at,
                updated_at=merge.merged_at,
            )
        return publications, group

    def get_candidate_duplicate_groups(self, project_id: str) -> DuplicateGroupListResponse:
        publications = self._active_publications(project_id)
        by_id = {p.record_id: p for p in publications}
        decisions = self._decision_repository.list_decisions_for_project(project_id)
        merges = self._merge_repository.list_merges_for_project(project_id)
        responses: list[DuplicateGroupResponse] = []
        live_groups = {str(group.group_id): group for group in self._builder.build(publications)}
        for group_id, group in live_groups.items():
            members = [by_id[i] for i in group.publication_ids]
            decision = decisions.get(group_id)
            merge = merges.get(group_id)
            state = (
                DuplicateGroupStatus.MERGED
                if merge is not None and merge.status == "merged"
                else (
                    DuplicateGroupStatus.APPROVED
                    if decision and decision.decision is DuplicateDecision.APPROVE
                    else DuplicateGroupStatus.REJECTED
                    if decision
                    else DuplicateGroupStatus.PENDING
                )
            )
            identifiers = _shared(members)
            detail = ", ".join(f"{i.identifier_type.upper()}: {i.value}" for i in identifiers)
            responses.append(
                DuplicateGroupResponse(
                    group_id=group_id,
                    reason=f"Zgodność identyfikatorów ({detail})" if detail else "Identical strong identifier match",
                    records_count=len(members),
                    status=state,
                    rationale=decision.rationale if decision else None,
                    canonical_record_id=str(merge.canonical_record_id) if merge else None,
                    merged_publication_ids=[str(record_id) for record_id in merge.merged_publication_ids] if merge else None,
                    merged_at=merge.merged_at.isoformat() if merge else None,
                    shared_identifiers=identifiers,
                    records=[_preview(p) for p in members],
                )
            )
        # A later import can change dynamic duplicate components.  Persisted
        # merges remain historical audit records and must still be queryable.
        for group_id, merge in sorted(merges.items()):
            if group_id in live_groups or merge.status != "merged":
                continue
            snapshot_by_id = {publication.record_id: publication for publication in merge.pre_merge_snapshots}
            members = [by_id.get(record_id, snapshot_by_id[record_id]) for record_id in merge.merged_publication_ids]
            decision = decisions.get(group_id)
            identifiers = _shared(members)
            detail = ", ".join(f"{i.identifier_type.upper()}: {i.value}" for i in identifiers)
            responses.append(
                DuplicateGroupResponse(
                    group_id=group_id,
                    reason=f"Zgodność identyfikatorów ({detail})" if detail else "Historical technical merge",
                    records_count=len(members),
                    status=DuplicateGroupStatus.MERGED,
                    rationale=decision.rationale if decision else None,
                    canonical_record_id=str(merge.canonical_record_id),
                    merged_publication_ids=[str(record_id) for record_id in merge.merged_publication_ids],
                    merged_at=merge.merged_at.isoformat(),
                    shared_identifiers=identifiers,
                    records=[_preview(publication) for publication in members],
                )
            )
        return DuplicateGroupListResponse(project_id=project_id, total_groups_count=len(responses), groups=responses)

    def record_decision(
        self, project_id: str, group_id: str, decision: DuplicateDecisionType | str, rationale: str | None = None
    ) -> DuplicateGroupDecisionResponse:
        self._find_group(project_id, group_id)
        if self._merge_repository.get_merge(project_id, group_id):
            raise ValueError("cannot change the reviewer decision of a merged group")
        record = DuplicateGroupReviewDecision(
            decision=DuplicateDecision(decision.value if isinstance(decision, DuplicateDecisionType) else decision),
            rationale=rationale,
        )
        self._decision_repository.save_decision(project_id, group_id, record)
        return DuplicateGroupDecisionResponse(
            project_id=project_id,
            group_id=group_id,
            decision=DuplicateDecisionStatus(record.decision.value),
            rationale=record.rationale,
        )

    def merge_group(self, project_id: str, group_id: str) -> DuplicateGroupMergeResponse:
        with self._transaction_manager.transaction() as connection:
            publications, group = self._find_group(project_id, group_id, connection=connection)
            if self._merge_repository.get_merge(project_id, group_id, connection=connection):
                raise ValueError("duplicate group is already merged")
            decision = self._decision_repository.get_decision(project_id, group_id, connection=connection)
            if decision is None or decision.decision is not DuplicateDecision.APPROVE:
                raise ValueError("duplicate group must be APPROVE before merge")
            members = [p for p in publications if p.record_id in group.publication_ids]
            if len(members) != len(group.publication_ids):
                raise ValueError("duplicate group members are not all present in project")
            superseded_by = self._repository.get_superseded_by_map(project_id, connection=connection)
            inactive_members = [member.record_id for member in members if superseded_by.get(member.record_id) is not None]
            if inactive_members:
                raise ValueError("duplicate group members must all be active before merge")
            canonical_id = min(p.record_id for p in members)
            if superseded_by.get(canonical_id) is not None:
                raise ValueError("canonical publication must be active before merge")
            canonical = reduce(publication_merge_policy.merge, sorted(members, key=lambda p: p.record_id))
            merge = DuplicateGroupMergeRecord(
                project_id=project_id,
                group_id=group_id,
                canonical_record_id=canonical_id,
                merged_publication_ids=tuple(sorted(group.publication_ids)),
                pre_merge_snapshots=tuple(members),
            )
            self._merge_repository.save_merge(merge, connection=connection)
            self._repository.update_publication(project_id, canonical, connection=connection)
            self._repository.mark_superseded(
                project_id,
                [p.record_id for p in members if p.record_id != canonical_id],
                canonical_id,
                connection=connection,
            )
        return DuplicateGroupMergeResponse(
            project_id=project_id,
            group_id=group_id,
            canonical_record_id=str(canonical_id),
            merged_publication_ids=[str(i) for i in merge.merged_publication_ids],
            merged_at=merge.merged_at.isoformat(),
        )

    def get_decision(self, project_id: str, group_id: str) -> DuplicateGroupDecisionResponse:
        self._find_group(project_id, group_id)
        record = self._decision_repository.get_decision(project_id, group_id)
        return DuplicateGroupDecisionResponse(
            project_id=project_id,
            group_id=group_id,
            decision=DuplicateDecisionStatus(record.decision.value) if record else DuplicateDecisionStatus.PENDING,
            rationale=record.rationale if record else None,
        )

    def reconcile_with_active_corpus(self, project_id: str) -> DuplicateReconciliationReport:
        """Remove stale duplicate state referencing records outside the Active Corpus.

        Deterministic reconciliation for projects previously deduplicated over
        the unfiltered population (WP2 D8): any persisted merge or reviewer
        decision whose group contains a pre-screening removed (or physically
        absent) publication is deleted. Merges and decisions fully contained in
        the Active Corpus — including legitimate historical merges whose
        non-canonical members are superseded by design — are preserved.

        No publication rows, screening decisions, or finalization records are
        touched. The operation is idempotent: a second run removes nothing.
        """
        active = self._active_publications(project_id)
        active_ids = {publication.record_id for publication in active}

        if hasattr(self._repository, "get_all_publications"):
            full_population = list(self._repository.get_all_publications(project_id))
        else:
            full_population = list(self._repository.get_publications(project_id))
        present_ids = {publication.record_id for publication in full_population}

        removed_ids: set[UUID] = set()
        if provides_removed_record_listing(self._repository):
            removed_ids = set(
                self._repository.get_pre_screening_removed_record_ids(project_id)  # type: ignore[attr-defined]
            )

        superseded_by: dict[UUID, UUID | None] = {}
        has_supersession_map = repository_provides_method(self._repository, "get_superseded_by_map")
        if has_supersession_map:
            superseded_by = dict(self._repository.get_superseded_by_map(project_id))

        def is_removed_or_absent(record_id: UUID) -> bool:
            if record_id in removed_ids:
                # A superseded-then-removed record is still a removed record:
                # no derived duplicate state may reference it.
                return True
            if record_id in active_ids:
                return False
            if record_id not in present_ids:
                # Physically archived records are absent from every read.
                return True
            # Present but inactive: a superseded member is a legitimate merge
            # product and must be preserved; anything else is inconsistent
            # state that reconciliation heals toward the Active Corpus.
            if has_supersession_map:
                return superseded_by.get(record_id) is None
            return False

        # Candidate groups rebuilt from the full (unfiltered) population reveal
        # exactly which historical group identities were tainted by removals.
        tainted_group_ids = {
            str(group.group_id)
            for group in self._builder.build(full_population)
            if any(is_removed_or_absent(member) for member in group.publication_ids)
        }

        removed_merges: list[str] = []
        for group_id, merge in self._merge_repository.list_merges_for_project(project_id).items():
            if group_id in tainted_group_ids or any(
                is_removed_or_absent(member) for member in merge.merged_publication_ids
            ):
                if self._merge_repository.delete_merge(project_id, group_id):
                    removed_merges.append(group_id)

        removed_decisions: list[str] = []
        for group_id in self._decision_repository.list_decisions_for_project(project_id):
            if group_id in tainted_group_ids:
                if self._decision_repository.delete_decision(project_id, group_id):
                    removed_decisions.append(group_id)

        # Physically archived members absent from every collection read never
        # appear in ``active_ids`` and have no superseded mapping, so the
        # per-member check above already classifies them as removed-or-absent.
        return DuplicateReconciliationReport(
            project_id=project_id,
            active_records_count=len(active_ids),
            removed_merge_group_ids=tuple(sorted(removed_merges)),
            removed_decision_group_ids=tuple(sorted(removed_decisions)),
        )


project_duplicate_service = ProjectDuplicateService()
