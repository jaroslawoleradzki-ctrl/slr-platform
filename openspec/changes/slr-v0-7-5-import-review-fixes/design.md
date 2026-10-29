# Design: Import Review Decision Feedback and Counter Refresh

## Context

See `proposal.md` for motivation. v0.7.4 establishes the authoritative
server-side behavior:

- `POST /projects/{project_id}/imports/{import_id}/review` commits an
  append-only decision and returns `effective_status` and `review_status`;
- `GET /imports` and `GET /sources-summary` derive `effective_status` with
  `effective_import_status` (`accepted -> success`);
- acceptance changes no publication, source-record, skip-audit, research
  decision, or PRISMA population;
- the Sources summary derives `successful_imports_count` and
  `warning_imports_count` from that effective status.

The defect is in the frontend orchestration. `ImportReviewModal` awaits
`onChanged()` before calling `onClose()`. `onChanged` in `FileDropzone`
sequentially awaits the Sources summary refresh and a shared
`refreshWorkflowStatus` fan-out of ten project endpoints. A slow refresh keeps
the dialog open with the pre-decision `detail` snapshot, and a rejected refresh
is caught by the decision handler as if the decision itself failed. Both
decision buttons and the close button share one `saving` flag, so the user sees
two spinners and a disabled dialog close. `SourcesIngestionPage` only renders a
summary error when no summary exists, so a failed refresh after a decision is
silent while old counters remain on screen.

## Goals / Non-Goals

**Goals:**

- Separate decision outcome from post-decision refresh outcome.
- Close the dialog as soon as the server confirms the decision.
- Show pending feedback only for the action in flight.
- Make refresh failures visible and retryable without implying decision loss.
- Keep counters consistent with the non-destructive acceptance contract.
- Add regression tests that fail on the v0.7.4 behavior.

**Non-Goals:**

- Changing the review endpoints, decision idempotency, rejection preflight, or
  stored data.
- Adding a new refresh endpoint, cache, or global state library.
- Introducing a global notification framework.
- Changing warning, PRISMA, or deduplication methodology.

## Decisions

### 1. Treat the decision response as the dialog's terminal state

`accept` and `reject` will use the returned `ImportReviewDecisionResponse` to
update local dialog state before closing:

- `effective_status`;
- `review_status`;
- `can_accept = false`, `can_reject = false`;
- the decision summary when available.

The dialog then notifies the parent with the same response and calls
`onClose()` immediately. The parent applies the response to the matching
`SourcesSummaryResponse.import_history` row (status, review state, decision
flags), so the active row reflects the committed decision before any network
refresh completes. This prevents a slow refresh from leaving an already-decided
import with an enabled accept/reject action or a stale `warning` label.

The POST remains the only operation whose failure keeps the dialog open and
shows an error or blockers. A refresh failure is handled separately.

Propagation uses a dedicated `onDecisionApplied(result)` callback from
`ImportReviewModal` through `FileDropzone` to `SourcesIngestionPage`. The
existing `onChanged` callback remains responsible only for background
refreshes, so decision delivery and read-model refresh cannot be conflated.

### 2. Split pending state by action

Replace the shared `saving` boolean with a discriminated pending state, for
example `pendingAction: 'accept' | 'reject' | null`.

- `isLoading` is true only for the matching action.
- Both decision triggers are disabled while any decision is pending.
- The close control is disabled only while the POST itself is pending; once the
  decision settles, dismissal is always available.
- The rejection confirmation dialog follows the same rule and closes on a
  successful rejection.

Rapid repeated activation is guarded by the pending state before the request is
started, preserving one POST per decision.

### 3. Refresh after close, concurrently, with explicit failure reporting

`FileDropzone.onChanged` will start both refreshes without serializing them:

```text
onChanged = () => {
  void Promise.allSettled([
    onRefresh?.(),
    refreshWorkflowStatus(projectId),
  ]).then(reportRefreshFailures)
}
```

The modal does not await this function. The Sources page remains responsible
for displaying the summary refresh outcome. `fetchSummary` will retain the old
summary for continuity but set an error that is rendered even when a summary
exists, together with a retry action. A failed workflow-status refresh remains
visible through the existing workflow/dashboard error state rather than being
reported as a decision failure.

An alternative was to keep awaiting the refresh behind a timeout. That still
blocks the user on unrelated endpoints and cannot distinguish a committed
decision from a failed refresh, so it is rejected.

### 4. Counter semantics stay non-destructive

The UI must not invent counter changes. After acceptance:

| Value | Expected behavior |
|---|---|
| Active import row status | `warning` -> `Zaimportowano` |
| Source summary `successful_imports_count` | +1 for that source |
| Source summary `warning_imports_count` | -1 for that source |
| `records_added_count` | unchanged |
| Working-collection total | unchanged |
| Canonical/source-record counts | unchanged |
| PRISMA identification and later stages | unchanged |

The existing backend already implements this. The change adds assertions that
pin it, so the UI fix cannot be mistaken for a request to alter research
counting.

### 5. Backend and persistence

No backend, API, or schema change is planned. The decision response already
contains the fields the dialog needs. If implementation reveals that a field is
missing, stop and update this design before changing a contract. There is no
migration and no rollback of stored data; reverting the frontend restores the
previous behavior without data repair.

## Risks / Trade-offs

- **Briefly stale parent view**: closing before refresh means the import row can
  be stale unless the decision response is applied immediately. Mitigation:
  propagate the response through `onDecisionApplied` and update the matching
  history row before closing; reconcile counters in the background and show a
  retry error if the refresh fails. A page reload always reads the committed
  server state.
- **Two refresh error surfaces**: summary and workflow status can fail
  independently. Mitigation: keep the Sources summary error local and reuse the
  existing workflow error state rather than inventing a global channel.
- **Conflicting clicks**: per-action spinners could tempt a reject click while
  accept is pending. Mitigation: disable both decision triggers, not only the
  active one.
- **Test coupling**: existing tests assert `onClose` after a resolved
  `onChanged`. They will be updated to assert decision-before-close and to cover
  pending and failed refreshes.
- **Counter expectation**: users may still expect PRISMA or working-collection
  totals to change after acceptance. Documentation and UI copy must state that
  acceptance is non-destructive and only the effective status changes.

## Migration Plan

None. This is a frontend behavior and test change. Deploying the frontend
against the existing backend is sufficient. If the change is reverted, no data
repair is required because the decision was already committed idempotently by
the unchanged backend.
