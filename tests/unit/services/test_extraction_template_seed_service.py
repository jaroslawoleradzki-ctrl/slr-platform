"""Unit tests for Phase 9.7 Lean Energy Extraction v1 Template Seed."""

from uuid import uuid4

import pytest

from app.domain.extraction import (
    ExtractedGroupItemState,
    ExtractedValueState,
    ExtractionCompletenessStatus,
    ValueOrigin,
    ValueStatus,
)
from app.repositories.extraction_repository import SqliteExtractionRepository
from app.repositories.extraction_template_repository import (
    ExtractionTemplateConflictError,
    SqliteExtractionTemplateRepository,
)
from app.services.extraction_configuration_service import ExtractionConfigurationService
from app.services.extraction_execution_service import ExtractionExecutionService
from app.services.extraction_template_seed_service import (
    LEAN_ENERGY_TEMPLATE_ID,
    LEAN_ENERGY_VERSION,
    ExtractionTemplateSeedService,
    get_lean_energy_v1_template_version,
    seed_lean_energy_v1_template,
)


@pytest.fixture
def temp_db(tmp_path):
    db_file = tmp_path / "test_seed.db"
    return db_file


@pytest.fixture
def template_repo(temp_db):
    return SqliteExtractionTemplateRepository(temp_db)


@pytest.fixture
def seed_service(template_repo):
    return ExtractionTemplateSeedService(template_repo=template_repo)


class TestLeanEnergyTemplateStructure:
    def test_lean_energy_template_seeded_and_deterministic_identity(self, seed_service, template_repo):
        version = seed_service.seed_lean_energy_v1()
        assert version.template_id == "lean_energy"
        assert version.version == "1.0.0"
        assert version.is_published is True
        assert version.is_active is True

        template = template_repo.get_template("lean_energy")
        assert template.template_id == "lean_energy"
        assert template.name == "Lean Energy Data Extraction"
        assert len(template.versions) >= 1

    def test_idempotence_and_no_duplicates(self, seed_service, template_repo):
        v1 = seed_service.seed_lean_energy_v1()
        v2 = seed_service.seed_lean_energy_v1()
        assert v1.template_id == v2.template_id
        assert v1.version == v2.version

        template = template_repo.get_template("lean_energy")
        assert len(template.versions) == 1

    def test_conflicting_existing_version_fails_loudly(self, seed_service, template_repo):
        seed_service.seed_lean_energy_v1()

        # Modify schema version target and try to re-seed conflicting version
        conflicting = get_lean_energy_v1_template_version().model_copy(
            update={"description": "Conflicting Mutated Description"}
        )
        with pytest.raises(ExtractionTemplateConflictError):
            template_repo.register_version(conflicting)

    def test_e1_to_e14_coverage_and_scope_separation(self, seed_service):
        version = seed_service.seed_lean_energy_v1()

        # Publication-level fields (E1-E3, E12-E14)
        pub_keys = {f.field_key for f in version.publication_fields}
        # E1 is canonical publication metadata, not reviewer-entered extraction data.
        assert "study_title" not in pub_keys
        assert "publication_year" not in pub_keys
        assert "study_country_industry" in pub_keys  # E2
        assert "study_design" in pub_keys  # E3
        assert "main_conclusions" in pub_keys  # E12
        assert "study_limitations" in pub_keys  # E13
        assert "research_gaps" in pub_keys  # E14

        # Relationship-level repeating group (E4-E11)
        assert len(version.repeating_groups) == 1
        group = version.repeating_groups[0]
        assert group.group_key == "lean_energy_relationships"
        assert group.min_items == 1
        assert group.max_items is None

        rel_keys = {f.field_key for f in group.field_definitions}
        assert "lean_practice" in rel_keys  # E4
        assert "application_scope" in rel_keys  # E5
        assert "energy_effect_indicator" in rel_keys  # E6
        assert "measurement_method" in rel_keys  # E7
        assert "effect_magnitude" in rel_keys  # E8
        assert "evidence_character" in rel_keys  # E9
        assert "impact_mechanism" in rel_keys  # E10
        assert "moderating_conditions" in rel_keys  # E11


