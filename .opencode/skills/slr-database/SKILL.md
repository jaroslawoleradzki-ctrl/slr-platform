---
name: SLR Database
description: Use when changing SQLite schema, adding or reviewing a migration, handling transaction safety, preserving research records, planning backup/restore, or assessing rollback for SLR Platform persistence.
---

# SLR Database

## Activation criteria

Activate for:

- a new `migrations/NNNN_*.sql` file or a schema change;
- repository SQL, indexes, constraints, or transaction handling;
- data backfills, reconciliation, archival, or corrective scripts;
- backup, restore, rollback, or schema-compatibility questions;
- any change that can alter persisted research records.

## Required context

Read `AGENTS.md`, then:

- `migrations/` (all numbered files, especially the latest);
- the owning repository's `_apply_migrations()` and transaction code;
- `docs/data-model.md` and `docs/SQLITE_CONSTRAINTS_REVIEW.md`;
- `tests/fixtures/migrations/` and migration-focused tests;
- the affected service and its integrity tests.

## Workflow

1. Identify the persisted contract and every reader/writer of the table.
2. Choose an additive migration first: new table, new nullable column, or new
   index. Avoid destructive rewrites unless explicitly approved.
3. Use the next free number. Never edit an applied migration.
4. Make application idempotent and compatible with `schema_migrations`.
5. Wrap multi-statement changes in a transaction; preserve existing repository
   transaction boundaries.
6. Backfill deterministically and preserve provenance/audit columns.
7. Test upgrade from the prior schema, not only a fresh database.
8. Rehearse restore on a copy: copy the database, run
   `PRAGMA integrity_check` and `PRAGMA foreign_key_check`, then exercise the
   affected read path.
9. Document rollback or forward-recovery steps. If rollback is unsafe, say so.

## Safety constraints

- Never modify or delete production data.
- Never read or copy the real `data/` database from an agent shell; use a
  disposable copy or the safe test wrapper.
- Never edit an already-applied migration.
- Never drop a table or column, rewrite identifiers, or merge records without
  explicit human approval and a documented recovery path.
- Never run a destructive reconciliation automatically.
- Never remove audit or provenance columns to simplify a schema.
- Never assume foreign keys are enforced; inspect the actual schema.
- Do not commit a database file or test artifact.

## Validation

```bash
bash scripts/agent/safe_pytest.sh tests/unit/repositories tests/integration -k "migration or reconciliation"
bash scripts/agent/safe_pytest.sh
uv run --frozen --no-sync ruff check app tests scripts
uv run --frozen --no-sync mypy app
uv run --frozen --no-sync python scripts/ci/check_migration_safety.py --base-ref origin/development
git diff --check
```

The migration-safety guard rejects modified/deleted existing migrations and
requires the `migration-safety: approved-destructive` marker for destructive SQL
in an added migration.

Also verify on a disposable copy:

```sql
PRAGMA integrity_check;
PRAGMA foreign_key_check;
```

## Expected outputs

- Migration file and the repository code that applies it.
- Upgrade-test evidence from the previous schema.
- Integrity/foreign-key check results.
- Backup/restore rehearsal notes.
- Rollback or forward-recovery plan.
- Explicit statement of any records that could be affected.

## References

- `AGENTS.md` sections B, C, and F
- `migrations/`
- `app/repositories/`
- `docs/data-model.md`
- `docs/SQLITE_CONSTRAINTS_REVIEW.md`
- `tests/fixtures/migrations/`
- `tests/unit/repositories/`
- `tests/integration/`
