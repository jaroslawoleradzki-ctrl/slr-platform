from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    StrictStr,
    field_validator,
    model_validator,
)


class ScreeningStage(StrEnum):
    """Stage of the systematic review screening process."""

    TITLE_ABSTRACT = "title_abstract"
    FULL_TEXT = "full_text"


class ScreeningCriterionStage(StrEnum):
    """Stage in the systematic review process where a screening criterion applies."""

    TITLE_ABSTRACT = "title_abstract"
    FULL_TEXT = "full_text"
    BOTH = "both"


class ScreeningCriterionType(StrEnum):
    """Type of screening criterion (inclusion vs exclusion)."""

    INCLUSION = "inclusion"
    EXCLUSION = "exclusion"


class ScreeningOutcome(StrEnum):
    """Possible inclusion decision at a screening stage."""

    INCLUDE = "include"
    EXCLUDE = "exclude"
    UNCERTAIN = "uncertain"


class CriterionAssessmentValue(StrEnum):
    """Methodology-neutral assessment value for an individual screening criterion."""

    MET = "met"
    NOT_MET = "not_met"
    UNCERTAIN = "uncertain"
    NOT_ASSESSED = "not_assessed"


class ScreeningCriterionEvaluationMode(StrEnum):
    """How a criterion assessment is produced."""

    MANUAL = "manual"
    METADATA_RULE = "metadata_rule"


class MetadataRuleField(StrEnum):
    """Safe, explicit canonical Publication fields available to rule evaluation."""

    PUBLICATION_YEAR = "publication_year"
    LANGUAGE = "language"
    DOCUMENT_TYPE = "document_type"
    OPEN_ACCESS = "open_access"
    DOI = "doi"
    ABSTRACT = "abstract"


class MetadataRuleOperator(StrEnum):
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    IN = "in"
    NOT_IN = "not_in"
    GREATER_THAN = "greater_than"
    GREATER_THAN_OR_EQUAL = "greater_than_or_equal"
    LESS_THAN = "less_than"
    LESS_THAN_OR_EQUAL = "less_than_or_equal"
    EXISTS = "exists"
    NOT_EXISTS = "not_exists"


MetadataRuleValue = StrictInt | StrictStr | StrictBool | list[StrictInt | StrictStr | StrictBool]


class MetadataRule(BaseModel):
    """A deterministic, non-programmable rule over an allow-listed publication field."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    field: MetadataRuleField
    operator: MetadataRuleOperator
    value: MetadataRuleValue | None = None

    @model_validator(mode="after")
    def validate_field_operator_and_value(self) -> "MetadataRule":
        presence_fields = {MetadataRuleField.DOI, MetadataRuleField.ABSTRACT}
        presence_operators = {MetadataRuleOperator.EXISTS, MetadataRuleOperator.NOT_EXISTS}
        equality_operators = {
            MetadataRuleOperator.EQUALS,
            MetadataRuleOperator.NOT_EQUALS,
            MetadataRuleOperator.IN,
            MetadataRuleOperator.NOT_IN,
        }
        comparison_operators = {
            MetadataRuleOperator.GREATER_THAN,
            MetadataRuleOperator.GREATER_THAN_OR_EQUAL,
            MetadataRuleOperator.LESS_THAN,
            MetadataRuleOperator.LESS_THAN_OR_EQUAL,
        }

        if self.field in presence_fields:
            if self.operator not in presence_operators or self.value is not None:
                raise ValueError(f"{self.field.value} supports only exists/not_exists without a value")
            return self

        if self.operator in presence_operators:
            if self.value is not None:
                raise ValueError("exists/not_exists operators must not include a value")
            return self

        if self.value is None:
            raise ValueError(f"{self.operator.value} requires a rule value")

        values = self.value if isinstance(self.value, list) else [self.value]
        if self.operator in comparison_operators:
            if self.field is not MetadataRuleField.PUBLICATION_YEAR:
                raise ValueError(f"{self.operator.value} is supported only for publication_year")
            if len(values) != 1 or not isinstance(values[0], int) or isinstance(values[0], bool):
                raise ValueError("publication_year comparisons require one integer value")
            return self

        if self.operator not in equality_operators:
            raise ValueError(f"unsupported operator '{self.operator.value}'")
        if self.operator in {MetadataRuleOperator.EQUALS, MetadataRuleOperator.NOT_EQUALS} and len(values) != 1:
            raise ValueError(f"{self.operator.value} requires one value")
        if self.operator in {MetadataRuleOperator.IN, MetadataRuleOperator.NOT_IN} and not isinstance(self.value, list):
            raise ValueError(f"{self.operator.value} requires a list value")

        expected_type = (
            int
            if self.field is MetadataRuleField.PUBLICATION_YEAR
            else bool
            if self.field is MetadataRuleField.OPEN_ACCESS
            else str
        )
        if any(not isinstance(value, expected_type) or (expected_type is int and isinstance(value, bool)) for value in values):
            raise ValueError(f"{self.field.value} requires {expected_type.__name__} rule values")
        return self


class ScreeningCriterion(BaseModel):
    """Domain model representing a configurable screening criterion for a project."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    criterion_id: UUID = Field(default_factory=uuid4)
    project_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str | None = None
    criterion_type: ScreeningCriterionType
    screening_stage: ScreeningCriterionStage
    display_order: int = Field(default=0, ge=0)
    is_active: bool = True
    is_required: bool = True
    evaluation_mode: ScreeningCriterionEvaluationMode = ScreeningCriterionEvaluationMode.MANUAL
    metadata_rule: MetadataRule | None = None

    @field_validator("project_id", "name")
    @classmethod
    def validate_non_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("text fields must not be blank")
        return stripped

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped if stripped else None

    @model_validator(mode="after")
    def validate_evaluation_configuration(self) -> "ScreeningCriterion":
        if self.evaluation_mode is ScreeningCriterionEvaluationMode.MANUAL:
            if self.metadata_rule is not None:
                raise ValueError("manual criterion must not define a metadata rule")
        elif self.metadata_rule is None:
            raise ValueError("metadata_rule criterion requires a metadata rule")
        return self


