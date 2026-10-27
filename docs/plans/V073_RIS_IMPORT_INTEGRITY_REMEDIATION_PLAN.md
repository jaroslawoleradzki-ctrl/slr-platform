# SLR Platform v0.7.3 — RIS Import Integrity Remediation Plan

## 1. Purpose

This plan revises the existing v0.7.3 remediation plan using the architectural and
methodological decisions required for RIS import integrity. It preserves the five
implementation packages, but expands the architecture for source records,
canonical publications, conservative import deduplication, auditability,
historical recovery, and PRISMA accounting.

No application code, database, import, deduplication, screening decision, commit,
push, merge, tag, release, or deployment is performed by this document.

## 2. Core architectural distinction

### A. Source Record

A source record is an individual bibliographic record retrieved from a specific
search or imported RIS file. It represents what was originally observed from a
source.

### B. Canonical Publication

A canonical publication is a unique scholarly work represented by one or more
source records.

The architecture must preserve:

- every source record,
- original source and import provenance,
- source filename,
- record index within the RIS file,
- original DOI and normalized DOI,
- bibliographic metadata,
- relationships between source records and canonical publications,
- duplicate matching decisions,
- manual review decisions,
- merge history.

The current schema stores publications in `project_publications` and import audit
metadata in `import_history`. It does not currently preserve skipped source
records or source-to-canonical relationships. Therefore, backward-compatible
extensions are required.

## 3. Existing schema and repository baseline

### Existing tables

- `project_publications`: stores canonical/source publication documents, provenance,
  identifiers, import linkage, supersession, and pre-screening status.
- `import_history`: stores aggregate import audit records, including `records_count`,
  `status`, and `warnings`.
- `duplicate_review_decisions`: stores reviewer decisions for duplicate groups.
- `duplicate_group_merges`: stores technical merge history and pre-merge snapshots.

### Existing import behavior

RIS records are mapped to `Publication` objects with:

- `source = "ris"` (or `source_database` if supplied)
- `source_record_id = normalized DOI` when a DOI is present
- otherwise `source_record_id = record title`

`SqliteProjectPublicationRepository.import_source_publications` skips an incoming
record when its `_source_key` already exists:

```
(provenance.source.strip().casefold(), provenance.source_record_id.strip())
```

This means:

- DOI-based duplicates are exact normalized-DOI matches.
- No-DOI records are exact stripped-title matches.
- Matching is against the existing project corpus.
- Skipped records are not persisted.
- Only aggregate skip counts are stored in `import_history.warnings`.

This behavior is unsafe for no-DOI records because identical titles may represent
distinct works.

## 4. Conservative import deduplication rules

### Rule A — Identical valid DOI

- Recognize as an exact duplicate candidate.
- Do not create a second canonical publication.
- Preserve the incoming source record and provenance.
- Record the matched canonical publication.
- Record the exact matching reason.
- Never silently discard source information.
- Do not automatically overwrite existing metadata.

### Rule B — Identical title without DOI

- Preserve both source records.
- Do not automatically merge or skip.
- Generate a manual deduplication candidate.
- Preserve author, year, and publication-type differences.

### Rule C — Similar titles

- Preserve both records.
- Generate candidates according to existing configurable similarity rules.
- Do not automatically merge.

### Rule D — Different valid DOI

- Do not automatically merge based on title alone.
- Preserve both records.
- Allow manual review if other metadata suggests a relationship.

### Rule E — Insufficient metadata

- Preserve source evidence whenever technically possible.
- Mark uncertainty explicitly.
- Do not silently skip records.
- Distinguish validation errors from duplicate warnings.

### Idempotency

Repeated imports must be idempotent. A source record must not be imported twice.
Import deduplication must distinguish:

- exact source-record identity,
- canonical publication identity,
- duplicate candidate generation.

## 5. Import provenance and auditability

### Required persistent concepts

The system must persist:

- source record identity,
- source file and record index,
- original and normalized DOI,
- original bibliographic metadata,
- canonical publication linkage,
- duplicate match type and reason,
- manual review decisions,
- merge history,
- recovery provenance.

### Preferred backward-compatible data model

Prefer extending existing tables and adding one audit table rather than
redesigning unrelated modules.

#### Reuse existing tables

- `project_publications`: continue to store canonical publication documents and
  source provenance.
