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

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from uuid import UUID

from app.domain.extraction import (
    ExtractionCompletenessStatus,
    ExtractionTemplateVersion,
    PublicationExtractionReadModel,
)
from app.domain.publication import Publication
from app.domain.quality_assessment import (
    QualityAssessmentResponse,
    QualityAssessmentTemplateCriterion,
)
from app.domain.screening import ScreeningDecision
from app.domain.synthesis import AnalyticalRelation, ClassificationApprovalState
from app.repositories.extraction_template_repository import (
    ExtractionTemplateNotFoundError,
    SqliteExtractionTemplateRepository,
    default_extraction_template_repository,
)
from app.repositories.project_publication_repository import (
    ProjectPublicationRepository,
    default_project_publication_repository,
)
from app.repositories.screening_reporting_repository import (
    ScreeningReportingRepository,
    default_screening_reporting_repository,
)
from app.services.extraction_configuration_service import (
    ExtractionConfigurationService,
    default_extraction_configuration_service,
)
from app.services.extraction_dataset_service import (
    ExtractionDatasetService,
    default_extraction_dataset_service,
)
from app.services.prisma_metrics_service import PrismaMetrics, PrismaMetricsService


@dataclass(frozen=True, slots=True)
class BibliographicEntry:
    """Active canonical record paired with its persisted collection position."""

    position: int
    publication: Publication


@dataclass(frozen=True, slots=True)
class QualityAssessmentRow:
    """One assessed publication with its responses keyed by criterion id."""

    publication_id: UUID
    reviewer_id: str
    template_id: str
    template_version: int
    responses_by_criterion: dict[UUID, QualityAssessmentResponse]
    assessed_at: datetime


@dataclass(frozen=True, slots=True)
class QualityAssessmentSheetData:
    """Configured-template criteria plus one row per assessed publication."""

    criteria: tuple[QualityAssessmentTemplateCriterion, ...]
    rows: tuple[QualityAssessmentRow, ...]


def _build_prisma_service_for_database(publication_repository, database_path: Path, reporting_repository):
    """Construct a PrismaMetricsService whose collaborators share one SQLite file.

    Mirrors the accepted PRISMA API-test wiring (tests/unit/api/test_prisma_metrics_api.py):
    every collaborator is bound to the same database so metrics never mix state
    across databases. Semantics (D4) are untouched — same service class, same
    counting logic.
    """
    from app.repositories.conflict_resolution_repository import SqliteConflictResolutionRepository
    from app.repositories.duplicate_review_decision_repository import SqliteDuplicateReviewDecisionRepository
    from app.repositories.import_history_repository import SqliteImportHistoryRepository
    from app.repositories.screening_decision_repository import SqliteScreeningDecisionRepository
    from app.repositories.screening_reviewer_assignment_repository import SqliteScreeningReviewerAssignmentRepository
    from app.services.duplicate_group_builder import DuplicateGroupBuilder
    from app.services.multi_reviewer_screening_service import MultiReviewerScreeningService
    from app.services.project_workflow_status_service import ProjectWorkflowStatusService
    from app.services.screening_eligibility_adapter import ScreeningEligibilityAdapter
    from app.services.screening_input_service import ScreeningInputService

    duplicate_decisions = SqliteDuplicateReviewDecisionRepository(database_path)
    screening_decisions = SqliteScreeningDecisionRepository(database_path)
    assignments = SqliteScreeningReviewerAssignmentRepository(database_path)
    resolutions = SqliteConflictResolutionRepository(database_path)

    input_service = ScreeningInputService(publication_repository, duplicate_decisions)
    multi_reviewer = MultiReviewerScreeningService(
        assignments=assignments,
        reporting=reporting_repository,
        resolutions=resolutions,
        input_service=input_service,
    )
    eligibility_adapter = ScreeningEligibilityAdapter(
        input_service=input_service,
        assignments_repo=assignments,
        decisions_repo=screening_decisions,
        multi_reviewer_service=multi_reviewer,
    )
    workflow_status = ProjectWorkflowStatusService(
        publication_repository=publication_repository,
        decision_repository=screening_decisions,
        assignment_repository=assignments,
        resolution_repository=resolutions,
        reporting_repository=reporting_repository,
        input_service=input_service,
        multi_reviewer_service=multi_reviewer,
        eligibility_adapter=eligibility_adapter,
    )
    return PrismaMetricsService(
        publication_repository=publication_repository,
        import_history_repository=SqliteImportHistoryRepository(database_path),
        decision_repository=duplicate_decisions,
        workflow_status_service=workflow_status,
        builder=DuplicateGroupBuilder(),
    )


