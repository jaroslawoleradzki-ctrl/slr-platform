from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from app.domain.conflict_resolution import ProjectScreeningOutcome, PublicationScreeningStatus, ResolvedOutcome
from app.domain.screening import ScreeningDecision, ScreeningOutcome, ScreeningStage
from app.repositories.screening_decision_repository import (
    ScreeningDecisionRepository,
    default_screening_decision_repository,
)
from app.repositories.screening_reviewer_assignment_repository import (
    SqliteScreeningReviewerAssignmentRepository,
    default_screening_reviewer_assignment_repository,
)
from app.services.multi_reviewer_screening_service import MultiReviewerScreeningService, ScreeningConflictStatus
from app.services.screening_input_service import ScreeningInputReadinessStatus, ScreeningInputService


class StageReadinessStatus(StrEnum):
    READY = "ready"
    INPUT_NOT_READY = "input_not_ready"
    UNRESOLVED_DUPLICATES = "unresolved_duplicates"
    MERGE_CONFLICT = "merge_conflict"
    WAITING_FOR_PREVIOUS_STAGE = "waiting_for_previous_stage"
    UNRESOLVED_CONFLICT = "unresolved_conflict"
    STALE_RESOLUTION = "stale_resolution"
    NO_ELIGIBLE_PUBLICATIONS = "no_eligible_publications"


@dataclass(frozen=True, slots=True)
class ScreeningStageReadiness:
    status: StageReadinessStatus
    eligible_count: int
    total_count: int

    @property
    def ready(self) -> bool:
        return self.status is StageReadinessStatus.READY


