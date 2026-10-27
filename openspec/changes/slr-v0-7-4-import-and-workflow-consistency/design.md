# Design: Import Warning Resolution and Workflow Consistency

## Context

See `proposal.md` for motivation. The current v0.7.3 baseline stores aggregate
warnings in `import_history` and per-source evidence in
`import_source_records`/`import_skip_audit`, but has no import-review decision.
Rejection cannot be based on `project_publications.import_id` alone because:

- exact-DOI imports link source records to a canonical publication owned by
  another import instead of creating a second canonical row;
- duplicate merges may combine publications from multiple imports and leave
  superseded rows with `superseded_by`;
- downstream tables reference publication IDs without comprehensive foreign
  keys;
- legacy imports may have no authoritative ownership evidence.

Deduplication and screening currently use different publication populations:
deduplication reads active records while screening readiness builds groups from
the screening corpus, which still contains superseded rows. The workflow-status
response has no deduplication section, and the frontend derives completion from
`PENDING` counts. An approved-but-unmerged group is therefore presented as
complete while screening reports `unmerged_duplicates`; a merge followed by a
later import can also produce different group IDs between the two stages.

## Goals / Non-Goals

**Goals:**

- Decide warning imports explicitly, with durable attribution and audit.
- Make rejection safe, explainable, atomic, and non-cascading.
- Preserve rejected-import evidence while removing it from active research.
- Reconcile rejected imports into PRISMA as a distinct removal category.
- Use one duplicate-readiness model for deduplication, screening, workflow
  status, and PRISMA.
- Keep all existing API and database contracts backward compatible.

**Non-Goals:**

- Provider-import rejection. Warning decisions apply to file imports whose
  warnings are currently persisted; provider imports remain diagnostic-only.
- Automatic restoration after a committed rejection.
- Authentication or user-account management. Reviewer identity remains a
  self-asserted workflow identifier, consistent with existing screening.
- Reworking duplicate comparison, similarity thresholds, or merge policy.
- Production data reconciliation or deployment.

## Decisions

### 1. Append-only import review decisions

Add migration `0038_import_review_decisions.sql` with an additive table. Do not
mutate `import_history`; its original status, warnings, and counts remain the
historical import record.

```text
import_review_decisions
  decision_id                     TEXT PRIMARY KEY
  project_id                      TEXT NOT NULL
  import_id                       TEXT NOT NULL
  decision                        TEXT NOT NULL  -- accepted | rejected
  reviewer_id                     TEXT NOT NULL
  rationale                       TEXT
  decided_at                      TEXT NOT NULL
  import_status_at_decision       TEXT NOT NULL
  warning_snapshot_json           TEXT NOT NULL  -- JSON array
  affected_source_record_ids_json TEXT NOT NULL  -- JSON array
  affected_publication_ids_json   TEXT NOT NULL  -- JSON array
  removed_publication_snapshots_json TEXT NOT NULL -- JSON array
  deleted_publication_count       INTEGER NOT NULL DEFAULT 0
  retained_source_record_count    INTEGER NOT NULL DEFAULT 0
  prisma_treatment                TEXT NOT NULL
  UNIQUE (project_id, import_id)
```

Indexes support project/import lookup and rejected-import filtering. The unique
constraint makes decisions terminal: the same decision is idempotent, while a
different decision returns a conflict. Source records and skip-audit rows are
not updated or deleted.

The effective status is derived by a left join to this table:

| Import state | Effective status |
|---|---|
| no decision, raw success | `success` / `Zaimportowano` |
| no decision, raw warning | `warning` / `Ostrzeżenie` |
| accepted | `success` / `Zaimportowano` |
| rejected | `rejected`; hidden from active history |

### 2. Acceptance is non-destructive

Acceptance inserts one decision row and nothing else. It preserves publications,
duplicate decisions, screening decisions, quality, extraction, synthesis, and
the existing PRISMA stage populations. The only changed observable is the
import’s review state and effective display status.

### 3. Rejection preflight and blocker model

Rejection resolves affected canonical publications from both authoritative
ownership sources:

- `project_publications.import_id = selected import`;
- `import_source_records.import_id = selected import` with a non-null
  `canonical_publication_id`.

The union is the deletion candidate set. A publication is blocked when:

