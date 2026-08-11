from __future__ import annotations

from pydantic import BaseModel, Field


class TitleAbstractScreeningStatusDTO(BaseModel):
    status: str = Field(description="Stage status: not_started, in_progress, completed, unresolved_conflict, stale_resolution")
    evaluated_count: int = Field(ge=0)
    total_count: int = Field(ge=0)
    conflict_count: int = Field(ge=0)
    resolved_count: int = Field(ge=0)


class FullTextScreeningStatusDTO(BaseModel):
    status: str = Field(description="Stage status: waiting_for_title_abstract, ready, in_progress, completed, unresolved_conflict, stale_resolution")
    eligible_count: int = Field(ge=0)
    evaluated_count: int = Field(ge=0)
    conflict_count: int = Field(ge=0)
    resolved_count: int = Field(ge=0)


class QualityAssessmentStatusDTO(BaseModel):
    status: str = Field(description="Stage status: waiting_for_full_text, ready, in_progress, completed")
    eligible_count: int = Field(ge=0)


class ProjectWorkflowStatusResponse(BaseModel):
    project_id: str
    title_abstract_screening: TitleAbstractScreeningStatusDTO
    full_text_screening: FullTextScreeningStatusDTO
    quality_assessment: QualityAssessmentStatusDTO
