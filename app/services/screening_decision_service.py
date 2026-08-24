from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator

from app.domain.publication import Publication
from app.domain.screening import (
    CriterionAssessment,
    CriterionAssessmentValue,
    ScreeningCriterionEvaluationMode,
    ScreeningCriterionStage,
    ScreeningDecision,
    ScreeningOutcome,
    ScreeningStage,
)
from app.repositories.project_publication_repository import (
    ProjectPublicationRepository,
    default_project_publication_repository,
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


class CriterionAssessmentInput(BaseModel):
    """Client input payload for an individual criterion assessment.

    Authoritative criterion metadata (name, type, stage, is_required) is populated
    server-side by ScreeningDecisionService from ScreeningCriterionRepository.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    criterion_id: UUID
    assessment_value: CriterionAssessmentValue
    notes: str | None = None

    @field_validator("notes")
    @classmethod
    def normalize_notes(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped if stripped else None


class ScreeningDecisionService:
    """Application service for recording and retrieving project-scoped screening decisions.

    Enforces cross-repository business rules and invariants:
    - Publication existence and project ownership in ProjectPublicationRepository.
    - Criterion existence and project ownership in ScreeningCriterionRepository.
    - Inactive criterion rejection for new decisions.
    - Stage compatibility (decision stage vs criterion stage).
    - Authoritative server-side snapshot construction for CriterionAssessment.
    - Completeness of required active criteria assessments.
    """

    def __init__(
        self,
        decision_repository: ScreeningDecisionRepository | None = None,
        criterion_repository: ScreeningCriterionRepository | None = None,
        publication_repository: ProjectPublicationRepository | None = None,
        rule_evaluator: ScreeningCriterionRuleEvaluator | None = None,
    ) -> None:
        self.decision_repo = (
            decision_repository if decision_repository is not None else default_screening_decision_repository()
        )
        self.criterion_repo = (
            criterion_repository if criterion_repository is not None else default_screening_criterion_repository()
        )
        self.publication_repo = (
            publication_repository if publication_repository is not None else default_project_publication_repository()
        )
        self._rule_evaluator = rule_evaluator or ScreeningCriterionRuleEvaluator()

    def record_decision(
        self,
        project_id: str,
        publication_id: UUID,
        stage: ScreeningStage,
        outcome: ScreeningOutcome,
        reviewer_id: str,
        rationale: str | None = None,
        assessment_inputs: list[CriterionAssessmentInput] | None = None,
        exclusion_reason_criterion_ids: list[UUID] | None = None,
        canonical_publication: Publication | None = None,
    ) -> ScreeningDecision:
        """Record a new screening decision after validating publication, criteria, stage, and required inputs."""
        stripped_project_id = project_id.strip()
        if not stripped_project_id:
            raise ValueError("project_id must not be blank")

        stripped_reviewer_id = reviewer_id.strip()
        if not stripped_reviewer_id:
            raise ValueError("reviewer_id must not be blank")

        # 1. Verify publication existence in project
        try:
            publications = (
                self.publication_repo.get_active_publications(stripped_project_id)
                if hasattr(self.publication_repo, "get_active_publications")
                else self.publication_repo.get_publications(stripped_project_id)
            )
        except Exception:
            publications = []

        publication = next((item for item in publications if item.record_id == publication_id), None)
        if publication is None:
            raise ValueError(f"Publication '{publication_id}' not found in project '{stripped_project_id}'.")
        if canonical_publication is not None and canonical_publication.record_id != publication_id:
            raise ValueError("canonical_publication record_id must match publication_id")
        publication_for_evaluation = canonical_publication or publication

        # 2. Fetch project criteria
        project_criteria = self.criterion_repo.list_by_project(stripped_project_id, active_only=False)
        criteria_by_id = {c.criterion_id: c for c in project_criteria}

        inputs = assessment_inputs or []
        assessments: list[CriterionAssessment] = []
        assessed_criterion_ids: set[UUID] = set()

        # 3. Validate each assessment input and build authoritative snapshot
        for inp in inputs:
            criterion = criteria_by_id.get(inp.criterion_id)
            if criterion is None:
                raise ValueError(f"Criterion '{inp.criterion_id}' not found in project '{stripped_project_id}'.")

            if not criterion.is_active:
                raise ValueError(
                    f"Cannot assess inactive criterion '{criterion.name}' ({criterion.criterion_id}) in a new decision."
                )

            if criterion.evaluation_mode is ScreeningCriterionEvaluationMode.METADATA_RULE:
                raise ValueError(
                    f"Automatic criterion '{criterion.name}' ({criterion.criterion_id}) is evaluated server-side and must not be sent by the client."
                )

            # Stage compatibility check
            if stage == ScreeningStage.TITLE_ABSTRACT:
                if criterion.screening_stage not in (
                    ScreeningCriterionStage.TITLE_ABSTRACT,
                    ScreeningCriterionStage.BOTH,
                ):
                    raise ValueError(
                        f"Criterion '{criterion.name}' (stage {criterion.screening_stage.value}) is incompatible with decision stage {stage.value}."
                    )
            elif stage == ScreeningStage.FULL_TEXT:
                if criterion.screening_stage not in (
                    ScreeningCriterionStage.FULL_TEXT,
                    ScreeningCriterionStage.BOTH,
                ):
                    raise ValueError(
                        f"Criterion '{criterion.name}' (stage {criterion.screening_stage.value}) is incompatible with decision stage {stage.value}."
                    )

            if inp.criterion_id in assessed_criterion_ids:
                raise ValueError(f"Duplicate assessment input for criterion '{criterion.name}' ({inp.criterion_id}).")
            assessed_criterion_ids.add(inp.criterion_id)

            assessments.append(
                CriterionAssessment(
                    criterion_id=criterion.criterion_id,
                    criterion_name=criterion.name,
                    criterion_description=criterion.description,
                    criterion_type=criterion.criterion_type,
                    criterion_stage=criterion.screening_stage,
                    criterion_is_required=criterion.is_required,
                    assessment_value=inp.assessment_value,
                    notes=inp.notes,
                    evaluation_mode=criterion.evaluation_mode,
                )
            )

        # 4. Automatic criteria are evaluated from the authoritative persisted
        # publication. Client payloads are deliberately unable to override them.
        for criterion in project_criteria:
            if (
                not criterion.is_active
                or criterion.evaluation_mode is not ScreeningCriterionEvaluationMode.METADATA_RULE
                or not self._applies_to_stage(criterion.screening_stage, stage)
            ):
                continue
            evaluation = self._rule_evaluator.evaluate(criterion, publication_for_evaluation)
            assessments.append(
                CriterionAssessment(
                    criterion_id=criterion.criterion_id,
                    criterion_name=criterion.name,
                    criterion_description=criterion.description,
                    criterion_type=criterion.criterion_type,
                    criterion_stage=criterion.screening_stage,
                    criterion_is_required=criterion.is_required,
                    assessment_value=evaluation.assessment_value,
                    evaluation_mode=criterion.evaluation_mode,
                    metadata_rule=criterion.metadata_rule,
                    evaluated_metadata_value=evaluation.evaluated_metadata_value,
                )
            )

        # 5. Validate required criteria completeness for stage
        # Persisted assessment snapshots are ordered by criterion_id.  Apply the
        # same deterministic order before saving so an in-memory decision and a
        # reopened decision have identical immutable representation.
        assessments.sort(key=lambda assessment: str(assessment.criterion_id))
        assessed_map = {a.criterion_id: a for a in assessments}
        for criterion in project_criteria:
            if not criterion.is_active or not criterion.is_required:
                continue

            # Check if required criterion applies to decision stage
            applies_to_stage = self._applies_to_stage(criterion.screening_stage, stage)
            if not applies_to_stage:
                continue

            assessment = assessed_map.get(criterion.criterion_id)
            if assessment is None or assessment.assessment_value == CriterionAssessmentValue.NOT_ASSESSED:
                raise ValueError(
                    f"Missing required assessment for active required criterion '{criterion.name}' ({criterion.criterion_id})."
                )

        # 6. Construct decision and save to repository
        decision = ScreeningDecision(
            project_id=stripped_project_id,
            publication_id=publication_id,
            stage=stage,
            outcome=outcome,
            reviewer_id=stripped_reviewer_id,
            rationale=rationale,
            criterion_assessments=assessments,
            exclusion_reason_criterion_ids=exclusion_reason_criterion_ids or [],
        )

        return self.decision_repo.save(decision)

    @staticmethod
    def _applies_to_stage(criterion_stage: ScreeningCriterionStage, stage: ScreeningStage) -> bool:
        return (
            stage is ScreeningStage.TITLE_ABSTRACT
            and criterion_stage in (ScreeningCriterionStage.TITLE_ABSTRACT, ScreeningCriterionStage.BOTH)
        ) or (
            stage is ScreeningStage.FULL_TEXT
            and criterion_stage in (ScreeningCriterionStage.FULL_TEXT, ScreeningCriterionStage.BOTH)
        )

    def get_decision(self, project_id: str, decision_id: UUID) -> ScreeningDecision:
        """Retrieve a screening decision by ID."""
        return self.decision_repo.get(project_id, decision_id)

    def get_latest_decision(
        self, project_id: str, publication_id: UUID, stage: ScreeningStage, reviewer_id: str
    ) -> ScreeningDecision | None:
        """Retrieve the latest decision for a publication, stage, and reviewer."""
        return self.decision_repo.get_latest_decision(project_id, publication_id, stage, reviewer_id)

    def list_history(
        self, project_id: str, publication_id: UUID, stage: ScreeningStage, reviewer_id: str | None = None
    ) -> list[ScreeningDecision]:
        """List decision history for a publication and stage."""
        return self.decision_repo.list_history(project_id, publication_id, stage, reviewer_id)

    def list_by_project(self, project_id: str, stage: ScreeningStage | None = None) -> list[ScreeningDecision]:
        """List all screening decisions for a project."""
        return self.decision_repo.list_by_project(project_id, stage)
