from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domain.quality_assessment import (
    ProjectQualityAssessmentConfiguration,
    QualityAssessment,
    QualityAssessmentResponse,
    QualityAssessmentResponseValue,
    QualityAssessmentTemplate,
    QualityAssessmentTemplateCriterion,
    QualityAssessmentTool,
)
from app.services.quality_assessment_execution_service import (
    EligiblePublicationRecord,
    QualityAssessmentOverview,
    QualityAssessmentRecordDetail,
    QualityAssessmentRecordList,
)


class ToolResponse(BaseModel):
    """DTO response for a quality assessment tool."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    tool_id: str
    name: str
    description: str | None = None
    is_active: bool
    created_at: datetime

    @classmethod
    def from_domain(cls, tool: QualityAssessmentTool) -> "ToolResponse":
        return cls(
            tool_id=tool.tool_id,
            name=tool.name,
            description=tool.description,
            is_active=tool.is_active,
            created_at=tool.created_at,
        )


class CriterionResponse(BaseModel):
    """DTO response for a quality assessment criterion."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    criterion_id: UUID
    template_id: UUID
    display_order: int
    question: str
    guidance: str | None = None
    is_required: bool
    created_at: datetime

    @classmethod
    def from_domain(cls, criterion: QualityAssessmentTemplateCriterion) -> "CriterionResponse":
        return cls(
            criterion_id=criterion.criterion_id,
            template_id=criterion.template_id,
            display_order=criterion.display_order,
            question=criterion.question,
            guidance=criterion.guidance,
            is_required=criterion.is_required,
            created_at=criterion.created_at,
        )


class TemplateResponse(BaseModel):
    """DTO response for a quality assessment template version."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    template_id: UUID
    tool_id: str
    template_key: str
    name: str
    version: int
    description: str | None = None
    is_active: bool
    criteria: list[CriterionResponse] = Field(default_factory=list)
    created_at: datetime

    @classmethod
    def from_domain(cls, template: QualityAssessmentTemplate) -> "TemplateResponse":
        return cls(
            template_id=template.template_id,
            tool_id=template.tool_id,
            template_key=template.template_key,
            name=template.name,
            version=template.version,
            description=template.description,
            is_active=template.is_active,
            criteria=[CriterionResponse.from_domain(c) for c in template.criteria],
            created_at=template.created_at,
        )


class ProjectQualityAssessmentConfigurationRequest(BaseModel):
    """DTO payload for setting or updating a project's active quality assessment configuration."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    tool_id: str = Field(min_length=1)
    template_id: UUID
    confirm_template_change: bool = False


