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
    QualityAssessment,
    QualityAssessmentResponse,
    QualityAssessmentTemplate,
    QualityAssessmentTemplateCriterion,
)
from app.domain.screening import ScreeningDecision
from app.domain.synthesis import AnalyticalRelation, ClassificationApprovalState
from app.repositories.extraction_repository import SqliteExtractionRepository
from app.repositories.extraction_template_repository import (
    ExtractionTemplateNotFoundError,
    SqliteExtractionTemplateRepository,
    default_extraction_template_repository,
)
from app.repositories.project_publication_repository import (
    ProjectPublicationRepository,
    default_project_publication_repository,
)
from app.repositories.project_repository import SqliteProjectRepository
from app.repositories.screening_reporting_repository import (
    ScreeningReportingRepository,
    default_screening_reporting_repository,
)
from app.repositories.sqlite_quality_assessment_repository import (
    SqliteProjectQualityAssessmentConfigurationRepository,
    SqliteQualityAssessmentCatalogRepository,
    SqliteQualityAssessmentRepository,
    default_project_quality_assessment_configuration_repository,
    default_quality_assessment_catalog_repository,
    default_quality_assessment_repository,
)
from app.repositories.synthesis_matrix_repository import (
    SqliteSynthesisMatrixRepository,
    default_synthesis_matrix_repository,
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

    position: int | None
    publication: Publication


@dataclass(frozen=True, slots=True)
class QualityAssessmentRow:
    """One assessed publication with its responses keyed by criterion id."""

    publication_id: UUID
    reviewer_id: str
    template_id: str
    template_version: int | None
    responses_by_criterion: dict[UUID, QualityAssessmentResponse]
    assessed_at: datetime


@dataclass(frozen=True, slots=True)
class QualityAssessmentSheetData:
    """Template criteria plus one row per assessed publication."""

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


def _build_extraction_service_for_database(publication_repo, database_path: Path) -> ExtractionDatasetService:
    """Construct an ExtractionDatasetService whose collaborators share one SQLite database."""
    from app.repositories.conflict_resolution_repository import SqliteConflictResolutionRepository
    from app.repositories.duplicate_review_decision_repository import SqliteDuplicateReviewDecisionRepository
    from app.repositories.screening_decision_repository import SqliteScreeningDecisionRepository
    from app.repositories.screening_reviewer_assignment_repository import SqliteScreeningReviewerAssignmentRepository
    from app.services.extraction_eligibility_service import (
        ExtractionEligibilityService,
        RepositoryQualityAssessmentCompletionReader,
    )
    from app.services.multi_reviewer_screening_service import MultiReviewerScreeningService
    from app.services.screening_input_service import ScreeningInputService

    duplicate_decisions = SqliteDuplicateReviewDecisionRepository(database_path)
    extraction_repo = SqliteExtractionRepository(database_path)
    template_repo = SqliteExtractionTemplateRepository(database_path)
    project_repo = SqliteProjectRepository(database_path)
    config_service = ExtractionConfigurationService(
        extraction_repo=extraction_repo,
        template_repo=template_repo,
        project_repo=project_repo,
    )
    decisions_repo = SqliteScreeningDecisionRepository(database_path)
    assignments_repo = SqliteScreeningReviewerAssignmentRepository(database_path)
    resolutions_repo = SqliteConflictResolutionRepository(database_path)
    reporting_repo = ScreeningReportingRepository(database_path)

    input_service = ScreeningInputService(publication_repo, duplicate_decisions)
    multi_reviewer = MultiReviewerScreeningService(
        assignments=assignments_repo,
        reporting=reporting_repo,
        resolutions=resolutions_repo,
        input_service=input_service,
    )
    qa_reader = RepositoryQualityAssessmentCompletionReader(
        config_repo=SqliteProjectQualityAssessmentConfigurationRepository(database_path),
        assessment_repo=SqliteQualityAssessmentRepository(database_path),
    )
    eligibility_service = ExtractionEligibilityService(
        config_service=config_service,
        input_service=input_service,
        multi_reviewer_service=multi_reviewer,
        decisions_repo=decisions_repo,
        qa_completion_reader=qa_reader,
    )
    return ExtractionDatasetService(
        config_service=config_service,
        eligibility_service=eligibility_service,
        template_repo=template_repo,
        extraction_repo=extraction_repo,
        publication_repo=publication_repo,
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
        database_path = getattr(self._publication_repository, "database_path", None)

        if screening_reporting_repository is not None:
            self._screening_reporting = screening_reporting_repository
        elif database_path is not None:
            self._screening_reporting = ScreeningReportingRepository(Path(database_path))
        else:
            self._screening_reporting = default_screening_reporting_repository()

        if prisma_service is not None:
            self._prisma_service = prisma_service
        elif database_path is not None:
            self._prisma_service = _build_prisma_service_for_database(
                self._publication_repository, Path(database_path), self._screening_reporting
            )
        else:
            self._prisma_service = PrismaMetricsService(
                publication_repository=self._publication_repository
            )

        if extraction_service is not None:
            self._extraction_service = extraction_service
        elif database_path is not None:
            self._extraction_service = _build_extraction_service_for_database(
                self._publication_repository, Path(database_path)
            )
        else:
            self._extraction_service = default_extraction_dataset_service()

        if extraction_configuration_service is not None:
            self._extraction_configuration = extraction_configuration_service
        elif database_path is not None:
            self._extraction_configuration = ExtractionConfigurationService(
                extraction_repo=SqliteExtractionRepository(Path(database_path)),
                template_repo=SqliteExtractionTemplateRepository(Path(database_path)),
                project_repo=SqliteProjectRepository(Path(database_path)),
            )
        else:
            self._extraction_configuration = default_extraction_configuration_service()

        if extraction_template_repository is not None:
            self._extraction_template_repository = extraction_template_repository
        elif database_path is not None:
            self._extraction_template_repository = SqliteExtractionTemplateRepository(Path(database_path))
        else:
            self._extraction_template_repository = default_extraction_template_repository()

        if qa_configuration_repository is not None:
            self._qa_configuration_repository = qa_configuration_repository
        elif database_path is not None:
            self._qa_configuration_repository = SqliteProjectQualityAssessmentConfigurationRepository(Path(database_path))
        else:
            self._qa_configuration_repository = default_project_quality_assessment_configuration_repository()

        if qa_catalog_repository is not None:
            self._qa_catalog_repository = qa_catalog_repository
        elif database_path is not None:
            self._qa_catalog_repository = SqliteQualityAssessmentCatalogRepository(Path(database_path))
        else:
            self._qa_catalog_repository = default_quality_assessment_catalog_repository()

        if qa_repository is not None:
            self._qa_repository = qa_repository
        elif database_path is not None:
            self._qa_repository = SqliteQualityAssessmentRepository(Path(database_path))
        else:
            self._qa_repository = default_quality_assessment_repository()

        if synthesis_matrix_repository is not None:
            self._synthesis_matrix_repository = synthesis_matrix_repository
        elif database_path is not None:
            self._synthesis_matrix_repository = SqliteSynthesisMatrixRepository(Path(database_path))
        else:
            self._synthesis_matrix_repository = default_synthesis_matrix_repository()

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
            BibliographicEntry(position=None, publication=publication)
            for publication in self.get_bibliographic_records(project_id)
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
            project_id, reviewer_id=reviewer_id, status_filter=status_filter
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

    def get_quality_assessment_sheet_data(
        self, project_id: str, reviewer_id: str = ""
    ) -> QualityAssessmentSheetData | None:
        """Assemble QA sheet inputs: criteria across templates plus assessed rows.

        Matches each QA response with metadata from the exact template version
        against which that response was created. Never silently substitutes
        latest/current template metadata.
        """
        configuration = self._qa_configuration_repository.get_configuration(project_id)

        active_pubs = self.get_bibliographic_records(project_id)
        raw_assessments: list[tuple[Publication, QualityAssessment]] = []
        for publication in active_pubs:
            assessment = self._qa_repository.get_latest_assessment(
                project_id, publication.record_id, reviewer_id
            )
            if assessment is not None:
                raw_assessments.append((publication, assessment))

        if configuration is None and not raw_assessments:
            return None

        # Resolve template metadata for configured template and all assessments
        templates_by_id: dict[UUID, QualityAssessmentTemplate] = {}
        if configuration is not None:
            configured_template = self._qa_catalog_repository.get_template_version(configuration.template_id)
            if configured_template is not None:
                templates_by_id[configured_template.template_id] = configured_template

        for _, assessment in raw_assessments:
            if assessment.template_id not in templates_by_id:
                tmpl = self._qa_catalog_repository.get_template_version(assessment.template_id)
                if tmpl is not None:
                    templates_by_id[tmpl.template_id] = tmpl

        # Collect unique criteria in deterministic template order
        seen_criterion_ids: set[UUID] = set()
        criteria_list: list[QualityAssessmentTemplateCriterion] = []

        ordered_templates: list[QualityAssessmentTemplate] = []
        seen_template_ids: set[UUID] = set()
        if configuration is not None and configuration.template_id in templates_by_id:
            configured_tmpl = templates_by_id[configuration.template_id]
            ordered_templates.append(configured_tmpl)
            seen_template_ids.add(configured_tmpl.template_id)
        for tid, tmpl in sorted(templates_by_id.items(), key=lambda item: (item[1].version, str(item[0]))):
            if tid not in seen_template_ids:
                ordered_templates.append(tmpl)
                seen_template_ids.add(tid)

        for tmpl in ordered_templates:
            sorted_criteria = sorted(
                tmpl.criteria,
                key=lambda criterion: (criterion.display_order, str(criterion.criterion_id)),
            )
            for crit in sorted_criteria:
                if crit.criterion_id not in seen_criterion_ids:
                    seen_criterion_ids.add(crit.criterion_id)
                    criteria_list.append(crit)

        criteria = tuple(criteria_list)

        rows: list[QualityAssessmentRow] = []
        for publication, assessment in raw_assessments:
            assessment_tmpl = templates_by_id.get(assessment.template_id)
            template_version = assessment_tmpl.version if assessment_tmpl is not None else None
            rows.append(
                QualityAssessmentRow(
                    publication_id=publication.record_id,
                    reviewer_id=assessment.reviewer_id,
                    template_id=str(assessment.template_id),
                    template_version=template_version,
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
