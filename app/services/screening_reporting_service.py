from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from uuid import UUID

from app.domain.conflict_resolution import ConflictResolution, ResolvedOutcome
from app.domain.screening import (
    CriterionAssessment,
    ScreeningDecision,
    ScreeningOutcome,
    ScreeningStage,
)
from app.repositories.conflict_resolution_repository import SqliteConflictResolutionRepository
from app.repositories.project_publication_repository import (
    ProjectPublicationRepository,
    default_project_publication_repository,
)
from app.repositories.screening_reporting_repository import (
    ScreeningReportingRepository,
    default_screening_reporting_repository,
)
from app.repositories.screening_reviewer_assignment_repository import (
    SqliteScreeningReviewerAssignmentRepository,
)
from app.services.screening_input_service import ScreeningInput, ScreeningInputService


@dataclass(frozen=True, slots=True)
class StageProgress:
    total_eligible: int
    screened: int
    remaining: int
    included: int
    excluded: int
    uncertain: int


@dataclass(frozen=True, slots=True)
class ScreeningTransitions:
    canonical_input: int
    title_abstract_screened: int
    title_abstract_included: int
    full_text_eligible: int
    full_text_screened: int
    full_text_included: int


@dataclass(frozen=True, slots=True)
class ReasonAggregation:
    criterion_id: UUID
    criterion_snapshot_key: str
    snapshot_schema_version: int
    assessment: CriterionAssessment
    snapshot_complete: bool
    count: int


@dataclass(frozen=True, slots=True)
class AuditEvent:
    decision: ScreeningDecision
    publication_title: str | None
    revision_index: int
    previous_outcome: ScreeningOutcome | None
    is_latest_for_reviewer: bool


@dataclass(frozen=True, slots=True)
class AuditResolutionEvent:
    resolution: ConflictResolution
    publication_title: str | None
    is_current: bool
    reviewer_outcomes: tuple[tuple[UUID, str, ResolvedOutcome], ...]


