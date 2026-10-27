"""Unit tests for the CI migration-safety guard."""

from __future__ import annotations

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "ci" / "check_migration_safety.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("check_migration_safety", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_destructive_sql_patterns_are_detected() -> None:
    module = _load_module()
    for sql in (
        "DROP TABLE publications;",
        "ALTER TABLE publications DROP COLUMN doi;",
        "DELETE FROM screening_decisions;",
        "TRUNCATE TABLE import_history;",
        "DROP INDEX idx_publications_doi;",
    ):
        assert module._destructive_hits(sql), sql


def test_non_destructive_sql_is_not_flagged() -> None:
    module = _load_module()
    for sql in (
        "CREATE TABLE example (id INTEGER PRIMARY KEY);",
        "CREATE INDEX idx_example ON example(id);",
        "ALTER TABLE example ADD COLUMN note TEXT;",
        "INSERT INTO example(id) VALUES (1);",
    ):
        assert not module._destructive_hits(sql), sql
