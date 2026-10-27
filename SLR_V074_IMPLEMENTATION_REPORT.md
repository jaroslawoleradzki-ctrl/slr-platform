# SLR Platform v0.7.4 — Implementation Report

## 1. Implementation summary

v0.7.4 implements the approved OpenSpec change
`slr-v0-7-4-import-and-workflow-consistency`.

Delivered:

- Explicit `Akceptuję` / `Odrzucam` decisions for warning imports.
- Non-destructive acceptance with effective `Zaimportowano` status.
- Confirmation-gated, transactional import rejection with ownership and
  downstream-dependency preflight.
- Structured rejection blockers and a clear UI explanation.
- Retention of rejected imports as non-active audit, including source records,
  skip audit, warnings, and removed-publication snapshots.
- PRISMA classification of rejected source records as
  `removed before screening — rejected import`.
- One active-corpus duplicate-readiness projection shared by deduplication,
  screening, workflow status, and PRISMA.
- Approved-unmerged duplicate groups now block as `merge_required` rather than
  being presented as completed.
- Regression coverage for shared publications, merges, downstream research
  records, rollback, legacy imports, and merged-group-plus-new-import cases.

No embedded AI/LLM behavior, autonomous research decisions, production data
operations, merge, release, or deployment were introduced.

## 2. Completed OpenSpec requirements

### `import-warning-resolution`

All requirements were implemented and covered by tests:

- warning decision workflow and import identification;
- acceptance and effective status;
- confirmation-gated rejection;
- ownership validation;
- downstream research-decision protection;
- atomic/idempotent rejection;
- non-active audit retention;
- exclusion from active populations;
- PRISMA rejected-import classification;
- explicit API errors;
- project-scoped, attributed decisions;
- backward-compatible import contracts.

### `deduplication-screening-consistency`

All requirements were implemented and covered by tests:

- single authoritative readiness projection;
- active-corpus-only grouping;
- pending groups blocking both stages;
- approved-unmerged groups requiring a merge;
- rejected groups not blocking;
- dynamic merged-group-plus-new-import consistency;
- distinct screening blocker messages;
- backend-authoritative UI status;
- consistent PRISMA counts;
- backward-compatible readiness contracts.

## 3. Files changed

### Backend

- `app/domain/import_review.py`
- `app/repositories/import_review_repository.py`
- `app/repositories/import_history_repository.py`
- `app/repositories/project_publication_repository.py`
- `app/services/import_review_service.py`
- `app/services/duplicate_readiness_service.py`
- `app/services/screening_input_service.py`
- `app/services/project_duplicate_service.py`
- `app/services/project_workflow_status_service.py`
- `app/services/sources_summary_service.py`
- `app/services/prisma_metrics_service.py`
- `app/services/project_deletion_service.py`
- `app/services/export/prisma_flow_builder.py`
- `app/services/export/xlsx_workbook.py`
- `app/api/dto/import_review.py`
- `app/api/dto/deduplication.py`
- `app/api/dto/workflow_status.py`
- `app/api/dto/sources_summary.py`
- `app/api/dto/search_strategy.py`
- `app/api/dto/prisma.py`
- `app/api/routers/import_review.py`
- `app/api/routers/search_strategy.py`
- `app/api/main.py`

### Frontend

- `frontend/src/components/imports/ImportReviewModal.tsx`
- `frontend/src/components/imports/FileDropzone.tsx`
- `frontend/src/components/common/Modal.tsx`
- `frontend/src/components/deduplication/DeduplicationSummaryCard.tsx`
- `frontend/src/components/layout/Sidebar.tsx`
- `frontend/src/components/workflow/WorkflowStepper.tsx`
- `frontend/src/context/ProjectContext.tsx`
- `frontend/src/pages/SourcesIngestionPage.tsx`
- `frontend/src/pages/DeduplicationPage.tsx`
- `frontend/src/pages/TitleAbstractScreeningPage.tsx`
- `frontend/src/pages/FullTextScreeningPage.tsx`
- `frontend/src/pages/ProjectDashboardPage.tsx`
- `frontend/src/services/api/projectApi.ts`
- `frontend/src/types/index.ts`

### Tests

- `tests/unit/repositories/test_import_review_repository.py`
- `tests/unit/services/test_import_review_service.py`
- `tests/unit/services/test_duplicate_readiness_consistency.py`
- `tests/unit/services/test_prisma_rejected_import_v074.py`
- `tests/unit/api/test_import_review_api.py`
- `tests/unit/api/test_workflow_status_deduplication_api.py`
- `tests/unit/api/test_prisma_metrics_api.py`
- `tests/integration/test_v074_import_review_integration.py`
- `tests/integration/test_v074_workflow_consistency.py`
- `frontend/tests/ImportWarningResolution.test.tsx`
- `frontend/tests/DeduplicationScreeningConsistency.test.tsx`
- updated deduplication, dashboard, screening, sources, workflow, and version
  regression tests.

### Documentation and metadata

- `migrations/0038_import_review_decisions.sql`
- `CHANGELOG.md`
- `VERSION`
- `pyproject.toml`
- `frontend/package.json`, `frontend/package-lock.json`, `uv.lock`
- `docs/data-model.md`
- `docs/SOURCES_IMPORTS_AUDIT.md`
- `docs/DATA_INTEGRITY_CLEANUP.md`
- `docs/GUI_FOUNDATION.md`
- `docs/DUPLICATE_REVIEW_API.md`
- `docs/DUPLICATE_REVIEW_DECISIONS.md`
- `docs/DUPLICATE_COMPARISON_UI.md`
- `docs/EXPORTS_PRISMA.md`
- `PROJECT_STATUS.md`, `ROADMAP.md`
- OpenSpec proposal, design, specs, and tasks under
  `openspec/changes/slr-v0-7-4-import-and-workflow-consistency/`.

