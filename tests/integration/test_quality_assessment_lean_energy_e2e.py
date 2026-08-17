"""Phase 8.5 — End-to-end integration tests for Lean Energy QA v1 workflow.

Tests the complete Quality Assessment lifecycle:
1. Seed catalog → casp_inspired tool + Lean Energy QA v1 template (7 criteria)
2. Create project & publication
3. Create FULL_TEXT INCLUDE screening decision (eligibility)
4. Configure project with Lean Energy template
5. Verify readiness, overview, record detail
6. Submit assessment with 7 mixed responses and non-blank justifications
7. Verify progress update, history, append-only semantics
8. Verify Full-Text decision is NOT modified by QA
9. Negative tests: incomplete responses, empty justification, seed immutability
"""

from pathlib import Path
from uuid import UUID, uuid4

import pytest

from app.domain.project import Project
from app.domain.publication import Publication
from app.domain.screening import ScreeningDecision, ScreeningOutcome, ScreeningStage
from app.repositories.project_publication_repository import SqliteProjectPublicationRepository
from app.repositories.project_repository import SqliteProjectRepository
from app.repositories.screening_decision_repository import SqliteScreeningDecisionRepository
from app.repositories.sqlite_quality_assessment_repository import (
    SqliteProjectQualityAssessmentConfigurationRepository,
    SqliteQualityAssessmentCatalogRepository,
    SqliteQualityAssessmentRepository,
)
from app.services.quality_assessment_configuration_service import (
    CASP_INSPIRED_TOOL_ID,
    LEAN_ENERGY_CRITERIA_SPECS,
    LEAN_ENERGY_TEMPLATE_ID,
    LEAN_ENERGY_TEMPLATE_KEY,
    DefaultQualityAssessmentConfigurationService,
    SeedCatalogConflictError,
)
from app.services.quality_assessment_execution_service import (
    CriterionResponseInput,
    DefaultQualityAssessmentExecutionService,
    MissingRequiredQualityCriterionResponseError,
    QualityAssessmentReadinessStatus,
)


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """Shared temporary DB path for all repos (single-file DB)."""
    return tmp_path / "test_lean_energy_e2e.db"


@pytest.fixture
def project_repo(db_path: Path) -> SqliteProjectRepository:
    return SqliteProjectRepository(db_path)


@pytest.fixture
def pub_repo(db_path: Path) -> SqliteProjectPublicationRepository:
    return SqliteProjectPublicationRepository(db_path)


@pytest.fixture
def decision_repo(db_path: Path) -> SqliteScreeningDecisionRepository:
    return SqliteScreeningDecisionRepository(db_path)


@pytest.fixture
def catalog_repo(db_path: Path) -> SqliteQualityAssessmentCatalogRepository:
    return SqliteQualityAssessmentCatalogRepository(db_path)


@pytest.fixture
def config_repo(db_path: Path) -> SqliteProjectQualityAssessmentConfigurationRepository:
    return SqliteProjectQualityAssessmentConfigurationRepository(db_path)


@pytest.fixture
def qa_repo(db_path: Path) -> SqliteQualityAssessmentRepository:
    return SqliteQualityAssessmentRepository(db_path)


@pytest.fixture
def config_service(
    catalog_repo: SqliteQualityAssessmentCatalogRepository,
    config_repo: SqliteProjectQualityAssessmentConfigurationRepository,
    project_repo: SqliteProjectRepository,
) -> DefaultQualityAssessmentConfigurationService:
    return DefaultQualityAssessmentConfigurationService(
        catalog_repo=catalog_repo,
        config_repo=config_repo,
        project_repo=project_repo,
    )


@pytest.fixture
def execution_service(
    project_repo: SqliteProjectRepository,
    pub_repo: SqliteProjectPublicationRepository,
    decision_repo: SqliteScreeningDecisionRepository,
    catalog_repo: SqliteQualityAssessmentCatalogRepository,
    config_repo: SqliteProjectQualityAssessmentConfigurationRepository,
    qa_repo: SqliteQualityAssessmentRepository,
) -> DefaultQualityAssessmentExecutionService:
    return DefaultQualityAssessmentExecutionService(
        project_repo=project_repo,
        publication_repo=pub_repo,
        screening_decision_repo=decision_repo,
        catalog_repo=catalog_repo,
        config_repo=config_repo,
        quality_assessment_repo=qa_repo,
    )


