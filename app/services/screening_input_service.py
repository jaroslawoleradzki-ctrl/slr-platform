from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from functools import reduce
from uuid import UUID

from app.domain.duplicate_review import DuplicateDecision
from app.domain.publication import Publication
from app.repositories.duplicate_review_decision_repository import (
    DuplicateReviewDecisionRepository,
    default_duplicate_review_decision_repository,
)
from app.repositories.project_publication_repository import (
    ProjectPublicationRepository,
    default_project_publication_repository,
)
from app.services.duplicate_group_builder import DuplicateGroupBuilder
from app.services.publication_merge_policy import (
    PublicationMergeConflict,
    PublicationMergePolicy,
)


class ScreeningInputReadinessStatus(StrEnum):
    READY = "ready"
    UNRESOLVED_DUPLICATES = "unresolved_duplicates"
    MERGE_CONFLICT = "merge_conflict"


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
        merge_policy: PublicationMergePolicy | None = None,
    ) -> None:
        self._publications = publication_repository or default_project_publication_repository()
        self._decisions = decision_repository or default_duplicate_review_decision_repository()
        self._builder = builder or DuplicateGroupBuilder()
        self._merge_policy = merge_policy or PublicationMergePolicy()

    def get_input_set(self, project_id: str) -> ScreeningInput:
        publications = self._publications.get_publications(project_id)
        by_id = {publication.record_id: publication for publication in publications}
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

        grouped_ids: set[UUID] = set()
        canonical: list[Publication] = []
        for group in groups:
            members = [by_id[member_id] for member_id in group.publication_ids]
            overlap = grouped_ids.intersection(group.publication_ids)
            if overlap:
                raise ValueError("duplicate groups overlap")
            grouped_ids.update(group.publication_ids)
            decision = decisions[str(group.group_id)].decision
            if decision is DuplicateDecision.APPROVE:
                try:
                    canonical.append(reduce(self._merge_policy.merge, members))
                except PublicationMergeConflict:
                    return ScreeningInput(
                        project_id,
                        False,
                        len(publications),
                        0,
                        0,
                        (),
                        ScreeningInputReadinessStatus.MERGE_CONFLICT,
                    )
            else:
                canonical.extend(members)

        canonical.extend(publication for publication in publications if publication.record_id not in grouped_ids)
        ordered = tuple(sorted(canonical, key=lambda item: item.record_id))
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
