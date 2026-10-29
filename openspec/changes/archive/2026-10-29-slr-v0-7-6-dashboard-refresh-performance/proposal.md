# Proposal

## Why

After v0.7.5, approving an import updates the Sources table row, but the shared
workflow status used by the sidebar and dashboard is not updated until a full
`refreshWorkflowStatus` completes. That refresh fans out ten endpoints and waits
for the slowest one (about 2.3 s on production data), so users see stale
counters and a long "Ładowanie statusu projektu..." state. The problem is
frontend state propagation and read-path performance, not research data.

## What Changes

- P0: Accepting or rejecting an import immediately updates the shared
  `workflowStatus` and the affected source-summary counters, mirroring the
  existing optimistic update pattern used for duplicate decisions.
- P0: If no import remains with `effective_status = warning` after a decision,
  the Sources stage transitions to `completed` without waiting for a full
  refresh.
- P1: `refreshWorkflowStatus` resolves incrementally: each endpoint updates
  the UI as it settles, with per-endpoint timeouts and partial results.
- P1: Replace the single global loading skeleton with a progressive,
  per-stage loading indicator.
- P1: Add short-lived memoization for in-flight and recently completed heavy
  read models (`getDuplicateGroups`, `getPrismaMetrics`) to avoid duplicate
  fetches during navigation.
- P2: Optimize backend hot paths only where measurements confirm a bottleneck:
  extraction progress eligibility evaluation, duplicate-group readiness, and
  PRISMA metric aggregation. No API contract changes.
- Add integration, E2E, and performance tests, including tests against a real
  backend.

## Capabilities

### New Capabilities

- `workflow-status`: Authoritative computation, incremental refresh, and
  loading behavior of the project workflow status shown in the sidebar and
  dashboard, including prompt propagation of import-review decisions.

### Modified Capabilities

- None. PRISMA semantics, research data, and deduplication logic are unchanged.

## Impact

- Affected frontend: `ProjectContext.tsx`, `SourcesIngestionPage.tsx`,
  `FileDropzone.tsx`, `ProjectDashboardPage.tsx`, sidebar components.
- Affected backend (P2 only, after measurement): extraction eligibility
  service, duplicate-group/readiness service, PRISMA metrics service.
- No database migrations, no data changes, no API breaking changes.
- New/updated tests under `frontend/tests/` and `tests/` (integration, E2E,
  performance).
