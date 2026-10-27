# SLR Platform v0.7.3 — R1–R5 Integration with Development Report

**Status:** PASS — integrated, locally validated, and GitHub Actions CI passed
**Date:** 2026-10-27
**Repository:** `jaroslawoleradzki-ctrl/slr-platform`
**Integration branch:** `integration/v0.7.3-r1-r5`
**Integration worktree:** `/home/cloud/dev/wt-v0.7.3-integration`

---

## 1. Repository and branch baseline

| Item | Value |
|---|---|
| Repository root | `/home/cloud/dev/slr-platform` |
| `origin` | `git@github.com:jaroslawoleradzki-ctrl/slr-platform.git` |
| `homelab` remote | `cloud@192.168.100.22:/tank/git/slr-platform.git` (untouched) |
| Local `development` HEAD | `e97c8b1c80e04e8d174ee8a1bcc0e0b701599595` |
| Local `development` worktree | Dirty with pre-existing user changes (preserved, never touched) |
| `origin/development` after fetch | `e97c8b1c80e04e8d174ee8a1bcc0e0b701599595` |
| Integration branch before creation | absent locally and on `origin` |
| Integration worktree before creation | absent |

The development worktree’s uncommitted/untracked files were not reset, cleaned, stashed, overwritten, or deleted. No existing branch or worktree was removed. No force push, rebase, squash, tag, release, or deploy was performed.

## 2. Source R5 commit

| Item | Value |
|---|---|
| R5 branch | `fix/v0.7.3-r5-quality-performance` |
| Expected R5 HEAD | `18e637b` |
| Actual R5 HEAD | `18e637b90e0d9c9712cbb2fcb816a5c423dfa1d2` |
| R5 worktree status | clean |
| R5 history since `4b34f9b` | `0faf9a9`, `c899a72`, `08323a9`, `18e637b` |
| Final R5 commit scope | one file, `docs/reviews/V073_R5_FINAL_REMEDIATION_REPORT.md` (+485 lines) |

The only commit after the expected R5 work was the final report commit, matching the task’s expectation.

## 3. Current development commit

`origin/development` was fetched immediately before integration and again before the final readiness check. It remained:

```text
e97c8b1c80e04e8d174ee8a1bcc0e0b701599595
Merge pull request #4 from jaroslawoleradzki-ctrl/ci/self-hosted-runner
```

Development commits preserved in the integration branch:

- `e97c8b1` — merge the self-hosted runner CI
- `d284c98` — run SQLite tests on disposable tmpfs
- `e918cd4` — make frontend Blob assertions realm-agnostic
- `33f4f9b` — fix workflow context usage and runner label
- `bd8cf12` — run workflows on the dedicated AI-node runner

## 4. Integration branch and worktree

```text
branch:   integration/v0.7.3-r1-r5
worktree: /home/cloud/dev/wt-v0.7.3-integration
base:     origin/development (e97c8b1)
```

Created with:

```bash
git worktree add -b integration/v0.7.3-r1-r5 \
  /home/cloud/dev/wt-v0.7.3-integration origin/development
```

The new worktree was clean at creation.

## 5. Merge result and conflicts

R5 was merged with a normal merge commit (no squash, no rebase):

```bash
git merge --no-ff --no-edit fix/v0.7.3-r5-quality-performance
```

**Result: merge succeeded with no conflicts.**

| Item | Value |
|---|---|
| Merge commit | `636b034d35bb2fb8057de5e70506122079643562` |
| Merge strategy | `ort` |
| Conflicts | none |
| R5 ancestry | `git merge-base --is-ancestor fix/v0.7.3-r5-quality-performance HEAD` → true |
| Development ancestry | `git merge-base --is-ancestor origin/development HEAD` → true |
| CI configuration | retained unchanged from development by the merge |

No conflict resolution was required. No earlier R1–R4 branch was merged separately; R5 already contains R1–R4.

### Integration-only CI adjustment

The inherited workflow triggered only on `main`, `development`, and pull requests. To let the existing workflow validate the integration branch without opening a PR or modifying development, the smallest safe change was made on the integration branch:

