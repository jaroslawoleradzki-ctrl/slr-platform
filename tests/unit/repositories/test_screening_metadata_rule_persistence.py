import sqlite3
from uuid import UUID

from app.domain.screening import (
    MetadataRule,
    ScreeningCriterion,
    ScreeningCriterionEvaluationMode,
    ScreeningCriterionStage,
    ScreeningCriterionType,
)
from app.repositories.screening_criterion_repository import SqliteScreeningCriterionRepository


def _automatic(project_id: str = "lean_energy") -> ScreeningCriterion:
    return ScreeningCriterion(
        project_id=project_id,
        name="Published after 2021",
        criterion_type=ScreeningCriterionType.INCLUSION,
        screening_stage=ScreeningCriterionStage.TITLE_ABSTRACT,
        evaluation_mode=ScreeningCriterionEvaluationMode.METADATA_RULE,
        metadata_rule=MetadataRule(field="publication_year", operator="greater_than", value=2021),
    )


def test_criteria_default_to_manual_and_automatic_rule_round_trips(tmp_path) -> None:
    repository = SqliteScreeningCriterionRepository(tmp_path / "criteria.db")
    manual = repository.create(
        ScreeningCriterion(
            project_id="lean_energy",
            name="Manual criterion",
            criterion_type=ScreeningCriterionType.INCLUSION,
            screening_stage=ScreeningCriterionStage.TITLE_ABSTRACT,
        )
    )
    automatic = repository.create(_automatic())

    assert repository.get("lean_energy", manual.criterion_id).evaluation_mode is ScreeningCriterionEvaluationMode.MANUAL
    assert repository.get("lean_energy", manual.criterion_id).metadata_rule is None
    assert repository.get("lean_energy", automatic.criterion_id) == automatic


def test_update_can_switch_between_manual_and_automatic_without_changing_identity(tmp_path) -> None:
    repository = SqliteScreeningCriterionRepository(tmp_path / "criteria.db")
    original = repository.create(
        ScreeningCriterion(
            project_id="lean_energy",
            name="Criterion",
            criterion_type=ScreeningCriterionType.INCLUSION,
            screening_stage=ScreeningCriterionStage.TITLE_ABSTRACT,
        )
    )
    automatic = original.model_copy(
        update={
            "evaluation_mode": ScreeningCriterionEvaluationMode.METADATA_RULE,
            "metadata_rule": MetadataRule(field="language", operator="equals", value="en"),
        }
    )
    repository.update(automatic)
    assert repository.get("lean_energy", original.criterion_id).metadata_rule == automatic.metadata_rule

    manual = automatic.model_copy(
        update={"evaluation_mode": ScreeningCriterionEvaluationMode.MANUAL, "metadata_rule": None}
    )
    repository.update(manual)
    restored = repository.get("lean_energy", original.criterion_id)
    assert restored.criterion_id == original.criterion_id
    assert restored.evaluation_mode is ScreeningCriterionEvaluationMode.MANUAL
    assert restored.metadata_rule is None


def test_existing_criteria_migrate_to_manual_without_changing_identity(tmp_path) -> None:
    database = tmp_path / "pre-0011.db"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE schema_migrations (version TEXT PRIMARY KEY)")
        connection.executescript(
            """
            CREATE TABLE screening_criteria (
                criterion_id TEXT PRIMARY KEY, project_id TEXT NOT NULL, name TEXT NOT NULL,
                description TEXT, criterion_type TEXT NOT NULL, screening_stage TEXT NOT NULL,
                display_order INTEGER NOT NULL DEFAULT 0, is_active INTEGER NOT NULL DEFAULT 1,
                is_required INTEGER NOT NULL DEFAULT 1
            );
            CREATE TABLE screening_decisions (decision_id TEXT PRIMARY KEY, project_id TEXT NOT NULL,
                publication_id TEXT NOT NULL, stage TEXT NOT NULL, outcome TEXT NOT NULL,
                reviewer_id TEXT NOT NULL, rationale TEXT, decided_at TEXT NOT NULL);
            CREATE TABLE screening_criterion_assessments (
                decision_id TEXT NOT NULL, criterion_id TEXT NOT NULL, criterion_name TEXT NOT NULL,
                criterion_type TEXT NOT NULL, criterion_stage TEXT NOT NULL,
                criterion_is_required INTEGER NOT NULL, assessment_value TEXT NOT NULL, notes TEXT,
                PRIMARY KEY (decision_id, criterion_id)
            );
            """
        )
        connection.execute(
            "INSERT INTO screening_criteria VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("00000000-0000-0000-0000-000000000001", "lean_energy", "Legacy", None, "inclusion", "title_abstract", 0, 1, 1),
        )
        connection.executemany(
            "INSERT INTO schema_migrations(version) VALUES (?)",
            [(f"{number:04d}_placeholder.sql",) for number in range(1, 12)],
        )
        connection.execute("DELETE FROM schema_migrations WHERE version = '0011_placeholder.sql'")
        connection.execute("INSERT INTO schema_migrations(version) VALUES ('0007_screening_criteria.sql')")
        connection.execute("INSERT INTO schema_migrations(version) VALUES ('0008_screening_decisions.sql')")

    repository = SqliteScreeningCriterionRepository(database)
    criterion = repository.get("lean_energy", UUID("00000000-0000-0000-0000-000000000001"))
    assert criterion.evaluation_mode is ScreeningCriterionEvaluationMode.MANUAL
    assert criterion.metadata_rule is None
