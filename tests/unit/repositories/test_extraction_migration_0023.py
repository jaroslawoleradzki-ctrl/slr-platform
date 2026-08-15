"""Migration safety checks for ADR-0007 / 0023."""
import sqlite3
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from app.domain.extraction import (
    ExtractedValueState,
    ExtractionCompletenessStatus,
    ExtractionRevision,
    InvalidRevisionError,
    InvalidValueError,
    ValueOrigin,
    ValueStatus,
    legacy_extraction_value_hydration,
)
from app.repositories.extraction_repository import SqliteExtractionRepository


def apply_to(db: Path, last: str) -> None:
    with sqlite3.connect(db) as c:
        c.execute("CREATE TABLE IF NOT EXISTS schema_migrations(version TEXT PRIMARY KEY)")
        for p in sorted((Path(__file__).parents[3] / "migrations").glob("*.sql")):
            if p.name <= last and not c.execute(
                "SELECT 1 FROM schema_migrations WHERE version=?", (p.name,)
            ).fetchone():
                c.executescript(p.read_text())
                c.execute("INSERT INTO schema_migrations VALUES(?)", (p.name,))


def legacy(db: Path) -> tuple[str, str]:
    apply_to(db, "0019_group_item_revision_identity.sql")
    pub, rec, one, two, group = (str(uuid4()) for _ in range(5))
    with sqlite3.connect(db) as c:
        c.execute("PRAGMA foreign_keys=ON")
        c.execute("INSERT INTO projects(project_id,title) VALUES('legacy','Legacy')")
        c.execute("INSERT INTO extraction_templates(template_id,name,created_at) VALUES('t','T','2026-01-01T00:00:00+00:00')")
        c.execute("INSERT INTO extraction_template_versions(template_id,version,is_active,is_published,schema_json,created_at) VALUES('t','1.0.0',1,1,'{}','2026-01-01T00:00:00+00:00')")
        c.execute("INSERT INTO project_extraction_configurations(project_id,template_id,template_version,configured_at,updated_at) VALUES('legacy','t','1.0.0','2026-01-01T00:00:00+00:00','2026-01-01T00:00:00+00:00')")
        c.execute("INSERT INTO extraction_records VALUES(?,?,?,?,?,?,?,?)", (rec, "legacy", pub, "t", "1.0.0", "complete", "2026-01-01T00:00:00+00:00", "2026-01-01T00:00:00+00:00"))
        for i, revision_id in enumerate((one, two), 1):
            c.execute("INSERT INTO extraction_revisions VALUES(?,?,?,?,?,?,?,?)", (revision_id, rec, "legacy", pub, i, "reviewer", "complete", "2026-01-01T00:00:00+00:00"))
            c.execute("INSERT INTO extracted_group_items VALUES(?,?,?,?,?)", (revision_id, group, "relations", 1, "2026-01-01T00:00:00+00:00"))
        c.execute("INSERT INTO extracted_values(value_id,revision_id,group_item_id,field_key,status,origin,source_page,source_locator,source_quote,reviewer_note) VALUES(?,?,?,?,?,?,?,?,?,?)", (str(uuid4()), one, None, "legacy_missing", "not_reported", "reported", "p1", "Table 1", "no value", "legacy assessment"))
        c.execute("INSERT INTO extracted_values(value_id,revision_id,group_item_id,field_key,status,origin,source_section,reviewer_note) VALUES(?,?,?,?,?,?,?,?)", (str(uuid4()), two, None, "legacy_na", "not_applicable", "reported", "Methods", "legacy non-applicability"))
        for revision_id in (one, two):
            c.execute("INSERT INTO extracted_values(value_id,revision_id,group_item_id,field_key,status,origin,text_value,source_page,reviewer_note) VALUES(?,?,?,?,?,?,?,?,?)", (str(uuid4()), revision_id, group, "relation", "present", "reported", "5S", "p2", "evidence"))
    return pub, group


def integrity(db: Path) -> None:
    with sqlite3.connect(db) as c:
        assert c.execute('PRAGMA foreign_key_check').fetchall() == []
        assert c.execute('PRAGMA integrity_check').fetchall() == [('ok',)]


