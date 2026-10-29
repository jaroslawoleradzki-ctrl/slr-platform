# SLR Platform v0.7.5 — Import Review Refresh Fix Report

## 1. Scope

Implements the OpenSpec change `slr-v0-7-5-import-review-fixes`.

The change fixes two user-visible defects in the v0.7.4 import warning flow:

- a confirmed decision could appear pending or stale because the dialog awaited
  the Sources summary and shared workflow refresh before closing;
- both decision controls shared one loading flag, and a refresh failure was
  caught as if the decision itself had failed.

No backend endpoint, schema, migration, research methodology, or stored data was
changed. No merge, archive, release, deployment, or production data operation
was performed.

## 2. Behaviour delivered

- The decision response is the dialog's terminal state. The dialog applies the
  returned `effective_status`, `review_status`, and decision summary, notifies
  the Sources page through `onDecisionApplied`, and closes immediately.
- The parent updates the matching import-history row before any refresh
  completes, so the row shows `Zaimportowano` without waiting on the network.
- `ImportReviewModal` tracks `pendingAction: 'accept' | 'reject' | null`.
  Only the active action shows a spinner. Both decision triggers are disabled
  while a decision is pending, and `Zamknij` becomes available again when the
  request settles.
- A ref-backed guard prevents repeated or conflicting decision POSTs.
- Decision errors keep the dialog open with the backend message and structured
  blockers. Refresh errors do not reopen the dialog and are not rendered as
  decision failures.
- `FileDropzone.onChanged` starts the Sources summary refresh and the workflow
  status refresh concurrently with `Promise.allSettled`; it does not block the
  dialog.
- `SourcesIngestionPage` renders a non-blocking refresh error with `Ponów` even
  when an older summary is still displayed. It also reloads on project-id
  changes instead of on every project-object identity change, which removes
  redundant summary requests during workflow refreshes.

## 3. Counter invariant

Acceptance is non-destructive and changes only values derived from the import's
effective status:

| Value | Expected after acceptance |
|---|---|
| Active import row | `Zaimportowano` (`effective_status=success`) |
| `successful_imports_count` | +1 for the source |
| `warning_imports_count` | -1 for the source |
| `records_added_count` | unchanged |
| Working-collection total | unchanged |
| Canonical publication count | unchanged |
| Source-record count | unchanged |
| Skip-audit rows | unchanged |
| Duplicate/screening/QA/extraction/synthesis records | unchanged |
| PRISMA populations | unchanged |

The backend already implemented this in v0.7.4. The change pins it with new
service, API, and integration assertions so the frontend fix cannot be mistaken
for a request to alter research counting.

## 4. Files changed

Frontend:

- `frontend/src/components/imports/ImportReviewModal.tsx`
- `frontend/src/components/imports/FileDropzone.tsx`
- `frontend/src/pages/SourcesIngestionPage.tsx`
- `frontend/tests/ImportWarningResolution.test.tsx`
- `frontend/tests/SourcesIngestionRefresh.test.tsx` (new)

Backend tests:

- `tests/unit/services/test_sources_summary_service.py`
- `tests/unit/services/test_import_review_service.py`
- `tests/unit/api/test_import_review_api.py`
- `tests/integration/test_v074_import_review_integration.py`

Documentation:

- `docs/GUI_FOUNDATION.md`
- `docs/SOURCES_IMPORTS_AUDIT.md`

## 5. Red/green evidence

### Red (before implementation)

```text
npm --prefix frontend test -- ImportWarningResolution.test.tsx SourcesIngestionRefresh.test.tsx
Test Files  2 failed (2)
     Tests  6 failed | 6 passed (12)
```

The six failures covered the three intended defects: accept and reject waiting
for a never-resolving `onChanged`, accept without a per-action spinner, refresh
failure reopening/reporting the decision as failed, and both Sources refresh
scenarios (error/retry with stale data, immediate row update).

### Green (after implementation)

```text
npm --prefix frontend test
Test Files  47 passed (47)
     Tests  358 passed (358)

npm --prefix frontend run type-check
tsc --noEmit                      # passed

npm --prefix frontend run build
vite build                        # passed (chunk-size advisory only)

bash scripts/agent/safe_pytest.sh \
  tests/unit/services/test_import_review_service.py \
  tests/unit/services/test_sources_summary_service.py \
  tests/unit/api/test_import_review_api.py \
  tests/integration/test_v074_import_review_integration.py
38 passed

uv run --frozen --no-sync ruff check app tests scripts
All checks passed!

uv run --frozen --no-sync mypy app
Success: no issues found in 208 source files

openspec validate slr-v0-7-5-import-review-fixes --strict
Change 'slr-v0-7-5-import-review-fixes' is valid

openspec validate --all --strict
Totals: 4 passed, 0 failed (4 items)
```

The backend counter tests pin behaviour that already existed in v0.7.4; after
the test fixtures were completed they passed against the unchanged backend.

## 6. Residual risk

- Browser E2E verification performed via Playwright (Chromium) with a mocked
  backend: `frontend/e2e/import-review.spec.ts` — 3/3 PASS (counter update after
  acceptance, spinner/close, refresh-failure retry). Full E2E against a running
  FastAPI backend remains a CI item outside this change.
- A failed workflow-status refresh is still surfaced through the existing
  workflow/dashboard error state, not through a new global notification. This
  follows the approved design.
- The dialog deliberately starts the background refresh without awaiting it.
  The modal catches a rejected/synchronously-throwing `onChanged` locally so it
  cannot be reported as a decision failure; `FileDropzone` itself uses
  `Promise.allSettled` and does not reject.
- The Sources page now depends on `activeProject.id` instead of the whole object
  for its summary loader. This is intentional and prevents redundant fetches,
  but it changes request timing for same-project workflow refreshes.
- The exact production screenshot for the original stale-counter report was not
  available. The fix targets the code-verified lifecycle defect and preserves
  the documented counter invariant.

## 7. Gates

| Gate | Status |
|---|---|
| Frontend tests | PASSED (358/358) |
| Frontend type-check | PASSED |
| Frontend build | PASSED |
| Focused backend tests | PASSED (38/38) |
| Ruff | PASSED |
| mypy | PASSED |
| OpenSpec validation | PASSED (4/4) |
| Research-integrity review before merge | PENDING — human gate |
| Manual browser / E2E verification | VERIFIED via Playwright (Chromium), 3/3 PASS (mocked backend) |
| Merge / archive / release / deploy | NOT PERFORMED — requires explicit human authorization |

READY FOR REVIEW: YES, subject to the pending research-integrity review gate.