class AIRecommendation(BaseModel):
    """Standalone AI-generated screening recommendation domain model (Phase 1)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    outcome: ScreeningOutcome
    confidence: float = Field(ge=0.0, le=1.0)
    model_name: str = Field(min_length=1)
    model_version: str | None = None
    rationale: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("model_name", "model_version", "rationale")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("text fields must not be blank")
        return stripped

    @field_validator("created_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")
        return value


class CriterionAssessment(BaseModel):
    """Assessment of an individual screening criterion with an immutable historical snapshot."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    criterion_id: UUID
    criterion_name: str = Field(min_length=1)
    criterion_type: ScreeningCriterionType
    criterion_stage: ScreeningCriterionStage
    criterion_is_required: bool
    assessment_value: CriterionAssessmentValue
    notes: str | None = None
    evaluation_mode: ScreeningCriterionEvaluationMode = ScreeningCriterionEvaluationMode.MANUAL
    metadata_rule: MetadataRule | None = None
    evaluated_metadata_value: MetadataRuleValue | None = None

    @field_validator("criterion_name")
    @classmethod
    def validate_non_blank_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("criterion_name must not be blank")
        return stripped

    @field_validator("notes")
    @classmethod
    def normalize_notes(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped if stripped else None

    @model_validator(mode="after")
    def validate_evaluation_snapshot(self) -> "CriterionAssessment":
        if self.evaluation_mode is ScreeningCriterionEvaluationMode.MANUAL:
            if self.metadata_rule is not None or self.evaluated_metadata_value is not None:
                raise ValueError("manual assessment must not include an automatic rule snapshot")
        elif self.metadata_rule is None:
            raise ValueError("automatic assessment requires a metadata rule snapshot")
        return self


class ScreeningDecision(BaseModel):
    """Immutable screening decision record for a single publication, reviewer, and stage.

    100% AI-free. Contains decision outcome, rationale, and criterion assessments snapshot.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    decision_id: UUID = Field(default_factory=uuid4)
    project_id: str = Field(min_length=1)
    publication_id: UUID
    stage: ScreeningStage
    outcome: ScreeningOutcome
    reviewer_id: str = Field(min_length=1)
    rationale: str | None = None
    criterion_assessments: list[CriterionAssessment] = Field(default_factory=list)
    # For Full Text exclusions this stores criterion IDs whose immutable
    # assessment snapshots explain the exclusion.  Stage-specific validation
    # lives in FullTextScreeningService; the generic decision model remains
    # reusable for other workflows.
    exclusion_reason_criterion_ids: list[UUID] = Field(default_factory=list)
    decided_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("project_id", "reviewer_id")
    @classmethod
    def validate_non_blank_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("text fields must not be blank")
        return stripped

    @field_validator("rationale")
    @classmethod
    def normalize_rationale(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped if stripped else None

    @field_validator("decided_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("decided_at must be timezone-aware")
        return value

    @model_validator(mode="after")
    def validate_unique_assessments(self) -> "ScreeningDecision":
        seen_criterion_ids: set[UUID] = set()
        for assessment in self.criterion_assessments:
            if assessment.criterion_id in seen_criterion_ids:
                raise ValueError(
                    f"Duplicate criterion assessment for criterion_id '{assessment.criterion_id}'"
                )
            seen_criterion_ids.add(assessment.criterion_id)
        if len(set(self.exclusion_reason_criterion_ids)) != len(
            self.exclusion_reason_criterion_ids
        ):
            raise ValueError("Duplicate exclusion reason criterion_id")
        return self
