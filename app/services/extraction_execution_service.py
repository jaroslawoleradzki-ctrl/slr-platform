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

    def get_progress(self, project_id: str, reviewer_id: str = "") -> dict:
        """Returns project extraction progress metrics (Phase 9.6)."""
        eligibility_results = self._eligibility_service.get_eligible_publications(project_id, reviewer_id)
        eligible_items = [res for res in eligibility_results if res.is_eligible]
        total_eligible = len(eligible_items)

        if total_eligible == 0:
            return {
                "project_id": project_id,
                "total_eligible_publications": 0,
                "not_started_count": 0,
                "in_progress_count": 0,
                "complete_count": 0,
                "needs_review_count": 0,
                "completion_percentage": 0.0,
            }

        eligible_pub_ids = [res.publication_id for res in eligible_items]
        latest_revisions = self._extraction_repo.get_latest_revision_batch(project_id, eligible_pub_ids)

        not_started = 0
        in_progress = 0
        complete = 0
        needs_review = 0

        for pub_id in eligible_pub_ids:
            rev = latest_revisions.get(pub_id)
            if rev is None:
                not_started += 1
            elif rev.completeness_status is ExtractionCompletenessStatus.IN_PROGRESS:
                in_progress += 1
            elif rev.completeness_status is ExtractionCompletenessStatus.COMPLETE:
                complete += 1
            elif rev.completeness_status is ExtractionCompletenessStatus.NEEDS_REVIEW:
                needs_review += 1
            else:
                not_started += 1

        completion_pct = round((complete / total_eligible) * 100.0, 1)

        return {
            "project_id": project_id,
            "total_eligible_publications": total_eligible,
            "not_started_count": not_started,
            "in_progress_count": in_progress,
            "complete_count": complete,
            "needs_review_count": needs_review,
            "completion_percentage": completion_pct,
        }

    def list_record_summaries(self, project_id: str, reviewer_id: str = "") -> list[dict]:
        """Returns batch-hydrated list of publication extraction record summaries (Phase 9.6)."""
        eligibility_results = self._eligibility_service.get_eligible_publications(project_id, reviewer_id)
        eligible_items = [res for res in eligibility_results if res.is_eligible]
        if not eligible_items:
            return []

        eligible_pub_ids = [res.publication_id for res in eligible_items]
        eligible_set = set(eligible_pub_ids)

        # Batch fetch publication metadata
        pubs_input = self._eligibility_service._input_service.get_input_set(project_id)
        pubs_by_id = {pub.record_id: pub for pub in pubs_input.publications if pub.record_id in eligible_set}

        # Batch fetch latest extraction revisions
        latest_revisions = self._extraction_repo.get_latest_revision_batch(project_id, eligible_pub_ids)

        summaries = []
        for pub_id in eligible_pub_ids:
            pub = pubs_by_id.get(pub_id)
            rev = latest_revisions.get(pub_id)

            status = rev.completeness_status.value if rev is not None else ExtractionCompletenessStatus.NOT_STARTED.value
            title = pub.title if pub else f"Publication {pub_id}"
            authors = pub.authors if pub else []
            year = pub.publication_year if pub else None

            summaries.append({
                "publication_id": pub_id,
                "title": title,
                "authors": authors,
                "publication_year": year,
                "extraction_status": status,
                "latest_revision_index": rev.revision_index if rev else None,
                "latest_reviewer_id": rev.reviewer_id if rev else None,
                "latest_updated_at": rev.created_at.isoformat() if rev else None,
            })

        return summaries

    def get_matrix(self, project_id: str, reviewer_id: str = "") -> dict:
        """Returns cross-study repeating group matrix items (Phase 9.6)."""
        config = self._config_service.get_configuration(project_id)
        if config is None:
            raise ExtractionConfigurationNotFoundError(f"Project '{project_id}' has no extraction configuration.")

        template_ver = self._template_repo.get_version(config.template_id, config.template_version)
        if template_ver is None:
            raise ExtractionConfigurationNotFoundError(
                f"Template version '{config.template_id} v{config.template_version}' not found."
            )

        group_keys = [g.group_key for g in template_ver.repeating_groups]
        group_names = {g.group_key: g.name for g in template_ver.repeating_groups}

        eligibility_results = self._eligibility_service.get_eligible_publications(project_id, reviewer_id)
        eligible_items = [res for res in eligibility_results if res.is_eligible]
        eligible_pub_ids = [res.publication_id for res in eligible_items]

        if not eligible_pub_ids:
            return {
                "project_id": project_id,
                "template_id": config.template_id,
                "template_version": config.template_version,
                "total_relationships": 0,
                "group_keys": group_keys,
                "items": [],
            }

        eligible_set = set(eligible_pub_ids)
        pubs_input = self._eligibility_service._input_service.get_input_set(project_id)
        pubs_by_id = {pub.record_id: pub for pub in pubs_input.publications if pub.record_id in eligible_set}

        latest_revisions = self._extraction_repo.get_latest_revision_batch(project_id, eligible_pub_ids)

        matrix_rows = []
        for pub_id in eligible_pub_ids:
            pub = pubs_by_id.get(pub_id)
            rev = latest_revisions.get(pub_id)
            if not rev or not rev.group_items:
                continue

            pub_title = pub.title if pub else f"Publication {pub_id}"

            for item in rev.group_items:
                matrix_rows.append({
                    "publication_id": pub_id,
                    "publication_title": pub_title,
                    "group_key": item.group_key,
                    "group_name": group_names.get(item.group_key, item.group_key),
                    "group_item_id": item.group_item_id,
                    "item_index": item.item_index,
                    "values": item.values,
                })

        return {
            "project_id": project_id,
            "template_id": config.template_id,
            "template_version": config.template_version,
            "total_relationships": len(matrix_rows),
            "group_keys": group_keys,
            "items": matrix_rows,
        }


def default_extraction_execution_service() -> ExtractionExecutionService:
    return ExtractionExecutionService()