class ProjectQualityAssessmentConfigurationResponse(BaseModel):
    """DTO response for a project's active quality assessment configuration."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    project_id: str
    tool_id: str
    template_id: UUID
    configured_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(
        cls, config: ProjectQualityAssessmentConfiguration
    ) -> "ProjectQualityAssessmentConfigurationResponse":
        return cls(
            project_id=config.project_id,
            tool_id=config.tool_id,
            template_id=config.template_id,
            configured_at=config.configured_at,
            updated_at=config.updated_at,
        )


class CriterionResponseInputDto(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    criterion_id: UUID
    response_value: QualityAssessmentResponseValue
    justification: str = ""


class SaveQualityAssessmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    reviewer_id: str = Field(min_length=1)
    publication_id: UUID
    responses: list[CriterionResponseInputDto] = Field(default_factory=list)


class QualityAssessmentResponseDto(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    response_id: UUID
    assessment_id: UUID
    criterion_id: UUID
    question_snapshot: str
    guidance_snapshot: str | None = None
    is_required_snapshot: bool
    response_value: QualityAssessmentResponseValue
    justification: str
    created_at: datetime

    @classmethod
    def from_domain(cls, resp: QualityAssessmentResponse) -> "QualityAssessmentResponseDto":
        return cls(
            response_id=resp.response_id,
            assessment_id=resp.assessment_id,
            criterion_id=resp.criterion_id,
            question_snapshot=resp.question_snapshot,
            guidance_snapshot=resp.guidance_snapshot,
            is_required_snapshot=resp.is_required_snapshot,
            response_value=resp.response_value,
            justification=resp.justification,
            created_at=resp.created_at,
        )


class QualityAssessmentDto(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    assessment_id: UUID
    project_id: str
    publication_id: UUID
    reviewer_id: str
    template_id: UUID
    responses: list[QualityAssessmentResponseDto]
    assessed_at: datetime

    @classmethod
    def from_domain(cls, qa: QualityAssessment) -> "QualityAssessmentDto":
        return cls(
            assessment_id=qa.assessment_id,
            project_id=qa.project_id,
            publication_id=qa.publication_id,
            reviewer_id=qa.reviewer_id,
            template_id=qa.template_id,
            responses=[QualityAssessmentResponseDto.from_domain(r) for r in qa.responses],
            assessed_at=qa.assessed_at,
        )


class QualityAssessmentOverviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    readiness: str
    tool_id: str | None = None
    template_id: UUID | None = None
    template_version: int | None = None
    total_eligible: int
    total_assessed: int
    total_remaining: int

    @classmethod
    def from_domain(cls, overview: QualityAssessmentOverview) -> "QualityAssessmentOverviewResponse":
        return cls(
            readiness=overview.readiness.value,
            tool_id=overview.tool_id,
            template_id=overview.template_id,
            template_version=overview.template_version,
            total_eligible=overview.total_eligible,
            total_assessed=overview.total_assessed,
            total_remaining=overview.total_remaining,
        )


class EligiblePublicationRecordDto(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    publication: dict
    has_assessment: bool
    latest_assessment: QualityAssessmentDto | None = None

    @classmethod
    def from_domain(cls, record: EligiblePublicationRecord) -> "EligiblePublicationRecordDto":
        return cls(
            publication=record.publication.model_dump(mode="json"),
            has_assessment=record.has_assessment,
            latest_assessment=(
                QualityAssessmentDto.from_domain(record.latest_assessment)
                if record.latest_assessment
                else None
            ),
        )


class QualityAssessmentRecordListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    items: list[EligiblePublicationRecordDto]
    total: int
    page: int
    page_size: int
    total_pages: int

    @classmethod
    def from_domain(cls, record_list: QualityAssessmentRecordList) -> "QualityAssessmentRecordListResponse":
        return cls(
            items=[EligiblePublicationRecordDto.from_domain(item) for item in record_list.items],
            total=record_list.total,
            page=record_list.page,
            page_size=record_list.page_size,
            total_pages=record_list.total_pages,
        )


class QualityAssessmentRecordDetailResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    project_id: str
    publication: dict
    reviewer_id: str
    is_currently_eligible: bool
    template: TemplateResponse
    latest_assessment: QualityAssessmentDto | None = None
    history: list[QualityAssessmentDto] = Field(default_factory=list)

    @classmethod
    def from_domain(cls, detail: QualityAssessmentRecordDetail) -> "QualityAssessmentRecordDetailResponse":
        return cls(
            project_id=detail.project_id,
            publication=detail.publication.model_dump(mode="json"),
            reviewer_id=detail.reviewer_id,
            is_currently_eligible=detail.is_currently_eligible,
            template=TemplateResponse.from_domain(detail.template),
            latest_assessment=(
                QualityAssessmentDto.from_domain(detail.latest_assessment)
                if detail.latest_assessment
                else None
            ),
            history=[QualityAssessmentDto.from_domain(qa) for qa in detail.history],
        )


SaveQualityAssessmentRequest.model_rebuild()
QualityAssessmentResponseDto.model_rebuild()
QualityAssessmentDto.model_rebuild()
QualityAssessmentOverviewResponse.model_rebuild()
EligiblePublicationRecordDto.model_rebuild()
QualityAssessmentRecordListResponse.model_rebuild()
QualityAssessmentRecordDetailResponse.model_rebuild()
