from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domain.identifiers import IdentifierType
from app.domain.publication import DocumentType
from app.domain.screening import (
    CriterionAssessment,
    CriterionAssessmentValue,
    MetadataRule,
    ScreeningCriterion,
    ScreeningCriterionEvaluationMode,
    ScreeningCriterionStage,
    ScreeningCriterionType,
    ScreeningDecision,
    ScreeningOutcome,
    ScreeningStage,
)
from app.domain.venue import VenueType
from app.services.screening_input_service import ScreeningInputReadinessStatus
from app.services.title_abstract_screening_service import (
    TitleAbstractOverview,
    TitleAbstractProgress,
    TitleAbstractRecord,
    TitleAbstractRecordPage,
    TitleAbstractScreeningStatus,
)


class ScreeningCriterionCreateRequest(BaseModel):
    """Payload for creating a new project screening criterion."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, description="Non-blank name of the criterion.")
    description: str | None = Field(default=None, description="Optional detailed description or instruction.")
    criterion_type: ScreeningCriterionType = Field(description="Type of criterion: 'inclusion' or 'exclusion'.")
    screening_stage: ScreeningCriterionStage = Field(
        description="Stage scope: 'title_abstract', 'full_text', or 'both'."
    )
    display_order: int = Field(default=0, ge=0, description="Non-negative sorting order index.")
    is_active: bool = Field(default=True, description="Whether the criterion is currently active.")
    is_required: bool = Field(default=True, description="Whether evaluation of this criterion is required.")
    evaluation_mode: ScreeningCriterionEvaluationMode = ScreeningCriterionEvaluationMode.MANUAL
    metadata_rule: MetadataRule | None = None


class ScreeningCriterionUpdateRequest(BaseModel):
    """Payload for updating an existing project screening criterion."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, description="Non-blank name of the criterion.")
    description: str | None = Field(default=None, description="Optional detailed description or instruction.")
    criterion_type: ScreeningCriterionType = Field(description="Type of criterion: 'inclusion' or 'exclusion'.")
    screening_stage: ScreeningCriterionStage = Field(
        description="Stage scope: 'title_abstract', 'full_text', or 'both'."
    )
    display_order: int = Field(default=0, ge=0, description="Non-negative sorting order index.")
    is_active: bool = Field(default=True, description="Whether the criterion is currently active.")
    is_required: bool = Field(default=True, description="Whether evaluation of this criterion is required.")
    evaluation_mode: ScreeningCriterionEvaluationMode = ScreeningCriterionEvaluationMode.MANUAL
    metadata_rule: MetadataRule | None = None


class ScreeningCriterionResponse(BaseModel):
    """API response model representing a screening criterion."""

    model_config = ConfigDict(extra="forbid")

    criterion_id: UUID = Field(description="Unique identifier of the criterion.")
    project_id: str = Field(description="Project identifier.")
    name: str = Field(description="Name of the criterion.")
    description: str | None = Field(description="Description of the criterion.")
    criterion_type: ScreeningCriterionType = Field(description="Type of criterion: 'inclusion' or 'exclusion'.")
    screening_stage: ScreeningCriterionStage = Field(
        description="Stage scope: 'title_abstract', 'full_text', or 'both'."
    )
    display_order: int = Field(description="Sorting order index.")
    is_active: bool = Field(description="Active status indicator.")
    is_required: bool = Field(description="Required status indicator.")
    evaluation_mode: ScreeningCriterionEvaluationMode
    metadata_rule: MetadataRule | None

    @classmethod
    def from_domain(cls, criterion: ScreeningCriterion) -> ScreeningCriterionResponse:
        return cls(
            criterion_id=criterion.criterion_id,
            project_id=criterion.project_id,
            name=criterion.name,
            description=criterion.description,
            criterion_type=criterion.criterion_type,
            screening_stage=criterion.screening_stage,
            display_order=criterion.display_order,
            is_active=criterion.is_active,
            is_required=criterion.is_required,
            evaluation_mode=criterion.evaluation_mode,
            metadata_rule=criterion.metadata_rule,
        )


class ScreeningCriterionListResponse(BaseModel):
    """Response model for a list of project screening criteria."""

    model_config = ConfigDict(extra="forbid")

    items: list[ScreeningCriterionResponse] = Field(description="List of screening criteria for the project.")
    total: int = Field(description="Total number of items returned.")


# --- Screening Decision DTOs ---


