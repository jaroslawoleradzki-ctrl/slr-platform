"""Tests for SqliteSynthesisClassificationRepository."""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.domain.project import Project
from app.domain.synthesis import (
    ClassificationApprovalState,
    EnergyEffectCategory,
    LeanPracticeCategory,
    TermMapping,
    TermType,
)
from app.repositories.project_repository import SqliteProjectRepository
from app.repositories.synthesis_classification_repository import (
    SqliteSynthesisClassificationRepository,
)


@pytest.fixture
def repo(tmp_path: Path):
    db_path = tmp_path / "classification_repo_test.db"
    proj_repo = SqliteProjectRepository(db_path)
    proj_repo.create(Project(project_id="proj-a", title="Project A"))
    proj_repo.create(Project(project_id="proj-b", title="Project B"))
    return SqliteSynthesisClassificationRepository(db_path)


def test_lean_category_crud_and_ordering(repo: SqliteSynthesisClassificationRepository):
    # Create categories
    cat1 = LeanPracticeCategory(
        project_id="proj-a",
        category_id="5s",
        name="5S & Workplace Organization",
        description="5S tools",
        display_order=2,
    )
    cat2 = LeanPracticeCategory(
        project_id="proj-a",
        category_id="vsm",
        name="Value Stream Mapping",
        description="VSM tools",
        display_order=1,
    )
    repo.create_lean_category(cat1)
    repo.create_lean_category(cat2)

    # List ordered by display_order
    cats = repo.list_lean_categories("proj-a")
    assert len(cats) == 2
    assert cats[0].category_id == "vsm"
    assert cats[1].category_id == "5s"

    # Get single
    fetched = repo.get_lean_category("proj-a", "5s")
    assert fetched is not None
    assert fetched.name == "5S & Workplace Organization"

    # Update
    updated = LeanPracticeCategory(
        project_id="proj-a",
        category_id="5s",
        name="5S / Visual Workplace",
        description="Updated description",
        display_order=2,
    )
    repo.update_lean_category(updated)
    fetched_updated = repo.get_lean_category("proj-a", "5s")
    assert fetched_updated is not None
    assert fetched_updated.name == "5S / Visual Workplace"

    # Delete
    assert repo.delete_lean_category("proj-a", "5s") is True
    assert repo.get_lean_category("proj-a", "5s") is None
    assert repo.delete_lean_category("proj-a", "nonexistent") is False


def test_energy_category_crud_and_ordering(repo: SqliteSynthesisClassificationRepository):
    cat1 = EnergyEffectCategory(
        project_id="proj-a",
        category_id="elec",
        name="Direct Electricity",
        display_order=2,
    )
    cat2 = EnergyEffectCategory(
        project_id="proj-a",
        category_id="heat",
        name="Thermal Energy",
        display_order=1,
    )
    repo.create_energy_category(cat1)
    repo.create_energy_category(cat2)

    cats = repo.list_energy_categories("proj-a")
    assert len(cats) == 2
    assert cats[0].category_id == "heat"
    assert cats[1].category_id == "elec"

    # Update
    updated = EnergyEffectCategory(
        project_id="proj-a",
        category_id="elec",
        name="Direct Electricity Reduction",
        display_order=2,
    )
    repo.update_energy_category(updated)
    assert repo.get_energy_category("proj-a", "elec").name == "Direct Electricity Reduction"

    # Delete
    assert repo.delete_energy_category("proj-a", "elec") is True
    assert repo.get_energy_category("proj-a", "elec") is None


def test_term_mapping_persistence_and_upsert(repo: SqliteSynthesisClassificationRepository):
    # Save mapping
    mapping = TermMapping(
        project_id="proj-a",
        term_type=TermType.LEAN_PRACTICE,
        source_value="5S Visual Standard",
        analytical_category_id="5s",
        approval_state=ClassificationApprovalState.PENDING,
    )
    saved = repo.save_term_mapping(mapping)
    assert saved.source_value == "5S Visual Standard"

    # Get mapping
    fetched = repo.get_term_mapping("proj-a", TermType.LEAN_PRACTICE, "5S Visual Standard")
    assert fetched is not None
    assert fetched.analytical_category_id == "5s"
    assert fetched.approval_state == ClassificationApprovalState.PENDING

    # Upsert with approval
    now = datetime.now(timezone.utc)
    updated_mapping = TermMapping(
        mapping_id=fetched.mapping_id,
        project_id="proj-a",
        term_type=TermType.LEAN_PRACTICE,
        source_value="5S Visual Standard",
        analytical_category_id="5s",
        approval_state=ClassificationApprovalState.APPROVED,
        approved_by="reviewer-1",
        approved_at=now,
    )
    repo.save_term_mapping(updated_mapping)

    fetched_approved = repo.get_term_mapping("proj-a", TermType.LEAN_PRACTICE, "5S Visual Standard")
    assert fetched_approved is not None
    assert fetched_approved.approval_state == ClassificationApprovalState.APPROVED
    assert fetched_approved.approved_by == "reviewer-1"

    # List mappings
    all_mappings = repo.list_term_mappings("proj-a", TermType.LEAN_PRACTICE)
    assert len(all_mappings) == 1

    # Delete mapping
    assert repo.delete_term_mapping("proj-a", TermType.LEAN_PRACTICE, "5S Visual Standard") is True
    assert repo.get_term_mapping("proj-a", TermType.LEAN_PRACTICE, "5S Visual Standard") is None


def test_project_isolation(repo: SqliteSynthesisClassificationRepository):
    # Create category and mapping in Project A
    repo.create_lean_category(LeanPracticeCategory(project_id="proj-a", category_id="5s", name="5S in A"))
    repo.save_term_mapping(
        TermMapping(
            project_id="proj-a",
            term_type=TermType.LEAN_PRACTICE,
            source_value="5S",
            analytical_category_id="5s",
        )
    )

    # Project B must see nothing
    assert len(repo.list_lean_categories("proj-b")) == 0
    assert repo.get_lean_category("proj-b", "5s") is None
    assert len(repo.list_term_mappings("proj-b")) == 0
    assert repo.get_term_mapping("proj-b", TermType.LEAN_PRACTICE, "5S") is None
