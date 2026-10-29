# Design

## Context

See proposal.md for motivation. Current state: `ProjectContext.refreshWorkflowStatus`
fans out 10 endpoints via `Promise.allSettled` and blocks the UI until the
slowest resolves. `handleDecisionApplied` in `SourcesIngestionPage` updates only
the local import-history row, not `source_summaries` or shared `workflowStatus`.
Existing optimistic-update pattern (`updateGroupDecision`) provides a template.

## Goals / Non-Goals

**Goals:**
- Prompt propagation of import-review decisions to shared workflow status and
  source-summary counters.
- Incremental, non-blocking status refresh with per-endpoint timeouts.
- Progressive per-stage loading UI.
- Short-lived memoization of heavy read models.
- Measurement-gated backend hot-path optimization.

**Non-Goals:**
- Changing PRISMA semantics or any research data.
- Changing deduplication logic or screening decisions.
- New database migrations.
- Replacing the client-side status computation with a single backend endpoint
  (out of scope for this change).

## Decisions

### D1: Optimistic update location

Update `workflowStatus` and `source_summaries` in `handleDecisionApplied`
(Sources page) and propagate to `ProjectContext` via a new callback, mirroring
`updateGroupDecision`. Alternative: re-run full refresh optimistically —
rejected because it still blocks on slow endpoints.

### D2: Incremental refresh

Replace `Promise.allSettled` with per-promise `.then`/`.catch` handlers that
call `setWorkflowStatus` with a partial merge as each endpoint resolves.
Keep a single `workflowStatusLoading` flag for backward compatibility but add
per-stage loading flags.

### D3: Timeouts

Wrap each fetch in `Promise.race` with a configurable timeout (default 5 s).
On timeout, mark the stage as error/pending and continue. Alternative: AbortController
per request — deferred to implementation; race is simpler and sufficient.

### D4: Memoization

Memoize `getDuplicateGroups` and `getPrismaMetrics` results keyed by project
id with a short TTL (e.g., 10 s) and deduplicate in-flight requests. Store in
`ProjectContext` refs; invalidate on mutations (import, decision, dedup action).

### D5: Progressive loading UI

Replace the single global skeleton with per-stage placeholders driven by a
`workflowStatusLoadingStages` set. Ready stages render their values immediately.

### D6: Backend optimization (P2)

Apply only after profiling confirms hotspots. Candidate: batch eligibility
evaluation in `ExtractionEligibilityService`, add indexes/batch queries for
duplicate groups and PRISMA metrics. Preserve response shapes and counts.

## Risks / Trade-offs

- [Optimistic state drift] → Reconcile on next full refresh; refresh always
  runs after decision (non-blocking).
- [Partial data inconsistency] → Incremental merge must be idempotent and
  guarded by project-id checks.
- [Memoization staleness] → Short TTL plus explicit invalidation on mutations.
- [Timeout false positives on slow networks] → Configurable timeout, retry
  action in UI.

## Migration Plan

No database migration. Frontend-first deployment: optimistic update and
incremental refresh can ship independently of backend changes. Backend P2
changes are additive performance improvements behind the same API contracts.
Rollback: revert frontend changes; backend changes are independently
revertible.

## Open Questions

- Exact timeout value and memoization TTL to be finalized during implementation
  based on measurements.
