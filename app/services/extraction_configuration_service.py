"""Service for managing project-level data extraction template configuration."""

from __future__ import annotations

from datetime import datetime, timezone

from app.domain.extraction import (
    ExtractionConfigurationLockedError,
    ProjectExtractionConfiguration,
)
from app.repositories.extraction_repository import (
    SqliteExtractionRepository,
    default_extraction_repository,
)
from app.repositories.extraction_template_repository import (
    SqliteExtractionTemplateRepository,
    default_extraction_template_repository,
)
from app.repositories.project_repository import (
    ProjectRepository,
    default_project_repository,
)


class ExtractionConfigurationService:
    """Manages project extraction template version selection and immutability rules."""

    def __init__(
        self,
        extraction_repo: SqliteExtractionRepository | None = None,
        template_repo: SqliteExtractionTemplateRepository | None = None,
        project_repo: ProjectRepository | None = None,
    ) -> None:
        self._extraction_repo = extraction_repo or default_extraction_repository()
        self._template_repo = template_repo or default_extraction_template_repository()
        self._project_repo = project_repo or default_project_repository()

    def get_configuration(self, project_id: str) -> ProjectExtractionConfiguration | None:
        """Retrieves active extraction configuration for project_id, or None if unconfigured."""
        return self._extraction_repo.get_project_configuration(project_id)

    def set_configuration(
        self, project_id: str, template_id: str, template_version: str
    ) -> ProjectExtractionConfiguration:
        """Sets or updates extraction configuration for project_id.

        Validates:
        1. Project exists.
        2. Template and version exist in template repository and are active/published.
        3. Enforces change-lock if extraction records already exist for the project.
        """
        # 1. Project check (raises ProjectNotFoundError if missing)
        self._project_repo.get(project_id)

        # 2. Template and Version existence & state check
        version = self._template_repo.get_version(template_id, template_version)
        if not version.is_active or not version.is_published:
            raise ValueError(
                f"Template version '{template_id}' v{template_version} is not active and published."
            )

        # 3. Check for existing extraction records in project (immutability rule)
        existing_records = self._extraction_repo.list_records(project_id)
        current_config = self.get_configuration(project_id)

        if existing_records and current_config:
            if (
                current_config.template_id != template_id
                or current_config.template_version != template_version
            ):
                raise ExtractionConfigurationLockedError(
                    f"Cannot change extraction configuration for project '{project_id}' "
                    f"because {len(existing_records)} extraction record(s) already exist."
                )

        now = datetime.now(timezone.utc)
        config = ProjectExtractionConfiguration(
            project_id=project_id,
            template_id=template_id,
            template_version=template_version,
            configured_at=current_config.configured_at if current_config else now,
            updated_at=now,
        )
        return self._extraction_repo.set_project_configuration(config)

    def delete_configuration(self, project_id: str) -> bool:
        """Deletes extraction configuration for project_id."""
        return self._extraction_repo.delete_project_configuration(project_id)


def default_extraction_configuration_service() -> ExtractionConfigurationService:
    return ExtractionConfigurationService()
