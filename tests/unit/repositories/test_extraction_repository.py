import sqlite3
from pathlib import Path
from uuid import UUID, uuid4

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
from app.repositories.extraction_repository import (
    ExtractionRecordConflictError,
    ExtractionRecordNotFoundError,
    ExtractionRevisionConflictError,
    SqliteExtractionRepository,
)
from app.repositories.extraction_template_repository import SqliteExtractionTemplateRepository
from app.repositories.project_repository import SqliteProjectRepository
from app.repositories.transaction_manager import SqliteTransactionManager
from app.services.project_deletion_service import SqliteProjectDeletionService


def _template_catalog(db_path: Path) -> SqliteExtractionTemplateRepository:
    catalog = SqliteExtractionTemplateRepository(db_path)
    catalog.register_template(ExtractionTemplate(template_id="generic", name="Generic"))
    catalog.register_version(
        ExtractionTemplateVersion(template_id="generic", version="1.0.0", name="Generic v1", is_published=True)
    )
    return catalog


def _record(project_id: str, publication_id: UUID | None = None) -> ExtractionRecord:
    return ExtractionRecord(
        project_id=project_id,
        publication_id=publication_id or uuid4(),
        template_id="generic",
        template_version="1.0.0",
    )


def _value(field_key: str, **kwargs) -> ExtractedValueState:
    return ExtractedValueState(
        field_key=field_key, status=ValueStatus.PRESENT, origin=ValueOrigin.REPORTED, **kwargs
    )


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "extraction.db"


@pytest.fixture
def repository(db_path: Path) -> SqliteExtractionRepository:
    project_repo = SqliteProjectRepository(db_path)
    project_repo.create(Project(project_id="project-a", title="A"))
    project_repo.create(Project(project_id="project-b", title="B"))
    _template_catalog(db_path)
    return SqliteExtractionRepository(db_path)


def test_migration_creates_expected_constraints_and_indexes(db_path: Path):
    repository = SqliteExtractionRepository(db_path)
    _template_catalog(db_path)
    with sqlite3.connect(db_path) as connection:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        indexes = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'index'")}
    assert {"extraction_templates", "extraction_template_versions", "extraction_records", "extraction_revisions", "extracted_values", "extracted_group_items"} <= tables
    assert {"idx_extraction_records_project", "idx_extraction_revisions_lookup", "idx_extracted_values_synthesis"} <= indexes
    with pytest.raises(ExtractionRecordConflictError):
        repository.create_record(_record("missing-project"))


def test_create_and_get_record_enforces_project_publication_uniqueness_and_isolation(repository):
    record = _record("project-a")
    assert repository.create_record(record) == record
    assert repository.get_record("project-a", record.publication_id) == record
    with pytest.raises(ExtractionRecordConflictError):
        repository.create_record(_record("project-a", record.publication_id))
    with pytest.raises(ExtractionRecordNotFoundError):
        repository.get_record("project-b", record.publication_id)


def test_append_only_history_latest_and_typed_value_hydration(repository):
    record = repository.create_record(_record("project-a"))
    r1 = ExtractionRevision(
        record_id=record.record_id, project_id="project-a", publication_id=record.publication_id,
        revision_index=1, reviewer_id="alice", completeness_status=ExtractionCompletenessStatus.IN_PROGRESS,
        publication_values=[
            _value("text", text_value="alpha", source_page="12", reviewer_note="note"),
            _value("integer", int_value=7), _value("decimal", float_value=1.5),
            _value("boolean", bool_value=True), _value("unit", float_value=10.0, unit_value="kWh"),
            _value("json", json_value=["a", "b"]),
        ],
    )
    r2 = ExtractionRevision(
        record_id=record.record_id, project_id="project-a", publication_id=record.publication_id,
        revision_index=2, reviewer_id="bob", completeness_status=ExtractionCompletenessStatus.COMPLETE,
        publication_values=[_value("text", text_value="beta")],
    )
    repository.append_revision(r1)
    repository.append_revision(r2)

    assert repository.get_latest_revision("project-a", record.publication_id) == r2
    history = repository.list_revision_history("project-a", record.publication_id)
    assert [item.revision_index for item in history] == [1, 2]
    assert history[0].publication_values == sorted(r1.publication_values, key=lambda item: item.field_key)
    assert history[1] == r2
    assert repository.get_record("project-a", record.publication_id).current_status is ExtractionCompletenessStatus.COMPLETE


def test_missingness_and_unclear_values_preserve_status_origin_and_provenance(repository):
    record = repository.create_record(_record("project-a"))
    revision = ExtractionRevision(
        record_id=record.record_id, project_id="project-a", publication_id=record.publication_id,
        revision_index=1, reviewer_id="alice", completeness_status=ExtractionCompletenessStatus.IN_PROGRESS,
        publication_values=[
            ExtractedValueState(field_key="missing", status=ValueStatus.NOT_REPORTED, origin=ValueOrigin.REPORTED),
            ExtractedValueState(field_key="unclear", status=ValueStatus.UNCLEAR, origin=ValueOrigin.REVIEWER_CODED, source_quote="unclear"),
        ],
    )
    repository.append_revision(revision)
    restored = repository.get_latest_revision("project-a", record.publication_id)
    assert restored is not None
    assert restored.publication_values == revision.publication_values


