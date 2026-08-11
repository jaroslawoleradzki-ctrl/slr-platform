from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from app.domain.full_text_screening import FullTextAvailability, FullTextAvailabilityStatus
from app.domain.publication import Publication
from app.domain.screening import (
    CriterionAssessmentValue,
    ScreeningCriterion,
    ScreeningCriterionEvaluationMode,
    ScreeningCriterionStage,
    ScreeningCriterionType,
    ScreeningDecision,
    ScreeningOutcome,
    ScreeningStage,
)
from app.repositories.full_text_availability_repository import (
    FullTextAvailabilityRepository,
    default_full_text_availability_repository,
)
from app.repositories.screening_criterion_repository import (
    ScreeningCriterionRepository,
    default_screening_criterion_repository,
)
from app.repositories.screening_decision_repository import (
    ScreeningDecisionRepository,
    default_screening_decision_repository,
)
from app.services.screening_criterion_rule_evaluator import ScreeningCriterionRuleEvaluator
from app.services.screening_decision_service import CriterionAssessmentInput, ScreeningDecisionService
from app.services.screening_input_service import (
    ScreeningInput,
    ScreeningInputReadinessStatus,
    ScreeningInputService,
)


class FullTextReadinessStatus(StrEnum):
    READY = "ready"
    UNRESOLVED_DUPLICATES = "unresolved_duplicates"
    MERGE_CONFLICT = "merge_conflict"
    WAITING_FOR_TITLE_ABSTRACT = "waiting_for_title_abstract"
    NO_ELIGIBLE_PUBLICATIONS = "no_eligible_publications"


class FullTextScreeningStatus(StrEnum):
    UNSCREENED = "unscreened"
    INCLUDED = "included"
    EXCLUDED = "excluded"
    UNCERTAIN = "uncertain"


class FullTextWorkflowNotReadyError(RuntimeError):
    def __init__(self, readiness_status: FullTextReadinessStatus) -> None:
        self.readiness_status = readiness_status
        super().__init__(f"full-text screening workflow is not ready: {readiness_status.value}")


class FullTextPublicationNotEligibleError(LookupError):
    pass


@dataclass(frozen=True, slots=True)
class FullTextReadiness:
    status: FullTextReadinessStatus
    eligible_count: int

    @property
    def ready(self) -> bool:
        return self.status is FullTextReadinessStatus.READY


@dataclass(frozen=True, slots=True)
class AutomaticCriterionAssessment:
    criterion_id: UUID
    assessment_value: CriterionAssessmentValue
    evaluated_metadata_value: object | None


@dataclass(frozen=True, slots=True)
class FullTextRecord:
    publication: Publication
    status: FullTextScreeningStatus
    latest_decision: ScreeningDecision | None
    availability: FullTextAvailability
    automatic_assessments: tuple[AutomaticCriterionAssessment, ...]


@dataclass(frozen=True, slots=True)
class FullTextProgress:
    total: int
    unscreened: int
    included: int
    excluded: int
    uncertain: int

    @property
    def completed(self) -> int:
        return self.included + self.excluded + self.uncertain


@dataclass(frozen=True, slots=True)
class FullTextOverview:
    project_id: str
    reviewer_id: str
    screening_input: ScreeningInput
    readiness: FullTextReadiness
    criteria: tuple[ScreeningCriterion, ...]
    progress: FullTextProgress | None


@dataclass(frozen=True, slots=True)
class FullTextRecordPage:
    project_id: str
    reviewer_id: str
    status_filter: FullTextScreeningStatus | None
    total: int
    offset: int
    limit: int
    items: tuple[FullTextRecord, ...]


_OUTCOME_STATUS = {
    ScreeningOutcome.INCLUDE: FullTextScreeningStatus.INCLUDED,
    ScreeningOutcome.EXCLUDE: FullTextScreeningStatus.EXCLUDED,
    ScreeningOutcome.UNCERTAIN: FullTextScreeningStatus.UNCERTAIN,
}