| Blocker code | Condition |
|---|---|
| `shared_publication` | A candidate is referenced by a source record from another import |
| `merged_publication` | A candidate is canonical or a member of a merge, or has non-null `superseded_by` |
| `duplicate_decision` | A candidate belongs to a group with a human duplicate decision or a decided candidate snapshot |
| `pre_screening_decision` | A candidate has a pre-screening decision or archive entry |
| `corpus_finalized` | A candidate belongs to a corpus finalization |
| `screening_decision` | A candidate has a title/abstract or full-text screening decision |
| `full_text_metadata` | A candidate has full-text availability metadata |
| `quality_assessment` | A candidate has a quality assessment |
| `extraction` | A candidate has an extraction record or revision |
| `synthesis` | A candidate is referenced by a synthesis relation, context, mechanism, or gap record |
| `unverifiable_ownership` | The import reports records but has no authoritative source or import ownership evidence |

Checks run inside the write transaction after acquiring the write lock. All
detected blockers are returned together. No cascade deletion or silent cleanup
is allowed.

### 4. Rejection transaction

Use the existing `SqliteTransactionManager` `BEGIN IMMEDIATE` boundary:

1. Load and validate the project/import pair.
2. Verify the import is a warning import with no existing decision.
3. Resolve candidate publications and run every ownership/downstream check.
4. If any blocker exists, roll back with a structured conflict response.
5. Delete only approved candidate publication rows.
6. Invalidate project normalization execution because the active corpus changed.
7. Reconcile stale duplicate state against the active corpus; no affected
   duplicate decision or merge may exist by preflight.
8. Insert the rejection decision with warning snapshot, affected IDs, removed
   publication snapshots, and counts.
9. Commit.

Any exception rolls back every step. Repeating a committed rejection returns the
existing decision without deleting again. A committed rejection has no automatic
restore; the decision snapshots and source records are the recovery evidence,
and restoration would require a separate human-approved reconciliation.

### 5. Active views and audit views

- Active import history, source summaries, working-collection count, warning
  counts, and workflow status exclude rejected imports.
- `GET /imports?include_rejected=true` exposes rejected imports for audit.
- Source-record and skip-audit endpoints remain queryable for rejected imports.
- Rejected imports do not enter screening, extraction, synthesis, or export
  populations.
- Existing import-history fields remain; review status, effective status, and
  decision metadata are added.

### 6. PRISMA treatment

Rejected source records remain in PRISMA identification history. Add metrics:

- `records_removed_rejected_import`: source occurrences belonging to rejected
  imports, including repeated occurrences already counted during identification;
- `duplicate_groups_awaiting_merge`: approved groups without a persisted merge;
- `duplicate_groups_blocking_screening`: pending plus approved-unmerged groups.

`records_removed_rejected_import` is included in the “removed before screening”
population and displayed as `removed before screening — rejected import`.
Identification counts continue to include the import. Later PRISMA stages use
the active corpus and exclude it. This preserves historical traceability without
double counting.

### 7. Shared duplicate readiness

Create a single duplicate-readiness projection with these states:

| State | Meaning | Dedup stage | Screening |
|---|---|---|---|
| `no_candidates` | No active candidate groups | completed | ready |
| `pending_review` | At least one group without decision | pending action | `unresolved_duplicates` |
| `approved_unmerged` | All decided, at least one APPROVE without merge | merge required, not completed | `unmerged_duplicates` |
| `ready` | Every group rejected or merged | completed | ready |

It returns total, pending, approved-unmerged, merged, rejected, stale-decision,
and blocking counts, plus a stable blocking reason. It builds groups only from
`get_active_publications()` and reuses the existing duplicate-group builder,
decision repository, and merge repository. The same projection is consumed by:

- `GET /projects/{project_id}/duplicate-groups`;
- `GET /projects/{project_id}/workflow-status`;
- screening input/readiness;
- PRISMA metrics and PRISMA exports.

Stale decisions for non-live group IDs remain audit but do not block. Historical
merges remain visible but do not block. Superseded rows never participate in
group construction, preventing phantom groups after later imports.

### 8. API contracts

Additive endpoints:

- `GET /api/v1/projects/{project_id}/imports/{import_id}/review`
  - returns import summary, warnings/counters, review status, effective status,
    `can_accept`, `can_reject`, and structured blockers.
