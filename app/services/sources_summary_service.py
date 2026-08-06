from __future__ import annotations

from typing import Literal, cast
from app.api.dto.sources_summary import (
    ImportHistoryItemDTO,
    SourceSummaryItem,
    SourcesSummaryResponse,
    WorkingCollectionSummary,
)
from app.repositories.import_history_repository import (
    ImportHistoryRepository,
    default_import_history_repository,
)
from app.repositories.project_publication_repository import (
    ProjectPublicationRepository,
    default_project_publication_repository,
)


class SourcesSummaryService:
    """Service building backend read model for Sources & Imports screen."""

    def __init__(
        self,
        publication_repository: ProjectPublicationRepository | None = None,
        import_history_repository: ImportHistoryRepository | None = None,
    ) -> None:
        self._pub_repo = publication_repository or default_project_publication_repository()
        self._history_repo = import_history_repository or default_import_history_repository()

    def get_sources_summary(self, project_id: str) -> SourcesSummaryResponse:
        # 1. Total records in Working Collection directly from publication repository count
        total_records = self._pub_repo.count_by_project(project_id)

        # 2. Get import history
        raw_history = self._history_repo.list_for_project(project_id)

        # 3. Transform import history into lightweight DTO list (sorted created_at DESC, import_id DESC)
        import_history_dtos = [
            ImportHistoryItemDTO(
                import_id=rec.import_id,
                source_type=cast(Literal["provider", "file"], rec.source_type),
                filename=rec.filename,
                format=rec.format,
                provider=rec.provider,
                query=rec.query,
                records_count=rec.records_count,
                status=cast(Literal["success", "warning", "failed"], rec.status),
                warnings=rec.warnings,
                created_at=rec.created_at,
            )
            for rec in sorted(
                raw_history,
                key=lambda x: (x.created_at, str(x.import_id)),
                reverse=True,
            )
        ]

        # 4. Group summaries per source using normalized machine-friendly identifiers
        source_groups: dict[tuple[str, Literal["provider", "file"]], list[ImportHistoryItemDTO]] = {}
        for item in import_history_dtos:
            if item.source_type == "provider":
                raw_source = item.provider or "provider"
            else:
                raw_source = item.format or "file"
            
            source_name = raw_source.lower()
            key = (source_name, item.source_type)
            source_groups.setdefault(key, []).append(item)

        source_summaries: list[SourceSummaryItem] = []
        for (source_name, source_kind), items in source_groups.items():
            # Sort items for this source by created_at DESC, import_id DESC to get latest import
            sorted_items = sorted(
                items, key=lambda x: (x.created_at, str(x.import_id)), reverse=True
            )
            latest = sorted_items[0]

            successful_count = sum(1 for i in items if i.status == "success")
            warning_count = sum(1 for i in items if i.status == "warning")
            failed_count = sum(1 for i in items if i.status == "failed")
            records_added = sum(i.records_count for i in items if i.status in ("success", "warning"))

            source_summaries.append(
                SourceSummaryItem(
                    source=source_name,
                    source_kind=source_kind,
                    successful_imports_count=successful_count,
                    warning_imports_count=warning_count,
                    failed_imports_count=failed_count,
                    records_added_count=records_added,
                    last_import_at=latest.created_at,
                    last_import_status=latest.status,
                )
            )

        # Sort source summaries deterministically by source_kind then source
        source_summaries.sort(key=lambda s: (s.source_kind, s.source.casefold()))

        return SourcesSummaryResponse(
            project_id=project_id,
            working_collection=WorkingCollectionSummary(total_records=total_records),
            source_summaries=source_summaries,
            import_history=import_history_dtos,
        )


default_sources_summary_service = SourcesSummaryService()