```diff
   push:
-    branches: [main, development]
+    branches: [main, development, integration/v0.7.3-r1-r5]
```

Commit: `fdde532d26b484983652f8bd3b1133283adbfc5d` — `ci: run quality gates on v0.7.3 integration branch`.

The runner policy script was not modified:

```text
CI runner policy PASSED: all jobs target [self-hosted, linux, slr-platform].
```

## 6. Changed files

`git diff --name-status origin/development..HEAD` reports **54 files**: 53 from the R1–R5 merge plus the one-line CI trigger change.

### Application and migrations

```text
M app/api/dto/prisma.py
M app/api/dto/sources_summary.py
M app/api/routers/search_strategy.py
M app/domain/deduplication.py
M app/normalization/__init__.py
M app/normalization/doi.py
M app/normalization/title.py
M app/providers/import_file/bibtex/mapper.py
M app/providers/import_file/ris/mapper.py
A app/repositories/import_source_record_repository.py
M app/repositories/project_publication_repository.py
M app/services/duplicate_group_builder.py
M app/services/export/prisma_flow_builder.py
M app/services/export/xlsx_workbook.py
A app/services/import_identity.py
M app/services/prisma_metrics_service.py
M app/services/project_duplicate_service.py
M app/services/project_import_service.py
M app/services/project_workflow_status_service.py
M app/services/screening_eligibility_adapter.py
M app/services/screening_input_service.py
M app/services/sources_summary_service.py
A migrations/0034_import_source_records.sql
A migrations/0035_import_skip_audit.sql
A migrations/0036_import_recovery_audit.sql
A migrations/0037_duplicate_candidate_snapshots.sql
A scripts/ris_import_reconciliation.py
```

### Frontend

```text
M frontend/src/components/imports/FileDropzone.tsx
M frontend/src/components/workflow/LivePrismaFlowChart.tsx
M frontend/src/pages/SourcesIngestionPage.tsx
M frontend/src/services/api/projectApi.ts
M frontend/src/types/index.ts
A frontend/tests/PrismaSourceAccounting.test.tsx
M frontend/tests/SourcesIngestion.test.tsx
```

### Tests and documentation

```text
M tests/integration/test_exports_e2e.py
A tests/integration/test_v073_r1_import_integrity.py
A tests/integration/test_v073_r1_migrations.py
A tests/integration/test_v073_r2_duplicate_review.py
A tests/integration/test_v073_r3_recovery.py
A tests/integration/test_v073_r4_prisma_source_aware.py
A tests/integration/test_v073_r5_doi_canonical_integrity.py
M tests/unit/api/test_prisma_metrics_api.py
M tests/unit/services/test_project_import_service.py
A tests/unit/services/test_v073_duplicate_candidate_remediation.py
A tests/unit/services/test_v073_import_integrity_remediation.py
A tests/unit/services/test_v073_r5_performance_equivalence.py
A docs/plans/V073_RIS_IMPORT_INTEGRITY_REMEDIATION_PLAN.md
A docs/reviews/V073_AUDIT_REMEDIATION_REPORT.md
A docs/reviews/V073_COMPLETE_IMPLEMENTATION_REPORT.md
A docs/reviews/V073_FINAL_REMEDIATION_REPORT.md
A docs/reviews/V073_R5_FINAL_REMEDIATION_REPORT.md
A docs/reviews/V073_RIS_DUPLICATE_SKIP_AUDIT.md
A docs/reviews/V073_RIS_IMPORT_WARNING_REPORT.md
M .github/workflows/ci.yml
```

No `.db`, `.sqlite`, secret, key, or production-data file is tracked.

## 7. Ruff and Mypy results

| Gate | Command | Result |
|---|---|---|
| Ruff | `ruff check app tests scripts` | **PASS** — All checks passed, exit 0 |
| Mypy | `mypy app` | **PASS** — no issues in 202 source files, exit 0 |

## 8. Backend and frontend results

