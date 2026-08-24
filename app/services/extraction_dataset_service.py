"""Phase 9.8 read models and deterministic structured extraction exports."""

from __future__ import annotations

import csv
import io
from typing import Any

from app.domain.extraction import (
    ExtractedGroupItemState,
    ExtractedValueState,
    ExtractionCompletenessStatus,
    ExtractionConfigurationNotFoundError,
    FieldDataType,
    PublicationExtractionReadModel,
    RelationshipExtractionReadModel,
    ValueStatus,
)
from app.domain.identifiers import IdentifierType
from app.repositories.extraction_repository import (
    SqliteExtractionRepository,
    default_extraction_repository,
)
from app.repositories.extraction_template_repository import (
    SqliteExtractionTemplateRepository,
    default_extraction_template_repository,
)
from app.repositories.project_publication_repository import (
    ProjectPublicationRepository,
    default_project_publication_repository,
)
from app.services.extraction_configuration_service import (
    ExtractionConfigurationService,
    default_extraction_configuration_service,
)
from app.services.extraction_eligibility_service import (
    ExtractionEligibilityService,
    default_extraction_eligibility_service,
)


class ExtractionDatasetService:
    """Build Phase 10-facing read models without exposing SQLite/EAV details."""

    def __init__(
        self,
        config_service: ExtractionConfigurationService | None = None,
        eligibility_service: ExtractionEligibilityService | None = None,
        template_repo: SqliteExtractionTemplateRepository | None = None,
        extraction_repo: SqliteExtractionRepository | None = None,
        publication_repo: ProjectPublicationRepository | None = None,
    ) -> None:
        self._config_service = config_service or default_extraction_configuration_service()
        self._eligibility_service = eligibility_service or default_extraction_eligibility_service()
        self._template_repo = template_repo or default_extraction_template_repository()
        self._extraction_repo = extraction_repo or default_extraction_repository()
        self._publication_repo = publication_repo or default_project_publication_repository()

    def get_publication_read_models(
        self,
        project_id: str,
        reviewer_id: str = "",
        *,
        status_filter: ExtractionCompletenessStatus | None = ExtractionCompletenessStatus.COMPLETE,
    ) -> list[PublicationExtractionReadModel]:
        """Return one model per publication, using only its latest revision."""
        config = self._configuration(project_id)
        eligibility = self._eligibility_service.get_eligible_publications(project_id, reviewer_id)
        eligible_ids = sorted(
            (result.publication_id for result in eligibility if result.is_eligible),
            key=str,
        )
        if not eligible_ids:
            return []

        # These are bounded batch reads: one publication collection read and one
        # latest-revision hydration (the latter is explicitly three SQL queries).
        publications = self._publication_repo.get_publications(project_id)
        publication_map = {publication.record_id: publication for publication in publications}
        try:
            revisions = self._extraction_repo.get_latest_revision_batch(
                project_id, eligible_ids, reviewer_id=reviewer_id
            )
        except TypeError:
            revisions = self._extraction_repo.get_latest_revision_batch(project_id, eligible_ids)

        models: list[PublicationExtractionReadModel] = []
        for publication_id in eligible_ids:
            revision = revisions.get(publication_id)
            if revision is None:
                continue
            if status_filter is not None and revision.completeness_status is not status_filter:
                continue

            publication = publication_map.get(publication_id)
            title = publication.title if publication else f"Publication {publication_id}"
            authors = [author.display_name for author in publication.authors] if publication else []
            year = publication.publication_year if publication else None
            doi = None
            journal = None
            if publication:
                doi = next(
                    (identifier.value for identifier in publication.identifiers if identifier.type is IdentifierType.DOI),
                    None,
                )
                journal = publication.venue.name if publication.venue else None

            models.append(
                PublicationExtractionReadModel(
                    project_id=project_id,
                    publication_id=publication_id,
                    canonical_title=title,
                    canonical_authors=authors,
                    canonical_publication_year=year,
                    canonical_doi=doi,
                    canonical_journal=journal,
                    template_id=config.template_id,
                    template_version=config.template_version,
                    completeness_status=revision.completeness_status,
                    latest_revision_index=revision.revision_index,
                    latest_revision_id=revision.revision_id,
                    reviewer_id=revision.reviewer_id,
                    submitted_at=revision.created_at,
                    publication_values=sorted(revision.publication_values, key=lambda value: value.field_key),
                    group_items=sorted(
                        revision.group_items,
                        key=lambda item: (item.group_key, item.item_index, str(item.group_item_id)),
                    ),
                )
            )
        return models

    def get_relationship_read_models(
        self,
        project_id: str,
        reviewer_id: str = "",
        *,
        status_filter: ExtractionCompletenessStatus | None = ExtractionCompletenessStatus.COMPLETE,
    ) -> list[RelationshipExtractionReadModel]:
        """Return one model per repeating-group item, preserving publication grain."""
        relationships: list[RelationshipExtractionReadModel] = []
        for publication in self.get_publication_read_models(
            project_id, reviewer_id=reviewer_id, status_filter=status_filter
        ):
            for item in publication.group_items:
                relationships.append(
                    RelationshipExtractionReadModel(
                        project_id=publication.project_id,
                        publication_id=publication.publication_id,
                        canonical_title=publication.canonical_title,
                        canonical_publication_year=publication.canonical_publication_year,
                        template_id=publication.template_id,
                        template_version=publication.template_version,
                        group_key=item.group_key,
                        group_item_id=item.group_item_id,
                        item_index=item.item_index,
                        reviewer_id=publication.reviewer_id,
                        submitted_at=publication.submitted_at,
                        relationship_values=sorted(item.values, key=lambda value: value.field_key),
                    )
                )
        return relationships

    def export_json(
        self,
        project_id: str,
        dataset: str = "publications",
        reviewer_id: str = "",
        *,
        status_filter: ExtractionCompletenessStatus | None = ExtractionCompletenessStatus.COMPLETE,
    ) -> list[dict[str, Any]]:
        """Return JSON-safe read models with stable value and multi-enum ordering."""
        if dataset == "relationships":
            return [_relationship_json(model) for model in self.get_relationship_read_models(
                project_id, reviewer_id, status_filter=status_filter
            )]
        return [_publication_json(model) for model in self.get_publication_read_models(
            project_id, reviewer_id, status_filter=status_filter
        )]

    def export_csv(
        self,
        project_id: str,
        dataset: str = "publications",
        reviewer_id: str = "",
        *,
        status_filter: ExtractionCompletenessStatus | None = ExtractionCompletenessStatus.COMPLETE,
    ) -> str:
        """Return a stable CSV for either the publication or relationship dataset."""
        config = self._configuration(project_id)
        template = self._template_repo.get_version(config.template_id, config.template_version)
        buffer = io.StringIO()
        writer = csv.writer(buffer, lineterminator="\n")

        if dataset == "relationships":
            relationship_models = self.get_relationship_read_models(
                project_id, reviewer_id, status_filter=status_filter
            )
            fields = _relationship_fields(template.repeating_groups)
            headers = [
                "project_id", "publication_id", "canonical_title", "canonical_publication_year",
                "template_id", "template_version", "group_key", "group_item_id", "item_index",
                "reviewer_id", "submitted_at",
            ] + _value_headers(fields)
            writer.writerow(headers)
            for relationship in relationship_models:
                values = {value.field_key: value for value in relationship.relationship_values}
                writer.writerow([
                    relationship.project_id, str(relationship.publication_id), relationship.canonical_title,
                    _csv_scalar(relationship.canonical_publication_year), relationship.template_id,
                    relationship.template_version, relationship.group_key, str(relationship.group_item_id),
                    relationship.item_index, relationship.reviewer_id, relationship.submitted_at.isoformat(),
                    *[cell for field in fields for cell in _serialize_csv_field(values.get(field.field_key), field.data_type)],
                ])
            return buffer.getvalue()

        publication_models = self.get_publication_read_models(
            project_id, reviewer_id, status_filter=status_filter
        )
        fields = list(template.publication_fields)
        headers = [
            "project_id", "publication_id", "canonical_title", "canonical_authors", "canonical_publication_year",
            "canonical_doi", "canonical_journal", "template_id", "template_version", "completeness_status",
            "latest_revision_index", "latest_revision_id", "reviewer_id", "submitted_at",
        ] + _value_headers(fields)
        writer.writerow(headers)
        for publication in publication_models:
            values = {value.field_key: value for value in publication.publication_values}
            writer.writerow([
                publication.project_id, str(publication.publication_id), publication.canonical_title,
                "; ".join(publication.canonical_authors), _csv_scalar(publication.canonical_publication_year),
                publication.canonical_doi or "", publication.canonical_journal or "", publication.template_id,
                publication.template_version, publication.completeness_status.value,
                publication.latest_revision_index, str(publication.latest_revision_id), publication.reviewer_id,
                publication.submitted_at.isoformat(),
                *[cell for field in fields for cell in _serialize_csv_field(values.get(field.field_key), field.data_type)],
            ])
        return buffer.getvalue()

    def _configuration(self, project_id: str):
        config = self._config_service.get_configuration(project_id)
        if config is None:
            raise ExtractionConfigurationNotFoundError(
                f"Project '{project_id}' has no extraction configuration."
            )
        return config


