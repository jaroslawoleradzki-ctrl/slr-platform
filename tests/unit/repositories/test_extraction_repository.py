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
        field_key=field_key,
        status=ValueStatus.PRESENT,
        origin=ValueOrigin.REPORTED,
        source_locator="fixture source",
        **kwargs,
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
    assert {
        "extraction_templates",
        "extraction_template_versions",
        "extraction_records",
        "extraction_revisions",
        "extracted_values",
        "extracted_group_items",
    } <= tables
    assert {
        "idx_extraction_records_project",
        "idx_extraction_revisions_lookup",
        "idx_extracted_values_synthesis",
    } <= indexes
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
        record_id=record.record_id,
        project_id="project-a",
        publication_id=record.publication_id,
        revision_index=1,
        reviewer_id="alice",
        completeness_status=ExtractionCompletenessStatus.IN_PROGRESS,
        publication_values=[
            _value("text", text_value="alpha", source_page="12", reviewer_note="note"),
            _value("integer", int_value=7),
            _value("decimal", float_value=1.5),
            _value("boolean", bool_value=True),
            _value("unit", float_value=10.0, unit_value="kWh"),
            _value("json", json_value=["a", "b"]),
        ],
    )
    r2 = ExtractionRevision(
        record_id=record.record_id,
        project_id="project-a",
        publication_id=record.publication_id,
        revision_index=2,
        reviewer_id="bob",
        completeness_status=ExtractionCompletenessStatus.COMPLETE,
        publication_values=[_value("text", text_value="beta")],
    )
    repository.append_revision(r1)
    repository.append_revision(r2)

    assert repository.get_latest_revision("project-a", record.publication_id) == r2
    history = repository.list_revision_history("project-a", record.publication_id)
    assert [item.revision_index for item in history] == [1, 2]
    assert history[0].publication_values == sorted(r1.publication_values, key=lambda item: item.field_key)
    assert history[1] == r2
    assert (
        repository.get_record("project-a", record.publication_id).current_status
        is ExtractionCompletenessStatus.COMPLETE
    )


def test_failed_append_rolls_back_first_record_and_later_revision(repository):
    """A persistence failure cannot leave an orphan record or partial revision."""
    duplicate_id = uuid4()
    record = _record("project-a")
    failed_first = ExtractionRevision(
        record_id=record.record_id,
        project_id="project-a",
        publication_id=record.publication_id,
        revision_index=1,
        reviewer_id="alice",
        completeness_status=ExtractionCompletenessStatus.IN_PROGRESS,
        publication_values=[
            _value("one", value_id=duplicate_id, text_value="One"),
            _value("two", value_id=duplicate_id, text_value="Two"),
        ],
    )
    with pytest.raises(ExtractionRevisionConflictError):
        repository.append_revision(failed_first, new_record=record)
    with pytest.raises(ExtractionRecordNotFoundError):
        repository.get_record("project-a", record.publication_id)

    repository.create_record(record)
    first = ExtractionRevision(
        record_id=record.record_id,
        project_id="project-a",
        publication_id=record.publication_id,
        revision_index=1,
        reviewer_id="alice",
        completeness_status=ExtractionCompletenessStatus.IN_PROGRESS,
        publication_values=[_value("one", text_value="One")],
    )
    repository.append_revision(first)
    with pytest.raises(ExtractionRevisionConflictError):
        repository.append_revision(
            ExtractionRevision(
                record_id=record.record_id,
                project_id="project-a",
                publication_id=record.publication_id,
                revision_index=2,
                reviewer_id="alice",
                completeness_status=ExtractionCompletenessStatus.COMPLETE,
                publication_values=[
                    _value("one", value_id=duplicate_id, text_value="Updated"),
                    _value("two", value_id=duplicate_id, text_value="Duplicate"),
                ],
            )
        )
    history = repository.list_revision_history("project-a", record.publication_id)
    assert len(history) == 1
    assert history[0].publication_values[0].text_value == "One"
    assert repository.get_record("project-a", record.publication_id).current_status is ExtractionCompletenessStatus.IN_PROGRESS


def test_missingness_and_unclear_values_preserve_status_and_notes(repository):
    record = repository.create_record(_record("project-a"))
    revision = ExtractionRevision(
        record_id=record.record_id,
        project_id="project-a",
        publication_id=record.publication_id,
        revision_index=1,
        reviewer_id="alice",
        completeness_status=ExtractionCompletenessStatus.IN_PROGRESS,
        publication_values=[
            ExtractedValueState(field_key="missing", status=ValueStatus.NOT_REPORTED),
            ExtractedValueState(
                field_key="unclear",
                status=ValueStatus.UNCLEAR,
                reviewer_note="The source is ambiguous.",
            ),
        ],
    )
    repository.append_revision(revision)
    restored = repository.get_latest_revision("project-a", record.publication_id)
    assert restored is not None
    assert restored.publication_values == revision.publication_values