class ScreeningEligibilityAdapter:
    """Unified single-reviewer and multi-reviewer stage transition & eligibility adapter.

    Enforces project-level outcomes when an active roster exists, and falls back to
    reviewer-specific append-only decision history when no roster is configured.
    """

    def __init__(
        self,
        input_service: ScreeningInputService | None = None,
        assignments_repo: SqliteScreeningReviewerAssignmentRepository | None = None,
        decisions_repo: ScreeningDecisionRepository | None = None,
        multi_reviewer_service: MultiReviewerScreeningService | None = None,
    ) -> None:
        self._input_service = input_service or ScreeningInputService()
        self._assignments_repo = assignments_repo or default_screening_reviewer_assignment_repository()
        self._decisions_repo = decisions_repo or default_screening_decision_repository()
        self._multi_reviewer = multi_reviewer_service or MultiReviewerScreeningService(
            assignments=self._assignments_repo,
            input_service=self._input_service,
        )

    def has_active_roster(self, project_id: str, stage: ScreeningStage) -> bool:
        """Returns True if project has active reviewer assignments for stage."""
        return len(self._assignments_repo.list(project_id, stage, active_only=True)) > 0

    def get_outcome(
        self,
        project_id: str,
        publication_id: UUID,
        stage: ScreeningStage,
        reviewer_id: str,
    ) -> ProjectScreeningOutcome:
        """Evaluates outcome for publication at stage.

        If active roster exists for stage, returns multi-reviewer project outcome.
        If no active roster exists, returns reviewer-specific outcome for reviewer_id.
        """
        if self.has_active_roster(project_id, stage):
            return self._multi_reviewer.project_outcome(project_id, publication_id, stage)

        # Single-reviewer fallback: find latest decision for reviewer_id at stage
        decisions = self._decisions_repo.list_by_project(project_id, stage)
        reviewer_decisions = [d for d in decisions if d.reviewer_id == reviewer_id and d.publication_id == publication_id]
        if not reviewer_decisions:
            return ProjectScreeningOutcome(PublicationScreeningStatus.INCOMPLETE, None)

        latest = max(reviewer_decisions, key=lambda d: (d.decided_at, str(d.decision_id)))
        return ProjectScreeningOutcome(
            PublicationScreeningStatus.AGREEMENT,
            ResolvedOutcome(latest.outcome.value),
        )

    def eligible_publications(
        self,
        project_id: str,
        source_stage: ScreeningStage,
        target_stage: ScreeningStage | str,
        reviewer_id: str,
    ) -> tuple[UUID, ...]:
        """Returns list of publication UUIDs eligible for target_stage.

        For target_stage == FULL_TEXT (source == TITLE_ABSTRACT):
          - Multi-reviewer (active T&A roster): publications where ProjectOutcome(T&A) == INCLUDE.
          - Single-reviewer (no T&A roster): publications where reviewer's latest T&A decision == INCLUDE.

        For target_stage == QUALITY_ASSESSMENT (source == FULL_TEXT):
          - Multi-reviewer (active FT roster): publications where ProjectOutcome(FT) == INCLUDE.
          - Single-reviewer (no FT roster): publications where reviewer's latest FT decision == INCLUDE.
        """
        input_set = self._input_service.get_input_set(project_id)
        if not input_set.ready:
            return ()

        publications = input_set.publications
        eligible: list[UUID] = []

        if self.has_active_roster(project_id, source_stage):
            # Multi-reviewer mode: check project-level outcome for source_stage
            for pub in publications:
                outcome = self._multi_reviewer.project_outcome(project_id, pub.record_id, source_stage)
                if outcome.is_final and outcome.outcome is ResolvedOutcome.INCLUDE:
                    eligible.append(pub.record_id)
        else:
            # Single-reviewer mode: check reviewer_id's latest decision for source_stage
            source_decisions = self._decisions_repo.list_by_project(project_id, source_stage)
            latest_by_pub: dict[UUID, ScreeningDecision] = {}
            for d in source_decisions:
                if d.reviewer_id == reviewer_id:
                    latest_by_pub.setdefault(d.publication_id, d)

            for pub in publications:
                latest = latest_by_pub.get(pub.record_id)
                if latest and latest.outcome is ScreeningOutcome.INCLUDE:
                    eligible.append(pub.record_id)

        return tuple(eligible)

    def excluded_publications(
        self,
        project_id: str,
        stage: ScreeningStage,
        reviewer_id: str,
    ) -> tuple[UUID, ...]:
        """Returns list of active canonical publication UUIDs with a final EXCLUDE outcome at stage.

        For stage == TITLE_ABSTRACT:
          - Multi-reviewer (active T&A roster): publications where ProjectOutcome(T&A) == EXCLUDE.
          - Single-reviewer (no T&A roster): publications where reviewer's latest T&A decision == EXCLUDE.

        For stage == FULL_TEXT:
          - Multi-reviewer (active FT roster): publications where ProjectOutcome(FT) == EXCLUDE.
          - Single-reviewer (no FT roster): publications where reviewer's latest FT decision == EXCLUDE.
        """
        input_set = self._input_service.get_input_set(project_id)
        if not input_set.ready:
            return ()

        publications = input_set.publications
        excluded: list[UUID] = []

        if self.has_active_roster(project_id, stage):
            for pub in publications:
                outcome = self._multi_reviewer.project_outcome(project_id, pub.record_id, stage)
                if outcome.is_final and outcome.outcome is ResolvedOutcome.EXCLUDE:
                    excluded.append(pub.record_id)
        else:
            source_decisions = self._decisions_repo.list_by_project(project_id, stage)
            latest_by_pub: dict[UUID, ScreeningDecision] = {}
            for d in source_decisions:
                if d.reviewer_id == reviewer_id:
                    latest_by_pub.setdefault(d.publication_id, d)

            for pub in publications:
                latest = latest_by_pub.get(pub.record_id)
                if latest and latest.outcome is ScreeningOutcome.EXCLUDE:
                    excluded.append(pub.record_id)

        return tuple(excluded)

    def stage_readiness(
        self,
        project_id: str,
        stage: ScreeningStage,
        reviewer_id: str,
    ) -> ScreeningStageReadiness:
        """Returns readiness status and eligible count for stage."""
        input_set = self._input_service.get_input_set(project_id)
        if not input_set.ready:
            if input_set.readiness_status is ScreeningInputReadinessStatus.UNRESOLVED_DUPLICATES:
                return ScreeningStageReadiness(StageReadinessStatus.UNRESOLVED_DUPLICATES, 0, 0)
            return ScreeningStageReadiness(StageReadinessStatus.MERGE_CONFLICT, 0, 0)

        total_input_count = len(input_set.publications)

        if stage is ScreeningStage.TITLE_ABSTRACT:
            if self.has_active_roster(project_id, ScreeningStage.TITLE_ABSTRACT):
                records, _ = self._multi_reviewer.conflicts(project_id, ScreeningStage.TITLE_ABSTRACT, limit=100000)
                conflicts = [r for r in records if r.status is ScreeningConflictStatus.CONFLICT]
                stale = [r for r in records if r.status is ScreeningConflictStatus.STALE_RESOLUTION]
                if conflicts:
                    return ScreeningStageReadiness(StageReadinessStatus.UNRESOLVED_CONFLICT, 0, total_input_count)
                if stale:
                    return ScreeningStageReadiness(StageReadinessStatus.STALE_RESOLUTION, 0, total_input_count)

            return ScreeningStageReadiness(StageReadinessStatus.READY, total_input_count, total_input_count)

        if stage is ScreeningStage.FULL_TEXT:
            if self.has_active_roster(project_id, ScreeningStage.TITLE_ABSTRACT):
                records, _ = self._multi_reviewer.conflicts(project_id, ScreeningStage.TITLE_ABSTRACT, limit=100000)
                if any(r.status is ScreeningConflictStatus.CONFLICT for r in records):
                    return ScreeningStageReadiness(StageReadinessStatus.UNRESOLVED_CONFLICT, 0, total_input_count)
                if any(r.status is ScreeningConflictStatus.STALE_RESOLUTION for r in records):
                    return ScreeningStageReadiness(StageReadinessStatus.STALE_RESOLUTION, 0, total_input_count)

            eligible = self.eligible_publications(
                project_id=project_id,
                source_stage=ScreeningStage.TITLE_ABSTRACT,
                target_stage=ScreeningStage.FULL_TEXT,
                reviewer_id=reviewer_id,
            )

            if not eligible:
                ta_decisions = self._decisions_repo.list_by_project(project_id, ScreeningStage.TITLE_ABSTRACT)
                if not ta_decisions:
                    return ScreeningStageReadiness(StageReadinessStatus.WAITING_FOR_PREVIOUS_STAGE, 0, total_input_count)
                return ScreeningStageReadiness(StageReadinessStatus.NO_ELIGIBLE_PUBLICATIONS, 0, total_input_count)

            return ScreeningStageReadiness(StageReadinessStatus.READY, len(eligible), total_input_count)

        return ScreeningStageReadiness(StageReadinessStatus.READY, total_input_count, total_input_count)
