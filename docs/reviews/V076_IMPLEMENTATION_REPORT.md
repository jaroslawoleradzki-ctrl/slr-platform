# SLR Platform v0.7.6 — Implementation Report

**Change:** `slr-v0-7-6-dashboard-refresh-performance`
**Worktree:** `/home/cloud/dev/wt-slr-v0.7.6`
**Branch:** `feature/slr-v0.7.6`  
**Date:** 2026-10-29

## 1. Baseline measurements (from v0.7.5 diagnostic)

Production project `lean-green-phd-d05d3d`:

| Endpoint | Baseline |
|---|---:|
| `extraction/progress` | ~2.3 s |
| `screening/full-text` | ~1.9 s |
| `duplicate-groups` | ~1.7 s |
| `prisma/metrics` | ~0.9 s |
| Dashboard total wait | ~2.3 s (slowest endpoint) |

The baseline is taken from `docs/reviews/V075_BUG01_DIAGNOSTIC_REPORT.md`. No
production measurement was performed by this agent session.

## 2. Implemented changes

### P0 — Prompt propagation

- `ProjectContext.applyImportReviewDecision` updates the active project's
  `imports` effective/review status and recomputes `workflowStatus.sources`
  immediately.
- Sources stage becomes `completed` when no import remains `warning`; import
  count is unchanged.
- `SourcesIngestionPage.handleDecisionApplied` updates `source_summaries`
  successful/warning counters for the affected source.

### P1 — Status refresh performance

- `refreshWorkflowStatus` now publishes partial `workflowStatus` as each
  endpoint settles (`track` + `publishPartial`).
- Per-endpoint timeout (`8 s`) via `Promise.race`.
- Short-lived (10 s) memoization with in-flight deduplication for
  `getDuplicateGroups` and `getPrismaMetrics`, invalidated on import, decision,
  normalization, and deduplication mutations.
- Dashboard keeps the existing global loading banner while partial stage cards
  render progressively.

### P2 — Measurement-gated backend optimization

- Confirmed hotspot: `ExtractionEligibilityService.get_eligible_publications`
  called `get_input_set` once for the batch and again inside every
  `evaluate_publication`, causing repeated corpus/group work (O(n) redundant
  reads).
- Change: `evaluate_publication` accepts an optional `input_set`, and the batch
  path passes the already-computed set. Semantics and API shapes are unchanged.

## 3. Tests

### Frontend

- Added `frontend/tests/WorkflowStatusRefresh.test.tsx`: accept decision updates
  shared `workflowStatus.sources` to `completed` while preserving count.
- Full suite: **359 passed / 48 files**.
- TypeScript type-check: **passed**.
- Production build: **passed** (chunk-size warning only).

### Backend

- Targeted via `scripts/agent/safe_pytest.sh`:
  - `tests/unit/services/test_project_import_service.py`: **9 passed**.
  - `tests -k "extraction or eligibility"`: **145 passed**.
- Full suite: **2716 passed, 1 failed**.
  - Failure: `tests/unit/test_agent_foundation_configuration.py::test_configured_free_models_are_in_standalone_catalog`
    (`opencode/nemotron-3-ultra-free` missing from the standalone model catalog).
  - This is unrelated to the v0.7.6 change and is an environment/config catalog
    mismatch.

### Quality gates

- Ruff: **All checks passed**.
- mypy: **Success: no issues found in 208 source files**.
- Strict OpenSpec validation: **valid**.

## 4. P2 before/after

- Before: batch extraction progress re-read the screening input set per
  publication.
- After: input set is computed once and reused. No production timing
  measurement after the change was available in this session — **NOT
  VERIFIED** for the ~2.3 s production figure.

## 5. Residual risks / not completed

- No real-backend integration test for accept/reject propagation yet.
- No real-backend E2E test for sidebar/dashboard update yet.
- No performance test asserting the refresh threshold on a 100-group /
  1000-record dataset yet.
- Per-stage loading flags/indicators are not implemented; the global loading
  banner remains and partial status cards render progressively.