def test_group_items_are_independent_and_ordered(repository):
    record = repository.create_record(_record("project-a"))
    revision = ExtractionRevision(
        record_id=record.record_id,
        project_id="project-a",
        publication_id=record.publication_id,
        revision_index=1,
        reviewer_id="alice",
        completeness_status=ExtractionCompletenessStatus.IN_PROGRESS,
        group_items=[
            ExtractedGroupItemState(
                group_key="relationship", item_index=index, values=[_value("outcome", text_value=f"value-{index}")]
            )
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
        record_id=record.record_id,
        project_id="project-a",
        publication_id=record.publication_id,
        revision_index=2,
        reviewer_id="alice",
        completeness_status=ExtractionCompletenessStatus.IN_PROGRESS,
    )
    with pytest.raises(ExtractionRevisionConflictError, match="Revision index must be 1"):
        repository.append_revision(wrong_index)
    invalid = ExtractionRevision(
        record_id=record.record_id,
        project_id="project-a",
        publication_id=record.publication_id,
        revision_index=1,
        reviewer_id="alice",
        completeness_status=ExtractionCompletenessStatus.IN_PROGRESS,
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
        repository.append_revision(
            ExtractionRevision(
                record_id=record.record_id,
                project_id="project-a",
                publication_id=record.publication_id,
                revision_index=1,
                reviewer_id="alice",
                completeness_status=ExtractionCompletenessStatus.IN_PROGRESS,
                publication_values=[_value("title", text_value="one")],
            )
        )
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
        extraction_repo.append_revision(
            ExtractionRevision(
                record_id=record.record_id,
                project_id=record.project_id,
                publication_id=record.publication_id,
                revision_index=1,
                reviewer_id="alice",
                completeness_status=ExtractionCompletenessStatus.IN_PROGRESS,
                group_items=[
                    ExtractedGroupItemState(group_key="group", item_index=1, values=[_value("value", text_value="x")])
                ],
            )
        )
    service = SqliteProjectDeletionService(
        project_repo=project_repo, extraction_repo=extraction_repo, tx_manager=SqliteTransactionManager(db_path)
    )
    service.delete_project("project-a")
    with pytest.raises(ExtractionRecordNotFoundError):
        extraction_repo.get_record("project-a", record_a.publication_id)
    assert extraction_repo.get_latest_revision("project-b", record_b.publication_id) is not None
    assert catalog.get_version("generic", "1.0.0").name == "Generic v1"
    with sqlite3.connect(db_path) as connection:
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM project_extraction_configurations WHERE project_id = 'project-a'"
            ).fetchone()[0]
            == 0
        )
        assert (
            connection.execute("SELECT COUNT(*) FROM extraction_revisions WHERE project_id = 'project-a'").fetchone()[0]
            == 0
        )
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM extracted_values WHERE revision_id NOT IN (SELECT revision_id FROM extraction_revisions)"
            ).fetchone()[0]
            == 0
        )