class ExportDatasetService:
    """Read-only facade over the datasets consumed by export serializers."""

    def __init__(
        self,
        publication_repository: ProjectPublicationRepository | None = None,
        extraction_service: ExtractionDatasetService | None = None,
        prisma_service: PrismaMetricsService | None = None,
        screening_reporting_repository: ScreeningReportingRepository | None = None,
        extraction_configuration_service: ExtractionConfigurationService | None = None,
        extraction_template_repository: SqliteExtractionTemplateRepository | None = None,
        qa_configuration_repository=None,
        qa_catalog_repository=None,
        qa_repository=None,
        synthesis_matrix_repository=None,
    ) -> None:
        self._publication_repository = publication_repository or default_project_publication_repository()
        self._extraction_service = extraction_service or default_extraction_dataset_service()
        self._screening_reporting = screening_reporting_repository or default_screening_reporting_repository()
        # Bind the metrics service to THIS facade's database when the injected
        # repository carries its own path (test/isolation databases); the
        # module-level singleton is pinned to the environment path at import
        # time. The collaborator graph mirrors the accepted PRISMA wiring.
        if prisma_service is not None:
            self._prisma_service = prisma_service
        else:
            database_path = getattr(self._publication_repository, "database_path", None)
            if database_path is not None:
                self._prisma_service = _build_prisma_service_for_database(
                    self._publication_repository, Path(database_path), self._screening_reporting
                )
            else:
                self._prisma_service = PrismaMetricsService(
                    publication_repository=self._publication_repository
                )
        self._extraction_configuration = extraction_configuration_service or default_extraction_configuration_service()
        self._extraction_template_repository = (
            extraction_template_repository or default_extraction_template_repository()
        )

        if qa_configuration_repository is None:
            from app.repositories.sqlite_quality_assessment_repository import (
                default_project_quality_assessment_configuration_repository,
            )

            qa_configuration_repository = default_project_quality_assessment_configuration_repository()
        self._qa_configuration_repository = qa_configuration_repository
        if qa_catalog_repository is None:
            from app.repositories.sqlite_quality_assessment_repository import (
                default_quality_assessment_catalog_repository,
            )

            qa_catalog_repository = default_quality_assessment_catalog_repository()
        self._qa_catalog_repository = qa_catalog_repository
        if qa_repository is None:
            from app.repositories.sqlite_quality_assessment_repository import (
                default_quality_assessment_repository,
            )

            qa_repository = default_quality_assessment_repository()
        self._qa_repository = qa_repository
        if synthesis_matrix_repository is None:
            from app.repositories.synthesis_matrix_repository import default_synthesis_matrix_repository

            synthesis_matrix_repository = default_synthesis_matrix_repository()
        self._synthesis_matrix_repository = synthesis_matrix_repository

    # ------------------------------------------------------------------
    # Slice 1 foundation
    # ------------------------------------------------------------------

    def get_bibliographic_records(self, project_id: str) -> list[Publication]:
        """Return active canonical records ordered by collection position.

        This is the single source of truth for bibliographic exports: it
        reuses ``ProjectPublicationRepository.get_active_publications``
        (``superseded_by IS NULL ORDER BY position ASC, rowid ASC``) so the
        exported set matches the Working Collection exactly.
        """
        return self._publication_repository.get_active_publications(project_id)

    def get_bibliographic_entries(self, project_id: str) -> list[BibliographicEntry]:
        """Active canonical records paired with their persisted positions."""
        getter = getattr(self._publication_repository, "get_active_publications_with_position", None)
        if callable(getter):
            return [BibliographicEntry(position=position, publication=pub) for position, pub in getter(project_id)]
        return [
            BibliographicEntry(position=index + 1, publication=publication)
            for index, publication in enumerate(self.get_bibliographic_records(project_id))
        ]

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

    # ------------------------------------------------------------------
    # Slice 2 additions (XLSX research matrix sources)
    # ------------------------------------------------------------------

    def get_screening_decisions(
        self, project_id: str, reviewer_id: str = "default_reviewer"
    ) -> list[ScreeningDecision]:
        """Latest recorded decision per publication/stage/reviewer, active records only.

        Source semantics match the plan (§11): the screening reporting
        repository's latest-decision-wins read, restricted to active canonical
        publications so superseded duplicates never appear.
        """
        decisions = self._screening_reporting.latest_decisions(project_id, reviewer_id)
        active_ids = {publication.record_id for publication in self.get_bibliographic_records(project_id)}
        return [decision for decision in decisions if decision.publication_id in active_ids]

    def get_extraction_template(self, project_id: str) -> ExtractionTemplateVersion | None:
        """Return the configured extraction template version, or ``None``.

        ``None`` means the project has no extraction configuration (or the
        configured template is unavailable); consumers emit a headers-only
        sheet instead of failing.
        """
        config = self._extraction_configuration.get_configuration(project_id)
        if config is None:
            return None
        try:
            return self._extraction_template_repository.get_version(config.template_id, config.template_version)
        except ExtractionTemplateNotFoundError:
            return None

    def get_quality_assessment_sheet_data(self, project_id: str) -> QualityAssessmentSheetData | None:
        """Assemble QA sheet inputs: configured criteria plus assessed-publication rows.

        Rows cover every active publication that has a persisted assessment
        (latest across reviewers). ``None`` signals no project QA configuration;
        consumers emit a headers-only sheet.
        """
        configuration = self._qa_configuration_repository.get_configuration(project_id)
        if configuration is None:
            return None
        template = self._qa_catalog_repository.get_template_version(configuration.template_id)
        if template is None:
            return None
        criteria = tuple(
            sorted(template.criteria, key=lambda criterion: (criterion.display_order, str(criterion.criterion_id)))
        )

        rows: list[QualityAssessmentRow] = []
        for publication in self.get_bibliographic_records(project_id):
            assessment = self._qa_repository.get_latest_assessment(project_id, publication.record_id, "")
            if assessment is None:
                continue
            rows.append(
                QualityAssessmentRow(
                    publication_id=publication.record_id,
                    reviewer_id=assessment.reviewer_id,
                    template_id=str(assessment.template_id),
                    template_version=template.version,
                    responses_by_criterion={
                        response.criterion_id: response for response in assessment.responses
                    },
                    assessed_at=assessment.assessed_at,
                )
            )
        return QualityAssessmentSheetData(criteria=criteria, rows=tuple(rows))

    def get_approved_synthesis_relations(self, project_id: str) -> list[AnalyticalRelation]:
        """Approved analytical relations of active publications, in persistence order."""
        relations = self._synthesis_matrix_repository.list_analytical_relations(project_id)
        active_ids = {publication.record_id for publication in self.get_bibliographic_records(project_id)}
        return [
            relation
            for relation in relations
            if relation.approval_state is ClassificationApprovalState.APPROVED
            and relation.publication_id in active_ids
        ]


def default_export_dataset_service() -> ExportDatasetService:
    return ExportDatasetService()