def test_group_items_are_independent_and_ordered(repository):
    record = repository.create_record(_record("project-a"))
    revision = ExtractionRevision(
        record_id=record.record_id, project_id="project-a", publication_id=record.publication_id,
        revision_index=1, reviewer_id="alice", completeness_status=ExtractionCompletenessStatus.IN_PROGRESS,
        group_items=[
            ExtractedGroupItemState(group_key="relationship", item_index=index, values=[_value("outcome", text_value=f"value-{index}")])
            for index in (3, 1, 2)
        ],
    )
    repository.append_revision(revision)
    restored = repository.get_latest_revision("project-a", record.publication_id)
    assert restored is not None
    assert [item.item_index for item in restored.group_items] == [1, 2, 3]
    assert [item.values[0].text_value for item in restored.group_items] == ["value-1", "value-2", "value-3"]


def test_invalid_revision_index_and_duplicate_group_item_roll_back_atomically(repository, db_path: Path):
    record = repository.create_record(_record("project-a"))
    wrong_index = ExtractionRevision(
        record_id=record.record_id, project_id="project-a", publication_id=record.publication_id,
        revision_index=2, reviewer_id="alice", completeness_status=ExtractionCompletenessStatus.IN_PROGRESS,
    )
    with pytest.raises(ExtractionRevisionConflictError, match="Revision index must be 1"):
        repository.append_revision(wrong_index)
    invalid = ExtractionRevision(
        record_id=record.record_id, project_id="project-a", publication_id=record.publication_id,
        revision_index=1, reviewer_id="alice", completeness_status=ExtractionCompletenessStatus.IN_PROGRESS,
        group_items=[
            ExtractedGroupItemState(group_key="group", item_index=1),
            ExtractedGroupItemState(group_key="group", item_index=1),
        ],
    )
    with pytest.raises(ExtractionRevisionConflictError, match="atomically"):
        repository.append_revision(invalid)
    with sqlite3.connect(db_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM extraction_revisions").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM extracted_group_items").fetchone()[0] == 0


def test_batch_hydration_has_bounded_query_count_and_no_n_plus_one(db_path: Path):
    statements: list[str] = []
    project_repo = SqliteProjectRepository(db_path)
    project_repo.create(Project(project_id="project-a", title="A"))
    _template_catalog(db_path)
    repository = SqliteExtractionRepository(db_path, query_observer=statements.append)
    records = [repository.create_record(_record("project-a")) for _ in range(3)]
    for record in records:
        repository.append_revision(ExtractionRevision(
            record_id=record.record_id, project_id="project-a", publication_id=record.publication_id,
            revision_index=1, reviewer_id="alice", completeness_status=ExtractionCompletenessStatus.IN_PROGRESS,
            publication_values=[_value("title", text_value="one")],
        ))
    statements.clear()
    hydrated = repository.get_latest_revision_batch("project-a", [record.publication_id for record in records])
    selects = [statement for statement in statements if statement.lstrip().upper().startswith(("SELECT", "WITH"))]
    assert len(selects) == 3
    assert all(hydrated[record.publication_id] is not None for record in records)


def test_project_hard_delete_removes_project_data_but_preserves_catalog_and_other_project(db_path: Path):
    project_repo = SqliteProjectRepository(db_path)
    project_repo.create(Project(project_id="project-a", title="A"))
    project_repo.create(Project(project_id="project-b", title="B"))
    catalog = _template_catalog(db_path)
    extraction_repo = SqliteExtractionRepository(db_path)
    record_a = extraction_repo.create_record(_record("project-a"))
    record_b = extraction_repo.create_record(_record("project-b"))
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """INSERT INTO project_extraction_configurations
            (project_id, template_id, template_version) VALUES (?, ?, ?)""",
            ("project-a", "generic", "1.0.0"),
        )
    for record in (record_a, record_b):
        extraction_repo.append_revision(ExtractionRevision(
            record_id=record.record_id, project_id=record.project_id, publication_id=record.publication_id,
            revision_index=1, reviewer_id="alice", completeness_status=ExtractionCompletenessStatus.IN_PROGRESS,
            group_items=[ExtractedGroupItemState(group_key="group", item_index=1, values=[_value("value", text_value="x")])],
        ))
    service = SqliteProjectDeletionService(
        project_repo=project_repo, extraction_repo=extraction_repo, tx_manager=SqliteTransactionManager(db_path)
    )
    service.delete_project("project-a")
    with pytest.raises(ExtractionRecordNotFoundError):
        extraction_repo.get_record("project-a", record_a.publication_id)
    assert extraction_repo.get_latest_revision("project-b", record_b.publication_id) is not None
    assert catalog.get_version("generic", "1.0.0").name == "Generic v1"
    with sqlite3.connect(db_path) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM project_extraction_configurations WHERE project_id = 'project-a'"
        ).fetchone()[0] == 0
        assert connection.execute(
            "SELECT COUNT(*) FROM extraction_revisions WHERE project_id = 'project-a'"
        ).fetchone()[0] == 0
        assert connection.execute(
            "SELECT COUNT(*) FROM extracted_values WHERE revision_id NOT IN (SELECT revision_id FROM extraction_revisions)"
        ).fetchone()[0] == 0