# ──────────────────────────────────────────────
# CATALOG SEED TESTS
# ──────────────────────────────────────────────


class TestLeanEnergyCatalogSeed:
    """Verify that seed_built_in_catalog correctly provisions casp_inspired tool + Lean Energy QA v1."""

    def test_seed_creates_casp_tool(
        self,
        config_service: DefaultQualityAssessmentConfigurationService,
        catalog_repo: SqliteQualityAssessmentCatalogRepository,
    ) -> None:
        config_service.seed_built_in_catalog()
        tool = catalog_repo.get_tool(CASP_INSPIRED_TOOL_ID)
        assert tool is not None
        assert tool.name == "CASP-inspired Quality Assessment"
        assert tool.is_active is True

    def test_seed_creates_lean_energy_template_v1(
        self,
        config_service: DefaultQualityAssessmentConfigurationService,
        catalog_repo: SqliteQualityAssessmentCatalogRepository,
    ) -> None:
        config_service.seed_built_in_catalog()
        template = catalog_repo.get_template_version(LEAN_ENERGY_TEMPLATE_ID)
        assert template is not None
        assert template.template_key == LEAN_ENERGY_TEMPLATE_KEY
        assert template.name == "Lean Energy Quality Assessment"
        assert template.version == 1
        assert template.is_active is True

    def test_seed_creates_exactly_7_criteria(
        self,
        config_service: DefaultQualityAssessmentConfigurationService,
        catalog_repo: SqliteQualityAssessmentCatalogRepository,
    ) -> None:
        config_service.seed_built_in_catalog()
        template = catalog_repo.get_template_version(LEAN_ENERGY_TEMPLATE_ID)
        assert template is not None
        assert len(template.criteria) == 7

    def test_seed_criteria_order_and_content(
        self,
        config_service: DefaultQualityAssessmentConfigurationService,
        catalog_repo: SqliteQualityAssessmentCatalogRepository,
    ) -> None:
        config_service.seed_built_in_catalog()
        template = catalog_repo.get_template_version(LEAN_ENERGY_TEMPLATE_ID)
        assert template is not None

        criteria = sorted(template.criteria, key=lambda c: c.display_order)
        for idx, (expected_id, expected_order, expected_q, expected_g) in enumerate(LEAN_ENERGY_CRITERIA_SPECS):
            c = criteria[idx]
            assert c.criterion_id == expected_id
            assert c.display_order == expected_order
            assert c.question == expected_q
            assert c.guidance == expected_g
            assert c.is_required is True

    def test_seed_criteria_questions_match_protocol(
        self,
        config_service: DefaultQualityAssessmentConfigurationService,
        catalog_repo: SqliteQualityAssessmentCatalogRepository,
    ) -> None:
        """Verify QA1-QA7 question text corresponds exactly to SLR Protocol v0.10 Chapter IX."""
        config_service.seed_built_in_catalog()
        template = catalog_repo.get_template_version(LEAN_ENERGY_TEMPLATE_ID)
        assert template is not None
        criteria = sorted(template.criteria, key=lambda c: c.display_order)

        assert "cel lub pytanie badawcze" in criteria[0].question
        assert "metoda badawcza" in criteria[1].question
        assert "pozyskania oraz analizy danych" in criteria[2].question
        assert "Lean Management" in criteria[3].question
        assert "pomiaru zużycia energii" in criteria[4].question
        assert "związek pomiędzy Lean Management" in criteria[5].question
        assert "wnioski autorów" in criteria[6].question

    def test_seed_is_idempotent(
        self,
        config_service: DefaultQualityAssessmentConfigurationService,
        catalog_repo: SqliteQualityAssessmentCatalogRepository,
    ) -> None:
        config_service.seed_built_in_catalog()
        config_service.seed_built_in_catalog()  # Second call must not raise
        config_service.seed_built_in_catalog()  # Third call must not raise

        # Still only one tool and one template
        tools = catalog_repo.list_tools()
        assert len(tools) == 1
        templates = catalog_repo.list_template_versions(tool_id=CASP_INSPIRED_TOOL_ID)
        assert len(templates) == 1

    def test_seed_raises_conflict_on_tool_name_mismatch(
        self,
        catalog_repo: SqliteQualityAssessmentCatalogRepository,
        config_repo: SqliteProjectQualityAssessmentConfigurationRepository,
        project_repo: SqliteProjectRepository,
    ) -> None:
        from app.domain.quality_assessment import QualityAssessmentTool

        catalog_repo.create_tool(
            QualityAssessmentTool(
                tool_id=CASP_INSPIRED_TOOL_ID,
                name="Wrong Tool Name",
            )
        )

        service = DefaultQualityAssessmentConfigurationService(
            catalog_repo=catalog_repo,
            config_repo=config_repo,
            project_repo=project_repo,
        )
        with pytest.raises(SeedCatalogConflictError):
            service.seed_built_in_catalog()

    def test_seed_response_scale_has_three_values(self) -> None:
        """Verify response scale: YES, NO, CANNOT_DETERMINE — no other values."""
        from app.domain.quality_assessment import QualityAssessmentResponseValue

        assert set(QualityAssessmentResponseValue) == {"YES", "NO", "CANNOT_DETERMINE"}

    def test_seed_no_scoring_fields_exist(
        self,
        config_service: DefaultQualityAssessmentConfigurationService,
        catalog_repo: SqliteQualityAssessmentCatalogRepository,
    ) -> None:
        """Verify template has NO total_score, percentage, quality_rating, pass_fail, or quality_class."""
        config_service.seed_built_in_catalog()
        template = catalog_repo.get_template_version(LEAN_ENERGY_TEMPLATE_ID)
        assert template is not None

        template_dict = template.model_dump()
        scoring_keywords = ["total_score", "percentage", "quality_rating", "pass_fail", "quality_class", "score"]
        for kw in scoring_keywords:
            assert kw not in template_dict, f"Unexpected scoring field '{kw}' in template"


