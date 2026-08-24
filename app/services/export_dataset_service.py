"""v0.6.1 read-only export dataset facade (plan §5.1).

Single authoritative query layer for every export format. The boundary for
"final publications" is the repository's own ``get_active_publications`` —
the canonical-lifecycle filtering introduced in v0.5.7 is reused verbatim and
never duplicated here, so superseded duplicate records structurally cannot
surface in any research export.

The facade is strictly read-only: repositories are invoked through read
methods only and no state is persisted or mutated during export.
"""

from __future__ import annotations

from app.domain.extraction import ExtractionCompletenessStatus, PublicationExtractionReadModel
from app.domain.publication import Publication
from app.repositories.project_publication_repository import (
    ProjectPublicationRepository,
    default_project_publication_repository,
)
from app.services.extraction_dataset_service import (
    ExtractionDatasetService,
    default_extraction_dataset_service,
)
from app.services.prisma_metrics_service import PrismaMetrics, PrismaMetricsService, default_prisma_metrics_service


class ExportDatasetService:
    """Read-only facade over the datasets consumed by export serializers."""

    def __init__(
        self,
        publication_repository: ProjectPublicationRepository | None = None,
        extraction_service: ExtractionDatasetService | None = None,
        prisma_service: PrismaMetricsService | None = None,
    ) -> None:
        self._publication_repository = publication_repository or default_project_publication_repository()
        self._extraction_service = extraction_service or default_extraction_dataset_service()
        self._prisma_service = prisma_service or default_prisma_metrics_service

    def get_bibliographic_records(self, project_id: str) -> list[Publication]:
        """Return active canonical records ordered by collection position.

        This is the single source of truth for bibliographic exports: it
        reuses ``ProjectPublicationRepository.get_active_publications``
        (``superseded_by IS NULL ORDER BY position ASC, rowid ASC``) so the
        exported set matches the Working Collection exactly.
        """
        return self._publication_repository.get_active_publications(project_id)

    def get_extraction_read_models(
        self,
        project_id: str,
        reviewer_id: str = "",
        *,
        status_filter: ExtractionCompletenessStatus | None = ExtractionCompletenessStatus.COMPLETE,
    ) -> list[PublicationExtractionReadModel]:
        """Delegate to the Phase 9.8 dataset service (reuse, not duplication)."""
        return self._extraction_service.get_publication_read_models(
            project_id, reviewer_id, status_filter=status_filter
        )

    def get_prisma_metrics(self, project_id: str, reviewer_id: str = "default_reviewer") -> PrismaMetrics:
        """Delegate to the authoritative PRISMA metrics service."""
        return self._prisma_service.get_metrics(project_id, reviewer_id=reviewer_id)


def default_export_dataset_service() -> ExportDatasetService:
    return ExportDatasetService()