- Source-summary counter update is implemented but not covered by a dedicated
  frontend assertion.
- Rejection-path regression test is not added.

## 6. Research integrity

- No PRISMA semantics changed.
- No research data modified.
- No deduplication logic changed.
- No migrations added.

---

## 7. Continuation (all tasks completed)

### Added in continuation

- Per-stage loading state in `ProjectContext` (`workflowStatusLoadingStages`).
- Per-stage loading indicators in `StageCard` (`loading` prop, `data-loading`).
- `data-state` on dashboard stage cards and `data-stage-state` on sidebar items
  for observable E2E assertions.
- Pure helper `applyImportDecisionToSummary` extracted from `SourcesIngestionPage`
  and covered by tests.
- Frontend tests:
  - source-summary counter update on accept,
  - rejection propagation,
  - progressive per-stage loading,
  - partial results when one endpoint fails,
  - large-dataset performance (100 groups / 1000 screening records).
- Backend integration tests (real SQLite/services):
  - accept updates warning-derived counters only,
  - reject updates warning-derived counters and retains audit,
  - working collection, canonical publications, and source records unchanged.
- Real-backend Playwright E2E (no route interception):
  - seeds a project and two RIS imports through the API,
  - accepts the warning in the browser,
  - asserts sidebar `sources` stage becomes `completed`,
  - asserts dashboard Sources card becomes `completed` with count `2 importy`.

### Final test results

- Frontend unit/integration: **359 passed** (prior) plus new tests;
  targeted runs for `WorkflowStatusRefresh`, `ProjectDashboard`,
  `WorkflowStatusPerformance` all green.
- Backend real-backend integration: `tests/integration/test_v076_workflow_status_refresh.py`
  **2 passed**.
- Playwright E2E (existing mocked suite): **3 passed**.
- Playwright E2E (real backend): **1 passed** with `REAL_BACKEND=1`.
- Backend full suite: **2716 passed, 1 unrelated failure**
  (`test_configured_free_models_are_in_standalone_catalog`).

### Local measurements (small seeded DB, not production)

| Endpoint | Local |
|---|---:|
| `extraction/progress` | 0.03 s |
| `screening/full-text` | 0.02 s |
| `duplicate-groups` | 0.01 s |
| `prisma/metrics` | 0.04 s |

These are sanity measurements on a tiny local dataset, not the production
100-group / 1000-record dataset. Production post-change timings remain
**NOT VERIFIED**.

### Residual risks

- Production performance improvement is **NOT VERIFIED**; only the redundant
  `get_input_set` call was removed and local/frontend tests pass.
- Timeout behavior is covered indirectly through partial-result tests; the
  `Promise.race` timeout path is not exercised with fake timers.
- Performance test uses mocked API responses with large arrays; it validates
  frontend computation/render, not real network/backend latency.

---

## 8. Post-verification critical fix

### Issue

The memoization cache used constant keys (`dedup`, `prisma`), so switching
projects within the 10 s TTL could reuse the previous project's duplicate-group
and PRISMA read models.

### Fix

- `trackMemo` keys are now scoped as `${targetProjectId}:dedup` and
  `${targetProjectId}:prisma`.
- `setActiveProjectId` clears `memoCacheRef` and `inFlightRef` on every switch.
- Added `frontend/tests/WorkflowStatusProjectSwitch.test.tsx` (RED before fix,
  GREEN after): switches A -> B -> A and asserts dashboard/sidebar read models
  only contain the active project's data.

### Re-verification (post-fix)

- Frontend full suite: **365 passed / 50 files**.
- TypeScript: **passed**.
- Production build: **passed** (chunk-size warning only).
- Backend v0.7.6 integration: **2 passed**.
- Playwright E2E (mocked + real backend): **4 passed**.
- Ruff: **passed**.
- mypy: **208 source files, no issues**.
- Strict OpenSpec validation: **valid**.

BUG-01 remains verified: acceptance updates the import row, source-summary
counters, shared `workflowStatus`, sidebar stage state, and dashboard stage card
without a page reload. Production performance remains **NOT VERIFIED**.