# ──────────────────────────────────────────────
# FULL E2E WORKFLOW TEST
# ──────────────────────────────────────────────


class TestLeanEnergyE2EWorkflow:
    """End-to-end workflow: seed → project → eligibility → configure → assess → verify."""

    @pytest.fixture
    def seeded_project(
        self,
        config_service: DefaultQualityAssessmentConfigurationService,
        project_repo: SqliteProjectRepository,
        pub_repo: SqliteProjectPublicationRepository,
        decision_repo: SqliteScreeningDecisionRepository,
    ) -> tuple[str, UUID, str]:
        """Creates a project with one FULL_TEXT INCLUDE publication, returns (project_id, pub_id, reviewer_id)."""
        config_service.seed_built_in_catalog()

        project_id = "proj_lean_e2e"
        project_repo.create(Project(project_id=project_id, title="Lean Energy Manufacturing Review"))

        pub_id = uuid4()
        pub = Publication(record_id=pub_id, title="Energy Efficiency via Kaizen in Automotive Plant")
        pub_repo.add_publications(project_id, [pub])

        reviewer_id = "rev_e2e_01"
        decision_repo.save(
            ScreeningDecision(
                project_id=project_id,
                publication_id=pub_id,
                stage=ScreeningStage.FULL_TEXT,
                outcome=ScreeningOutcome.INCLUDE,
                reviewer_id=reviewer_id,
                rationale="High quality empirical study on VSM energy metrics.",
            )
        )

        return project_id, pub_id, reviewer_id

    def test_readiness_before_configuration(
        self,
        seeded_project: tuple[str, UUID, str],
        execution_service: DefaultQualityAssessmentExecutionService,
    ) -> None:
        project_id, _, reviewer_id = seeded_project
        readiness = execution_service.check_readiness(project_id, reviewer_id)
        assert readiness == QualityAssessmentReadinessStatus.NO_QUALITY_ASSESSMENT_CONFIGURATION

    def test_configure_project_with_lean_energy(
        self,
        seeded_project: tuple[str, UUID, str],
        config_service: DefaultQualityAssessmentConfigurationService,
    ) -> None:
        project_id, _, _ = seeded_project
        config = config_service.configure_project(project_id, CASP_INSPIRED_TOOL_ID, LEAN_ENERGY_TEMPLATE_ID)
        assert config.tool_id == CASP_INSPIRED_TOOL_ID
        assert config.template_id == LEAN_ENERGY_TEMPLATE_ID

    def test_readiness_after_configuration(
        self,
        seeded_project: tuple[str, UUID, str],
        config_service: DefaultQualityAssessmentConfigurationService,
        execution_service: DefaultQualityAssessmentExecutionService,
    ) -> None:
        project_id, _, reviewer_id = seeded_project
        config_service.configure_project(project_id, CASP_INSPIRED_TOOL_ID, LEAN_ENERGY_TEMPLATE_ID)
        readiness = execution_service.check_readiness(project_id, reviewer_id)
        assert readiness == QualityAssessmentReadinessStatus.READY

    def test_overview_shows_one_eligible_zero_assessed(
        self,
        seeded_project: tuple[str, UUID, str],
        config_service: DefaultQualityAssessmentConfigurationService,
        execution_service: DefaultQualityAssessmentExecutionService,
    ) -> None:
        project_id, _, reviewer_id = seeded_project
        config_service.configure_project(project_id, CASP_INSPIRED_TOOL_ID, LEAN_ENERGY_TEMPLATE_ID)
        overview = execution_service.get_overview(project_id, reviewer_id)
        assert overview.readiness == QualityAssessmentReadinessStatus.READY
        assert overview.total_eligible == 1
        assert overview.total_assessed == 0
        assert overview.total_remaining == 1
        assert overview.template_version == 1

    def test_record_detail_before_assessment(
        self,
        seeded_project: tuple[str, UUID, str],
        config_service: DefaultQualityAssessmentConfigurationService,
        execution_service: DefaultQualityAssessmentExecutionService,
    ) -> None:
        project_id, pub_id, reviewer_id = seeded_project
        config_service.configure_project(project_id, CASP_INSPIRED_TOOL_ID, LEAN_ENERGY_TEMPLATE_ID)
        detail = execution_service.get_record_detail(project_id, pub_id, reviewer_id)
        assert detail.is_currently_eligible is True
        assert detail.latest_assessment is None
        assert len(detail.template.criteria) == 7

    def test_save_assessment_with_7_responses(
        self,
        seeded_project: tuple[str, UUID, str],
        config_service: DefaultQualityAssessmentConfigurationService,
        execution_service: DefaultQualityAssessmentExecutionService,
        catalog_repo: SqliteQualityAssessmentCatalogRepository,
    ) -> None:
        project_id, pub_id, reviewer_id = seeded_project
        config_service.configure_project(project_id, CASP_INSPIRED_TOOL_ID, LEAN_ENERGY_TEMPLATE_ID)

        template = catalog_repo.get_template_version(LEAN_ENERGY_TEMPLATE_ID)
        assert template is not None
        criteria = sorted(template.criteria, key=lambda c: c.display_order)

        from app.domain.quality_assessment import QualityAssessmentResponseValue

        response_inputs = [
            CriterionResponseInput(criterion_id=criteria[0].criterion_id, response_value=QualityAssessmentResponseValue.YES, justification="Jasny cel ujęty we wprowadzeniu."),
            CriterionResponseInput(criterion_id=criteria[1].criterion_id, response_value=QualityAssessmentResponseValue.YES, justification="Metoda 5S opisana ze szczegółami."),
            CriterionResponseInput(criterion_id=criteria[2].criterion_id, response_value=QualityAssessmentResponseValue.YES, justification="Próba 12 zakładów i analiza regresji."),
            CriterionResponseInput(criterion_id=criteria[3].criterion_id, response_value=QualityAssessmentResponseValue.YES, justification="Zidentyfikowano Kaizen oraz VSM."),
            CriterionResponseInput(criterion_id=criteria[4].criterion_id, response_value=QualityAssessmentResponseValue.YES, justification="Pomiar w kWh na jednostkę wyrobu."),
            CriterionResponseInput(criterion_id=criteria[5].criterion_id, response_value=QualityAssessmentResponseValue.CANNOT_DETERMINE, justification="Brak bezpośredniego modelu korelacyjnego."),
            CriterionResponseInput(criterion_id=criteria[6].criterion_id, response_value=QualityAssessmentResponseValue.NO, justification="Wnioski nie uwzględniają ograniczeń próby."),
        ]

        assessment = execution_service.save_assessment(
            project_id=project_id,
            publication_id=pub_id,
            reviewer_id=reviewer_id,
            response_inputs=response_inputs,
        )

        assert assessment.project_id == project_id
        assert assessment.publication_id == pub_id
        assert assessment.reviewer_id == reviewer_id
        assert assessment.template_id == LEAN_ENERGY_TEMPLATE_ID
        assert len(assessment.responses) == 7

    def test_overview_after_assessment_shows_assessed(
        self,
        seeded_project: tuple[str, UUID, str],
        config_service: DefaultQualityAssessmentConfigurationService,
        execution_service: DefaultQualityAssessmentExecutionService,
        catalog_repo: SqliteQualityAssessmentCatalogRepository,
    ) -> None:
        project_id, pub_id, reviewer_id = seeded_project
        config_service.configure_project(project_id, CASP_INSPIRED_TOOL_ID, LEAN_ENERGY_TEMPLATE_ID)

        template = catalog_repo.get_template_version(LEAN_ENERGY_TEMPLATE_ID)
        assert template is not None
        criteria = sorted(template.criteria, key=lambda c: c.display_order)

        from app.domain.quality_assessment import QualityAssessmentResponseValue

        response_inputs = [
            CriterionResponseInput(
                criterion_id=c.criterion_id,
                response_value=QualityAssessmentResponseValue.YES,
                justification=f"Uzasadnienie dla kryterium {c.display_order}.",
            )
            for c in criteria
        ]
        execution_service.save_assessment(project_id, pub_id, reviewer_id, response_inputs)

        overview = execution_service.get_overview(project_id, reviewer_id)
        assert overview.total_assessed == 1
        assert overview.total_remaining == 0

    def test_history_returns_assessment_audit_log(
        self,
        seeded_project: tuple[str, UUID, str],
        config_service: DefaultQualityAssessmentConfigurationService,
        execution_service: DefaultQualityAssessmentExecutionService,
        catalog_repo: SqliteQualityAssessmentCatalogRepository,
    ) -> None:
        project_id, pub_id, reviewer_id = seeded_project
        config_service.configure_project(project_id, CASP_INSPIRED_TOOL_ID, LEAN_ENERGY_TEMPLATE_ID)

        template = catalog_repo.get_template_version(LEAN_ENERGY_TEMPLATE_ID)
        assert template is not None
        criteria = sorted(template.criteria, key=lambda c: c.display_order)

        from app.domain.quality_assessment import QualityAssessmentResponseValue

        # First assessment
        inputs_1 = [
            CriterionResponseInput(criterion_id=c.criterion_id, response_value=QualityAssessmentResponseValue.YES, justification="Pierwsze uzasadnienie.")
            for c in criteria
        ]
        execution_service.save_assessment(project_id, pub_id, reviewer_id, inputs_1)

        # Second assessment (append-only)
        inputs_2 = [
            CriterionResponseInput(criterion_id=c.criterion_id, response_value=QualityAssessmentResponseValue.NO, justification="Drugie uzasadnienie, zmieniona ocena.")
            for c in criteria
        ]
        execution_service.save_assessment(project_id, pub_id, reviewer_id, inputs_2)

        history = execution_service.get_assessment_history(project_id, pub_id, reviewer_id)
        assert len(history) == 2
        assert history[0].template_id == LEAN_ENERGY_TEMPLATE_ID
        assert history[1].template_id == LEAN_ENERGY_TEMPLATE_ID

    def test_full_text_decision_not_modified_by_qa(
        self,
        seeded_project: tuple[str, UUID, str],
        config_service: DefaultQualityAssessmentConfigurationService,
        execution_service: DefaultQualityAssessmentExecutionService,
        catalog_repo: SqliteQualityAssessmentCatalogRepository,
        decision_repo: SqliteScreeningDecisionRepository,
    ) -> None:
        """QA does NOT create screening decisions or modify Full-Text INCLUDE/EXCLUDE."""
        project_id, pub_id, reviewer_id = seeded_project
        config_service.configure_project(project_id, CASP_INSPIRED_TOOL_ID, LEAN_ENERGY_TEMPLATE_ID)

        template = catalog_repo.get_template_version(LEAN_ENERGY_TEMPLATE_ID)
        assert template is not None
        criteria = sorted(template.criteria, key=lambda c: c.display_order)

        from app.domain.quality_assessment import QualityAssessmentResponseValue

        response_inputs = [
            CriterionResponseInput(criterion_id=c.criterion_id, response_value=QualityAssessmentResponseValue.NO, justification="All criteria rated NO deliberately.")
            for c in criteria
        ]
        execution_service.save_assessment(project_id, pub_id, reviewer_id, response_inputs)

        # Full-Text decision must still be INCLUDE
        latest_decision = decision_repo.get_latest_decision(
            project_id, pub_id, ScreeningStage.FULL_TEXT, reviewer_id
        )
        assert latest_decision is not None
        assert latest_decision.outcome == ScreeningOutcome.INCLUDE