- `import_history`: retain aggregate import audit and warnings.
- `duplicate_review_decisions`: reuse for manual duplicate candidates.
- `duplicate_group_merges`: reuse for confirmed merges.

#### New table: `import_source_records`

Recommended minimal addition:

```
import_source_records (
  source_record_id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  import_id TEXT NOT NULL,
  source_filename TEXT,
  source_record_index INTEGER NOT NULL,
  title TEXT NOT NULL,
  publication_year INTEGER,
  original_doi TEXT,
  normalized_doi TEXT,
  authors_json TEXT,
  document_type TEXT,
  provenance_json TEXT NOT NULL,
  canonical_publication_id TEXT,
  duplicate_match_type TEXT,
  duplicate_match_reason TEXT,
  duplicate_candidate_group_id TEXT,
  recovery_status TEXT,
  created_at TEXT NOT NULL
)
```

This table preserves every source record, including skipped records, and links it
to a canonical publication.

#### New table: `import_skip_audit`

Recommended for historical and future skip diagnostics:

```
import_skip_audit (
  skip_audit_id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  import_id TEXT NOT NULL,
  source_filename TEXT,
  source_record_index INTEGER NOT NULL,
  source_title TEXT NOT NULL,
  source_doi TEXT,
  matched_publication_id TEXT,
  match_type TEXT NOT NULL,
  match_reason TEXT NOT NULL,
  proposed_action TEXT NOT NULL,
  review_required INTEGER NOT NULL,
  recovery_status TEXT NOT NULL,
  created_at TEXT NOT NULL
)
```

#### Indexes and constraints

- Unique `(project_id, import_id, source_record_index)`.
- Index `(project_id, normalized_doi)`.
- Index `(project_id, canonical_publication_id)`.
- Foreign-key linkage where practical, but preserve compatibility with existing
  SQLite migrations.

#### Repository changes

- Extend `ProjectPublicationRepository` or add a dedicated
  `ImportSourceRecordRepository`.
- Add methods for creating, listing, and finding source records.
- Add idempotent recovery lookup by recovery fingerprint.
- Preserve existing repository interfaces for tests.

#### API contracts

- Add read-only endpoints for source records and skip audit entries.
- Add structured warning objects to import history responses.
- Keep existing `warnings` string tuples for backward compatibility.

#### Transaction boundaries

- Import file parsing, source-record persistence, canonical publication insertion,
  skip audit creation, and import history creation occur in one transaction.
- Recovery operations occur in separate explicitly authorized transactions.
- No automatic production recovery occurs during normal import.

## 6. Historical recovery for 62 skipped records

### Source evidence

The original eight Google Scholar RIS files contain:

- GS01.ris: 380 source records
- GS2.ris: 15
- GS3.ris: 29
- GS4.ris: 8
- GS5.ris: 20
- GS6.ris: 17
- GS7.ris: 19
- GS8.ris: 20

Total: 508 source records.

Existing production import results:

- GS01.ris: 378 imported
- GS2.ris: 11
- GS3.ris: 19
- GS4.ris: 5
- GS5.ris: 14
- GS6.ris: 6
- GS7.ris: 2
- GS8.ris: 11

Total: 446 imported, 62 skipped.

### Recovery classification

Each of the 62 skipped records must be classified as:

1. Confirmed exact DOI duplicate.
2. Confirmed duplicate based on verified evidence.
3. Ambiguous potential duplicate.
4. Confirmed distinct publication.
5. Insufficient evidence.

Do not assume all 62 records must be restored.

### Dry-run reconciliation report

Produce one row per source record, including:

- source file,
- source record index,
- title,
- DOI,
- matched publication ID,
- match evidence,
- proposed action,
- review requirement,
- recovery status.

### Ambiguous records

- Preserve source evidence.
- Create manual deduplication candidates.
- Require researcher approval before modifying the canonical corpus.

### Recovery safety

- Recovery is idempotent.
- Previously resolved duplicate groups are not reopened automatically.
- Existing canonical publication IDs remain stable.
- Existing screening decisions remain valid.
- Existing merges remain valid.

## 7. PRISMA accounting

### Counting rules

Distinguish source-record counts from canonical publication counts.

Define:

- records identified: source records found by searches and imports.
- records imported: source records accepted into the Working Collection.
- exact duplicates identified during import: source records skipped by exact DOI.
- duplicates resolved during manual deduplication: canonical publications merged.
- records remaining before screening: active canonical publications.
- records screened: canonical publications with screening decisions.
- records excluded: canonical publications excluded at each stage.
- full-text assessment: canonical publications assessed.
- studies included: final included canonical publications.