def test_0023_preserves_legacy_and_repository_hydration(tmp_path: Path) -> None:
    db = tmp_path / "legacy.db"
    pub, group = legacy(db)
    integrity(db)
    with sqlite3.connect(db) as c:
        before = c.execute("SELECT * FROM extracted_values ORDER BY value_id").fetchall()
    apply_to(db, "0023_extraction_field_state_contract.sql")
    integrity(db)
    with sqlite3.connect(db) as c:
        assert c.execute("SELECT * FROM extracted_values ORDER BY value_id").fetchall() == before
    repo = SqliteExtractionRepository(db)
    history = repo.list_revision_history("legacy", UUID(pub))
    assert len(history) == 2
    assert all(item.group_items[0].group_item_id == UUID(group) for item in history)
    assert history[0].publication_values[0].status.value == "not_reported"
    assert history[0].publication_values[0].origin.value == "reported"
    assert history[1].publication_values[0].status.value == "not_applicable"
    assert history[1].publication_values[0].origin.value == "reported"
    with sqlite3.connect(db) as c:
        revision = c.execute("SELECT revision_id FROM extraction_revisions ORDER BY revision_index LIMIT 1").fetchone()[0]
        c.execute("INSERT INTO extracted_values(value_id,revision_id,field_key,status,origin) VALUES(?,?,?,?,NULL)", (str(uuid4()), revision, "u", "unassessed"))
        c.execute("INSERT INTO extracted_values(value_id,revision_id,field_key,status,origin) VALUES(?,?,?,?,NULL)", (str(uuid4()), revision, "nr", "not_reported"))
        with pytest.raises(sqlite3.IntegrityError):
            c.execute("INSERT INTO extracted_values(value_id,revision_id,field_key,status,origin) VALUES(?,?,?,?,?)", (str(uuid4()), revision, "bad", "present", "bad"))
    integrity(db)


def test_0023_failure_rolls_back(tmp_path: Path) -> None:
    db = tmp_path / "broken.db"
    legacy(db)
    integrity(db)
    script = (Path(__file__).parents[3] / "migrations" / "0023_extraction_field_state_contract.sql").read_text().replace("DROP TABLE extracted_values;", "SELECT no_such_function();\nDROP TABLE extracted_values;")
    with sqlite3.connect(db) as c:
        with pytest.raises(sqlite3.OperationalError):
            c.executescript(script)
        c.rollback()
        assert c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='extracted_values'").fetchone()
        assert not c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='extracted_values_new'").fetchone()
        assert c.execute('SELECT COUNT(*) FROM extracted_values').fetchone()[0] == 4
    integrity(db)


def test_legacy_value_does_not_hide_corrupt_sibling_or_revision_metadata(tmp_path: Path) -> None:
    """Legacy compatibility is per value, never a bypass for a whole revision."""
    db = tmp_path / "mixed.db"
    pub, _ = legacy(db)
    apply_to(db, "0023_extraction_field_state_contract.sql")
    repo = SqliteExtractionRepository(db)

    # The fixture already contains one legacy NOT_REPORTED+REPORTED snapshot
    # and one valid PRESENT+REPORTED group value.  Add an unrelated malformed
    # row which the old schema permits but ADR-0007 does not.
    with sqlite3.connect(db) as c:
        revision = c.execute("SELECT revision_id FROM extraction_revisions ORDER BY revision_index LIMIT 1").fetchone()[0]
        c.execute(
            "INSERT INTO extracted_values(value_id,revision_id,field_key,status,origin) VALUES(?,?,?,?,?)",
            (str(uuid4()), revision, "corrupt", "not_reported", "reviewer_coded"),
        )
    with pytest.raises(InvalidValueError):
        repo.list_revision_history("legacy", UUID(pub))

    legacy_value = ExtractedValueState.model_construct(
        value_id=uuid4(), field_key="legacy", status=ValueStatus.NOT_REPORTED, origin=ValueOrigin.REPORTED
    )
    with legacy_extraction_value_hydration({legacy_value.value_id}):
        with pytest.raises(InvalidRevisionError):
            ExtractionRevision(
                record_id=uuid4(),
                project_id="legacy",
                publication_id=uuid4(),
                revision_index=0,
                reviewer_id="reviewer",
                completeness_status=ExtractionCompletenessStatus.IN_PROGRESS,
                publication_values=[legacy_value],
            )


@pytest.mark.parametrize(
    ("field_key", "source_quote", "text_value"),
    [
        ("   ", None, None),
        ("legacy_quote", "x" * 501, None),
        ("legacy_typed", None, "not actually missing"),
    ],
)
def test_legacy_shaped_but_structurally_invalid_rows_fail_hydration(
    tmp_path: Path, field_key: str, source_quote: str | None, text_value: str | None
) -> None:
    db = tmp_path / "malformed-legacy.db"
    pub, _ = legacy(db)
    apply_to(db, "0023_extraction_field_state_contract.sql")
    with sqlite3.connect(db) as c:
        revision = c.execute("SELECT revision_id FROM extraction_revisions ORDER BY revision_index LIMIT 1").fetchone()[0]
        c.execute(
            """INSERT INTO extracted_values
            (value_id, revision_id, field_key, status, origin, text_value, source_quote)
            VALUES (?, ?, ?, 'not_reported', 'reported', ?, ?)""",
            (str(uuid4()), revision, field_key, text_value, source_quote),
        )
    with pytest.raises((InvalidValueError, ValueError)):
        SqliteExtractionRepository(db).list_revision_history("legacy", UUID(pub))
