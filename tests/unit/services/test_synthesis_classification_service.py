"""Unit tests for SynthesisClassificationService."""

from pathlib import Path
from uuid import uuid4

import pytest

from app.domain.extraction import (
    ExtractedGroupItemState,
    ExtractedValueState,
    ExtractionCompletenessStatus,
    ExtractionRecord,
    ExtractionRevision,
    ExtractionTemplate,
    ExtractionTemplateVersion,
    ValueOrigin,
    ValueStatus,
)
from app.domain.project import Project
from app.domain.synthesis import (
    ClassificationApprovalState,
    TermType,
)
from app.repositories.extraction_repository import SqliteExtractionRepository
from app.repositories.extraction_template_repository import SqliteExtractionTemplateRepository
from app.repositories.project_repository import SqliteProjectRepository
from app.repositories.synthesis_classification_repository import (
    SqliteSynthesisClassificationRepository,
)
from app.services.synthesis_classification_service import (
    CategoryConflictError,
    CategoryNotFoundError,
    SynthesisClassificationService,
)


@pytest.fixture
def service_env(tmp_path: Path):
    db_path = tmp_path / "classification_service_test.db"

    proj_repo = SqliteProjectRepository(db_path)
    proj_repo.create(Project(project_id="proj-a", title="Project A"))
    proj_repo.create(Project(project_id="proj-b", title="Project B"))

    template_repo = SqliteExtractionTemplateRepository(db_path)
    template_repo.register_template(ExtractionTemplate(template_id="lean_energy", name="Lean Energy"))
    template_repo.register_version(
        ExtractionTemplateVersion(template_id="lean_energy", version="1.0.0", name="v1", is_published=True)
    )

    extraction_repo = SqliteExtractionRepository(db_path)
    classification_repo = SqliteSynthesisClassificationRepository(db_path)

    # Seed 2 publications with extraction revisions in Project A
    pub1 = uuid4()
    pub2 = uuid4()

    rec1 = extraction_repo.create_record(
        ExtractionRecord(project_id="proj-a", publication_id=pub1, template_id="lean_energy", template_version="1.0.0")
    )
    rec2 = extraction_repo.create_record(
        ExtractionRecord(project_id="proj-a", publication_id=pub2, template_id="lean_energy", template_version="1.0.0")
    )

    # Pub 1: 5S -> 12% electricity reduction, VSM -> compressed air + non-canonical and non-contract fields
    extraction_repo.append_revision(
        ExtractionRevision(
            record_id=rec1.record_id,
            project_id="proj-a",
            publication_id=pub1,
            revision_index=1,
            reviewer_id="reviewer-1",
            completeness_status=ExtractionCompletenessStatus.COMPLETE,
            publication_values=[
                ExtractedValueState(
                    field_key="study_design",
                    status=ValueStatus.PRESENT,
                    origin=ValueOrigin.REPORTED,
                    text_value="Case Study Empirical",
                    source_locator="Table 1",
                ),
                ExtractedValueState(
                    field_key="main_conclusions",
                    status=ValueStatus.PRESENT,
                    origin=ValueOrigin.REPORTED,
                    text_value="Significant energy efficiency improvements found",
                    source_locator="Table 1",
                ),
            ],
            group_items=[
                ExtractedGroupItemState(
                    group_item_id=uuid4(),
                    group_key="lean_energy_relationships",
                    item_index=1,
                    values=[
                        ExtractedValueState(
                            field_key="lean_practice",
                            status=ValueStatus.PRESENT,
                            origin=ValueOrigin.REPORTED,
                            text_value="5S Visual",
                            source_locator="Table 1",
                        ),
                        ExtractedValueState(
                            field_key="energy_effect_indicator",
                            status=ValueStatus.PRESENT,
                            origin=ValueOrigin.REPORTED,
                            text_value="12% Electricity",
                            source_locator="Table 1",
                        ),
                        ExtractedValueState(
                            field_key="impact_mechanism",
                            status=ValueStatus.PRESENT,
                            origin=ValueOrigin.REPORTED,
                            text_value="Shutdown protocol during setup",
                            source_locator="Table 1",
                        ),
                        ExtractedValueState(
                            field_key="practice",  # Non-contract alias candidate
                            status=ValueStatus.PRESENT,
                            origin=ValueOrigin.REPORTED,
                            text_value="Ignored Generic Practice Alias",
                            source_locator="Table 1",
                        ),
                        ExtractedValueState(
                            field_key="effect",  # Non-contract alias candidate
                            status=ValueStatus.PRESENT,
                            origin=ValueOrigin.REPORTED,
                            text_value="Ignored Generic Effect Alias",
                            source_locator="Table 1",
                        ),
                        ExtractedValueState(
                            field_key="practice_notes",
                            status=ValueStatus.PRESENT,
                            origin=ValueOrigin.REPORTED,
                            text_value="Floor marking notes",
                            source_locator="Table 1",
                        ),
                        ExtractedValueState(
                            field_key="effect_notes",
                            status=ValueStatus.PRESENT,
                            origin=ValueOrigin.REPORTED,
                            text_value="Measured via smart meter",
                            source_locator="Table 1",
                        ),
                    ],
                ),
                ExtractedGroupItemState(
                    group_item_id=uuid4(),
                    group_key="lean_energy_relationships",
                    item_index=2,
                    values=[
                        ExtractedValueState(
                            field_key="lean_practice",
                            status=ValueStatus.PRESENT,
                            origin=ValueOrigin.REPORTED,
                            text_value="VSM Mapping",
                            source_locator="Table 1",
                        ),
                        ExtractedValueState(
                            field_key="energy_effect_indicator",
                            status=ValueStatus.PRESENT,
                            origin=ValueOrigin.REPORTED,
                            text_value="Compressed Air Leak Reduction",
                            source_locator="Table 1",
                        ),
                        ExtractedValueState(
                            field_key="measurement_method",
                            status=ValueStatus.PRESENT,
                            origin=ValueOrigin.REPORTED,
                            text_value="Ultrasonic leak detection",
                            source_locator="Table 1",
                        ),
                    ],
                ),
            ],
        )
    )

    # Pub 2: 5S Visual -> 8% Electricity
    extraction_repo.append_revision(
        ExtractionRevision(
            record_id=rec2.record_id,
            project_id="proj-a",
            publication_id=pub2,
            revision_index=1,
            reviewer_id="reviewer-1",
            completeness_status=ExtractionCompletenessStatus.COMPLETE,
            group_items=[
                ExtractedGroupItemState(
                    group_item_id=uuid4(),
                    group_key="lean_energy_relationships",
                    item_index=1,
                    values=[
                        ExtractedValueState(
                            field_key="lean_practice",
                            status=ValueStatus.PRESENT,
                            origin=ValueOrigin.REPORTED,
                            text_value="5S Visual",
                            source_locator="Table 1",
                        ),
                        ExtractedValueState(
                            field_key="energy_effect_indicator",
                            status=ValueStatus.PRESENT,
                            origin=ValueOrigin.REPORTED,
                            text_value="8% Electricity",
                            source_locator="Table 1",
                        ),
                    ],
                ),
            ],
        )
    )

    service = SynthesisClassificationService(
        classification_repo=classification_repo,
        extraction_repo=extraction_repo,
        project_repo=proj_repo,
    )

    return {
        "service": service,
        "extraction_repo": extraction_repo,
        "classification_repo": classification_repo,
        "project_repo": proj_repo,
        "db_path": db_path,
        "pub1": pub1,
        "pub2": pub2,
    }


