# v0.7.5 — Remediation of research-integrity review LOW findings

## Scope
Removes the three LOW findings raised in `V075_RESEARCH_INTEGRITY_REVIEW.md`:
LOW-1 (downstream snapshot test), LOW-2 (per-source counters), LOW-3 (browser E2E).

No backend, schema, migration, or PRISMA semantics changed. No commit/merge/archive/release/deploy.

## Changes
- `tests/unit/services/test_import_review_service.py`: acceptance snapshot fixture now inserts
  non-empty rows into `screening_decisions`, `quality_assessments` (with template), `extraction_records`
  (with template + version), and `synthesis_analytical_relations`, plus row-count assertions.
- `frontend/e2e/import-review.spec.ts` (new): Playwright (Chromium) E2E with mocked backend,
  3 scenarios.
- `frontend/playwright.config.ts` (new) and `@playwright/test` devDependency.
- Documentation/report updates: `V075_RESEARCH_INTEGRITY_REVIEW.md`, `V075_IMPORT_REVIEW_REFRESH_FIX_REPORT.md`.

## LOW-2 determination
Per-source counters are server-derived and update on successful refresh (per approved spec scenario
"WHEN … the Sources summary refresh succeeds"). `handleDecisionApplied` intentionally updates only the
active import row immediately; counters are not invented client-side (Design §4). Refresh runs in the
background without a page reload; failure shows `role="alert"` + `Ponów`. No code change required.

## Test results
- Backend focused: `tests/unit/services/test_import_review_service.py`,
  `test_sources_summary_service.py`, `test_import_review_api.py`,
  `test_v074_import_review_integration.py` → 38 passed.
- Frontend vitest: 47 files / 358 tests passed.
- Frontend type-check: PASS. Frontend build: PASS.
- Playwright (Chromium): `frontend/e2e/import-review.spec.ts` → 3/3 PASS.
- Ruff: PASS. mypy: PASS (208 files).
- OpenSpec: `openspec validate --all --strict` → 4/4 PASS.
- Diff hygiene: `safe_git_inspect.py diff --check` → no issues.

## Verdict: PASS (all three LOW findings resolved; no new blockers)
