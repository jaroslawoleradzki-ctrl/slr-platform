from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from app.domain.conflict_resolution import (
    ConflictResolution,
    ProjectScreeningOutcome,
    PublicationScreeningStatus,
    ResolvedOutcome,
    compute_decision_set_key,
)
from app.domain.screening import ScreeningDecision, ScreeningOutcome, ScreeningStage
from app.repositories.conflict_resolution_repository import SqliteConflictResolutionRepository
from app.repositories.screening_reporting_repository import (
    ScreeningReportingRepository,
    default_screening_reporting_repository,
)
from app.repositories.screening_reviewer_assignment_repository import (
    SqliteScreeningReviewerAssignmentRepository,
    default_screening_reviewer_assignment_repository,
)
from app.services.screening_input_service import ScreeningInputService


class ScreeningConflictStatus(StrEnum):
    INCOMPLETE = "incomplete"
    AGREEMENT = "agreement"
    CONFLICT = "conflict"
    RESOLVED = "resolved"
    STALE_RESOLUTION = "stale_resolution"


@dataclass(frozen=True, slots=True)
class ReviewerLatestDecision:
    reviewer_id: str
    outcome: ScreeningOutcome
    decision_id: UUID
    decided_at: str


@dataclass(frozen=True, slots=True)
class ScreeningConflictRecord:
    project_id: str
    publication_id: UUID
    publication_title: str | None
    stage: ScreeningStage
    status: ScreeningConflictStatus
    expected_reviewers: tuple[str, ...]
    pending_reviewers: tuple[str, ...]
    latest_decisions: tuple[ReviewerLatestDecision, ...]
    current_decision_set_key: str
    resolution: ConflictResolution | None = None
    source_decisions: tuple[ScreeningDecision, ...] = ()


@dataclass(frozen=True, slots=True)
class ScreeningConflictMetrics:
    incomplete: int
    agreement: int
    conflict: int
    resolved: int
    stale_resolution: int
    agreement_rate: float | None
    resolution_rate: float | None