# ──────────────────────────────────────────────
# NEGATIVE / VALIDATION TESTS
# ──────────────────────────────────────────────


class TestLeanEnergyNegativeValidation:
    """Negative tests for completeness, justification, and invariant enforcement."""

    @pytest.fixture
    def configured_project(
        self,
        config_service: DefaultQualityAssessmentConfigurationService,
        project_repo: SqliteProjectRepository,
        pub_repo: SqliteProjectPublicationRepository,
        decision_repo: SqliteScreeningDecisionRepository,
    ) -> tuple[str, UUID, str]:
        config_service.seed_built_in_catalog()
        project_id = "proj_neg_test"
        project_repo.create(Project(project_id=project_id, title="Negative Test Project"))
        config_service.configure_project(project_id, CASP_INSPIRED_TOOL_ID, LEAN_ENERGY_TEMPLATE_ID)

        pub_id = uuid4()
        pub_repo.add_publications(project_id, [Publication(record_id=pub_id, title="Test Paper")])

        reviewer_id = "rev_neg_01"
        decision_repo.save(
            ScreeningDecision(
                project_id=project_id,
                publication_id=pub_id,
                stage=ScreeningStage.FULL_TEXT,
                outcome=ScreeningOutcome.INCLUDE,
                reviewer_id=reviewer_id,
            )
        )

        return project_id, pub_id, reviewer_id

    def test_missing_required_criterion_raises_error(
        self,
        configured_project: tuple[str, UUID, str],
        execution_service: DefaultQualityAssessmentExecutionService,
        catalog_repo: SqliteQualityAssessmentCatalogRepository,
    ) -> None:
        project_id, pub_id, reviewer_id = configured_project
        template = catalog_repo.get_template_version(LEAN_ENERGY_TEMPLATE_ID)
        assert template is not None
        criteria = sorted(template.criteria, key=lambda c: c.display_order)

        from app.domain.quality_assessment import QualityAssessmentResponseValue

        # Only 6 out of 7 required criteria
        incomplete_inputs = [
            CriterionResponseInput(criterion_id=c.criterion_id, response_value=QualityAssessmentResponseValue.YES, justification="Valid text")
            for c in criteria[:6]
        ]

        with pytest.raises(MissingRequiredQualityCriterionResponseError):
            execution_service.save_assessment(project_id, pub_id, reviewer_id, incomplete_inputs)

    def test_blank_justification_raises_error(
        self,
        configured_project: tuple[str, UUID, str],
        execution_service: DefaultQualityAssessmentExecutionService,
        catalog_repo: SqliteQualityAssessmentCatalogRepository,
    ) -> None:
        project_id, pub_id, reviewer_id = configured_project
        template = catalog_repo.get_template_version(LEAN_ENERGY_TEMPLATE_ID)
        assert template is not None
        criteria = sorted(template.criteria, key=lambda c: c.display_order)

        from app.domain.quality_assessment import QualityAssessmentResponseValue

        # NO responses with blank (whitespace-only) justification must raise error
        blank_inputs = [
            CriterionResponseInput(criterion_id=c.criterion_id, response_value=QualityAssessmentResponseValue.NO, justification="   ")
            for c in criteria
        ]

        with pytest.raises((ValueError, Exception)):
            execution_service.save_assessment(project_id, pub_id, reviewer_id, blank_inputs)

    def test_yes_response_with_empty_justification_succeeds(
        self,
        configured_project: tuple[str, UUID, str],
        execution_service: DefaultQualityAssessmentExecutionService,
        catalog_repo: SqliteQualityAssessmentCatalogRepository,
    ) -> None:
        project_id, pub_id, reviewer_id = configured_project
        template = catalog_repo.get_template_version(LEAN_ENERGY_TEMPLATE_ID)
        assert template is not None
        criteria = sorted(template.criteria, key=lambda c: c.display_order)

        from app.domain.quality_assessment import QualityAssessmentResponseValue

        # YES responses with empty justification are valid
        yes_inputs = [
            CriterionResponseInput(criterion_id=c.criterion_id, response_value=QualityAssessmentResponseValue.YES, justification="")
            for c in criteria
        ]

        assessment = execution_service.save_assessment(project_id, pub_id, reviewer_id, yes_inputs)
        assert assessment is not None
        assert len(assessment.responses) == len(criteria)
        assert all(r.response_value == QualityAssessmentResponseValue.YES for r in assessment.responses)
        assert all(r.justification == "" for r in assessment.responses)

    def test_duplicate_criterion_response_raises_error(
        self,
        configured_project: tuple[str, UUID, str],
        execution_service: DefaultQualityAssessmentExecutionService,
        catalog_repo: SqliteQualityAssessmentCatalogRepository,
    ) -> None:
        project_id, pub_id, reviewer_id = configured_project
        template = catalog_repo.get_template_version(LEAN_ENERGY_TEMPLATE_ID)
        assert template is not None
        criteria = sorted(template.criteria, key=lambda c: c.display_order)

        from app.domain.quality_assessment import QualityAssessmentResponseValue

        # Duplicate first criterion
        inputs = [
            CriterionResponseInput(criterion_id=c.criterion_id, response_value=QualityAssessmentResponseValue.YES, justification="Valid")
            for c in criteria
        ] + [
            CriterionResponseInput(criterion_id=criteria[0].criterion_id, response_value=QualityAssessmentResponseValue.NO, justification="Duplicate")
        ]

        with pytest.raises(ValueError, match="Duplicate"):
            execution_service.save_assessment(project_id, pub_id, reviewer_id, inputs)

    def test_non_template_criterion_raises_error(
        self,
        configured_project: tuple[str, UUID, str],
        execution_service: DefaultQualityAssessmentExecutionService,
        catalog_repo: SqliteQualityAssessmentCatalogRepository,
    ) -> None:
        project_id, pub_id, reviewer_id = configured_project
        template = catalog_repo.get_template_version(LEAN_ENERGY_TEMPLATE_ID)
        assert template is not None
        criteria = sorted(template.criteria, key=lambda c: c.display_order)

        from app.domain.quality_assessment import QualityAssessmentResponseValue

        # Valid 6 criteria + 1 fake criterion
        inputs = [
            CriterionResponseInput(criterion_id=c.criterion_id, response_value=QualityAssessmentResponseValue.YES, justification="Valid")
            for c in criteria[:6]
        ] + [
            CriterionResponseInput(criterion_id=uuid4(), response_value=QualityAssessmentResponseValue.YES, justification="Fake criterion")
        ]

        with pytest.raises(ValueError, match="does not belong"):
            execution_service.save_assessment(project_id, pub_id, reviewer_id, inputs)

    def test_ineligible_publication_raises_error(
        self,
        config_service: DefaultQualityAssessmentConfigurationService,
        project_repo: SqliteProjectRepository,
        pub_repo: SqliteProjectPublicationRepository,
        execution_service: DefaultQualityAssessmentExecutionService,
    ) -> None:
        """Publication without FULL_TEXT INCLUDE decision cannot be assessed."""
        from app.services.quality_assessment_execution_service import PublicationNotEligibleForQualityAssessmentError

        config_service.seed_built_in_catalog()
        project_id = "proj_ineligible"
        project_repo.create(Project(project_id=project_id, title="Ineligible Project"))
        config_service.configure_project(project_id, CASP_INSPIRED_TOOL_ID, LEAN_ENERGY_TEMPLATE_ID)

        pub_id = uuid4()
        pub_repo.add_publications(project_id, [Publication(record_id=pub_id, title="Ineligible Paper")])

        from app.domain.quality_assessment import QualityAssessmentResponseValue

        inputs = [
            CriterionResponseInput(criterion_id=cid, response_value=QualityAssessmentResponseValue.YES, justification="Test")
            for cid, _, _, _ in LEAN_ENERGY_CRITERIA_SPECS
        ]

        with pytest.raises(PublicationNotEligibleForQualityAssessmentError):
            execution_service.save_assessment(project_id, pub_id, "rev_no_access", inputs)