| Gate | Command | Result |
|---|---|---|
| Backend | `pytest -q -p no:cacheprovider` with disposable `SLR_DATABASE_PATH`/`TMPDIR` under `/dev/shm` | **PASS — 2544 passed**, 1 warning, 94.03 s |
| Frontend tests | `npm test` (44 files) | **PASS — 342 passed**, 7.14 s |
| TypeScript | `npm run type-check` (`tsc --noEmit`) | **PASS** |
| Production build | `npm run build` | **PASS**, built in 1.55 s |

The build emits the pre-existing chunk-size warning for the main JS bundle (719 kB); it does not fail the build. Local frontend validation reused the existing workspace `node_modules` (TypeScript 5.9.3, compatible with `^5.7.2`); CI performed the locked `npm ci` install and passed independently.

## 9. Migration test results

Command:

```bash
pytest -q -p no:cacheprovider \
  tests/integration/test_v073_r1_migrations.py \
  tests/integration/test_pre_screening_archive_migration_and_workflow.py \
  tests/unit/repositories/test_extraction_migration_0019.py \
  tests/unit/repositories/test_extraction_migration_0023.py \
  tests/unit/repositories/test_synthesis_migration_0020.py \
  tests/unit/repositories/test_synthesis_migration_0021.py \
  tests/unit/repositories/test_synthesis_migration_0022.py \
  tests/unit/repositories/test_synthesis_migration_0025.py \
  tests/unit/repositories/test_synthesis_migration_0026.py \
  tests/unit/repositories/test_migration_reconciliation.py
```

Result: **31 passed in 0.77 s**. Migrations `0034`–`0037` arrived from R1–R4 and apply cleanly.

## 10. R1–R5 regression results

```bash
pytest -q -p no:cacheprovider \
  tests/integration/test_v073_r1_import_integrity.py \
  tests/integration/test_v073_r1_migrations.py \
  tests/integration/test_v073_r2_duplicate_review.py \
  tests/integration/test_v073_r3_recovery.py \
  tests/integration/test_v073_r4_prisma_source_aware.py \
  tests/integration/test_v073_r5_doi_canonical_integrity.py \
  tests/unit/services/test_v073_r5_performance_equivalence.py
```

Result: **60 passed, 1 warning in 6.26 s**.

This includes the 7 R5.3 DOI/canonical tests (one-step, multi-step, missing target, cycle, conflicting DOI, project isolation, provider path) and the 9 R5.2 candidate/reuse tests.

## 11. Performance validation

The performance-relevant files are byte-identical between R5 and the integration branch:

```text
git diff --stat fix/v0.7.3-r5-quality-performance..HEAD -- \
  app/services/duplicate_group_builder.py app/normalization/title.py \
  app/services/prisma_metrics_service.py app/services/project_workflow_status_service.py \
  app/services/screening_eligibility_adapter.py app/services/screening_input_service.py \
  app/services/project_import_service.py
→ empty
```

Re-measured on the integration worktree with the deterministic A–E dataset and disposable SQLite:

| Check | Result |
|---|---|
| Candidate equivalence | **PASS** — 224,472 old/new similarity decisions, **0 mismatches**, identical groups through 2000 records |
| 2000-record builder | **0.477 s median / 0.484 s max**, 31 groups |
| 2000-record duplicate-groups service path | **0.551 s median / 0.555 s max**, 31 groups |
| 2000-record PRISMA | **1.028 s median / 1.036 s max**, 31 pending groups |
| Post-merge DOI integrity | **PASS** — all 7 R5.3 tests |
| Original quadratic regression | **not reintroduced**; no candidate cap or comparison fallback |

These match the R5 report (0.531 s service, 1.027 s PRISMA) within measurement noise.

## 12. GitHub Actions workflow and run URL

The integration branch inherits `.github/workflows/ci.yml` from development:

- runner: self-hosted `ai-node-slr-platform` on AI-node;
- labels: `[self-hosted, linux, slr-platform]`;
- jobs: `ci-policy`, `Backend (Python 3.12)`, `Frontend (Node 22)`;
- backend runs Ruff, Mypy, and the full pytest suite against a disposable tmpfs SQLite database;
- frontend runs `npm ci`, type-check, unit tests, and production build;
- runner-policy check fails closed on any GitHub-hosted runner.

After the CI trigger adjustment was pushed, GitHub Actions ran automatically:

