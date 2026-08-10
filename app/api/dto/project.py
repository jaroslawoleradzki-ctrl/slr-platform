from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domain.project import Project, ProjectStatus


class ProjectCreateRequest(BaseModel):
    """Client payload for creating a new SLR project."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, description="Title/name of the project.")
    description: str | None = Field(
        default=None, description="Optional description of the review scope."
    )
    protocol_version: str = Field(
        default="1.0", min_length=1, description="Protocol version specification."
    )


class ProjectUpdateRequest(BaseModel):
    """Client payload for updating project metadata."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, description="Updated title/name.")
    description: str | None = Field(default=None, description="Updated description.")
    protocol_version: str = Field(min_length=1, description="Updated protocol version.")


class ProjectResponse(BaseModel):
    """API response model for an SLR project."""

    model_config = ConfigDict(extra="forbid")

    project_id: str = Field(description="Unique, immutable project identifier.")
    title: str = Field(description="Project title.")
    description: str | None = Field(description="Project description.")
    protocol_version: str = Field(description="Protocol version.")
    status: ProjectStatus = Field(description="Project status ('active' or 'archived').")
    created_at: datetime = Field(description="Timezone-aware creation timestamp.")
    updated_at: datetime = Field(description="Timezone-aware last update timestamp.")

    @classmethod
    def from_domain(cls, project: Project) -> ProjectResponse:
        return cls(
            project_id=project.project_id,
            title=project.title,
            description=project.description,
            protocol_version=project.protocol_version,
            status=project.status,
            created_at=project.created_at,
            updated_at=project.updated_at,
        )


class ProjectListResponse(BaseModel):
    """API response model for listing projects."""

    model_config = ConfigDict(extra="forbid")

    items: list[ProjectResponse] = Field(description="List of projects.")
    total: int = Field(description="Total number of projects returned.")
