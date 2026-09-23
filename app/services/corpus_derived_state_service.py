"""Rebuild of Normalization/Deduplication derived state from the Active Corpus (WP2).

A project previously normalized or deduplicated over the unfiltered
``project_publications`` population carries stale derived state: inflated
normalization execution counts and duplicate groups/merges/decisions involving
pre-screening removed records. This module provides the single
application-level operation that restores the WP2 invariant::

    derived active state = function(Active Corpus)

with no removed publication participating in any derived artifact.

The rebuild never creates formal screening decisions and never mutates
finalization records. Rebuilding a finalized corpus is refused unless the
caller explicitly opts in with ``allow_finalized=True``.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.repositories.corpus_finalization_repository import (
    CorpusFinalizationRepository,
    SqliteCorpusFinalizationRepository,
)
from app.repositories.normalization_execution_repository import (
    NormalizationExecutionRepository,
    default_normalization_execution_repository,
)
from app.repositories.project_publication_repository import (
    ProjectPublicationRepository,
    default_project_publication_repository,
)
from app.services.normalization_service import normalize_project
from app.services.pre_screening_review_service import CorpusFinalizedError
from app.services.project_duplicate_service import ProjectDuplicateService


@dataclass(frozen=True, slots=True)
class CorpusDerivedStateRebuildReport:
    """Outcome of rebuilding derived Normalization/Deduplication state."""

    project_id: str
    normalization_processed_records: int
    normalization_clean_records: int
    active_duplicate_groups_count: int
    removed_merge_group_ids: tuple[str, ...] = ()
    removed_decision_group_ids: tuple[str, ...] = ()

    @property
    def removed_merges_count(self) -> int:
        return len(self.removed_merge_group_ids)

    @property
    def removed_decisions_count(self) -> int:
        return len(self.removed_decision_group_ids)


class CorpusDerivedStateService:
    """Rebuild derived pipeline state exclusively from the Active Corpus."""

    def __init__(
        self,
        publication_repository: ProjectPublicationRepository | None = None,
        normalization_execution_repository: NormalizationExecutionRepository | None = None,
        duplicate_service: ProjectDuplicateService | None = None,
        finalization_repository: CorpusFinalizationRepository | None = None,
    ) -> None:
        self._publications = publication_repository or default_project_publication_repository()
        self._executions = normalization_execution_repository or default_normalization_execution_repository()
        self._duplicates = duplicate_service or ProjectDuplicateService()
        if finalization_repository is not None:
            self._finalizations: CorpusFinalizationRepository | None = finalization_repository
        elif hasattr(self._publications, "_database_path"):
            self._finalizations = SqliteCorpusFinalizationRepository(self._publications._database_path)  # type: ignore[attr-defined]
        else:
            self._finalizations = None

    def rebuild(self, project_id: str, *, allow_finalized: bool = False) -> CorpusDerivedStateRebuildReport:
        """Rebuild Normalization + Deduplication state from the Active Corpus.

        Steps: normalize the Active Corpus (persisting a fresh execution
        summary whose counts describe records actually processed), then
        reconcile stale duplicate merges/decisions referencing removed
        records. Raises :class:`CorpusFinalizedError` when the project corpus
        is already finalized unless ``allow_finalized`` is set.
        """
        if not allow_finalized and self._finalizations is not None:
            finalization = self._finalizations.get_latest_finalization(project_id)
            if finalization is not None:
                raise CorpusFinalizedError(
                    f"Corpus for project '{project_id}' is finalized; "
                    "derived-state rebuild is locked."
                )

        execution = normalize_project(self._publications, project_id)
        self._executions.save(execution)

        reconciliation = self._duplicates.reconcile_with_active_corpus(project_id)
        live_groups = self._duplicates.get_candidate_duplicate_groups(project_id)

        return CorpusDerivedStateRebuildReport(
            project_id=project_id,
            normalization_processed_records=execution.processed_records,
            normalization_clean_records=execution.clean_records,
            active_duplicate_groups_count=live_groups.total_groups_count,
            removed_merge_group_ids=reconciliation.removed_merge_group_ids,
            removed_decision_group_ids=reconciliation.removed_decision_group_ids,
        )


def default_corpus_derived_state_service() -> CorpusDerivedStateService:
    return CorpusDerivedStateService()