```text
Run URL:  https://github.com/jaroslawoleradzki-ctrl/slr-platform/actions/runs/40473794313
Run ID:   40473794313
Head:     fdde532d26b484983652f8bd3b1133283adbfc5d
Trigger:  push
Status:   completed
Result:   success
```

Job results:

| Job | Duration | Result |
|---|---:|---|
| CI runner policy | 8 s | success |
| Frontend (Node 22) | 25 s | success |
| Backend (Python 3.12) | 1 m 52 s | success |

The runner-policy job’s “Prove execution on AI-node” step passed, confirming the run executed on the dedicated self-hosted runner rather than a GitHub-hosted runner.

## 13. GitHub Actions final status

**PASS** — run `40473794313` completed successfully with all three required jobs green.

The report commit is documentation-only and triggers one additional run of the same workflow; it was pushed and watched to completion before the final sign-off (result recorded in the final output).

## 14. Remaining issues

1. **Historical 508/62 real-data verification** remains `NOT VERIFIED` from R5 because the original RIS files/source rows are unavailable. This is unchanged by integration.
2. **Performance figures are synthetic** (deterministic A–E fixtures), not the audit’s original 578-record project, which is not present in the repository.
3. **Node.js 20 deprecation annotation:** `actions/checkout@v4` is being force-run on Node 24. It is a non-blocking warning inherited from development CI, not a failed check.
4. **Frontend local install:** local validation reused existing `node_modules`; CI’s locked `npm ci` run is the authoritative dependency check and passed.
5. No pull request was opened, no merge into `development` was performed, and no deployment/release occurred.

## 15. Final integration commit SHA

| Commit | Purpose |
|---|---|
| `636b034d35bb2fb8057de5e70506122079643562` | Normal merge of R5 into `integration/v0.7.3-r1-r5` |
| `fdde532d26b484983652f8bd3b1133283adbfc5d` | Minimal CI trigger for the integration branch |
| report commit | Documentation-only commit at the branch tip (SHA in final output) |

## 16. Merge readiness verdict

| Criterion | Status |
|---|---|
| Integration branch clean | **YES** |
| All intended R1–R5 commits present | **YES** |
| Development CI commits/workflow preserved | **YES** |
| Only intended files changed | **YES** — 54 files, all R1–R5 or the one-line CI trigger |
| No secrets or production data committed | **YES** |
| `origin/development` unchanged during integration | **YES** — still `e97c8b1` |
| Ruff / Mypy | **PASS** |
| Backend / Frontend / TypeScript / Build | **PASS** |
| Migrations | **PASS** |
| R1–R5 regression | **PASS** |
| Performance | **PASS** |
| GitHub Actions | **PASS** |

**Ready to merge into development: YES**, subject only to the standard review/approval process and confirmation that the docs-only report commit’s CI run is green (verified before final output). Merging remains an explicit human decision; this task did not merge into `development`.

---

## Required final status block

```text
SLR V0.7.3 INTEGRATION STATUS: PASS

R5 SOURCE HEAD:
18e637b90e0d9c9712cbb2fcb816a5c423dfa1d2

DEVELOPMENT BASE:
e97c8b1c80e04e8d174ee8a1bcc0e0b701599595

INTEGRATION HEAD:
the report commit at the branch tip (see final output)

INTEGRATION BRANCH:
integration/v0.7.3-r1-r5

WORKTREE:
/home/cloud/dev/wt-v0.7.3-integration

RUFF: PASS
MYPY: PASS

BACKEND: PASS
FRONTEND: PASS
TYPESCRIPT: PASS
BUILD: PASS

MIGRATIONS: PASS
R1–R5 REGRESSION: PASS
PERFORMANCE: PASS

GITHUB ACTIONS: PASS

GITHUB ACTIONS RUN:
https://github.com/jaroslawoleradzki-ctrl/slr-platform/actions/runs/40473794313

READY TO MERGE INTO DEVELOPMENT: YES

MERGED INTO DEVELOPMENT: NO

DEPLOYED: NO

REPORT:
docs/reviews/V073_R1_R5_INTEGRATION_REPORT.md
```
