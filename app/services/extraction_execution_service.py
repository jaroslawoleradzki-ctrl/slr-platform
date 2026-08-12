"""Service for executing and persisting append-only Data Extraction revisions (Phase 9.4)."""

from __future__ import annotations

from uuid import UUID

from app.domain.extraction import (
    ExtractedGroupItemState,
    ExtractedValueState,
    ExtractionCompletenessStatus,
    ExtractionConfigurationNotFoundError,
    ExtractionIneligibleError,
    ExtractionRecord,
    ExtractionRevision,
    ExtractionValidationError,
)
from app.repositories.extraction_repository import (
    ExtractionRecordNotFoundError,
    SqliteExtractionRepository,
    default_extraction_repository,
)
from app.repositories.extraction_template_repository import (
    SqliteExtractionTemplateRepository,
    default_extraction_template_repository,
)
from app.services.extraction_configuration_service import (
    ExtractionConfigurationService,
    default_extraction_configuration_service,
)
from app.services.extraction_eligibility_service import (
    ExtractionEligibilityService,
    default_extraction_eligibility_service,
)


class ExtractionExecutionService:
    """Orchestrates append-only data extraction revision submissions and validations."""

    def __init__(
        self,
        config_service: ExtractionConfigurationService | None = None,
        eligibility_service: ExtractionEligibilityService | None = None,
        template_repo: SqliteExtractionTemplateRepository | None = None,
        extraction_repo: SqliteExtractionRepository | None = None,
    ) -> None:
        self._config_service = config_service or default_extraction_configuration_service()
        self._eligibility_service = eligibility_service or default_extraction_eligibility_service()
        self._template_repo = template_repo or default_extraction_template_repository()
        self._extraction_repo = extraction_repo or default_extraction_repository()

    def submit_revision(
        self,
        project_id: str,
        publication_id: UUID,
        reviewer_id: str,
        publication_values: list[ExtractedValueState],
        group_items: list[ExtractedGroupItemState] | None = None,
        *,
        mark_complete: bool = False,
    ) -> ExtractionRevision:
        """Submits an append-only extraction revision for a publication.

        Steps:
        1. Check project extraction configuration.
        2. Enforce extraction eligibility via ExtractionEligibilityService.
        3. Fetch immutable template version.
        4. Validate field values and repeating groups.
        5. Calculate server-side completeness status.
        6. If mark_complete is True and status is not COMPLETE, fail with ExtractionValidationError.
        7. Ensure/create extraction record header if first revision.
        8. Build append-only revision (revision_index = next available index).
        9. Persist revision and update record current_status atomically.
        """
        # 1. Project extraction configuration check
        config = self._config_service.get_configuration(project_id)
        if config is None:
            raise ExtractionConfigurationNotFoundError(
                f"Project '{project_id}' has no extraction configuration."
            )

        # 2. Eligibility Gate
        eligibility = self._eligibility_service.evaluate_publication(
            project_id, publication_id, reviewer_id=reviewer_id
        )
        if not eligibility.is_eligible:
            raise ExtractionIneligibleError(
                project_id=project_id,
                publication_id=publication_id,
                status=eligibility.status,
                reason_details=eligibility.reason_details,
            )

        # 3. Resolve template version
        version = self._template_repo.get_version(config.template_id, config.template_version)
        if not version.is_active or not version.is_published:
            raise ValueError(
                f"Extraction template version '{config.template_id}' v{config.template_version} is not active and published."
            )

        # 4. Get/Create ExtractionRecord header
        try:
            record = self._extraction_repo.get_record(project_id, publication_id)
        except ExtractionRecordNotFoundError:
            record = ExtractionRecord(
                project_id=project_id,
                publication_id=publication_id,
                template_id=config.template_id,
                template_version=config.template_version,
                current_status=ExtractionCompletenessStatus.NOT_STARTED,
            )
            record = self._extraction_repo.create_record(record)

        # Calculate next revision index
        history = self._extraction_repo.list_revision_history(project_id, publication_id)
        next_index = len(history) + 1

        items = group_items or []

        # Construct temporary draft revision for validation & completeness computation
        draft_revision = ExtractionRevision(
            record_id=record.record_id,
            project_id=project_id,
            publication_id=publication_id,
            revision_index=next_index,
            reviewer_id=reviewer_id,
            completeness_status=ExtractionCompletenessStatus.IN_PROGRESS,
            publication_values=publication_values,
            group_items=items,
        )

        # Validate against template structure
        validation_errors = version.validate_revision(draft_revision)

        # Calculate server-side completeness status
        if not validation_errors:
            completeness = ExtractionCompletenessStatus.COMPLETE
        else:
            completeness = ExtractionCompletenessStatus.IN_PROGRESS

        # If user explicitly requested mark_complete, but completeness is not COMPLETE:
        if mark_complete and completeness != ExtractionCompletenessStatus.COMPLETE:
            raise ExtractionValidationError(
                [
                    f"Cannot mark extraction as COMPLETE: {err}"
                    for err in validation_errors
                ]
                if validation_errors
                else ["Extraction record is incomplete."]
            )

        # For Save Draft (mark_complete=False), structural/value-type errors must still fail!
        if not mark_complete and validation_errors:
            structural_errors = [
                err
                for err in validation_errors
                if not (
                    "is missing" in err
                    or "requires at least" in err
                    or "missing in group" in err
                )
            ]
            if structural_errors:
                raise ExtractionValidationError(structural_errors)

        # Build final revision with calculated completeness
        final_revision = ExtractionRevision(
            record_id=record.record_id,
            project_id=project_id,
            publication_id=publication_id,
            revision_index=next_index,
            reviewer_id=reviewer_id,
            completeness_status=completeness,
            publication_values=publication_values,
            group_items=items,
        )

        # Persist revision atomically
        return self._extraction_repo.append_revision(final_revision)

    def get_latest_revision(
        self, project_id: str, publication_id: UUID
    ) -> ExtractionRevision | None:
        """Returns latest extraction revision for publication, or None."""
        return self._extraction_repo.get_latest_revision(project_id, publication_id)

    def get_record(self, project_id: str, publication_id: UUID) -> ExtractionRecord | None:
        """Returns extraction record header, or None if not started."""
        try:
            return self._extraction_repo.get_record(project_id, publication_id)
        except ExtractionRecordNotFoundError:
            return None

    def get_revision_history(
        self, project_id: str, publication_id: UUID
    ) -> list[ExtractionRevision]:
        """Returns append-only history of extraction revisions for publication."""
        return self._extraction_repo.list_revision_history(project_id, publication_id)


def default_extraction_execution_service() -> ExtractionExecutionService:
    return ExtractionExecutionService()
