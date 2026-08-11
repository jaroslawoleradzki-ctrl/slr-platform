from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from app.domain.publication import Publication
from app.domain.screening import (
    CriterionAssessmentValue,
    ScreeningCriterion,
    ScreeningCriterionEvaluationMode,
    ScreeningCriterionStage,
    ScreeningDecision,
    ScreeningOutcome,
    ScreeningStage,
)
from app.repositories.screening_criterion_repository import (
    ScreeningCriterionRepository,
    default_screening_criterion_repository,
)
from app.repositories.screening_decision_repository import (
    ScreeningDecisionRepository,
    default_screening_decision_repository,
)
from app.services.screening_criterion_rule_evaluator import (
    ScreeningCriterionRuleEvaluator,
)
from app.services.screening_decision_service import (
    CriterionAssessmentInput,
    ScreeningDecisionService,
)
from app.services.screening_input_service import (
    ScreeningInput,
    ScreeningInputReadinessStatus,
    ScreeningInputService,
)


class TitleAbstractScreeningStatus(StrEnum):
    UNSCREENED = "unscreened"
    INCLUDED = "included"
    EXCLUDED = "excluded"
    UNCERTAIN = "uncertain"


class ScreeningWorkflowNotReadyError(RuntimeError):
    def __init__(self, readiness_status: ScreeningInputReadinessStatus) -> None:
        self.readiness_status = readiness_status
        super().__init__(f"screening workflow is not ready: {readiness_status.value}")


class ScreeningPublicationNotEligibleError(LookupError):
    pass


@dataclass(frozen=True, slots=True)
class TitleAbstractProgress:
    total: int
    unscreened: int
    included: int
    excluded: int
    uncertain: int

    @property
    def completed(self) -> int:
        return self.included + self.excluded + self.uncertain


@dataclass(frozen=True, slots=True)
class TitleAbstractRecord:
    publication: Publication
    status: TitleAbstractScreeningStatus
    latest_decision: ScreeningDecision | None
    automatic_assessments: tuple["AutomaticCriterionAssessment", ...]


@dataclass(frozen=True, slots=True)
class AutomaticCriterionAssessment:
    criterion_id: UUID
    assessment_value: CriterionAssessmentValue
    evaluated_metadata_value: object | None


@dataclass(frozen=True, slots=True)
class TitleAbstractOverview:
    project_id: str
    reviewer_id: str
    screening_input: ScreeningInput
    criteria: tuple[ScreeningCriterion, ...]
    progress: TitleAbstractProgress | None


@dataclass(frozen=True, slots=True)
class TitleAbstractRecordPage:
    project_id: str
    reviewer_id: str
    status_filter: TitleAbstractScreeningStatus | None
    total: int
    offset: int
    limit: int
    items: tuple[TitleAbstractRecord, ...]


_OUTCOME_STATUS = {
    ScreeningOutcome.INCLUDE: TitleAbstractScreeningStatus.INCLUDED,
    ScreeningOutcome.EXCLUDE: TitleAbstractScreeningStatus.EXCLUDED,
    ScreeningOutcome.UNCERTAIN: TitleAbstractScreeningStatus.UNCERTAIN,
}


