# Proposal: Import Review Decision Feedback and Counter Refresh

## Why

The v0.7.4 import warning dialog performs the decision and the post-decision
read-model refresh as one blocking operation. When the refresh is slow or fails,
the dialog stays open, both decision buttons show the same loading state, and
the accepted import still appears with its pre-decision status and counters.
Users can interpret this as a failed acceptance or as stale warning counters,
even though the backend already committed the decision.

The problem is visible in the Sources & Imports workflow, which is the entry
point for import provenance and warning resolution. Fixing it is necessary
before v0.7.5 so a successful research decision is never presented as pending
or failed.

## What Changes

- Make a successful accept or reject decision complete independently of the
  subsequent Sources/workflow refresh. The dialog uses the server response as
  the authoritative decision result and closes without waiting for unrelated
  read models.
- Update the dialog's visible status, review state, and available actions from
  the decision response so it cannot keep offering an already-applied decision.
- Track the pending action per button instead of one shared `saving` flag. Only
  the action that is in flight shows a spinner; both decision triggers remain
  disabled until the request settles.
- Treat a post-decision refresh failure as a refresh problem, not as a failed
  decision. Keep the committed decision, do not reopen or block the dialog, and
  surface a visible retry affordance on the Sources page.
- Refresh the Sources summary and the shared workflow status concurrently after
  a decision, so the import row, warning/success counters, sidebar, dashboard,
  and PRISMA state converge without serial network waits.
- Make silent stale summary state impossible: when a refresh fails while an
  older summary is displayed, show an error and retry control instead of
  presenting the old counters as current.
- Preserve the v0.7.4 research-integrity contract: acceptance changes only the
  effective import status and warning-derived counts. Working-collection,
  canonical-publication, source-record, and PRISMA populations remain
  unchanged.
- Add regression coverage for slow refreshes, failed refreshes, per-action
  loading, duplicate submission, counter changes, and unchanged research
  populations.

## Capabilities

### New Capabilities

None. This change corrects behavior already owned by
`import-warning-resolution`.

### Modified Capabilities

- `import-warning-resolution`: the decision dialog lifecycle, pending-action
  feedback, post-decision refresh behavior, visible refresh errors, and the
  counter invariants for acceptance are clarified and made observable.

## Impact

- Frontend: `ImportReviewModal`, `FileDropzone`, and
  `SourcesIngestionPage`; shared workflow refresh remains in `ProjectContext`.
- Backend: no behavior change expected. Existing review, imports, and
  sources-summary endpoints already return the effective status. Tests will
  pin the counter invariants so a future backend change cannot silently make
  acceptance destructive.
- API: no endpoint, request, or response contract change.
- Persistence: no schema or migration change.
- Tests: frontend component/page tests plus focused backend service, API, and
  integration assertions for acceptance counters and unchanged research state.
- Documentation: `docs/GUI_FOUNDATION.md` and
  `docs/SOURCES_IMPORTS_AUDIT.md` will describe the non-blocking decision flow
  and the distinction between decision and refresh failures.
- Risk tier: **HIGH** because the change touches the import-review decision
  surface and the counters reviewers use to judge provenance and warning
  resolution, even though it does not alter stored research data.
- Human approval: research-integrity review is required before merge. No
  production deployment, data migration, merge, release, or archive is
  authorized by this change.

Out of scope: changing acceptance semantics, rejection safety rules, PRISMA
methodology, provider-import review, authentication, backend API changes,
database migrations, production infrastructure, merge, release, and
deployment.