def test_durable_group_item_id_across_revisions_reordering_insertion_and_deletion(repository):
    """Verifies that durable group_item_id UUID survives persistence, edits, insertions, reordering, and deletion across revisions."""
    record = repository.create_record(_record("project-a"))

    # 1. Revision 1: Create Relation A and Relation B with durable IDs
    id_a = uuid4()
    id_b = uuid4()
    item_a_r1 = ExtractedGroupItemState(
        group_item_id=id_a,
        group_key="lean_ee_relationships",
        item_index=1,
        values=[_value("practice", text_value="5S"), _value("effect", float_value=12.5, unit_value="%")],
    )
    item_b_r1 = ExtractedGroupItemState(
        group_item_id=id_b,
        group_key="lean_ee_relationships",
        item_index=2,
        values=[_value("practice", text_value="TPM"), _value("effect", float_value=8.0, unit_value="%")],
    )
    r1 = ExtractionRevision(
        record_id=record.record_id,
        project_id="project-a",
        publication_id=record.publication_id,
        revision_index=1,
        reviewer_id="reviewer-1",
        completeness_status=ExtractionCompletenessStatus.IN_PROGRESS,
        group_items=[item_a_r1, item_b_r1],
    )
    repository.append_revision(r1)

    # Verify readback of Revision 1
    hydrated_r1 = repository.get_latest_revision("project-a", record.publication_id)
    assert hydrated_r1 is not None
    assert len(hydrated_r1.group_items) == 2
    assert hydrated_r1.group_items[0].group_item_id == id_a
    assert hydrated_r1.group_items[0].item_index == 1
    vals_a_r1 = {v.field_key: v for v in hydrated_r1.group_items[0].values}
    assert vals_a_r1["practice"].text_value == "5S"
    assert vals_a_r1["effect"].float_value == 12.5
    assert hydrated_r1.group_items[1].group_item_id == id_b
    assert hydrated_r1.group_items[1].item_index == 2

    # 2. Revision 2: Insert Relation X at top (item_index 1), shift A to index 2, edit A's value, shift B to index 3
    id_x = uuid4()
    item_x_r2 = ExtractedGroupItemState(
        group_item_id=id_x,
        group_key="lean_ee_relationships",
        item_index=1,
        values=[_value("practice", text_value="Kaizen"), _value("effect", float_value=5.0, unit_value="%")],
    )
    item_a_r2 = ExtractedGroupItemState(
        group_item_id=id_a,  # Same durable ID
        group_key="lean_ee_relationships",
        item_index=2,  # Shifted index
        values=[
            _value("practice", text_value="5S Extended"),
            _value("effect", float_value=15.0, unit_value="%"),
        ],  # Edited
    )
    item_b_r2 = ExtractedGroupItemState(
        group_item_id=id_b,  # Same durable ID
        group_key="lean_ee_relationships",
        item_index=3,  # Shifted index
        values=[_value("practice", text_value="TPM"), _value("effect", float_value=8.0, unit_value="%")],
    )
    r2 = ExtractionRevision(
        record_id=record.record_id,
        project_id="project-a",
        publication_id=record.publication_id,
        revision_index=2,
        reviewer_id="reviewer-1",
        completeness_status=ExtractionCompletenessStatus.IN_PROGRESS,
        group_items=[item_x_r2, item_a_r2, item_b_r2],
    )
    repository.append_revision(r2)

    # Verify readback of Revision 2
    hydrated_r2 = repository.get_latest_revision("project-a", record.publication_id)
    assert hydrated_r2 is not None
    assert len(hydrated_r2.group_items) == 3
    assert [item.group_item_id for item in hydrated_r2.group_items] == [id_x, id_a, id_b]
    assert [item.item_index for item in hydrated_r2.group_items] == [1, 2, 3]
    # Check edited values on relation A
    vals_a_r2 = {v.field_key: v for v in hydrated_r2.group_items[1].values}
    assert vals_a_r2["practice"].text_value == "5S Extended"
    assert vals_a_r2["effect"].float_value == 15.0

    # 3. Revision 3: Delete Relation A, reorder B to index 1 and X to index 2
    item_b_r3 = ExtractedGroupItemState(
        group_item_id=id_b,  # Same durable ID
        group_key="lean_ee_relationships",
        item_index=1,  # Reordered to index 1
        values=[_value("practice", text_value="TPM"), _value("effect", float_value=8.0, unit_value="%")],
    )
    item_x_r3 = ExtractedGroupItemState(
        group_item_id=id_x,  # Same durable ID
        group_key="lean_ee_relationships",
        item_index=2,  # Reordered to index 2
        values=[_value("practice", text_value="Kaizen"), _value("effect", float_value=5.0, unit_value="%")],
    )
    r3 = ExtractionRevision(
        record_id=record.record_id,
        project_id="project-a",
        publication_id=record.publication_id,
        revision_index=3,
        reviewer_id="reviewer-2",
        completeness_status=ExtractionCompletenessStatus.COMPLETE,
        group_items=[item_b_r3, item_x_r3],
    )
    repository.append_revision(r3)

    # Verify readback of Revision 3
    hydrated_r3 = repository.get_latest_revision("project-a", record.publication_id)
    assert hydrated_r3 is not None
    assert len(hydrated_r3.group_items) == 2
    assert [item.group_item_id for item in hydrated_r3.group_items] == [id_b, id_x]
    assert [item.item_index for item in hydrated_r3.group_items] == [1, 2]

    # Verify complete history isolation (no cross-revision corruption)
    history = repository.list_revision_history("project-a", record.publication_id)
    assert len(history) == 3
    # Revision 1 history snapshot
    assert [item.group_item_id for item in history[0].group_items] == [id_a, id_b]
    vals_a_h1 = {v.field_key: v for v in history[0].group_items[0].values}
    assert vals_a_h1["practice"].text_value == "5S"
    assert vals_a_h1["effect"].float_value == 12.5
    # Revision 2 history snapshot
    assert [item.group_item_id for item in history[1].group_items] == [id_x, id_a, id_b]
    vals_a_h2 = {v.field_key: v for v in history[1].group_items[1].values}
    assert vals_a_h2["practice"].text_value == "5S Extended"
    assert vals_a_h2["effect"].float_value == 15.0
    # Revision 3 history snapshot
    assert [item.group_item_id for item in history[2].group_items] == [id_b, id_x]