class FullTextScreeningService:
    """Derived reviewer-scoped Full Text workflow over immutable decision history."""

    def __init__(
        self,
        input_service: ScreeningInputService | None = None,
        criterion_repository: ScreeningCriterionRepository | None = None,
        decision_repository: ScreeningDecisionRepository | None = None,
        decision_service: ScreeningDecisionService | None = None,
        availability_repository: FullTextAvailabilityRepository | None = None,
        rule_evaluator: ScreeningCriterionRuleEvaluator | None = None,
    ) -> None:
        self._input = input_service or ScreeningInputService()
        self._criteria = criterion_repository or default_screening_criterion_repository()
        self._decisions = decision_repository or default_screening_decision_repository()
        self._decision_service = decision_service or ScreeningDecisionService()
        self._availability = availability_repository or default_full_text_availability_repository()
        self._rule_evaluator = rule_evaluator or ScreeningCriterionRuleEvaluator()

    @staticmethod
    def _reviewer_id(reviewer_id: str) -> str:
        reviewer = reviewer_id.strip()
        if not reviewer:
            raise ValueError("reviewer_id must not be blank")
        return reviewer

    def _latest_by_publication(
        self, project_id: str, reviewer_id: str, stage: ScreeningStage
    ) -> dict[UUID, ScreeningDecision]:
        latest: dict[UUID, ScreeningDecision] = {}
        for decision in self._decisions.list_by_project(project_id, stage):
            if decision.reviewer_id == reviewer_id:
                latest.setdefault(decision.publication_id, decision)
        return latest

    @staticmethod
    def _input_blocking_status(screening_input: ScreeningInput) -> FullTextReadinessStatus | None:
        if screening_input.ready:
            return None
        if screening_input.readiness_status is ScreeningInputReadinessStatus.UNRESOLVED_DUPLICATES:
            return FullTextReadinessStatus.UNRESOLVED_DUPLICATES
        return FullTextReadinessStatus.MERGE_CONFLICT

    @staticmethod
    def _status(decision: ScreeningDecision | None) -> FullTextScreeningStatus:
        return FullTextScreeningStatus.UNSCREENED if decision is None else _OUTCOME_STATUS[decision.outcome]

    def _active_criteria(self, project_id: str) -> tuple[ScreeningCriterion, ...]:
        return tuple(
            criterion
            for criterion in self._criteria.list_by_project(project_id, active_only=True)
            if criterion.screening_stage in (ScreeningCriterionStage.FULL_TEXT, ScreeningCriterionStage.BOTH)
        )

    def _eligible_publications(
        self,
        screening_input: ScreeningInput,
        title_abstract_latest: dict[UUID, ScreeningDecision],
    ) -> tuple[Publication, ...]:
        return tuple(
            publication
            for publication in screening_input.publications
            if title_abstract_latest.get(publication.record_id) is not None
            and title_abstract_latest[publication.record_id].outcome is ScreeningOutcome.INCLUDE
        )

    def _readiness(
        self,
        screening_input: ScreeningInput,
        eligible_publications: tuple[Publication, ...],
        title_abstract_latest: dict[UUID, ScreeningDecision],
    ) -> FullTextReadiness:
        blocking = self._input_blocking_status(screening_input)
        if blocking is not None:
            return FullTextReadiness(blocking, 0)
        if eligible_publications:
            return FullTextReadiness(FullTextReadinessStatus.READY, len(eligible_publications))
        has_nonfinal_or_uncertain = any(
            title_abstract_latest.get(publication.record_id) is None
            or title_abstract_latest[publication.record_id].outcome is ScreeningOutcome.UNCERTAIN
            for publication in screening_input.publications
        )
        return FullTextReadiness(
            FullTextReadinessStatus.WAITING_FOR_TITLE_ABSTRACT
            if has_nonfinal_or_uncertain
            else FullTextReadinessStatus.NO_ELIGIBLE_PUBLICATIONS,
            0,
        )

    def _records(
        self,
        publications: tuple[Publication, ...],
        latest: dict[UUID, ScreeningDecision],
        criteria: tuple[ScreeningCriterion, ...],
        project_id: str,
    ) -> tuple[FullTextRecord, ...]:
        availability_by_publication = {
            item.publication_id: item for item in self._availability.list_by_project(project_id)
        }
        records: list[FullTextRecord] = []
        for publication in publications:
            availability = availability_by_publication.get(publication.record_id) or FullTextAvailability(
                project_id=project_id, publication_id=publication.record_id
            )
            automatic_assessments = tuple(
                AutomaticCriterionAssessment(
                    criterion.criterion_id,
                    evaluation.assessment_value,
                    evaluation.evaluated_metadata_value,
                )
                for criterion in criteria
                if criterion.evaluation_mode is ScreeningCriterionEvaluationMode.METADATA_RULE
                for evaluation in [self._rule_evaluator.evaluate(criterion, publication)]
            )
            records.append(
                FullTextRecord(
                    publication,
                    self._status(latest.get(publication.record_id)),
                    latest.get(publication.record_id),
                    availability,
                    automatic_assessments,
                )
            )
        return tuple(records)

    def _current(
        self, project_id: str, reviewer_id: str
    ) -> tuple[ScreeningInput, tuple[Publication, ...], dict[UUID, ScreeningDecision], FullTextReadiness]:
        screening_input = self._input.get_input_set(project_id)
        title_abstract_latest = self._latest_by_publication(
            project_id, reviewer_id, ScreeningStage.TITLE_ABSTRACT
        )
        eligible = self._eligible_publications(screening_input, title_abstract_latest)
        return screening_input, eligible, title_abstract_latest, self._readiness(
            screening_input, eligible, title_abstract_latest
        )

    @staticmethod
    def _require_ready(readiness: FullTextReadiness) -> None:
        if not readiness.ready:
            raise FullTextWorkflowNotReadyError(readiness.status)

    def get_overview(self, project_id: str, reviewer_id: str) -> FullTextOverview:
        reviewer = self._reviewer_id(reviewer_id)
        screening_input, eligible, _, readiness = self._current(project_id, reviewer)
        criteria = self._active_criteria(project_id)
        progress = None
        if readiness.ready:
            latest = self._latest_by_publication(project_id, reviewer, ScreeningStage.FULL_TEXT)
            records = self._records(eligible, latest, criteria, project_id)
            counts = {status: 0 for status in FullTextScreeningStatus}
            for record in records:
                counts[record.status] += 1
            progress = FullTextProgress(
                total=len(records),
                unscreened=counts[FullTextScreeningStatus.UNSCREENED],
                included=counts[FullTextScreeningStatus.INCLUDED],
                excluded=counts[FullTextScreeningStatus.EXCLUDED],
                uncertain=counts[FullTextScreeningStatus.UNCERTAIN],
            )
        return FullTextOverview(project_id, reviewer, screening_input, readiness, criteria, progress)

    def list_records(
        self, project_id: str, reviewer_id: str, *, status_filter: FullTextScreeningStatus | None = None,
        offset: int = 0, limit: int = 50,
    ) -> FullTextRecordPage:
        reviewer = self._reviewer_id(reviewer_id)
        _, eligible, _, readiness = self._current(project_id, reviewer)
        self._require_ready(readiness)
        records = self._records(
            eligible,
            self._latest_by_publication(project_id, reviewer, ScreeningStage.FULL_TEXT),
            self._active_criteria(project_id),
            project_id,
        )
        if status_filter is not None:
            records = tuple(record for record in records if record.status is status_filter)
        return FullTextRecordPage(project_id, reviewer, status_filter, len(records), offset, limit, records[offset : offset + limit])

    def get_record(self, project_id: str, publication_id: UUID, reviewer_id: str) -> FullTextRecord:
        reviewer = self._reviewer_id(reviewer_id)
        _, eligible, _, readiness = self._current(project_id, reviewer)
        self._require_ready(readiness)
        publication = next((item for item in eligible if item.record_id == publication_id), None)
        if publication is None:
            raise FullTextPublicationNotEligibleError(str(publication_id))
        criteria = self._active_criteria(project_id)
        return self._records(
            (publication,), self._latest_by_publication(project_id, reviewer, ScreeningStage.FULL_TEXT), criteria, project_id
        )[0]

    def save_availability(
        self, project_id: str, publication_id: UUID, reviewer_id: str,
        status: FullTextAvailabilityStatus, external_url: str | None, notes: str | None,
    ) -> FullTextAvailability:
        # Availability belongs to the Full Text workflow: it cannot be altered for a
        # record outside the reviewer's current eligible set.
        self.get_record(project_id, publication_id, reviewer_id)
        return self._availability.save(FullTextAvailability(
            project_id=project_id, publication_id=publication_id, status=status,
            external_url=external_url, notes=notes,
        ))

    def record_decision(
        self, project_id: str, publication_id: UUID, reviewer_id: str, outcome: ScreeningOutcome,
        rationale: str | None, assessment_inputs: list[CriterionAssessmentInput],
        exclusion_reason_criterion_ids: list[UUID],
    ) -> ScreeningDecision:
        reviewer = self._reviewer_id(reviewer_id)
        record = self.get_record(project_id, publication_id, reviewer)
        self._validate_exclusion_reasons(
            project_id, outcome, record, assessment_inputs, exclusion_reason_criterion_ids
        )
        return self._decision_service.record_decision(
            project_id=project_id,
            publication_id=publication_id,
            stage=ScreeningStage.FULL_TEXT,
            outcome=outcome,
            reviewer_id=reviewer,
            rationale=rationale,
            assessment_inputs=assessment_inputs,
            exclusion_reason_criterion_ids=exclusion_reason_criterion_ids,
            canonical_publication=record.publication,
        )

    def _validate_exclusion_reasons(
        self, project_id: str, outcome: ScreeningOutcome, record: FullTextRecord,
        assessment_inputs: list[CriterionAssessmentInput], reason_ids: list[UUID],
    ) -> None:
        if outcome is not ScreeningOutcome.EXCLUDE:
            if reason_ids:
                raise ValueError("Only Full Text exclusions may include exclusion reasons")
            return
        if not reason_ids:
            raise ValueError("Full Text exclusion requires at least one structured exclusion reason")
        if len(set(reason_ids)) != len(reason_ids):
            raise ValueError("Duplicate exclusion reason criterion_id")

        criteria = {criterion.criterion_id: criterion for criterion in self._active_criteria(project_id)}
        assessment_values = {
            item.criterion_id: item.assessment_value for item in assessment_inputs
        }
        for automatic in record.automatic_assessments:
            assessment_values[automatic.criterion_id] = automatic.assessment_value
        for reason_id in reason_ids:
            criterion = criteria.get(reason_id)
            assessment_value = assessment_values.get(reason_id)
            if criterion is None or assessment_value is None:
                raise ValueError(
                    "Each Full Text exclusion reason must reference an assessment in this decision"
                )
            valid = (
                criterion.criterion_type is ScreeningCriterionType.INCLUSION
                and assessment_value is CriterionAssessmentValue.NOT_MET
            ) or (
                criterion.criterion_type is ScreeningCriterionType.EXCLUSION
                and assessment_value is CriterionAssessmentValue.MET
            )
            if not valid:
                raise ValueError(
                    "Full Text exclusion reasons require an unmet inclusion criterion or met exclusion criterion"
                )