class CriterionAssessmentRequest(BaseModel):
    """Client payload for evaluating an individual screening criterion.

    Authoritative criterion metadata is populated server-side from ScreeningCriterionRepository.
    """

    model_config = ConfigDict(extra="forbid")

    criterion_id: UUID = Field(description="Identifier of the criterion being evaluated.")
    assessment_value: CriterionAssessmentValue = Field(
        description="Assessment value: 'met', 'not_met', 'uncertain', or 'not_assessed'."
    )
    notes: str | None = Field(default=None, description="Optional reviewer notes for this assessment.")


class ScreeningDecisionCreateRequest(BaseModel):
    """Payload for recording a new screening decision for a publication."""

    model_config = ConfigDict(extra="forbid")

    publication_id: UUID = Field(description="Identifier of the publication being screened.")
    stage: ScreeningStage = Field(description="Screening stage: 'title_abstract' or 'full_text'.")
    outcome: ScreeningOutcome = Field(description="Decision outcome: 'include', 'exclude', or 'uncertain'.")
    reviewer_id: str = Field(min_length=1, description="Non-blank reviewer identifier.")
    rationale: str | None = Field(default=None, description="Optional overall decision rationale.")
    criterion_assessments: list[CriterionAssessmentRequest] = Field(
        default_factory=list, description="Criterion-level assessments."
    )


class CriterionAssessmentResponse(BaseModel):
    """API response model representing a criterion assessment snapshot."""

    model_config = ConfigDict(extra="forbid")

    criterion_id: UUID = Field(description="Criterion identifier.")
    criterion_name: str = Field(description="Criterion name at decision time.")
    criterion_type: ScreeningCriterionType = Field(description="Criterion type.")
    criterion_stage: ScreeningCriterionStage = Field(description="Criterion stage scope.")
    criterion_is_required: bool = Field(description="Whether criterion was required at decision time.")
    assessment_value: CriterionAssessmentValue = Field(description="Assessment value.")
    notes: str | None = Field(description="Reviewer notes.")
    evaluation_mode: ScreeningCriterionEvaluationMode
    metadata_rule: MetadataRule | None
    evaluated_metadata_value: object | None

    @classmethod
    def from_domain(cls, assessment: CriterionAssessment) -> CriterionAssessmentResponse:
        return cls(
            criterion_id=assessment.criterion_id,
            criterion_name=assessment.criterion_name,
            criterion_type=assessment.criterion_type,
            criterion_stage=assessment.criterion_stage,
            criterion_is_required=assessment.criterion_is_required,
            assessment_value=assessment.assessment_value,
            notes=assessment.notes,
            evaluation_mode=assessment.evaluation_mode,
            metadata_rule=assessment.metadata_rule,
            evaluated_metadata_value=assessment.evaluated_metadata_value,
        )


class ScreeningDecisionResponse(BaseModel):
    """API response model representing a screening decision record."""

    model_config = ConfigDict(extra="forbid")

    decision_id: UUID = Field(description="Unique identifier of the decision record.")
    project_id: str = Field(description="Project identifier.")
    publication_id: UUID = Field(description="Publication identifier.")
    stage: ScreeningStage = Field(description="Screening stage.")
    outcome: ScreeningOutcome = Field(description="Screening outcome.")
    reviewer_id: str = Field(description="Reviewer identifier.")
    rationale: str | None = Field(description="Decision rationale.")
    criterion_assessments: list[CriterionAssessmentResponse] = Field(description="Criterion assessments snapshot.")
    decided_at: datetime = Field(description="Timezone-aware decision timestamp.")

    @classmethod
    def from_domain(cls, decision: ScreeningDecision) -> ScreeningDecisionResponse:
        return cls(
            decision_id=decision.decision_id,
            project_id=decision.project_id,
            publication_id=decision.publication_id,
            stage=decision.stage,
            outcome=decision.outcome,
            reviewer_id=decision.reviewer_id,
            rationale=decision.rationale,
            criterion_assessments=[CriterionAssessmentResponse.from_domain(a) for a in decision.criterion_assessments],
            decided_at=decision.decided_at,
        )


class ScreeningDecisionListResponse(BaseModel):
    """Response model for a list of screening decision records."""

    model_config = ConfigDict(extra="forbid")

    items: list[ScreeningDecisionResponse] = Field(description="List of screening decision records.")
    total: int = Field(description="Total number of items returned.")


class ScreeningPublicationIdentifierResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: IdentifierType
    value: str
    source: str | None


class ScreeningPublicationVenueResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    type: VenueType | None
    publisher: str | None


class TitleAbstractScreeningRecordResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    publication_id: UUID
    title: str
    abstract: str | None
    authors: list[str]
    publication_year: int | None
    publication_date: str | None
    identifiers: list[ScreeningPublicationIdentifierResponse]
    doi: str | None
    venue: ScreeningPublicationVenueResponse | None
    publisher: str | None
    document_type: DocumentType | None
    language: str | None
    keywords: list[str]
    urls: list[str]
    open_access: bool | None
    status: TitleAbstractScreeningStatus
    latest_decision: ScreeningDecisionResponse | None
    automatic_assessments: list["AutomaticCriterionAssessmentResponse"]

    @classmethod
    def from_read_model(cls, record: TitleAbstractRecord) -> TitleAbstractScreeningRecordResponse:
        publication = record.publication
        doi = next(
            (identifier.value for identifier in publication.identifiers if identifier.type is IdentifierType.DOI),
            None,
        )
        return cls(
            publication_id=publication.record_id,
            title=publication.title,
            abstract=publication.abstract,
            authors=[author.display_name for author in publication.authors],
            publication_year=publication.publication_year,
            publication_date=(
                publication.publication_date.isoformat() if publication.publication_date is not None else None
            ),
            identifiers=[
                ScreeningPublicationIdentifierResponse(type=item.type, value=item.value, source=item.source)
                for item in publication.identifiers
            ],
            doi=doi,
            venue=(
                ScreeningPublicationVenueResponse(
                    name=publication.venue.name,
                    type=publication.venue.type,
                    publisher=publication.venue.publisher,
                )
                if publication.venue is not None
                else None
            ),
            publisher=publication.publisher,
            document_type=publication.document_type,
            language=publication.language,
            keywords=publication.keywords,
            urls=publication.urls,
            open_access=publication.open_access,
            status=record.status,
            latest_decision=(
                ScreeningDecisionResponse.from_domain(record.latest_decision)
                if record.latest_decision is not None
                else None
            ),
            automatic_assessments=[
                AutomaticCriterionAssessmentResponse(
                    criterion_id=item.criterion_id,
                    assessment_value=item.assessment_value,
                    evaluated_metadata_value=item.evaluated_metadata_value,
                )
                for item in record.automatic_assessments
            ],
        )


class AutomaticCriterionAssessmentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    criterion_id: UUID
    assessment_value: CriterionAssessmentValue
    evaluated_metadata_value: object | None


class TitleAbstractScreeningProgressResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total: int
    unscreened: int
    included: int
    excluded: int
    uncertain: int
    completed: int

    @classmethod
    def from_read_model(cls, progress: TitleAbstractProgress) -> TitleAbstractScreeningProgressResponse:
        return cls(
            total=progress.total,
            unscreened=progress.unscreened,
            included=progress.included,
            excluded=progress.excluded,
            uncertain=progress.uncertain,
            completed=progress.completed,
        )


class TitleAbstractScreeningOverviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str
    reviewer_id: str
    ready: bool
    readiness_status: ScreeningInputReadinessStatus
    working_collection_count: int
    canonical_records_count: int
    unresolved_duplicate_groups: int
    criteria: list[ScreeningCriterionResponse]
    progress: TitleAbstractScreeningProgressResponse | None

    @classmethod
    def from_read_model(cls, overview: TitleAbstractOverview) -> TitleAbstractScreeningOverviewResponse:
        value = overview.screening_input
        return cls(
            project_id=overview.project_id,
            reviewer_id=overview.reviewer_id,
            ready=value.ready,
            readiness_status=value.readiness_status,
            working_collection_count=value.working_collection_count,
            canonical_records_count=value.canonical_records_count,
            unresolved_duplicate_groups=value.unresolved_groups_count,
            criteria=[ScreeningCriterionResponse.from_domain(item) for item in overview.criteria],
            progress=(
                TitleAbstractScreeningProgressResponse.from_read_model(overview.progress)
                if overview.progress is not None
                else None
            ),
        )


class TitleAbstractScreeningListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str
    reviewer_id: str
    ready: bool = True
    status_filter: TitleAbstractScreeningStatus | None
    total: int
    offset: int
    limit: int
    items: list[TitleAbstractScreeningRecordResponse]

    @classmethod
    def from_read_model(cls, page: TitleAbstractRecordPage) -> TitleAbstractScreeningListResponse:
        return cls(
            project_id=page.project_id,
            reviewer_id=page.reviewer_id,
            status_filter=page.status_filter,
            total=page.total,
            offset=page.offset,
            limit=page.limit,
            items=[TitleAbstractScreeningRecordResponse.from_read_model(item) for item in page.items],
        )


class TitleAbstractDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    publication_id: UUID
    reviewer_id: str = Field(min_length=1)
    outcome: ScreeningOutcome
    rationale: str | None = None
    criterion_assessments: list[CriterionAssessmentRequest] = Field(default_factory=list)