def test_initial_project_state_has_discovered_terms_and_zero_categories(service_env):
    service: SynthesisClassificationService = service_env["service"]

    # Initial state for Project A: source terms are discovered, but categories and mappings are empty
    workspace = service.get_workspace_classifications("proj-a")
    assert len(workspace["lean_categories"]) == 0
    assert len(workspace["energy_categories"]) == 0
    assert workspace["stats"]["mapped_count"] == 0
    assert workspace["stats"]["approved_count"] == 0
    assert workspace["stats"]["total_lean_terms"] == 2
    assert workspace["stats"]["total_energy_terms"] == 3


def test_canonical_source_term_discovery_and_filtering(service_env):
    service: SynthesisClassificationService = service_env["service"]

    workspace = service.get_workspace_classifications("proj-a")

    # Canonical lean field ("lean_practice") discovered
    lean_values = {t.source_value for t in workspace["lean_terms"]}
    assert lean_values == {"5S Visual", "VSM Mapping"}

    # Canonical energy field ("energy_effect_indicator") discovered
    energy_values = {t.source_value for t in workspace["energy_terms"]}
    assert energy_values == {"12% Electricity", "Compressed Air Leak Reduction", "8% Electricity"}

    # Non-canonical / alias / unrelated text fields strictly excluded
    all_discovered = lean_values | energy_values
    assert "Case Study Empirical" not in all_discovered
    assert "Significant energy efficiency improvements found" not in all_discovered
    assert "Shutdown protocol during setup" not in all_discovered
    assert "Ultrasonic leak detection" not in all_discovered
    assert "Ignored Generic Practice Alias" not in all_discovered
    assert "Ignored Generic Effect Alias" not in all_discovered

    # Similarly named fields strictly excluded
    assert "Floor marking notes" not in all_discovered
    assert "Measured via smart meter" not in all_discovered