### Invariants

- Source-record counts may exceed canonical publication counts.
- PRISMA screening counts use canonical publications, not source records.
- Repeated searches must not double-count without explicit handling.
- Recovered records must be counted exactly once after recovery.
- Existing screening decisions must not be reset.
- PRISMA calculations must be derived from persistent data.

### Reconciliation checks

- Source records minus exact DOI duplicates should reconcile with imported
  canonical publications.
- Canonical publication count before deduplication should equal active source
  records after exact-duplicate handling.
- Technical merge count should equal superseded canonical members.
- Screening counts should reference active canonical publications only.

## 8. Metadata preservation

Multiple sources may describe the same publication. For example, Crossref may
provide a DOI and journal name while Google Scholar provides the same DOI with
different or more complete metadata.

Requirements:

- retain both source records,
- link them to the same canonical publication,
- preserve original metadata,
- never silently overwrite canonical fields,
- define controlled metadata enrichment rules,
- retain provenance for enriched fields.

Do not implement a complex metadata enrichment engine unless necessary. Prefer
metadata preservation and provenance linkage first.

## 9. Existing deduplication safety

The project has existing reviewed duplicate groups and completed merges.

Guarantees:

- no existing decisions are deleted,
- no completed merges are undone,
- no screening decisions are reset,
- recovered records do not automatically reopen previously resolved groups,
- duplicate candidates remain auditable,
- existing canonical publication IDs remain stable.

## 10. Five implementation packages

### WP1 — Conservative Import Rules

- Scope: change RIS import duplicate detection so automatic skipping occurs only
  for exact valid DOI duplicates.
- Affected files/components:
  - `app/api/routers/search_strategy.py`
  - `app/services/project_import_service.py`
  - `app/repositories/project_publication_repository.py`
- Dependencies: WP2 schema changes for source-record and skip-audit persistence.
  WP1 must not be implemented as a standalone silent change unless minimal
  warnings are acceptable; full auditability requires WP2.
- Required migrations: none for minimal rule change; WP2 migrations required for
  full audit.
- Acceptance criteria:
  - exact DOI duplicates are skipped,
  - no-DOI records are not silently skipped,
  - warnings remain accurate.
- Risks: increased Working Collection size and review workload.
- Rollback: revert import rule change.
- Recommended branch: `wp1-conservative-import-rules`
- Recommended worktree: `wt-wp1-conservative-import-rules`
- Recommended model: backend-focused coding model.

### WP2 — Provenance and Audit

- Scope: persist source records, source-to-canonical links, matching reasons,
  and import history.
- Affected files/components:
  - migrations
  - `app/repositories/project_publication_repository.py`
  - new source-record repository
  - `app/services/project_import_service.py`
  - import DTOs and routers
- Dependencies: none; this is foundational.
- Required migrations: add `import_source_records` and `import_skip_audit`.
- Acceptance criteria:
  - every source record is traceable,
  - every skip has a reason,
  - existing projects remain compatible.
- Risks: migration complexity and storage growth.
- Rollback: migration rollback or ignore new tables.
- Recommended branch: `wp2-import-provenance-audit`
- Recommended worktree: `wt-wp2-import-provenance-audit`
- Recommended model: backend/data coding model.

### WP3 — Duplicate Candidate Integration

- Scope: integrate ambiguous import matches with the existing manual deduplication
  workflow.
- Affected files/components:
  - duplicate group builder
  - duplicate review service
  - import service
  - deduplication API
- Dependencies: WP1 and WP2.
- Required migrations: none beyond WP2.
- Acceptance criteria:
  - ambiguous candidates appear in manual review,
  - no automatic merge occurs for ambiguous records.
- Risks: additional reviewer workload.
- Rollback: disable candidate generation.
- Recommended branch: `wp3-import-duplicate-candidates`
- Recommended worktree: `wt-wp3-import-duplicate-candidates`
- Recommended model: backend/domain coding model.

### WP4 — Import Diagnostics

- Scope: expose structured import warnings and source-level diagnostics in the
  frontend.
- Affected files/components:
  - `frontend/src/components/imports/FileDropzone.tsx`
  - Sources & Imports page
  - frontend types and API services
