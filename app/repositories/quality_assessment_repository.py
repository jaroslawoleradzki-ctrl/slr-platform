from __future__ import annotations

from typing import Any, Protocol, runtime_checkable
from uuid import UUID

from app.domain.quality_assessment import (
    ProjectQualityAssessmentConfiguration,
    QualityAssessment,
    QualityAssessmentTemplate,
    QualityAssessmentTool,
)


@runtime_checkable
class QualityAssessmentCatalogRepository(Protocol):
    """Abstract protocol for immutable tool and versioned template catalog storage."""

    def create_tool(self, tool: QualityAssessmentTool, connection: Any = None) -> QualityAssessmentTool: ...

    def get_tool(self, tool_id: str, connection: Any = None) -> QualityAssessmentTool | None: ...

    def list_tools(self, connection: Any = None) -> list[QualityAssessmentTool]: ...

    def create_template_version(
        self, template: QualityAssessmentTemplate, connection: Any = None
    ) -> QualityAssessmentTemplate: ...

    def get_template_version(
        self, template_id: UUID, connection: Any = None
    ) -> QualityAssessmentTemplate | None: ...

    def get_template_version_by_key(
        self, tool_id: str, template_key: str, version: int, connection: Any = None
    ) -> QualityAssessmentTemplate | None: ...

    def list_template_versions(
        self,
        tool_id: str | None = None,
        template_key: str | None = None,
        is_active_only: bool = False,
        connection: Any = None,
    ) -> list[QualityAssessmentTemplate]: ...

    def set_template_version_active(
        self, template_id: UUID, is_active: bool, connection: Any = None
    ) -> None: ...


@runtime_checkable
class QualityAssessmentRepository(Protocol):
    """Abstract protocol for publication quality assessments storage (Append-only)."""

    def save_assessment(self, assessment: QualityAssessment, connection: Any = None) -> QualityAssessment: ...

    def get_latest_assessment(
        self, project_id: str, publication_id: UUID, reviewer_id: str, connection: Any = None
    ) -> QualityAssessment | None: ...

    def list_assessments_for_publication(
        self, project_id: str, publication_id: UUID, reviewer_id: str, connection: Any = None
    ) -> list[QualityAssessment]: ...

    def delete_for_project(self, project_id: str, connection: Any = None) -> None: ...


@runtime_checkable
class ProjectQualityAssessmentConfigurationRepository(Protocol):
    """Abstract protocol for project-scoped Quality Assessment active configuration storage."""

    def save_configuration(
        self, config: ProjectQualityAssessmentConfiguration, connection: Any = None
    ) -> ProjectQualityAssessmentConfiguration: ...

    def get_configuration(
        self, project_id: str, connection: Any = None
    ) -> ProjectQualityAssessmentConfiguration | None: ...

    def delete_for_project(self, project_id: str, connection: Any = None) -> None: ...