class TitleAbstractScreeningService:
    def __init__(
        self,
        input_service: ScreeningInputService | None = None,
        criterion_repository: ScreeningCriterionRepository | None = None,
        decision_repository: ScreeningDecisionRepository | None = None,
        decision_service: ScreeningDecisionService | None = None,
        rule_evaluator: ScreeningCriterionRuleEvaluator | None = None,
    ) -> None:
        self._input = input_service or ScreeningInputService()
        self._criteria = criterion_repository or default_screening_criterion_repository()
        self._decisions = decision_repository or default_screening_decision_repository()
        self._decision_service = decision_service or ScreeningDecisionService()
        self._rule_evaluator = rule_evaluator or ScreeningCriterionRuleEvaluator()

    @staticmethod
    def _reviewer_id(reviewer_id: str) -> str:
        value = reviewer_id.strip()
        if not value:
            raise ValueError("reviewer_id must not be blank")
        return value

    def _latest_by_publication(self, project_id: str, reviewer_id: str) -> dict[UUID, ScreeningDecision]:
        latest: dict[UUID, ScreeningDecision] = {}
        for decision in self._decisions.list_by_project(project_id, ScreeningStage.TITLE_ABSTRACT):
            if decision.reviewer_id == reviewer_id:
                latest.setdefault(decision.publication_id, decision)
        return latest

    @staticmethod
    def _status(decision: ScreeningDecision | None) -> TitleAbstractScreeningStatus:
        return TitleAbstractScreeningStatus.UNSCREENED if decision is None else _OUTCOME_STATUS[decision.outcome]

    def _records(
        self,
        screening_input: ScreeningInput,
        latest: dict[UUID, ScreeningDecision],
        criteria: tuple[ScreeningCriterion, ...],
    ) -> tuple[TitleAbstractRecord, ...]:
        return tuple(
            TitleAbstractRecord(
                publication,
                self._status(latest.get(publication.record_id)),
                latest.get(publication.record_id),
                tuple(
                    AutomaticCriterionAssessment(
                        criterion.criterion_id,
                        evaluation.assessment_value,
                        evaluation.evaluated_metadata_value,
                    )
                    for criterion in criteria
                    if criterion.evaluation_mode is ScreeningCriterionEvaluationMode.METADATA_RULE
                    for evaluation in [self._rule_evaluator.evaluate(criterion, publication)]
                ),
            )
            for publication in screening_input.publications
        )

    def _active_title_abstract_criteria(self, project_id: str) -> tuple[ScreeningCriterion, ...]:
        return tuple(
            criterion
            for criterion in self._criteria.list_by_project(project_id, active_only=True)
            if criterion.screening_stage
            in (ScreeningCriterionStage.TITLE_ABSTRACT, ScreeningCriterionStage.BOTH)
        )

    @staticmethod
    def _require_ready(screening_input: ScreeningInput) -> None:
        if not screening_input.ready:
            raise ScreeningWorkflowNotReadyError(screening_input.readiness_status)

    def get_overview(self, project_id: str, reviewer_id: str) -> TitleAbstractOverview:
        reviewer = self._reviewer_id(reviewer_id)
        screening_input = self._input.get_input_set(project_id)
        criteria = self._active_title_abstract_criteria(project_id)
        progress = None
        if screening_input.ready:
            records = self._records(
                screening_input,
                self._latest_by_publication(project_id, reviewer),
                criteria,
            )
            counts = {status: 0 for status in TitleAbstractScreeningStatus}
            for record in records:
                counts[record.status] += 1
            progress = TitleAbstractProgress(
                len(records),
                counts[TitleAbstractScreeningStatus.UNSCREENED],
                counts[TitleAbstractScreeningStatus.INCLUDED],
                counts[TitleAbstractScreeningStatus.EXCLUDED],
                counts[TitleAbstractScreeningStatus.UNCERTAIN],
            )
        return TitleAbstractOverview(project_id, reviewer, screening_input, criteria, progress)

    def list_records(
        self,
        project_id: str,
        reviewer_id: str,
        *,
        status_filter: TitleAbstractScreeningStatus | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> TitleAbstractRecordPage:
        reviewer = self._reviewer_id(reviewer_id)
        screening_input = self._input.get_input_set(project_id)
        self._require_ready(screening_input)
        records = self._records(
            screening_input,
            self._latest_by_publication(project_id, reviewer),
            self._active_title_abstract_criteria(project_id),
        )
        if status_filter is not None:
            records = tuple(item for item in records if item.status is status_filter)
        return TitleAbstractRecordPage(
            project_id,
            reviewer,
            status_filter,
            len(records),
            offset,
            limit,
            records[offset : offset + limit],
        )

    def get_record(self, project_id: str, publication_id: UUID, reviewer_id: str) -> TitleAbstractRecord:
        reviewer = self._reviewer_id(reviewer_id)
        screening_input = self._input.get_input_set(project_id)
        self._require_ready(screening_input)
        publication = next(
            (item for item in screening_input.publications if item.record_id == publication_id),
            None,
        )
        if publication is None:
            raise ScreeningPublicationNotEligibleError(str(publication_id))
        latest = self._latest_by_publication(project_id, reviewer).get(publication_id)
        automatic_assessments = tuple(
            AutomaticCriterionAssessment(
                criterion.criterion_id,
                evaluation.assessment_value,
                evaluation.evaluated_metadata_value,
            )
            for criterion in self._active_title_abstract_criteria(project_id)
            if criterion.evaluation_mode is ScreeningCriterionEvaluationMode.METADATA_RULE
            for evaluation in [self._rule_evaluator.evaluate(criterion, publication)]
        )
        return TitleAbstractRecord(publication, self._status(latest), latest, automatic_assessments)

    def record_decision(
        self,
        project_id: str,
        publication_id: UUID,
        reviewer_id: str,
        outcome: ScreeningOutcome,
        rationale: str | None,
        assessment_inputs: list[CriterionAssessmentInput],
    ) -> ScreeningDecision:
        reviewer = self._reviewer_id(reviewer_id)
        screening_input = self._input.get_input_set(project_id)
        self._require_ready(screening_input)
        publication = next(
            (item for item in screening_input.publications if item.record_id == publication_id), None
        )
        if publication is None:
            raise ScreeningPublicationNotEligibleError(str(publication_id))
        return self._decision_service.record_decision(
            project_id=project_id,
            publication_id=publication_id,
            stage=ScreeningStage.TITLE_ABSTRACT,
            outcome=outcome,
            reviewer_id=reviewer,
            rationale=rationale,
            assessment_inputs=assessment_inputs,
            canonical_publication=publication,
        )
