"""Unit tests for SqliteSynthesisMatrixRepository."""

import sqlite3
from pathlib import Path
from uuid import uuid4

import pytest

from app.domain.project import Project
from app.domain.synthesis import (
    AnalyticalRelation,
    ClassificationApprovalState,
    ConvertedValue,
    EnergyEffectCategory,
    EvidenceCharacter,
    LeanPracticeCategory,
    RelationDirection,
)
from app.repositories.project_repository import SqliteProjectRepository
from app.repositories.synthesis_classification_repository import (
    SqliteSynthesisClassificationRepository,
)
from app.repositories.synthesis_matrix_repository import (
    SqliteSynthesisMatrixRepository,
)


def _apply_migrations_up_to(db_path: Path, max_version: str | None = None) -> None:
    migrations_dir = Path(__file__).parents[3] / "migrations"
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "version TEXT PRIMARY KEY, "
            "applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP"
            ");"
        )
        applied = {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}
        for sql_file in sorted(migrations_dir.glob("*.sql")):
            if max_version and sql_file.name > max_version:
                continue
            if sql_file.name not in applied:
                conn.executescript(sql_file.read_text(encoding="utf-8"))
                conn.execute("INSERT INTO schema_migrations (version) VALUES (?);", (sql_file.name,))
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def repos(tmp_path: Path):
    db_path = tmp_path / "test_matrix_repo.db"
    _apply_migrations_up_to(db_path, "0021_analytical_relations.sql")

    proj_repo = SqliteProjectRepository(db_path)
    class_repo = SqliteSynthesisClassificationRepository(db_path)
    matrix_repo = SqliteSynthesisMatrixRepository(db_path)

    proj_repo.create(Project(project_id="p1", title="Project One", description=""))
    class_repo.create_lean_category(LeanPracticeCategory(project_id="p1", category_id="c_5s", name="5S"))
    class_repo.create_energy_category(EnergyEffectCategory(project_id="p1", category_id="c_elec", name="Electricity"))

    return matrix_repo, class_repo, db_path


def test_save_and_get_analytical_relation(repos):
    matrix_repo, _, db_path = repos
    rel_id = uuid4()
    group_item_id = uuid4()
    pub_id = uuid4()
    rev_id = uuid4()

    rel = AnalyticalRelation(
        relation_id=rel_id,
        project_id="p1",
        publication_id=pub_id,
        latest_revision_id=rev_id,
        group_item_id=group_item_id,
        item_index=1,
        source_practice="5S Visuals",
        analytical_lean_category_id="c_5s",
        source_effect="10 kWh reduction",
        analytical_energy_category_id="c_elec",
        direction=RelationDirection.POSITIVE,
        magnitude=10.0,
        original_unit="kWh",
        converted_value=ConvertedValue(
            transformed_value=36.0,
            transformed_unit="MJ",
            conversion_rule="1 kWh = 3.6 MJ",
        ),
        evidence_character=EvidenceCharacter.EMPIRICAL,
        approval_state=ClassificationApprovalState.APPROVED,
    )

    saved = matrix_repo.save_analytical_relation(rel)
    assert saved.relation_id == rel_id

    fetched = matrix_repo.get_analytical_relation("p1", rel_id)
    assert fetched is not None
    assert fetched.source_practice == "5S Visuals"
    assert fetched.converted_value is not None
    assert fetched.converted_value.transformed_value == 36.0
    assert fetched.converted_value.transformed_unit == "MJ"

    # Fetch by group_item_id
    by_item = matrix_repo.get_analytical_relation_by_group_item("p1", group_item_id)
    assert by_item is not None
    assert by_item.relation_id == rel_id

    # Reopen DB check
    new_repo = SqliteSynthesisMatrixRepository(db_path)
    reopened = new_repo.get_analytical_relation("p1", rel_id)
    assert reopened is not None
    assert reopened.group_item_id == group_item_id


def test_update_converted_value(repos):
    matrix_repo, _, _ = repos
    rel_id = uuid4()
    group_item_id = uuid4()

    rel = AnalyticalRelation(
        relation_id=rel_id,
        project_id="p1",
        publication_id=uuid4(),
        latest_revision_id=uuid4(),
        group_item_id=group_item_id,
        item_index=1,
        source_practice="Kanban",
        source_effect="20 Wh",
        direction=RelationDirection.POSITIVE,
        magnitude=20.0,
        original_unit="Wh",
        evidence_character=EvidenceCharacter.EMPIRICAL,
    )
    matrix_repo.save_analytical_relation(rel)

    conv = ConvertedValue(
        transformed_value=72000.0,
        transformed_unit="J",
        conversion_rule="1 Wh = 3600 J",
    )
    updated = matrix_repo.update_converted_value("p1", rel_id, conv)
    assert updated is True

    fetched = matrix_repo.get_analytical_relation("p1", rel_id)
    assert fetched is not None
    assert fetched.converted_value is not None
    assert fetched.converted_value.transformed_value == 72000.0


def test_clear_category_references_on_category_deletion(repos):
    matrix_repo, class_repo, _ = repos
    rel_id = uuid4()
    group_item_id = uuid4()

    rel = AnalyticalRelation(
        relation_id=rel_id,
        project_id="p1",
        publication_id=uuid4(),
        latest_revision_id=uuid4(),
        group_item_id=group_item_id,
        item_index=1,
        source_practice="5S Practice",
        analytical_lean_category_id="c_5s",
        source_effect="Electricity Effect",
        analytical_energy_category_id="c_elec",
        direction=RelationDirection.POSITIVE,
        evidence_character=EvidenceCharacter.EMPIRICAL,
    )
    matrix_repo.save_analytical_relation(rel)

    # Deleting lean category should set analytical_lean_category_id to NULL
    class_repo.delete_lean_category("p1", "c_5s")

    fetched = matrix_repo.get_analytical_relation("p1", rel_id)
    assert fetched is not None
    assert fetched.analytical_lean_category_id is None
    assert fetched.analytical_energy_category_id == "c_elec"