def _relationship_fields(groups):
    """Return a deterministic union of fields across all repeating groups."""
    fields = []
    seen = set()
    for group in groups:
        for field in group.field_definitions:
            if field.field_key not in seen:
                fields.append(field)
                seen.add(field.field_key)
    return fields


def _value_headers(fields) -> list[str]:
    headers: list[str] = []
    for field in fields:
        prefix = field.field_key
        headers.extend([
            prefix, f"{prefix}__status", f"{prefix}__origin",
            f"{prefix}__source_page", f"{prefix}__source_section", f"{prefix}__source_locator",
            f"{prefix}__source_quote", f"{prefix}__reviewer_note",
        ])
        if field.data_type is FieldDataType.NUMBER_WITH_UNIT:
            headers.insert(len(headers) - 5, f"{prefix}__unit")
    return headers


def _serialize_csv_field(value: ExtractedValueState | None, data_type: FieldDataType) -> list[str]:
    if value is None:
        result = ["", ValueStatus.UNASSESSED.value, ""]
        if data_type is FieldDataType.NUMBER_WITH_UNIT:
            result.append("")
        return result + ["", "", "", "", ""]

    if value.text_value is not None:
        typed = value.text_value
    elif value.int_value is not None:
        typed = str(value.int_value)
    elif value.float_value is not None:
        typed = str(value.float_value)
    elif value.bool_value is not None:
        typed = "true" if value.bool_value else "false"
    elif value.json_value is not None:
        typed = "; ".join(sorted(value.json_value))
    else:
        typed = ""

    result = [typed, value.status.value, value.origin.value if value.origin is not None else ""]
    if data_type is FieldDataType.NUMBER_WITH_UNIT:
        result.append(value.unit_value or "")
    return result + [
        value.source_page or "", value.source_section or "", value.source_locator or "",
        value.source_quote or "", value.reviewer_note or "",
    ]


def _publication_json(model: PublicationExtractionReadModel) -> dict[str, Any]:
    payload = model.model_dump(mode="json")
    payload["publication_values"] = [_value_json(value) for value in model.publication_values]
    payload["group_items"] = [_group_item_json(item) for item in model.group_items]
    return payload


def _relationship_json(model: RelationshipExtractionReadModel) -> dict[str, Any]:
    payload = model.model_dump(mode="json")
    payload["relationship_values"] = [_value_json(value) for value in model.relationship_values]
    return payload


def _group_item_json(item: ExtractedGroupItemState) -> dict[str, Any]:
    payload = item.model_dump(mode="json")
    payload["values"] = [_value_json(value) for value in sorted(item.values, key=lambda value: value.field_key)]
    return payload


def _value_json(value: ExtractedValueState) -> dict[str, Any]:
    payload = value.model_dump(mode="json")
    if value.json_value is not None:
        payload["json_value"] = sorted(value.json_value)
    return payload


def _csv_scalar(value: Any) -> Any:
    return "" if value is None else value


def default_extraction_dataset_service() -> ExtractionDatasetService:
    return ExtractionDatasetService()