class MultiReviewerScreeningService:
    def __init__(
        self,
        assignments: SqliteScreeningReviewerAssignmentRepository | None = None,
        reporting: ScreeningReportingRepository | None = None,
        input_service: ScreeningInputService | None = None,
        resolutions: SqliteConflictResolutionRepository | None = None,
    ) -> None:
        self._assignments = assignments or default_screening_reviewer_assignment_repository()
        self._reporting = reporting or default_screening_reporting_repository()
        self._input_service = input_service or ScreeningInputService()
        self._resolutions = resolutions or SqliteConflictResolutionRepository(self._reporting._database_path)

    def roster(self, project_id: str, stage: ScreeningStage, reviewer_ids: list[str] | None = None):
        # Keep roster operations project-scoped even before any reviewer assignment exists.
        self._input_service.get_input_set(project_id)
        if reviewer_ids is not None:
            if any(not item.strip() for item in reviewer_ids):
                raise ValueError("reviewer_id must not be blank")
            return self._assignments.replace_active(project_id, stage, reviewer_ids)
        return self._assignments.list(project_id, stage)

    def conflicts(
        self,
        project_id: str,
        stage: ScreeningStage,
        *,
        status: ScreeningConflictStatus | None = None,
        viewer_reviewer_id: str | None = None,
        reveal_decisions: bool = False,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[ScreeningConflictRecord], int]:
        expected = tuple(item.reviewer_id for item in self._assignments.list(project_id, stage, active_only=True))
        if not expected:
            return [], 0
        input_set = self._input_service.get_input_set(project_id)
        if not input_set.ready:
            return [], 0
        latest = self._latest_all(project_id, stage)
        title_abstract_latest = (
            self._latest_all(project_id, ScreeningStage.TITLE_ABSTRACT) if stage is ScreeningStage.FULL_TEXT else {}
        )
        publications = input_set.publications
        titles = {item.record_id: item.title for item in publications}
        latest_resolutions = self._resolutions.latest_batch(project_id, stage)
        records = []
        for publication_id in titles:
            expected_for_publication = expected
            if stage is ScreeningStage.FULL_TEXT:
                eligible_reviewers = {
                    item.reviewer_id
                    for item in title_abstract_latest.get(publication_id, [])
                    if item.outcome is ScreeningOutcome.INCLUDE
                }
                expected_for_publication = tuple(reviewer for reviewer in expected if reviewer in eligible_reviewers)
                if not expected_for_publication:
                    continue
            decisions = latest.get(publication_id, [])
            by_reviewer = {item.reviewer_id: item for item in decisions if item.reviewer_id in expected_for_publication}
            pending = tuple(reviewer for reviewer in expected_for_publication if reviewer not in by_reviewer)
            outcomes = {item.outcome for item in by_reviewer.values()}
            key = compute_decision_set_key(project_id, publication_id, stage, expected_for_publication, by_reviewer)
            resolution = latest_resolutions.get(publication_id)
            if pending:
                derived = ScreeningConflictStatus.INCOMPLETE
            elif len(outcomes) == 1:
                derived = ScreeningConflictStatus.AGREEMENT
            elif resolution is None:
                derived = ScreeningConflictStatus.CONFLICT
            elif resolution.decision_set_key == key:
                derived = ScreeningConflictStatus.RESOLVED
            else:
                derived = ScreeningConflictStatus.STALE_RESOLUTION
            visible_decisions: list[ScreeningDecision] = (
                list(by_reviewer.values())
                if reveal_decisions or (viewer_reviewer_id is not None and viewer_reviewer_id in by_reviewer)
                else []
            )
            if status is None or status is derived:
                records.append(
                    ScreeningConflictRecord(
                        project_id,
                        publication_id,
                        titles.get(publication_id),
                        stage,
                        derived,
                        expected_for_publication,
                        pending,
                        tuple(
                            ReviewerLatestDecision(
                                item.reviewer_id, item.outcome, item.decision_id, item.decided_at.isoformat()
                            )
                            for item in sorted(visible_decisions, key=lambda value: value.reviewer_id)
                        ),
                        key,
                        resolution,
                        tuple(sorted(by_reviewer.values(), key=lambda value: value.reviewer_id)),
                    )
                )
        records.sort(key=lambda item: str(item.publication_id))
        return records[offset : offset + limit], len(records)

    def metrics(self, project_id: str, stage: ScreeningStage) -> ScreeningConflictMetrics:
        records, _ = self.conflicts(project_id, stage, limit=100000)
        counts = {status: sum(item.status is status for item in records) for status in ScreeningConflictStatus}
        denominator = counts[ScreeningConflictStatus.AGREEMENT] + counts[ScreeningConflictStatus.CONFLICT]
        resolution_denominator = (
            counts[ScreeningConflictStatus.CONFLICT]
            + counts[ScreeningConflictStatus.RESOLVED]
            + counts[ScreeningConflictStatus.STALE_RESOLUTION]
        )
        return ScreeningConflictMetrics(
            incomplete=counts[ScreeningConflictStatus.INCOMPLETE],
            agreement=counts[ScreeningConflictStatus.AGREEMENT],
            conflict=counts[ScreeningConflictStatus.CONFLICT],
            resolved=counts[ScreeningConflictStatus.RESOLVED],
            stale_resolution=counts[ScreeningConflictStatus.STALE_RESOLUTION],
            agreement_rate=counts[ScreeningConflictStatus.AGREEMENT] / denominator if denominator else None,
            resolution_rate=counts[ScreeningConflictStatus.RESOLVED] / resolution_denominator
            if resolution_denominator
            else None,
        )

    def publication_state(
        self, project_id: str, publication_id: UUID, stage: ScreeningStage, *, reveal_decisions: bool = False
    ) -> ScreeningConflictRecord | None:
        records, _ = self.conflicts(project_id, stage, reveal_decisions=reveal_decisions, limit=100000)
        return next((item for item in records if item.publication_id == publication_id), None)

    def project_outcome(self, project_id: str, publication_id: UUID, stage: ScreeningStage) -> ProjectScreeningOutcome:
        record = self.publication_state(project_id, publication_id, stage)
        if record is None:
            latest = self._latest_all(project_id, stage).get(publication_id, [])
            if not latest:
                return ProjectScreeningOutcome(PublicationScreeningStatus.INCOMPLETE, None)
            value = max(latest, key=lambda item: (item.decided_at, str(item.decision_id)))
            return ProjectScreeningOutcome(PublicationScreeningStatus.AGREEMENT, ResolvedOutcome(value.outcome.value))
        status = PublicationScreeningStatus(record.status.value)
        if record.status is ScreeningConflictStatus.AGREEMENT:
            return ProjectScreeningOutcome(status, ResolvedOutcome(record.source_decisions[0].outcome.value))
        if record.status is ScreeningConflictStatus.RESOLVED and record.resolution:
            return ProjectScreeningOutcome(status, record.resolution.resolved_outcome)
        return ProjectScreeningOutcome(status, None)

    def _latest_all(self, project_id: str, stage: ScreeningStage) -> dict[UUID, list[ScreeningDecision]]:
        decisions = self._reporting.latest_decisions_for_stage_all_reviewers(project_id, stage)
        result: dict[UUID, list[ScreeningDecision]] = {}
        for decision in decisions:
            result.setdefault(decision.publication_id, []).append(decision)
        return result
