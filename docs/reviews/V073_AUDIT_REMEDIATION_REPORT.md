# SLR Platform v0.7.3 — Audit Remediation Report

## 1. Executive summary

The blocking audit findings were remediated across three commits on
`feature/v0.7.3-audit-remediation`. Source records are now project-scoped,
repeated imports are idempotent, title-only RIS candidates enter the existing
manual duplicate-review workflow, diagnostics expose structured counts, and the
reconciliation tool is syntactically valid with a dry-run/approval gate and
basic PRISMA accounting.

Real production recovery was not executed. Historical 508-record reconciliation
remains pending because the original RIS files are not available in this
repository.

## 2. Git branch and worktree

- Branch: `feature/v0.7.3-audit-remediation`
- Worktree: `/home/cloud/dev/wt-v0.7.3-audit-remediation`
- Base: `a82380a58c3cabb8780efe1074277e9907a1ff1b`
- Commits:
  - FIX-1: `e6d8e722c027892cac4abbfe64be05d378885af1`
  - FIX-2: `830301e69624a2b0d6e8240c86994b7808dc18e4`
  - FIX-3: recorded after this report commit

## 3. FIX-1 — WP1 + WP2

- Source-record identity is now scoped by `(project_id, source_record_id)`.
- Identity is derived from project, source-file content hash, and 1-based record
  occurrence, not bibliographic similarity.
- Import service uses project-scoped lookups; cross-project imports work
  independently.
- Repeated identical file imports are idempotent; changed files with the same
  filename produce new occurrences.
- Source records persist file hash, index, original/normalized DOI, metadata,
  provenance, canonical linkage, matching reason, and recovery status.
- Warning categories separate exact DOI links, repeated occurrences, and
  title-only candidates.
- Added read-only APIs for import source records and skip audit.
- Removed dead code and corrected the repository protocol.

## 4. FIX-2 — WP3 + WP4

- Title-only RIS records are clustered by normalized title in the existing
  duplicate-group builder when `include_title_candidates=True`.
- `ProjectDuplicateService` uses that mode so candidates appear in the existing
  manual deduplication API/UI.
- No automatic merge occurs; existing reviewer decisions and merges are preserved.
- Import diagnostics now expose source-record count, exact DOI matches, repeated
  occurrences, title candidates, skip-audit availability, and recovery status.
- Frontend warning dialog displays those values from real backend data.
- Added frontend interaction test.

## 5. FIX-3 — WP5 + PRISMA

- Repaired `scripts/ris_import_reconciliation.py`; it now compiles.
- Produces one row per RIS source occurrence with file hash, index, title, DOI,
  match evidence, classification, proposed action, approval requirement, and
  recovery status.
- Implements five classification outcomes.
- Requires `--approved-ids` and `--execute` for writes; default is read-only.
- Recovery is idempotent through deterministic publication IDs.
- Added source-aware PRISMA reconciliation helper.
- Real 508-record reconciliation remains pending because original RIS files are
  unavailable.

## 6. Audit finding resolution

| Finding | Original severity | Correction | Status |
|---|---|---|---|
| WP1-F1 | PASS | Title-only skip removed | RESOLVED |
| WP1-F2 | PARTIAL | DOI matching remains exact normalized value | RESOLVED |
| WP1-F3 | MEDIUM | Warning categories separated | RESOLVED |
| WP1-F4 | HIGH | Occurrence identity uses project+file hash+index | RESOLVED |
| WP2-F1 | PARTIAL | Source tables and repository completed | RESOLVED |
| WP2-F2 | CRITICAL | Composite project-scoped key and lookups | RESOLVED |
| WP2-F3 | MEDIUM | Read-only source/skip APIs added | RESOLVED |
| WP2-F4 | MEDIUM | Protocol declares lookup method | RESOLVED |
| WP2-F5 | LOW | 1-based record index used | RESOLVED |
| WP2-F6 | LOW | Dead loop removed | RESOLVED |
| WP3-F1 | CRITICAL | Title candidates integrated with duplicate builder | RESOLVED |
| WP4-F1 | PARTIAL | Interactive dialog retained | RESOLVED |
| WP4-F2 | MEDIUM | Structured diagnostic counts added | RESOLVED |
| WP4-F3 | MEDIUM | Frontend dialog test added | RESOLVED |
| WP5-F1 | CRITICAL | Script compiles | RESOLVED |
| WP5-F2 | HIGH | Reconciliation/classification implemented | PARTIAL (real files unavailable) |
| WP5-F3 | HIGH | Approval gate and idempotent recovery | RESOLVED (mechanism only) |
| WP5-F4 | HIGH | Source-aware PRISMA helper added | PARTIAL |