- `POST /api/v1/projects/{project_id}/imports/{import_id}/review`
  - body: `decision` (`accept` or `reject`), `reviewer_id`, optional
    `rationale`, and `confirm_rejection` required for rejection.
  - success returns the decision, effective status, and review metadata.
  - missing project/import: 404;
  - invalid reviewer/confirmation: 422;
  - existing conflicting decision or blocked rejection: 409 with
    `detail.code` and `detail.blockers`.

Additive fields:

- import history and sources summary: `review_status`, `effective_status`,
  `reviewer_id`, `reviewed_at`, `can_accept`, `can_reject`;
- duplicate-group list: `readiness`;
- workflow status: `deduplication` with the same readiness fields;
- PRISMA: the rejected-import and duplicate-readiness counts listed above.

Existing fields, endpoints, and status codes remain unchanged. Rejected imports
are excluded by default from active history.

### 9. Frontend

- Replace the non-interactive warning badge with an accessible dialog. It shows
  import identity, date, counts, warning messages/categories, and the two
  decisions.
- `Akceptuję` calls the review endpoint and refreshes history/source/workflow
  state. No optimistic success is shown before the server confirms.
- `Odrzucam` opens a custom confirmation dialog using the approved Polish copy:

  > **Odrzucić import?**
  >
  > „Czy na pewno chcesz odrzucić ten import? Operacja usunie dane należące do
  > wybranego importu. Nie wpłynie na pozostałe importy.”
  >
  > `Anuluj` / `Potwierdź odrzucenie`

  Cancel performs no request. Confirm submits `confirm_rejection: true`.
- A blocked rejection keeps the dialog open and lists blocker categories and
  counts. It never labels the import as rejected.
- Deduplication and screening consume the shared readiness data. Pending groups
  show a review count; approved-unmerged groups show a merge-required count;
  `Oceniono` is shown only in the `ready`/`no_candidates` states.
- Screening maps `unresolved_duplicates` and `unmerged_duplicates` to distinct
  explanations and links to deduplication. The warning is never hidden.

## Risks / Trade-offs

- **Shared or merged publications are deleted accidentally** → union ownership
  resolution, cross-import source check, merge checks, and transactional
  preflight; tests cover both canonical and superseded members.
- **A downstream table is missed because SQLite has no comprehensive foreign
  keys** → enumerate every publication-referencing ledger in preflight and test
  each blocker category; fail closed on unknown linkage.
- **A committed rejection cannot be automatically restored** → confirmation,
  terminal decision, source/audit evidence, removed-publication snapshots, and a
  documented manual recovery path.
- **PRISMA identification totals appear unchanged after rejection** → expose
  rejected-import removals separately and reconcile every stage; this is the
  approved methodology.
- **Readiness computed twice diverges** → one projection and one active-corpus
  read per request; contract tests compare deduplication, screening, workflow,
  and PRISMA.
- **Legacy imports have no ownership proof** → block destructive rejection when
  records may exist, while allowing acceptance and diagnostic review.
- **Reviewer identity is self-asserted** → preserve the existing workflow
  convention and document the authentication limitation; this change does not
  claim authenticated authorization.

## Migration Plan

1. Add the additive `0038_import_review_decisions.sql` migration; do not edit
   migrations `0034`–`0037`.
2. Verify upgrade from the v0.7.3 schema on a disposable database, including
   `PRAGMA integrity_check` and `PRAGMA foreign_key_check`.
3. Deploy application support before relying on rejected-import filtering.
4. Rollback of the application code is safe with the table present; the table is
   additive and ignored by v0.7.3.
5. Do not drop the table in production. If a committed rejection must be
   reversed, use a separate approved reconciliation based on the decision,
   source records, and removed-publication snapshots.

## Rejected Alternatives

- **Cascade deletion of dependent decisions:** rejected because it would erase
  human research decisions and violate audit integrity.
- **Delete import history and source records:** rejected because the repository
  requires import provenance and skip-audit traceability.
- **Reject by `import_id` alone:** rejected because exact-DOI links and merges
  allow shared canonical ownership.
- **Soft-delete publications without changing active queries:** rejected
  because every downstream query would need a new filter, creating a larger
  orphan/counting risk than a guarded physical removal.
- **Keep frontend-derived deduplication state:** rejected because it produced
  the reported contradiction and cannot be verified server-side.
- **Use the screening corpus for duplicate grouping:** rejected because
  superseded records create phantom groups and unstable group IDs.

## Open Questions

None. The rejection blockers, audit retention, and PRISMA treatment are approved
decisions for this change.
