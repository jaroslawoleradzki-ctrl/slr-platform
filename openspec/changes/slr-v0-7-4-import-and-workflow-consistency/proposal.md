# Proposal: Import Warning Resolution and Workflow Consistency

## Why

v0.7.3 made import warnings inspectable, but a reviewer still cannot record an
explicit decision to accept or reject the affected import. Import history also
lacks a safe ownership model for destructive cleanup: a canonical publication
may be linked from several imports, merged with records from another import, or
already used by screening and later research stages.

Separately, deduplication reports completion while screening can still report
unresolved duplicate groups. The two stages build duplicate groups from
different publication populations and use different completion criteria, so a
merged group followed by a later import can produce contradictory workflow
feedback. This undermines confidence in screening readiness and PRISMA
traceability.

This change defines explicit, auditable import decisions and one authoritative
duplicate-readiness model for deduplication, screening, PRISMA, and the UI.

## What Changes

- Add explicit `Akceptuję` and `Odrzucam` decisions for warning imports.
- Record acceptance without changing imported publications, duplicate
  decisions, or screening decisions; the import's effective display status
  becomes `Zaimportowano` while its original warning history is retained.
- Require a confirmation dialog before rejection and an explicit backend
  confirmation flag.
- Reject an import transactionally only when ownership is provable and no
  duplicate merge, duplicate review decision, screening decision, or downstream
  research record depends on its publications.
- Return structured rejection blockers to the UI and keep the import intact
  when rejection is unsafe.
- Retain rejected imports, source records, skip-audit rows, and the rejection
  decision as non-active audit.
- Remove rejected imports from active history, active corpus, screening,
  extraction, synthesis, and export populations.
- Keep rejected source records in PRISMA identification history and classify
  them as `removed before screening — rejected import`.
- Build duplicate groups from the active canonical corpus consistently across
  deduplication, screening readiness, workflow status, and PRISMA.
- Treat an approved-but-unmerged group as blocking `merge_required`, not as
  deduplication completion.
- Expose the same duplicate-readiness state to the deduplication page, workflow
  status, and screening readiness, and show the exact blocker instead of a
  generic conflict.
- Add regression coverage for shared publications, merges, downstream decisions,
  legacy imports, and the merged-group-plus-new-import inconsistency.

## Capabilities

### New Capabilities

- `import-warning-resolution`: explicit accept/reject decisions, rejection
  preflight and transaction semantics, non-active audit retention, active-view
  filtering, PRISMA treatment, and API/UI behavior.
- `deduplication-screening-consistency`: a single duplicate-readiness model
  over the active corpus, consistent pending/merge-required/ready states across
  deduplication, screening, workflow status, and PRISMA.

### Modified Capabilities

None. The existing `agent-engineering-foundation` specification defines
development governance, not application workflow behavior.

## Impact

- Backend: import history/source-record repositories, a new import-review
  repository and service, duplicate-readiness service, screening input,
  workflow status, PRISMA metrics, source summaries, and export aggregation.
- API: additive import review endpoints and additive readiness fields on import
  history, sources summary, duplicate groups, and workflow status responses.
  Existing fields and endpoints remain backward compatible.
- Frontend: warning detail dialog, accept action, reject confirmation, blocker
  explanation, import-history refresh, and backend-authoritative deduplication
  and screening status presentation.
- Persistence: one additive migration for append-only import review decisions.
  No existing migration is edited.
- Tests: unit, integration, contract, migration-focused, and frontend tests,
  including shared-publication and downstream-decision cases.
- Risk tier: **HIGH** because the change touches imports, deduplication,
  screening, PRISMA accounting, and a destructive import-rejection path.
- Human approval: research-integrity review is required, and the approved
  PRISMA treatment and rejection-blocking rules must remain in force. No
  production data migration, merge, release, or deployment is authorized by
  this change.

Out of scope: embedded AI or LLM behavior, autonomous scientific decisions,
provider-import rejection, changing duplicate-review methodology, authentication
or user-account management, production database reconciliation, production
deployment, merging the branch, and publishing a release.
