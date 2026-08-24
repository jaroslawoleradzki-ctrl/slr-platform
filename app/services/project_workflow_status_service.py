from __future__ import annotations

from app.api.dto.workflow_status import (
    FullTextScreeningStatusDTO,
    ProjectWorkflowStatusResponse,
    QualityAssessmentStatusDTO,
    TitleAbstractScreeningStatusDTO,
)
from app.domain.screening import ScreeningStage
from app.repositories.conflict_resolution_repository import (
    SqliteConflictResolutionRepository,
    default_conflict_resolution_repository,
)
from app.repositories.project_publication_repository import (
    ProjectPublicationRepository,
    default_project_publication_repository,
)
from app.repositories.screening_decision_repository import (
    ScreeningDecisionRepository,
    default_screening_decision_repository,
)
from app.repositories.screening_reporting_repository import (
    ScreeningReportingRepository,
    default_screening_reporting_repository,
)
from app.repositories.screening_reviewer_assignment_repository import (
    SqliteScreeningReviewerAssignmentRepository,
    default_screening_reviewer_assignment_repository,
)
from app.services.multi_reviewer_screening_service import MultiReviewerScreeningService
from app.services.screening_eligibility_adapter import ScreeningEligibilityAdapter
from app.services.screening_input_service import ScreeningInputService


