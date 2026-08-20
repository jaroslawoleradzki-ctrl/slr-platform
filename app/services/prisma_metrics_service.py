from __future__ import annotations

from dataclasses import dataclass

from app.api.dto.prisma import PrismaMetricsResponse
from app.repositories.duplicate_review_decision_repository import (
    DuplicateReviewDecisionRepository,
    default_duplicate_review_decision_repository,
)
from app.repositories.import_history_repository import (
    ImportHistoryRepository,
    default_import_history_repository,
)
from app.repositories.project_publication_repository import (
    ProjectPublicationRepository,
    default_project_publication_repository,
)
from app.services.duplicate_group_builder import (
    DuplicateGroupBuilder,
    duplicate_group_builder,
)
from app.services.project_workflow_status_service import (
    ProjectWorkflowStatusService,
    default_project_workflow_status_service,
)

_SUCCESS_STATUSES = ("success", "warning")


@dataclass(frozen=True, slots=True)
class PrismaMetrics:
    """Read model for authoritative PRISMA funnel metrics.

    Metric semantics (all derived from persisted project state):

    - records_identified_providers: sum of records successfully introduced through
      live/API provider imports (`import_history` where source_type == "provider").
    - records_identified_imports: sum of records successfully introduced through
      manual/imported files (`import_history` where source_type == "file").
    - total_identified: records_identified_providers + records_identified_imports.
    - records_after_normalization: current Working Collection count. Normalization
      is a 1:1 in-place transform, so this is the authoritative post-normalization
      canonical record count.
    - records_before_dedup: records entering the deduplication stage. The
      deduplication stage operates on the current Working Collection.
    - records_after_technical_merger: Working Collection count minus the members
      deterministically merged away by the shared strong-identifier technical merge
      (one canonical record per candidate duplicate group).
    - duplicate_groups_pending_review: candidate duplicate groups without a recorded
      reviewer decision (status PENDING).
    - records_screened_title_abstract: records with a final Title & Abstract
      screening decision (project outcome in multi-reviewer mode, latest reviewer
      decision otherwise).
    - records_screened_full_text: records with a completed Full-Text screening
      decision (project outcome in multi-reviewer mode, latest reviewer decision
      otherwise).
    - studies_included_synthesis: records with a final INCLUDE outcome at the
      Full-Text stage, i.e. the publications eligible for Quality Assessment,
      extraction, and synthesis. This is the closest authoritative persisted state
      for final synthesis inclusion.
    """

    project_id: str
    records_identified_providers: int
    records_identified_imports: int
    total_identified: int
    records_after_normalization: int
    records_before_dedup: int
    records_after_technical_merger: int
    duplicate_groups_pending_review: int
    records_screened_title_abstract: int
    records_screened_full_text: int
    studies_included_synthesis: int


class PrismaMetricsService:
    """Service computing authoritative PRISMA funnel metrics for a project.

    The service is project-scoped and supports partially completed workflows:
    every count is derived independently from persisted state and never blocks
    on later workflow stages being finished.
    """

    def __init__(
        self,
        publication_repository: ProjectPublicationRepository | None = None,
        import_history_repository: ImportHistoryRepository | None = None,
        decision_repository: DuplicateReviewDecisionRepository | None = None,
        workflow_status_service: ProjectWorkflowStatusService | None = None,
        builder: DuplicateGroupBuilder | None = None,
    ) -> None:
        self._publications = publication_repository or default_project_publication_repository()
        self._history = import_history_repository or default_import_history_repository()
        self._decisions = decision_repository or default_duplicate_review_decision_repository()
        self._workflow_status = workflow_status_service or default_project_workflow_status_service()
        self._builder = builder or duplicate_group_builder

    def get_metrics(self, project_id: str, reviewer_id: str = "default_reviewer") -> PrismaMetrics:
        working_count = self._publications.count_by_project(project_id)

        identified_providers = 0
        identified_imports = 0
        for record in self._history.list_for_project(project_id):
            if record.status not in _SUCCESS_STATUSES:
                continue
            if record.source_type == "provider":
                identified_providers += record.records_count
            elif record.source_type == "file":
                identified_imports += record.records_count

        publications = self._publications.get_publications(project_id)
        groups = self._builder.build(publications)
        decisions = self._decisions.list_decisions_for_project(project_id)

        merged_away = sum(len(group.publication_ids) - 1 for group in groups)
        records_after_technical_merger = max(0, working_count - merged_away)
        duplicate_groups_pending_review = sum(
            1 for group in groups if str(group.group_id) not in decisions
        )

        workflow = self._workflow_status.get_status(project_id, reviewer_id=reviewer_id)

        return PrismaMetrics(
            project_id=project_id,
            records_identified_providers=identified_providers,
            records_identified_imports=identified_imports,
            total_identified=identified_providers + identified_imports,
            records_after_normalization=working_count,
            records_before_dedup=working_count,
            records_after_technical_merger=records_after_technical_merger,
            duplicate_groups_pending_review=duplicate_groups_pending_review,
            records_screened_title_abstract=workflow.title_abstract_screening.evaluated_count,
            records_screened_full_text=workflow.full_text_screening.evaluated_count,
            studies_included_synthesis=workflow.quality_assessment.eligible_count,
        )

    def to_response(self, metrics: PrismaMetrics) -> PrismaMetricsResponse:
        return PrismaMetricsResponse(
            project_id=metrics.project_id,
            records_identified_providers=metrics.records_identified_providers,
            records_identified_imports=metrics.records_identified_imports,
            total_identified=metrics.total_identified,
            records_after_normalization=metrics.records_after_normalization,
            records_before_dedup=metrics.records_before_dedup,
            records_after_technical_merger=metrics.records_after_technical_merger,
            duplicate_groups_pending_review=metrics.duplicate_groups_pending_review,
            records_screened_title_abstract=metrics.records_screened_title_abstract,
            records_screened_full_text=metrics.records_screened_full_text,
            studies_included_synthesis=metrics.studies_included_synthesis,
        )


default_prisma_metrics_service = PrismaMetricsService()
