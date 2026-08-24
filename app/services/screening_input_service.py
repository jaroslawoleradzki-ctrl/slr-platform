from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.domain.duplicate_review import DuplicateDecision
from app.domain.publication import Publication
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


class ScreeningInputService:
    """Derive a non-destructive, project-scoped input set for later screening."""

    def __init__(
        self,
        publication_repository: ProjectPublicationRepository | None = None,
        decision_repository: DuplicateReviewDecisionRepository | None = None,
        builder: DuplicateGroupBuilder | None = None,
        merge_repository: DuplicateMergeRepository | None = None,
    ) -> None:
        self._publications = publication_repository or default_project_publication_repository()
        self._decisions = decision_repository or default_duplicate_review_decision_repository()
        self._builder = builder or DuplicateGroupBuilder()
        self._merges = merge_repository or (
            SqliteDuplicateMergeRepository(self._publications._database_path)
            if hasattr(self._publications, "_database_path")
            else InMemoryDuplicateMergeRepository()
        )

    def get_input_set(self, project_id: str) -> ScreeningInput:
        publications = (
            self._publications.get_all_publications(project_id)
            if hasattr(self._publications, "get_all_publications")
            else self._publications.get_publications(project_id)
        )
        groups = self._builder.build(publications)
        decisions = self._decisions.list_decisions_for_project(project_id)
        unresolved = [group for group in groups if str(group.group_id) not in decisions]
        if unresolved:
            return ScreeningInput(
                project_id,
                False,
                len(publications),
                0,
                len(unresolved),
                (),
                ScreeningInputReadinessStatus.UNRESOLVED_DUPLICATES,
            )

        unmerged = [
            group
            for group in groups
            if decisions[str(group.group_id)].decision is DuplicateDecision.APPROVE
            and self._merges.get_merge(project_id, str(group.group_id)) is None
        ]
        if unmerged:
            return ScreeningInput(
                project_id,
                False,
                len(publications),
                0,
                len(unmerged),
                (),
                ScreeningInputReadinessStatus.UNMERGED_DUPLICATES,
            )
        active = (
            self._publications.get_active_publications(project_id)
            if hasattr(self._publications, "get_active_publications")
            else publications
        )
        ordered = tuple(sorted(active, key=lambda item: item.record_id))
        return ScreeningInput(
            project_id,
            True,
            len(publications),
            len(ordered),
            0,
            ordered,
            ScreeningInputReadinessStatus.READY,
        )

    def get_readiness(self, project_id: str) -> ScreeningInput:
        return self.get_input_set(project_id)
