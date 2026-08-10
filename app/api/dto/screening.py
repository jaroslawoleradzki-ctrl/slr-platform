from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domain.screening import (
    ScreeningCriterion,
    ScreeningCriterionStage,
    ScreeningCriterionType,
)


class ScreeningCriterionCreateRequest(BaseModel):
    """Payload for creating a new project screening criterion."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, description="Non-blank name of the criterion.")
    description: str | None = Field(
        default=None, description="Optional detailed description or instruction."
    )
    criterion_type: ScreeningCriterionType = Field(
        description="Type of criterion: 'inclusion' or 'exclusion'."
    )
    screening_stage: ScreeningCriterionStage = Field(
        description="Stage scope: 'title_abstract', 'full_text', or 'both'."
    )
    display_order: int = Field(
        default=0, ge=0, description="Non-negative sorting order index."
    )
    is_active: bool = Field(
        default=True, description="Whether the criterion is currently active."
    )
    is_required: bool = Field(
        default=True, description="Whether evaluation of this criterion is required."
    )


class ScreeningCriterionUpdateRequest(BaseModel):
    """Payload for updating an existing project screening criterion."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, description="Non-blank name of the criterion.")
    description: str | None = Field(
        default=None, description="Optional detailed description or instruction."
    )
    criterion_type: ScreeningCriterionType = Field(
        description="Type of criterion: 'inclusion' or 'exclusion'."
    )
    screening_stage: ScreeningCriterionStage = Field(
        description="Stage scope: 'title_abstract', 'full_text', or 'both'."
    )
    display_order: int = Field(
        default=0, ge=0, description="Non-negative sorting order index."
    )
    is_active: bool = Field(
        default=True, description="Whether the criterion is currently active."
    )
    is_required: bool = Field(
        default=True, description="Whether evaluation of this criterion is required."
    )


class ScreeningCriterionResponse(BaseModel):
    """API response model representing a screening criterion."""

    model_config = ConfigDict(extra="forbid")

    criterion_id: UUID = Field(description="Unique identifier of the criterion.")
    project_id: str = Field(description="Project identifier.")
    name: str = Field(description="Name of the criterion.")
    description: str | None = Field(description="Description of the criterion.")
    criterion_type: ScreeningCriterionType = Field(
        description="Type of criterion: 'inclusion' or 'exclusion'."
    )
    screening_stage: ScreeningCriterionStage = Field(
        description="Stage scope: 'title_abstract', 'full_text', or 'both'."
    )
    display_order: int = Field(description="Sorting order index.")
    is_active: bool = Field(description="Active status indicator.")
    is_required: bool = Field(description="Required status indicator.")

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
        )


class ScreeningCriterionListResponse(BaseModel):
    """Response model for a list of project screening criteria."""

    model_config = ConfigDict(extra="forbid")

    items: list[ScreeningCriterionResponse] = Field(
        description="List of screening criteria for the project."
    )
    total: int = Field(description="Total number of items returned.")