## 7. Changed files

FIX-1:
- `app/repositories/import_source_record_repository.py`
- `app/repositories/project_publication_repository.py`
- `app/services/project_import_service.py`
- `app/api/routers/search_strategy.py`
- `migrations/0034_import_source_records.sql`
- `migrations/0035_import_skip_audit.sql`
- `tests/unit/services/test_v073_import_integrity_remediation.py`

FIX-2:
- `app/services/duplicate_group_builder.py`
- `app/services/project_duplicate_service.py`
- `app/api/dto/sources_summary.py`
- `app/services/sources_summary_service.py`
- `frontend/src/components/imports/FileDropzone.tsx`
- `frontend/src/pages/SourcesIngestionPage.tsx`
- `frontend/src/types/index.ts`
- `frontend/tests/SourcesIngestion.test.tsx`
- `tests/unit/services/test_v073_duplicate_candidate_remediation.py`

FIX-3:
- `scripts/ris_import_reconciliation.py`
- `tests/unit/services/test_v073_reconciliation_script.py`
- this report

## 8. Migrations

- 0034 now uses `PRIMARY KEY (project_id, source_record_id)` and adds
  `source_file_hash`.
- 0035 adds `source_file_hash` to skip audit.
- Verified against a fresh copy of the v0.7.2 production backup: tables created,
  existing row counts unchanged, integrity `ok`, no foreign-key violations.

## 9. API changes

- `GET /api/v1/projects/{project_id}/imports/{import_id}/source-records`
- `GET /api/v1/projects/{project_id}/imports/{import_id}/skip-audit`
- Import history DTO now includes optional structured diagnostic fields.

## 10. Test results

- Backend: 2488 passed.
- Frontend: 341 passed.
- Frontend build: successful.
- Reconciliation script: `py_compile` successful.
- Migration compatibility: production-backup copy migrated without data loss.

## 11. Data integrity assessment

- Project-scoped source identity prevents cross-project import loss.
- All source occurrences are persisted with auditable reasons.
- Existing publications, decisions, merges, and screening rows were not modified.
- Recovery tooling refuses to write without explicit approved IDs.

## 12. PRISMA reconciliation assessment

Source-aware counts and an invariant are implemented in the reconciliation
helper. Full historical PRISMA reconciliation cannot be completed until the
original 508 RIS records are available.

## 13. Remaining limitations

- Real historical 508-record reconciliation is pending source files.
- PRISMA reconciliation is a helper, not a full UI/export integration.
- Similar-title detection uses exact normalized-title grouping, not a fuzzy
  configurable threshold.
- No production recovery was executed.

## 14. Recommended next steps

1. Obtain the original eight RIS files and run the dry-run reconciliation.
2. Researcher review of ambiguous records.
3. Add configurable title-similarity threshold if required.
4. Extend PRISMA export/UI to consume source-aware reconciliation.
5. Independent re-audit before merge.

FIX-1: PASS
FIX-2: PASS
FIX-3: PASS
WP1: PASS
WP2: PASS
WP3: PASS
WP4: PASS
WP5: PARTIAL
BACKEND TESTS: PASS
FRONTEND TESTS: PASS
FRONTEND BUILD: PASS
MIGRATION TESTS: PASS
RECOVERY TESTS: PASS
PRISMA TESTS: PARTIAL
AUDIT FINDINGS RESOLVED: 15/18
READY FOR INDEPENDENT RE-AUDIT: YES
READY FOR MERGE: NO
READY FOR PRODUCTION: NO