class ScreeningReportingService:
    def __init__(
        self,
        input_service: ScreeningInputService | None = None,
        reporting_repository: ScreeningReportingRepository | None = None,
        publication_repository: ProjectPublicationRepository | None = None,
        resolution_repository: SqliteConflictResolutionRepository | None = None,
    ) -> None:
        self._input = input_service or ScreeningInputService()
        self._reporting = reporting_repository or default_screening_reporting_repository()
        self._publications = publication_repository or default_project_publication_repository()
        self._resolutions = resolution_repository or SqliteConflictResolutionRepository(self._reporting._database_path)

    @staticmethod
    def _reviewer(reviewer_id: str) -> str:
        reviewer = reviewer_id.strip()
        if not reviewer:
            raise ValueError("reviewer_id must not be blank")
        return reviewer

    @staticmethod
    def _progress(publication_ids: set[UUID], latest: dict[UUID, ScreeningDecision]) -> StageProgress:
        outcomes = [latest[publication_id].outcome for publication_id in publication_ids if publication_id in latest]
        included = outcomes.count(ScreeningOutcome.INCLUDE)
        excluded = outcomes.count(ScreeningOutcome.EXCLUDE)
        uncertain = outcomes.count(ScreeningOutcome.UNCERTAIN)
        return StageProgress(
            total_eligible=len(publication_ids),
            screened=len(outcomes),
            remaining=len(publication_ids) - len(outcomes),
            included=included,
            excluded=excluded,
            uncertain=uncertain,
        )

    def report(
        self, project_id: str, reviewer_id: str
    ) -> tuple[
        ScreeningInput,
        StageProgress | None,
        StageProgress | None,
        ScreeningTransitions | None,
        list[ReasonAggregation],
    ]:
        reviewer = self._reviewer(reviewer_id)
        input_set = self._input.get_input_set(project_id)
        if not input_set.ready:
            return input_set, None, None, None, []

        latest = self._reporting.latest_decisions(project_id, reviewer)
        latest_title_abstract = {
            item.publication_id: item for item in latest if item.stage is ScreeningStage.TITLE_ABSTRACT
        }
        latest_full_text = {item.publication_id: item for item in latest if item.stage is ScreeningStage.FULL_TEXT}
        canonical_ids = {item.record_id for item in input_set.publications}
        title_abstract_progress = self._progress(canonical_ids, latest_title_abstract)
        eligible_full_text_ids = {
            publication_id
            for publication_id in canonical_ids
            if latest_title_abstract.get(publication_id)
            and latest_title_abstract[publication_id].outcome is ScreeningOutcome.INCLUDE
        }
        full_text_progress = self._progress(eligible_full_text_ids, latest_full_text)
        transitions = ScreeningTransitions(
            canonical_input=len(canonical_ids),
            title_abstract_screened=title_abstract_progress.screened,
            title_abstract_included=title_abstract_progress.included,
            full_text_eligible=len(eligible_full_text_ids),
            full_text_screened=full_text_progress.screened,
            full_text_included=full_text_progress.included,
        )
        reason_groups: dict[str, tuple[CriterionAssessment, int, int]] = {}
        historical_full_text_exclusions = self._reporting.decisions_for_stage_outcome(
            project_id,
            reviewer,
            ScreeningStage.FULL_TEXT,
            ScreeningOutcome.EXCLUDE,
        )
        for decision in historical_full_text_exclusions:
            assessments = {item.criterion_id: item for item in decision.criterion_assessments}
            for criterion_id in decision.exclusion_reason_criterion_ids:
                assessment = assessments[criterion_id]
                key = self._snapshot_key(decision, assessment)
                previous = reason_groups.get(key)
                reason_groups[key] = (
                    assessment,
                    decision.criterion_snapshot_schema_version,
                    (previous[2] if previous else 0) + 1,
                )
        reason_aggregations = [
            ReasonAggregation(
                criterion_id=value[0].criterion_id,
                criterion_snapshot_key=key,
                snapshot_schema_version=value[1],
                assessment=value[0],
                snapshot_complete=value[1] >= 2,
                count=value[2],
            )
            for key, value in reason_groups.items()
        ]
        return (
            input_set,
            title_abstract_progress,
            full_text_progress,
            transitions,
            sorted(
                reason_aggregations,
                key=lambda item: item.criterion_snapshot_key,
            ),
        )

    @staticmethod
    def _snapshot_key(decision: ScreeningDecision, assessment: CriterionAssessment) -> str:
        snapshot = {
            "criterion_id": str(assessment.criterion_id),
            "criterion_name": assessment.criterion_name,
            "criterion_description": assessment.criterion_description,
            "criterion_type": assessment.criterion_type.value,
            "criterion_stage": assessment.criterion_stage.value,
            "criterion_is_required": assessment.criterion_is_required,
            "evaluation_mode": assessment.evaluation_mode.value,
            "metadata_rule": (assessment.metadata_rule.model_dump(mode="json") if assessment.metadata_rule else None),
            "snapshot_schema_version": decision.criterion_snapshot_schema_version,
        }
        digest = json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(digest).hexdigest()

    def audit(
        self,
        project_id: str,
        *,
        reviewer_id: str | None = None,
        publication_id: UUID | None = None,
        stage: ScreeningStage | None = None,
        outcome: ScreeningOutcome | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[AuditEvent | AuditResolutionEvent], int]:
        if reviewer_id is not None:
            reviewer_id = self._reviewer(reviewer_id)
        # Decisions and resolutions are loaded in batches, merged chronologically,
        # and only then paginated as one audit timeline.
        rows, _ = self._reporting.audit_page(
            project_id,
            reviewer_id=reviewer_id,
            publication_id=publication_id,
            stage=stage,
            outcome=outcome,
            offset=0,
            limit=1_000_000,
        )
        titles = {item.record_id: item.title for item in self._publications.get_publications(project_id)}
        events: list[AuditEvent | AuditResolutionEvent] = [
            AuditEvent(
                decision=row.decision,
                publication_title=titles.get(row.decision.publication_id),
                revision_index=row.revision_index,
                previous_outcome=row.previous_outcome,
                is_latest_for_reviewer=row.is_latest_for_reviewer,
            )
            for row in rows
        ]
        resolutions = self._resolutions.audit_events(project_id, stage)
        if publication_id is not None:
            resolutions = [item for item in resolutions if item.publication_id == publication_id]
        # Reviewer filtering remains decision-specific; project resolution events
        # stay visible in the unified trail. Outcome filtering applies to both types.
        if outcome is not None:
            resolutions = [
                item for item in resolutions if item.resolved_outcome.value == outcome.value
            ]

        from app.services.multi_reviewer_screening_service import MultiReviewerScreeningService

        multi = MultiReviewerScreeningService(
            assignments=SqliteScreeningReviewerAssignmentRepository(self._reporting._database_path),
            reporting=self._reporting,
            input_service=self._input,
            resolutions=self._resolutions,
        )
        stages = [stage] if stage else [ScreeningStage.TITLE_ABSTRACT, ScreeningStage.FULL_TEXT]
        current_ids: set[UUID] = set()
        for current_stage in stages:
            records, _ = multi.conflicts(project_id, current_stage, limit=1_000_000)
            current_ids.update(
                record.resolution.resolution_id
                for record in records
                if record.resolution is not None and record.status.value == "resolved"
            )
        links = self._resolutions.links_batch([item.resolution_id for item in resolutions])
        events.extend(
            AuditResolutionEvent(
                item,
                titles.get(item.publication_id),
                item.resolution_id in current_ids,
                links.get(item.resolution_id, ()),
            )
            for item in resolutions
        )
        events.sort(
            key=lambda value: (
                value.resolution.resolved_at if isinstance(value, AuditResolutionEvent) else value.decision.decided_at,
                str(
                    value.resolution.resolution_id
                    if isinstance(value, AuditResolutionEvent)
                    else value.decision.decision_id
                ),
            ),
            reverse=True,
        )
        return events[offset : offset + limit], len(events)