class ProjectWorkflowStatusService:
    """Service building unified status read model for SLR project workflow stages."""

    def __init__(
        self,
        publication_repository: ProjectPublicationRepository | None = None,
        decision_repository: ScreeningDecisionRepository | None = None,
        assignment_repository: SqliteScreeningReviewerAssignmentRepository | None = None,
        resolution_repository: SqliteConflictResolutionRepository | None = None,
        reporting_repository: ScreeningReportingRepository | None = None,
        input_service: ScreeningInputService | None = None,
        multi_reviewer_service: MultiReviewerScreeningService | None = None,
        eligibility_adapter: ScreeningEligibilityAdapter | None = None,
    ) -> None:
        self._pub_repo = publication_repository or default_project_publication_repository()
        self._decision_repo = decision_repository or default_screening_decision_repository()
        self._assignment_repo = assignment_repository or default_screening_reviewer_assignment_repository()
        self._resolution_repo = resolution_repository or default_conflict_resolution_repository()
        self._reporting_repo = reporting_repository or default_screening_reporting_repository()
        self._input_service = input_service or ScreeningInputService(publication_repository=self._pub_repo)
        self._multi_service = multi_reviewer_service or MultiReviewerScreeningService(
            assignments=self._assignment_repo,
            reporting=self._reporting_repo,
            resolutions=self._resolution_repo,
            input_service=self._input_service,
        )
        self._adapter = eligibility_adapter or ScreeningEligibilityAdapter(
            input_service=self._input_service,
            assignments_repo=self._assignment_repo,
            decisions_repo=self._decision_repo,
            multi_reviewer_service=self._multi_service,
        )

    def get_status(
        self, project_id: str, reviewer_id: str = "default_reviewer"
    ) -> ProjectWorkflowStatusResponse:
        input_set = self._input_service.get_input_set(project_id)
        total_ta = len(input_set.publications)
        active_publication_ids = {publication.record_id for publication in input_set.publications}

        # ── 1. Title & Abstract Stage Status ────────────────────────────────────
        ta_has_roster = self._adapter.has_active_roster(project_id, ScreeningStage.TITLE_ABSTRACT)
        ta_evaluated_count = 0
        ta_conflict_count = 0
        ta_resolved_count = 0
        ta_stale_count = 0

        if ta_has_roster:
            records, _ = self._multi_service.conflicts(
                project_id, ScreeningStage.TITLE_ABSTRACT, limit=100000
            )
            for r in records:
                if r.publication_id not in active_publication_ids:
                    continue
                if r.status.value in ("agreement", "resolved"):
                    ta_evaluated_count += 1
                elif r.status.value == "conflict":
                    ta_conflict_count += 1
                elif r.status.value == "stale_resolution":
                    ta_stale_count += 1

                if r.status.value == "resolved":
                    ta_resolved_count += 1
        else:
            decisions = [
                d
                for d in self._reporting_repo.latest_decisions(project_id, reviewer_id)
                if d.stage == ScreeningStage.TITLE_ABSTRACT and d.publication_id in active_publication_ids
            ]
            ta_evaluated_count = len(decisions)

        if ta_stale_count > 0:
            ta_status = "stale_resolution"
        elif ta_conflict_count > 0:
            ta_status = "unresolved_conflict"
        elif ta_evaluated_count == 0:
            ta_status = "not_started"
        elif ta_evaluated_count < total_ta:
            ta_status = "in_progress"
        else:
            ta_status = "completed"

        # ── 2. Full-Text Stage Status ──────────────────────────────────────────
        ft_eligible_pubs = self._adapter.eligible_publications(
            project_id, ScreeningStage.TITLE_ABSTRACT, ScreeningStage.FULL_TEXT, reviewer_id
        )
        ft_eligible_count = len(ft_eligible_pubs)

        ft_has_roster = self._adapter.has_active_roster(project_id, ScreeningStage.FULL_TEXT)
        ft_evaluated_count = 0
        ft_conflict_count = 0
        ft_resolved_count = 0
        ft_stale_count = 0

        if ft_has_roster:
            records, _ = self._multi_service.conflicts(
                project_id, ScreeningStage.FULL_TEXT, limit=100000
            )
            for r in records:
                if r.publication_id not in active_publication_ids:
                    continue
                if r.status.value in ("agreement", "resolved"):
                    ft_evaluated_count += 1
                elif r.status.value == "conflict":
                    ft_conflict_count += 1
                elif r.status.value == "stale_resolution":
                    ft_stale_count += 1

                if r.status.value == "resolved":
                    ft_resolved_count += 1
        else:
            decisions = [
                d
                for d in self._reporting_repo.latest_decisions(project_id, reviewer_id)
                if d.stage == ScreeningStage.FULL_TEXT and d.publication_id in active_publication_ids
            ]
            ft_evaluated_count = len(decisions)

        if ta_status in ("unresolved_conflict", "stale_resolution"):
            ft_status = ta_status
        elif ta_status != "completed" and ft_eligible_count == 0:
            ft_status = "waiting_for_title_abstract"
        elif ft_stale_count > 0:
            ft_status = "stale_resolution"
        elif ft_conflict_count > 0:
            ft_status = "unresolved_conflict"
        elif ft_evaluated_count == 0:
            ft_status = "ready"
        elif ft_evaluated_count < ft_eligible_count:
            ft_status = "in_progress"
        else:
            ft_status = "completed"

        # ── 3. Quality Assessment Status ───────────────────────────────────────
        qa_eligible_pubs = self._adapter.eligible_publications(
            project_id, ScreeningStage.FULL_TEXT, "quality_assessment", reviewer_id
        )
        qa_eligible_count = len(qa_eligible_pubs)

        if ft_status != "completed":
            qa_status = "waiting_for_full_text"
        else:
            qa_status = "ready"

        return ProjectWorkflowStatusResponse(
            project_id=project_id,
            title_abstract_screening=TitleAbstractScreeningStatusDTO(
                status=ta_status,
                evaluated_count=ta_evaluated_count,
                total_count=total_ta,
                conflict_count=ta_conflict_count,
                resolved_count=ta_resolved_count,
            ),
            full_text_screening=FullTextScreeningStatusDTO(
                status=ft_status,
                eligible_count=ft_eligible_count,
                evaluated_count=ft_evaluated_count,
                conflict_count=ft_conflict_count,
                resolved_count=ft_resolved_count,
            ),
            quality_assessment=QualityAssessmentStatusDTO(
                status=qa_status,
                eligible_count=qa_eligible_count,
            ),
        )


def default_project_workflow_status_service() -> ProjectWorkflowStatusService:
    return ProjectWorkflowStatusService()