- Dependencies: WP2 and WP3.
- Required migrations: none.
- Acceptance criteria:
  - warnings are interactive,
  - historical gaps show fallback,
  - failed imports are distinct from warnings.
- Risks: UI complexity.
- Rollback: revert frontend changes.
- Recommended branch: `wp4-import-diagnostics`
- Recommended worktree: `wt-wp4-import-diagnostics`
- Recommended model: frontend coding model.

### WP5 — Historical Recovery and PRISMA Reconciliation

- Scope: provide dry-run reconciliation, researcher approval, controlled
  recovery, and PRISMA verification.
- Affected files/components:
  - recovery scripts/services
  - import history and source-record repositories
  - PRISMA metrics service
- Dependencies: WP1–WP4.
- Required migrations: none beyond WP2.
- Acceptance criteria:
  - 508-row dry-run report is produced,
  - only approved records are recovered,
  - PRISMA counts reconcile.
- Risks: data integrity if source files are incomplete.
- Rollback: restore from verified backup.
- Recommended branch: `wp5-historical-recovery-prisma`
- Recommended worktree: `wt-wp5-historical-recovery-prisma`
- Recommended model: backend/data coding model.

### Dependency graph

```
WP2 -> WP1 -> WP3 -> WP4 -> WP5
```

WP1 depends on WP2 for full auditability. WP3 depends on WP1 and WP2. WP4
depends on WP2 and WP3. WP5 depends on all previous packages.

## 11. Test strategy

### WP1 tests

- identical DOI across multiple RIS imports is skipped,
- DOI normalization is applied,
- invalid DOI values do not cause false matches,
- identical title without DOI is imported,
- same title with different DOI is imported,
- same title with different year is imported,
- conference versus journal versions are imported,
- repeated import is idempotent.

### WP2 tests

- source records are persisted,
- skip audit entries are created,
- source-to-canonical links are correct,
- legacy databases migrate successfully,
- historical imports remain readable.

### WP3 tests

- no-DOI candidates are generated,
- ambiguous candidates enter manual review,
- existing merged groups are not reopened,
- duplicate candidates remain auditable.

### WP4 tests

- warning badge interaction works,
- warning counts are correct,
- failed imports are distinct from warnings,
- historical imports without diagnostics show fallback.

### WP5 tests

- dry-run report has one row per source record,
- recovery is idempotent,
- PRISMA reconciliation is correct,
- previous decisions and merges remain valid,
- rollback restores prior state.

## 12. Production recovery safety

1. Verify production database backup.
2. Hash original RIS files.
3. Execute read-only reconciliation.
4. Produce a complete 508-row report.
5. Identify all 62 skipped records.
6. Present ambiguous cases for researcher approval.
7. Execute only explicitly approved recovery actions.
8. Verify corpus and PRISMA counts.
9. Verify previous decisions and merges.
10. Retain rollback capability.

No production recovery may happen during WP1–WP4. WP5 implementation must not
automatically execute production recovery. Production recovery requires separate
authorization.

## 13. Release readiness gates

GATE 1: Architecture and migration review approved.
GATE 2: WP1–WP4 implemented and tested.
GATE 3: 508-record reconciliation dry-run completed.
GATE 4: Researcher reviewed ambiguous cases.
GATE 5: Production backup and migration verified.
GATE 6: Controlled recovery completed and PRISMA reconciled.

Application release readiness is distinct from production data recovery readiness.

## 14. Unresolved architectural questions

1. Whether no-DOI records with identical titles should always be retained or
   sent to manual review.
2. Whether historical recovery should restore all ambiguous records or only
   clearly distinct works.
3. Whether a new migration is acceptable for skip-audit persistence.
4. Whether PRISMA counts should be recalculated after recovery.
5. Whether Google Scholar RIS imports should require DOI extraction improvements
   before further imports.
6. Whether source records should be stored in a new table or embedded in
   publication provenance.

ARCHITECTURE READY: YES
IMPLEMENTATION READY: NO
UNRESOLVED BLOCKERS:
- Original RIS files are not retained in production, so individual recovery
  decisions require external source evidence.
- Researcher approval is required before any recovery.
- Migration strategy requires review before implementation.
RECOMMENDED FIRST PACKAGE: WP2
RECOMMENDED EXECUTION ORDER: WP2 -> WP1 -> WP3 -> WP4 -> WP5