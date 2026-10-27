from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.domain.deduplication import DuplicateGroup
from app.domain.publication import Publication
from app.repositories.corpus_finalization_repository import (
    CorpusFinalizationRepository,
    SqliteCorpusFinalizationRepository,
)
from app.repositories.duplicate_merge_repository import (
    DuplicateMergeRepository,
    InMemoryDuplicateMergeRepository,
    SqliteDuplicateMergeRepository,
)
from app.repositories.duplicate_review_decision_repository import (
    DuplicateReviewDecisionRepository,
    default_duplicate_review_decision_repository,
)
from app.repositories.project_publication_repository import (
    ProjectPublicationRepository,
    default_project_publication_repository,
)
from app.services.duplicate_group_builder import DuplicateGroupBuilder
from app.services.duplicate_readiness_service import (
    DuplicateReadiness,
    DuplicateReadinessStatus,
    evaluate_duplicate_readiness,
)


class ScreeningInputReadinessStatus(StrEnum):
    READY = "ready"
    UNRESOLVED_DUPLICATES = "unresolved_duplicates"
    UNMERGED_DUPLICATES = "unmerged_duplicates"


@dataclass(frozen=True, slots=True)
class ScreeningInput:
    project_id: str
    ready: bool
    working_collection_count: int
    canonical_records_count: int
    unresolved_groups_count: int
    publications: tuple[Publication, ...]
    readiness_status: ScreeningInputReadinessStatus
    duplicate_readiness: DuplicateReadiness


class ScreeningInputService:
    """Derive a non-destructive, project-scoped input set for later screening."""

    def __init__(
        self,
        publication_repository: ProjectPublicationRepository | None = None,
        decision_repository: DuplicateReviewDecisionRepository | None = None,
        builder: DuplicateGroupBuilder | None = None,
        merge_repository: DuplicateMergeRepository | None = None,
        finalization_repository: CorpusFinalizationRepository | None = None,
    ) -> None:
        self._publications = publication_repository or default_project_publication_repository()
        self._decisions = decision_repository or default_duplicate_review_decision_repository()
        self._builder = builder or DuplicateGroupBuilder()
        self._merges = merge_repository or (
            SqliteDuplicateMergeRepository(self._publications._database_path)
            if hasattr(self._publications, "_database_path")
            else InMemoryDuplicateMergeRepository()
        )
        self._finalizations = finalization_repository or (
            SqliteCorpusFinalizationRepository(self._publications._database_path)
            if hasattr(self._publications, "_database_path")
            else None
        )

    def get_input_set(
        self,
        project_id: str,
        *,
        groups: list[DuplicateGroup] | None = None,
    ) -> ScreeningInput:
        if hasattr(self._publications, "get_screening_corpus_publications"):
            corpus_publications = self._publications.get_screening_corpus_publications(project_id)
        elif hasattr(self._publications, "get_all_publications"):
            corpus_publications = self._publications.get_all_publications(project_id)
        else:
            corpus_publications = self._publications.get_publications(project_id)

        active = (
            list(self._publications.get_active_publications(project_id))
            if hasattr(self._publications, "get_active_publications")
            else list(corpus_publications)
        )
        # Duplicate review is defined over active canonical publications only.
        # The screening corpus may still contain superseded rows for provenance,
        # but those rows must never create phantom candidate groups.
        if groups is None:
            groups = self._builder.build(active, include_title_candidates=True)
        decisions = self._decisions.list_decisions_for_project(project_id)
        merges = self._merges.list_merges_for_project(project_id)
        duplicate_readiness = evaluate_duplicate_readiness(groups, decisions, merges)

        if duplicate_readiness.status is DuplicateReadinessStatus.PENDING_REVIEW:
            return ScreeningInput(
                project_id,
                False,
                len(corpus_publications),
                0,
                duplicate_readiness.blocking_groups,
                (),
                ScreeningInputReadinessStatus.UNRESOLVED_DUPLICATES,
                duplicate_readiness,
            )

        if duplicate_readiness.status is DuplicateReadinessStatus.APPROVED_UNMERGED:
            return ScreeningInput(
                project_id,
                False,
                len(corpus_publications),
                0,
                duplicate_readiness.blocking_groups,
                (),
                ScreeningInputReadinessStatus.UNMERGED_DUPLICATES,
                duplicate_readiness,
            )

        if self._finalizations is not None:
            latest_finalization = self._finalizations.get_latest_finalization(project_id)
            if latest_finalization is not None:
                admitted_ids = self._finalizations.get_admitted_record_ids(project_id)
                active = [p for p in active if p.record_id in admitted_ids]

        ordered = tuple(sorted(active, key=lambda item: item.record_id))
        return ScreeningInput(
            project_id,
            True,
            len(corpus_publications),
            len(ordered),
            0,
            ordered,
            ScreeningInputReadinessStatus.READY,
            duplicate_readiness,
        )

    def get_readiness(
        self,
        project_id: str,
        *,
        groups: list[DuplicateGroup] | None = None,
    ) -> ScreeningInput:
        return self.get_input_set(project_id, groups=groups)