def test_source_value_preservation_invariant(service_env):
    service: SynthesisClassificationService = service_env["service"]
    extraction_repo: SqliteExtractionRepository = service_env["extraction_repo"]

    # 1. Manually create researcher analytical categories
    service.create_lean_category("proj-a", "5s", "5S & Visuals", "5S definition")
    service.create_lean_category("proj-a", "kaizen", "Kaizen CI", "Kaizen definition")

    # 2. Map source term "5S Visual" to category "5s"
    mapping = service.set_term_mapping(
        project_id="proj-a",
        term_type=TermType.LEAN_PRACTICE,
        source_value="5S Visual",
        analytical_category_id="5s",
    )
    assert mapping.source_value == "5S Visual"
    assert mapping.analytical_category_id == "5s"
    assert mapping.approval_state == ClassificationApprovalState.PENDING

    # 3. Update mapping to a different category "kaizen"
    mapping_updated = service.set_term_mapping(
        project_id="proj-a",
        term_type=TermType.LEAN_PRACTICE,
        source_value="5S Visual",
        analytical_category_id="kaizen",
    )
    assert mapping_updated.source_value == "5S Visual"
    assert mapping_updated.analytical_category_id == "kaizen"

    # 4. Mandatory invariant check: Phase 9 extraction revisions are completely untouched
    rev1 = extraction_repo.get_latest_revision("proj-a", service_env["pub1"])
    assert rev1 is not None
    p1 = next(v for v in rev1.group_items[0].values if v.field_key == "lean_practice")
    assert p1.text_value == "5S Visual"

    rev2 = extraction_repo.get_latest_revision("proj-a", service_env["pub2"])
    assert rev2 is not None
    p2 = next(v for v in rev2.group_items[0].values if v.field_key == "lean_practice")
    assert p2.text_value == "5S Visual"


def test_approval_workflow_lifecycle(service_env):
    service: SynthesisClassificationService = service_env["service"]
    service.create_lean_category("proj-a", "5s", "5S & Visuals")
    service.create_lean_category("proj-a", "tpm", "TPM Maintenance")

    # Map term -> PENDING
    mapping = service.set_term_mapping(
        project_id="proj-a",
        term_type=TermType.LEAN_PRACTICE,
        source_value="5S Visual",
        analytical_category_id="5s",
    )
    assert mapping.approval_state == ClassificationApprovalState.PENDING
    assert mapping.approved_by is None
    assert mapping.approved_at is None

    # Explicit approval -> APPROVED
    approved = service.approve_term_mapping(
        project_id="proj-a",
        term_type=TermType.LEAN_PRACTICE,
        source_value="5S Visual",
        reviewer_id="reviewer-1",
    )
    assert approved.approval_state == ClassificationApprovalState.APPROVED
    assert approved.approved_by == "reviewer-1"
    assert approved.approved_at is not None

    # Re-mapping to same category preserves approval
    remapped_same = service.set_term_mapping(
        project_id="proj-a",
        term_type=TermType.LEAN_PRACTICE,
        source_value="5S Visual",
        analytical_category_id="5s",
    )
    assert remapped_same.approval_state == ClassificationApprovalState.APPROVED

    # Re-mapping to a different category resets approval to PENDING
    remapped_different = service.set_term_mapping(
        project_id="proj-a",
        term_type=TermType.LEAN_PRACTICE,
        source_value="5S Visual",
        analytical_category_id="tpm",
    )
    assert remapped_different.approval_state == ClassificationApprovalState.PENDING
    assert remapped_different.approved_by is None
    assert remapped_different.approved_at is None


