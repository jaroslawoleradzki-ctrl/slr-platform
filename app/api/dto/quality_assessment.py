from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domain.quality_assessment import (
    ProjectQualityAssessmentConfiguration,
    QualityAssessmentTemplate,
    QualityAssessmentTemplateCriterion,
    QualityAssessmentTool,
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