## 4. Database migration

Added one additive migration:

```text
migrations/0038_import_review_decisions.sql
```

It creates `import_review_decisions` with:

- terminal accepted/rejected decision and reviewer attribution;
- original import status and warning snapshot;
- affected source/publication identifiers;
- removed-publication snapshots;
- deletion and source-retention counts;
- PRISMA treatment;
- unique `(project_id, import_id)` terminal decision.

No existing migration was edited. No production database or research database
was accessed. Migration safety check passed with one migration change.

## 5. TDD evidence

### Duplicate readiness

Initial failing run:

```bash
bash scripts/agent/safe_pytest.sh tests/unit/services/test_duplicate_readiness_consistency.py
```

Result: **5 failed**. The expected failure was:

```text
AttributeError: 'DuplicateGroupListResponse' object has no attribute 'readiness'
```

After implementing the shared readiness projection and active-corpus grouping:

```text
5 passed
```

Combined readiness/screening regression:

```text
19 passed
```

### Import review

The import-review tests were authored before the service was implemented and
then expanded through the blast-radius cases. The first run exposed a test
fixture construction error:

```text
TypeError: ImportSourceRecord.__init__() missing 1 required positional argument: 'source_file_hash'
```

After correcting the fixture and implementing the repository/service:

```text
7 passed → 17 passed
```

The suite now covers acceptance, rejection, confirmation, shared ownership,
merges, duplicate decisions, pre-screening, corpus finalization, screening,
full-text metadata, quality assessment, extraction, synthesis, recovery,
legacy ownership, idempotency, and rollback.

This report does not claim strict red-first evidence for every module; it records
the observed failing runs and the final green evidence.

## 6. Test results

### Backend

```bash
bash scripts/agent/safe_pytest.sh
```

```text
2714 passed, 1 warning in 111.05s
```

The warning is the existing Starlette `TestClient`/`httpx` deprecation warning.

Focused v0.7.4 suite:

```bash
bash scripts/agent/safe_pytest.sh \
  tests/unit/repositories/test_import_review_repository.py \
  tests/unit/services/test_import_review_service.py \
  tests/unit/services/test_duplicate_readiness_consistency.py \
  tests/unit/services/test_prisma_rejected_import_v074.py \
  tests/unit/api/test_import_review_api.py \
  tests/unit/api/test_workflow_status_deduplication_api.py \
  tests/integration/test_v074_import_review_integration.py \
  tests/integration/test_v074_workflow_consistency.py
```

Result: **33 passed**.

### Frontend

```bash
npm --prefix frontend test
```

```text
46 test files passed, 349 tests passed
```

```bash
npm --prefix frontend run type-check
```

Result: **PASS**.

```bash
npm --prefix frontend run build
```

Result: **PASS**; Vite reports the pre-existing >500 kB chunk-size advisory only.

### Static analysis

```bash
uv run --frozen --no-sync ruff check app tests scripts
uv run --frozen --no-sync mypy app
```

Result: **PASS**; mypy checked 208 source files.

### Migration safety

```bash
uv run --frozen --no-sync python scripts/ci/check_migration_safety.py --base-ref origin/development
```

Result:

```text
migration-safety: PASSED (1 migration change(s))
```

## 7. OpenSpec validation

```bash
openspec validate slr-v0-7-4-import-and-workflow-consistency --strict
openspec validate --all --strict
```

Both commands pass. All 52 OpenSpec tasks were implemented and marked complete.

## 8. Known limitations

- Provider-import rejection is out of scope; only warning file imports expose
  terminal accept/reject decisions.
- A committed rejection has no automatic restore. Recovery requires a separate
  human-approved reconciliation using retained source records and removed-
  publication snapshots.
- Reviewer identity is self-asserted because the application has no
  authentication/account layer.
- Rejected imports remain in PRISMA identification by design; their removal is
  reported separately and included in the pre-screening removal population.
- Historical imports without ownership evidence can be accepted but cannot be
  destructively rejected.
- The full browser/manual workflow was not exercised against a production-like
  dataset; automated UI and integration coverage was used instead.

## 9. Git commits

| Commit | Purpose |
|---|---|
| `55b0562` | OpenSpec proposal, design, specs, and tasks |
| `0b2d3d8` | Unified deduplication/screening readiness |
| `cae68a9` | Import warning acceptance and guarded rejection |
| `e409322` | v0.7.4 version metadata and documentation |

This report is committed separately after the implementation commits.

## 10. Push status

**PUSHED** to `origin/feature/slr-v0.7.4`. The branch tracks its upstream and
the working tree is clean. No merge, tag, release, or deployment push was
performed.

## 11. Remaining risks

- **Unscreened research population changes:** rejection deletes active canonical
  rows only when no downstream research record exists; the audit snapshots are
  the recovery evidence.
- **Missing foreign keys:** blocker coverage is explicit and fail-closed, but a
  future publication-referencing table must be added to the blocker inventory.
- **No authentication:** reviewer attribution is traceable but not
  authenticated.
- **PRISMA methodology:** rejected imports remain identified and are removed
  before screening; this is the approved treatment and must not be reinterpreted
  as silent deletion.
- **CI not run:** local gates are green, but CI is authoritative and remains
  `NOT VERIFIED` in this report.

## 12. Merge-readiness recommendation

**PASS WITH CONDITIONS**

Conditions:

1. CI must run and pass for the exact pushed commit.
2. The required research-integrity review gate must be completed before merge.

Local implementation, regression, type-check, build, migration-safety, and
OpenSpec validation evidence is green. Do not merge, release, or deploy from
this report alone.