def test_category_domain_mismatch_rejection(service_env):
    service: SynthesisClassificationService = service_env["service"]
    service.create_lean_category("proj-a", "5s", "5S & Visuals")
    service.create_energy_category("proj-a", "electricity_direct", "Electricity Direct")

    # Attempt to map a Lean practice term to an Energy effect category ID ("electricity_direct")
    with pytest.raises(CategoryNotFoundError, match="Lean category 'electricity_direct' not found"):
        service.set_term_mapping(
            project_id="proj-a",
            term_type=TermType.LEAN_PRACTICE,
            source_value="5S Visual",
            analytical_category_id="electricity_direct",
        )

    # Attempt to map an Energy effect term to a Lean category ID ("5s")
    with pytest.raises(CategoryNotFoundError, match="Energy category '5s' not found"):
        service.set_term_mapping(
            project_id="proj-a",
            term_type=TermType.ENERGY_EFFECT,
            source_value="12% Electricity",
            analytical_category_id="5s",
        )


def test_cross_project_category_mapping_rejection(service_env):
    service: SynthesisClassificationService = service_env["service"]

    # Category exists in Project B, but not in Project A
    service.create_lean_category("proj-b", "lean_b", "Lean Category in B")

    with pytest.raises(CategoryNotFoundError, match="Lean category 'lean_b' not found in project 'proj-a'"):
        service.set_term_mapping(
            project_id="proj-a",
            term_type=TermType.LEAN_PRACTICE,
            source_value="5S Visual",
            analytical_category_id="lean_b",
        )


def test_category_deletion_cascades_mapping_to_unmapped(service_env):
    service: SynthesisClassificationService = service_env["service"]
    service.create_lean_category("proj-a", "5s", "5S & Visuals")

    # Map and approve term
    service.set_term_mapping("proj-a", TermType.LEAN_PRACTICE, "5S Visual", "5s")
    service.approve_term_mapping("proj-a", TermType.LEAN_PRACTICE, "5S Visual", "reviewer-1")

    # Delete category "5s"
    deleted = service.delete_lean_category("proj-a", "5s")
    assert deleted is True

    # Mapping should now have analytical_category_id = None and approval_state = PENDING
    workspace = service.get_workspace_classifications("proj-a")
    lean_5s = next(t for t in workspace["lean_terms"] if t.source_value == "5S Visual")
    assert lean_5s.analytical_category_id is None
    assert lean_5s.analytical_category_name is None
    assert lean_5s.approval_state == ClassificationApprovalState.PENDING


def test_category_crud_and_duplicate_conflict(service_env):
    service: SynthesisClassificationService = service_env["service"]

    # Create category
    cat = service.create_lean_category("proj-a", "kaizen", "Kaizen", "Continuous improvement", 2)
    assert cat.category_id == "kaizen"
    assert cat.display_order == 2

    # Duplicate category ID raises conflict error
    with pytest.raises(CategoryConflictError):
        service.create_lean_category("proj-a", "kaizen", "Duplicate Kaizen")

    # Update category
    updated = service.update_lean_category("proj-a", "kaizen", "Kaizen Updated", "New desc", 3)
    assert updated.name == "Kaizen Updated"
    assert updated.display_order == 3

    # Updating non-existent category raises error
    with pytest.raises(CategoryNotFoundError):
        service.update_lean_category("proj-a", "nonexistent", "Name")


def test_database_reopen_preserves_categories_and_mappings(service_env):
    db_path = service_env["db_path"]
    service: SynthesisClassificationService = service_env["service"]

    service.create_lean_category("proj-a", "smed", "SMED Changeover", display_order=1)
    service.set_term_mapping("proj-a", TermType.LEAN_PRACTICE, "5S Visual", "smed")
    service.approve_term_mapping("proj-a", TermType.LEAN_PRACTICE, "5S Visual", "reviewer-audit")

    # Reopen service with fresh repository instances pointing to same database
    fresh_class_repo = SqliteSynthesisClassificationRepository(db_path)
    fresh_ext_repo = SqliteExtractionRepository(db_path)
    fresh_proj_repo = SqliteProjectRepository(db_path)
    reopened_service = SynthesisClassificationService(
        classification_repo=fresh_class_repo,
        extraction_repo=fresh_ext_repo,
        project_repo=fresh_proj_repo,
    )

    workspace = reopened_service.get_workspace_classifications("proj-a")
    assert len(workspace["lean_categories"]) == 1
    assert workspace["lean_categories"][0].category_id == "smed"

    term = next(t for t in workspace["lean_terms"] if t.source_value == "5S Visual")
    assert term.analytical_category_id == "smed"
    assert term.analytical_category_name == "SMED Changeover"
    assert term.approval_state == ClassificationApprovalState.APPROVED
    assert term.approved_by == "reviewer-audit"
