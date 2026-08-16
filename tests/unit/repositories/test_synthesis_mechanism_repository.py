"""Unit tests for SqliteSynthesisMechanismRepository (Task 10.4)."""

import sqlite3
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from app.domain.synthesis import (
    AnalyticalMechanismCategory,
    ClassificationApprovalState,
    MechanismPathway,
)
from app.repositories.synthesis_mechanism_repository import (
    SqliteSynthesisMechanismRepository,
)


@pytest.fixture
def repo(tmp_path: Path):
    migrations_dir = Path(__file__).parents[3] / "migrations"
    db_path = tmp_path / "test_mechanism_repo.db"
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    for sql_file in sorted(migrations_dir.glob("*.sql")):
        conn.executescript(sql_file.read_text(encoding="utf-8"))
    conn.commit()

    # Create dummy project and analytical relation for FK constraints
    proj_id = "test-proj-repo"
    conn.execute(
        "INSERT INTO projects (project_id, title, description) VALUES (?, ?, ?);",
        (proj_id, "Test Project", "Desc"),
    )
    rel_id = str(uuid4())
    group_item_id = str(uuid4())
    conn.execute(
        """
        INSERT INTO synthesis_analytical_relations (
            relation_id, project_id, publication_id, latest_revision_id, group_item_id,
            item_index, source_practice, source_effect, direction, evidence_character, approval_state
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """,
        (
            rel_id,
            proj_id,
            str(uuid4()),
            str(uuid4()),
            group_item_id,
            1,
            "5S Practice",
            "Energy effect",
            "positive",
            "empirical",
            "approved",
        ),
    )
    conn.commit()
    conn.close()

    return SqliteSynthesisMechanismRepository(db_path), proj_id, rel_id, group_item_id


def test_category_crud_operations(repo):
    repository, proj_id, _, _ = repo

    # 1. Create
    cat = AnalyticalMechanismCategory(
        category_id="heat_recovery",
        name="Waste Heat Recovery",
        project_id=proj_id,
        description="Capturing flue gas heat.",
        display_order=2,
    )
    created = repository.create_category(cat)
    assert created.category_id == "heat_recovery"

    # 2. Get
    fetched = repository.get_category(proj_id, "heat_recovery")
    assert fetched is not None
    assert fetched.name == "Waste Heat Recovery"
    assert fetched.display_order == 2

    # 3. List
    cat2 = AnalyticalMechanismCategory(
        category_id="idle_reduction",
        name="Idle Reduction",
        project_id=proj_id,
        display_order=1,
    )
    repository.create_category(cat2)
    cats = repository.list_categories(proj_id)
    assert len(cats) == 2
    assert cats[0].category_id == "idle_reduction"  # Ordered by display_order

    # 4. Update
    updated = AnalyticalMechanismCategory(
        category_id="heat_recovery",
        name="Waste Heat Recovery & Reuse",
        project_id=proj_id,
        description="Updated desc",
        display_order=3,
    )
    repository.update_category(updated)
    fetched_updated = repository.get_category(proj_id, "heat_recovery")
    assert fetched_updated.name == "Waste Heat Recovery & Reuse"

    # 5. Delete
    assert repository.delete_category(proj_id, "heat_recovery") is True
    assert repository.get_category(proj_id, "heat_recovery") is None


def test_pathway_persistence_and_category_deletion_nulling(repo):
    repository, proj_id, rel_id, group_item_id = repo

    cat = AnalyticalMechanismCategory(
        category_id="flow_opt",
        name="Flow Optimization",
        project_id=proj_id,
    )
    repository.create_category(cat)

    path_id = uuid4()
    pub_id = uuid4()
    rev_id = uuid4()
    pathway = MechanismPathway(
        pathway_id=path_id,
        project_id=proj_id,
        analytical_relation_id=UUID(rel_id),
        group_item_id=UUID(group_item_id),
        publication_id=pub_id,
        latest_revision_id=rev_id,
        source_mechanism_text="Continuous flow eliminated batch reheating steps.",
        analytical_mechanism_category_id="flow_opt",
        is_review_synthesized=False,
        approval_state=ClassificationApprovalState.APPROVED,
    )
    repository.save_pathway(pathway)

    # Fetch pathway
    fetched = repository.get_pathway(proj_id, path_id)
    assert fetched is not None
    assert fetched.source_mechanism_text == "Continuous flow eliminated batch reheating steps."
    assert fetched.analytical_mechanism_category_id == "flow_opt"

    # Fetch by relation
    by_rel = repository.get_pathway_by_relation(proj_id, UUID(rel_id))
    assert by_rel is not None
    assert by_rel.pathway_id == path_id

    # Deleting category must set pathway's analytical_mechanism_category_id to NULL
    repository.delete_category(proj_id, "flow_opt")
    after_cat_del = repository.get_pathway(proj_id, path_id)
    assert after_cat_del is not None
    assert after_cat_del.analytical_mechanism_category_id is None
    # Source mechanism text remains 100% intact
    assert after_cat_del.source_mechanism_text == "Continuous flow eliminated batch reheating steps."
