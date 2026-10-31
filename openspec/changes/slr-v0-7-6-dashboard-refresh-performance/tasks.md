# Tasks

## 1. Baseline measurement and test scaffolding

- [ ] 1.1 Record current `refreshWorkflowStatus` endpoint timings on a dataset with at least 100 duplicate groups and 1000 screening records and save the measurement note in the implementation report.
- [ ] 1.2 Add a failing frontend integration test that asserts shared `workflowStatus.sources` reflects an accepted import before a full refresh completes, using a deferred `getSourcesSummary` promise.
- [ ] 1.3 Add a failing frontend integration test that asserts source-summary successful/warning counters update after an accepted import.
- [ ] 1.4 Add a failing frontend test for progressive per-stage loading indicators during status refresh.

## 2. P0 — Prompt propagation of import-review decisions (frontend)

- [ ] 2.1 Extend `handleDecisionApplied` in `SourcesIngestionPage` to update `source_summaries` counters (successful +1, warning −1) for the affected source.
- [ ] 2.2 Add a callback from `SourcesIngestionPage` to `ProjectContext` that optimistically updates shared `workflowStatus.sources` from the decision result, mirroring `updateGroupDecision`.
- [ ] 2.3 Implement the optimistic transition: set Sources stage to `completed` when no import remains `warning`; otherwise keep `warning`; never change import count.
- [ ] 2.4 Ensure the full (non-blocking) refresh still runs after the decision to reconcile state.
- [ ] 2.5 Verify tasks 1.2 and 1.3 pass and add regression coverage for rejection decisions.

## 3. P1 — Incremental status refresh (frontend)

- [ ] 3.1 Refactor `refreshWorkflowStatus` to resolve each endpoint independently and merge partial results into `workflowStatus` as they settle.
- [ ] 3.2 Add per-endpoint timeout (configurable, default 5 s) via `Promise.race` with graceful partial results.
- [ ] 3.3 Track per-stage loading state in `ProjectContext` and expose it for UI consumption.
- [ ] 3.4 Replace the single global loading skeleton in `ProjectDashboardPage` with per-stage loading indicators.
- [ ] 3.5 Add short-lived memoization (TTL ~10 s) with in-flight deduplication for `getDuplicateGroups` and `getPrismaMetrics`, with explicit invalidation on mutations.
- [ ] 3.6 Verify task 1.4 passes and add tests for timeout/partial-result behavior.

## 4. P2 — Measurement-gated backend optimization

- [ ] 4.1 Profile extraction progress, duplicate-group readiness, and PRISMA metrics endpoints on the large dataset and record hotspots in the implementation report.
- [ ] 4.2 Optimize only confirmed hotspots (e.g., batch eligibility evaluation, SQL/index improvements) while preserving API response shapes and counts.
- [ ] 4.3 Add backend tests proving unchanged response shapes and counting semantics after optimization.
- [ ] 4.4 Re-run measurements and document before/after timings in the implementation report.

## 5. Integration, E2E, and performance tests

- [ ] 5.1 Add an integration test (real backend) for accept → shared workflow status update and source-summary counter update.
- [ ] 5.2 Add an integration test (real backend) for reject decision propagation.
- [ ] 5.3 Add an E2E test (real backend, no route interception) for accept → sidebar/dashboard update.
- [ ] 5.4 Add a performance test asserting refresh duration on the large dataset stays within the agreed threshold.
- [ ] 5.5 Add regression tests verifying research data (working collection, canonical publications, source records, PRISMA) is unchanged by refresh and decisions.

## 6. Verification gates

- [ ] 6.1 Run targeted frontend tests and confirm green.
- [ ] 6.2 Run targeted backend tests via `scripts/agent/safe_pytest.sh` and confirm green.
- [ ] 6.3 Run Ruff, mypy, TypeScript type-check, and frontend build; confirm green.
- [ ] 6.4 Run strict OpenSpec validation and confirm no errors.
- [ ] 6.5 Produce implementation report with red/green evidence, timings, and residual risk.

## Workflow follow-up

- Archive the change after review requirements are satisfied.
- Verify the archived result.