class TestLeanEnergyDomainBehavior:
    @pytest.fixture
    def setup_lean_project(self, temp_db, template_repo):
        from app.domain.project import Project
        from app.repositories.project_repository import SqliteProjectRepository

        project_repo = SqliteProjectRepository(temp_db)
        project_repo.create(Project(project_id="proj_lean", title="Lean Project", description="Description"))

        extraction_repo = SqliteExtractionRepository(temp_db)
        seed_lean_energy_v1_template(template_repo=template_repo)

        from app.services.extraction_eligibility_service import ExtractionEligibilityService

        config_service = ExtractionConfigurationService(
            extraction_repo=extraction_repo,
            template_repo=template_repo,
            project_repo=project_repo,
        )

        # Configure project to use lean_energy v1.0.0
        config_service.set_configuration("proj_lean", LEAN_ENERGY_TEMPLATE_ID, LEAN_ENERGY_VERSION)

        from unittest.mock import MagicMock

        from app.domain.extraction import ExtractionEligibilityResult, ExtractionEligibilityStatus

        eligibility_service = ExtractionEligibilityService(
            config_service=config_service,
        )
        eligibility_service.evaluate_publication = MagicMock(
            side_effect=lambda proj, pub, reviewer_id="": ExtractionEligibilityResult(
                publication_id=pub,
                status=ExtractionEligibilityStatus.ELIGIBLE,
                is_eligible=True,
            )
        )

        execution_service = ExtractionExecutionService(
            config_service=config_service,
            eligibility_service=eligibility_service,
            template_repo=template_repo,
            extraction_repo=extraction_repo,
        )

        return {
            "project_id": "proj_lean",
            "publication_id": uuid4(),
            "reviewer_id": "rev_lean_1",
            "execution_service": execution_service,
        }

    def test_single_relationship_can_become_complete(self, setup_lean_project):
        env = setup_lean_project
        svc = env["execution_service"]

        pub_vals = [
            ExtractedValueState(
                field_key="study_design",
                status=ValueStatus.PRESENT,
                origin=ValueOrigin.REPORTED,
                text_value="Case Study",
            ),
        ]

        rel1 = ExtractedGroupItemState(
            group_key="lean_energy_relationships",
            item_index=1,
            values=[
                ExtractedValueState(
                    field_key="lean_practice",
                    status=ValueStatus.PRESENT,
                    origin=ValueOrigin.REPORTED,
                    text_value="SMED (Single-Minute Exchange of Die)",
                ),
                ExtractedValueState(
                    field_key="energy_effect_indicator",
                    status=ValueStatus.PRESENT,
                    origin=ValueOrigin.REPORTED,
                    text_value="Electricity Consumption",
                ),
                ExtractedValueState(
                    field_key="evidence_character",
                    status=ValueStatus.PRESENT,
                    origin=ValueOrigin.REPORTED,
                    text_value="Empirically Demonstrated",
                ),
            ],
        )

        rev = svc.submit_revision(
            env["project_id"],
            env["publication_id"],
            env["reviewer_id"],
            pub_vals,
            [rel1],
            mark_complete=True,
        )

        assert rev.completeness_status == ExtractionCompletenessStatus.COMPLETE

    def test_two_independent_relationships_remain_separate(self, setup_lean_project):
        env = setup_lean_project
        svc = env["execution_service"]

        pub_vals = [
            ExtractedValueState(
                field_key="study_design",
                status=ValueStatus.PRESENT,
                origin=ValueOrigin.REPORTED,
                text_value="Empirical / Field Experiment",
            ),
        ]

        rel1 = ExtractedGroupItemState(
            group_key="lean_energy_relationships",
            item_index=1,
            values=[
                ExtractedValueState(
                    field_key="lean_practice",
                    status=ValueStatus.PRESENT,
                    origin=ValueOrigin.REPORTED,
                    text_value="SMED (Single-Minute Exchange of Die)",
                ),
                ExtractedValueState(
                    field_key="energy_effect_indicator",
                    status=ValueStatus.PRESENT,
                    origin=ValueOrigin.REPORTED,
                    text_value="Electricity Consumption",
                ),
                ExtractedValueState(
                    field_key="evidence_character",
                    status=ValueStatus.PRESENT,
                    origin=ValueOrigin.REPORTED,
                    text_value="Quantitatively Measured",
                ),
            ],
        )

        rel2 = ExtractedGroupItemState(
            group_key="lean_energy_relationships",
            item_index=2,
            values=[
                ExtractedValueState(
                    field_key="lean_practice",
                    status=ValueStatus.PRESENT,
                    origin=ValueOrigin.REPORTED,
                    text_value="5S",
                ),
                ExtractedValueState(
                    field_key="energy_effect_indicator",
                    status=ValueStatus.PRESENT,
                    origin=ValueOrigin.REPORTED,
                    text_value="Standby / Idle Energy",
                ),
                ExtractedValueState(
                    field_key="evidence_character",
                    status=ValueStatus.PRESENT,
                    origin=ValueOrigin.REPORTED,
                    text_value="Qualitatively Described",
                ),
            ],
        )

        rev = svc.submit_revision(
            env["project_id"],
            env["publication_id"],
            env["reviewer_id"],
            pub_vals,
            [rel1, rel2],
            mark_complete=True,
        )

        assert rev.completeness_status == ExtractionCompletenessStatus.COMPLETE
        assert len(rev.group_items) == 2
        assert rev.group_items[0].item_index == 1
        assert rev.group_items[1].item_index == 2
