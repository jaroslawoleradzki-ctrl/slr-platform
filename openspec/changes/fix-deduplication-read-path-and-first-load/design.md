# Design

## Context

See `proposal.md` for motivation and `specs/deduplication-screening-consistency/spec.md` for the observable contract. The current duplicate-group service derives response groups from active publications, reviewer decisions, and persisted merges, then clears and repopulates `import_source_records.duplicate_candidate_group_id` and inserts candidate snapshots. Screening and PRISMA independently derive readiness from active publications, decisions, and merges; they do not consume that source-record field. The field is nevertheless returned by the source-record API, so its freshness is externally observable. Current runtime latency and first-load failure evidence are unavailable.

## Goals / Non-Goals

**Goals:**
- Make the duplicate-groups GET path read-only while preserving its response shape and deterministic group results.
- Preserve current reviewer decisions, merges, snapshots, research records, screening readiness, and PRISMA accounting.
- Establish trustworthy server and browser measurements before choosing a remedy for slow or unreliable first loads.
- Verify the first-load path against a real test API and real disposable project data, not only mocked responses.

**Non-Goals:**
- Changing duplicate matching, title/identifier rules, group IDs, review semantics, merge behavior, or scientific decisions.
- Changing snapshot semantics or rebuilding/deleting audit history.
- Selecting a new timeout, retry policy, cache policy, asynchronous job protocol, or background worker before runtime evidence and approval.
- Changing source-record API fields or silently redefining freshness of `duplicate_candidate_group_id`.
- Production infrastructure, research data, deployment, release, merge, or archive changes.

## Decisions

### 1. Separate projection reads from writes

The duplicate-group GET will compute the response from the same active corpus, decision repository, merge repository, builder, and readiness evaluator as today, but will not invoke source-record group clear/update or snapshot insertion. The response contract and algorithm remain unchanged. No schema change is expected.

The approved projection policy is to recompute `duplicate_candidate_group_id` at each operation that changes inputs to the active duplicate groups, in the same transaction as that operation. Reuse the existing builder and stable IDs, calculate the complete new mapping before applying the clear-and-set projection, and use the same SQLite connection for all row updates so any error rolls back both the corpus mutation and projection. Source-record API shape and freshness remain unchanged after successful mutations.

Snapshot writes also leave GET. Preserve the existing table, unique key, immutable first-write behavior, columns, and payload meaning (group membership, match metadata, status and observation time); materialize the same group snapshot in the mutation-boundary reconciliation transaction. Do not update or delete existing snapshots. Because snapshots are only a membership/status observation and are not a decision ledger, import-review's historical-membership fallback must pair snapshot group IDs with the persisted `duplicate_review_decisions` row and use that row's current decision as authority. It must not reject a valid membership snapshot merely because its immutable first observation status is `PENDING`.

Runtime and code evidence show this fallback matters: on HomeLab the read-only aggregate query found 355 snapshot rows across 355 distinct project/group pairs (205 `PENDING`, 150 `MERGED`); 54 groups with current `APPROVE` decisions have immutable `PENDING` snapshots, and 3 current decisions have no snapshot. These records were not modified. Preserve every existing row and decision. The 3 missing historical memberships cannot be reconstructed from the decision table alone and must not be backfilled or fabricated.

The mutation paths for provider/file import, import rejection, pre-screening remove/restore, and duplicate merge already use shared SQLite transactions. Normalization currently does not, but it is feasible to compose with the existing `SqliteTransactionManager`: it already gives callers one SQLite connection, starts `BEGIN IMMEDIATE`, commits once on success, and rolls back on an exception. The SQLite publication repository already accepts a connection for active-corpus reads, `update_publication`, and `replace_publications`; the missing pieces are connection propagation through `normalize_project` and its helpers, connection-aware normalization-summary persistence, and calling normalization plus group-projection/snapshot materialization inside one transaction in the POST operation. Use the same DB path for all participating repositories and verify this in dependency wiring/tests. Do not create nested repository connections or commits when a connection is supplied.

Transaction-boundary map verified against current call sites:

| Mutation path | Current boundary and connection | Gap to close |
|---|---|---|
| Provider/file imports | `ProjectImportService.import_provider_results_group` and `import_bibliographic_publications` open/reuse `SqliteTransactionManager.transaction()` and pass `conn` through publication, source-record, and history writes (`app/services/project_import_service.py`). API routes call those entry points (`app/api/routers/search_strategy.py`). | Rebuild candidate-ID projection and insert immutable snapshots before the same transaction exits. |
| Import rejection | `ImportReviewService.reject` opens one transaction and passes `connection` to review/history/publication/normalization-summary writes (`app/services/import_review_service.py`). | Rebuild projection/snapshots after publication deletion, before commit. Acceptance does not change corpus membership and needs no projection write. |
| Pre-screen removal/restoration | `PreScreeningReviewService.archive_pre_screening_removal`, retained restoration, and archived restoration use one transaction and pass `conn` to archive, decision, and publication writes (`app/services/pre_screening_review_service.py`). | Rebuild projection/snapshots on each branch that changes active membership, before commit. |
| Duplicate merge | `ProjectDuplicateService.merge_group` wraps reviewer decision, merge ledger, canonical update, and superseding in one transaction (`app/services/project_duplicate_service.py`). | Materialize projection/snapshots from the resulting active corpus before commit. Preserve merge and decision ledgers. |
| Normalization API | `run_normalization` calls `normalize_project` and then summary `save` separately (`app/api/routers/normalization.py`); each publication update and summary save may commit through its own repository connection (`app/services/normalization_service.py`, `app/repositories/project_publication_repository.py`, `app/repositories/normalization_execution_repository.py`). | Add one shared transaction and connection propagation for reads, publication writes, projection/snapshots, and summary save. |
| Derived-state rebuild | `CorpusDerivedStateService.rebuild` calls normalization, summary save, stale-decision/merge reconciliation, and GET in sequence (`app/services/corpus_derived_state_service.py`). | Route its normalization/projection/summary phase through the same atomic operation; retain current reconciliation order and behavior, then use read-only GET. |

There are no direct transaction commits in application services for these paths beyond the transaction manager; the existing candidate projection and snapshot repository methods are exceptions because they open and commit their own connections (`app/repositories/import_source_record_repository.py`). Make those methods connection-aware before invoking them under mutation transactions. The search-results route may call the provider import operation once per provider group, each in its existing transaction; keep that established unit of atomicity rather than introducing a broader request transaction.

The atomic operation should be: begin transaction; read the active corpus using that connection; normalize in memory with the existing algorithm; persist all normalized active rows using that connection; build groups from the resulting active corpus using the same connection; update the complete source-record group-ID projection and insert snapshots using that connection; save the normalization execution summary using that connection; then commit. Any exception from reading, normalization, any row update, projection, snapshot insert, or summary persistence must roll back the entire operation. Preserve the active-only behavior and metadata protections in `replace_publications`.

Implement this as a shared application-level operation used by both `POST /normalization` and `CorpusDerivedStateService.rebuild`, rather than allowing a persistent SQLite call to `normalize_project` to silently open independent commits. Make `normalize_project` accept a caller connection and pass it through `_read_active_corpus` and `_persist_normalized_corpus`; add connection parameters to repository protocol methods that currently omit them even though the SQLite implementation supports them. Make normalization-summary `save` and group projection/snapshot writes connection-aware. Wire the transaction manager and repositories to the same database path; API test overrides must use one disposable database and the same transaction manager. Non-SQLite/in-memory adapters can retain their existing behavior for tests or demo use, but they are not evidence of SQLite atomicity.

`CorpusDerivedStateService.rebuild` currently invokes normalization, saves the execution, reconciles stale merge/decision rows, then reads duplicate groups. Route its normalization phase through the same atomic operation so publications, execution summary, candidate IDs, and snapshots commit together. Keep the existing reconciliation behavior/order and do not remap, rewrite, or expand reviewer decision history as part of projection materialization. The explicit GET remains read-only; the rebuild must call the dedicated materialization operation rather than relying on GET side effects.

This makes the write lock span corpus reading, CPU normalization, group construction, and persistence. A mid-list SQL failure currently can leave an already committed prefix of normalized publications while later rows and the execution summary remain old; a failure while building groups after publication writes can likewise leave group IDs stale. The shared transaction prevents both states. This is the smallest clear atomic design, not a proven latency-safe one: measure transaction duration, active row/group counts, and SQLite busy/locked outcomes with synthetic projects and concurrent readers/writers. Do not optimize away the lock by computing outside the transaction unless a consistent-corpus revision/precondition is designed and tested. If measured lock duration is unacceptable, stop this element and present an optimistic revision-checked alternative rather than weakening atomicity.

### 2. Collect baseline runtime evidence before performance choices

First add low-content observability around the endpoint and client first load. Backend measurements should report total duration/status and stage durations for active-corpus read, decision/merge reads, group construction, readiness calculation, serialization, and response completion. Include bounded aggregate dimensions such as active publication count, source-record count, candidate group count, response bytes, and group-size distribution. Client instrumentation should record request start, response/error/timeout, and first-visible result/render time, tagged with project-safe correlation data but no publication content or identifiers.

Report p50/p95/p99 latency, first-load latency, client timeout count, HTTP 5xx count, and UI render latency over representative synthetic test projects and a controlled runtime measurement interval. Keep the configured 8-second timeout unchanged during baseline collection. Do not add automatic retry. Only after evidence shows the remaining failure mode and latency distribution may a bounded GET retry, timeout adjustment, or asynchronous job be proposed. Persistent 5xx and validation errors must remain visible as errors.

### 3. Preserve one readiness source across workflows

Do not make `duplicate_candidate_group_id` authoritative for grouping or readiness. Continue to use the active corpus plus persisted decisions and merges, ensuring screening and PRISMA agree with deduplication. Add equivalence regression checks for groups/readiness/counts before and after the read/write separation. Do not modify screening or PRISMA algorithms to accommodate the storage projection.

### 4. Keep corpus mutation and materialized metadata atomic

Use the connection passed by each mutation transaction for active-corpus reads, group calculation inputs, source-record projection changes, snapshot insertion, and normalization execution-summary persistence. Existing publication methods already support connection passing in their SQLite implementation; update repository protocols where signatures lag. The source-record projection/snapshot methods and normalization-summary `save` currently open and commit their own connections; add connection-aware operations that do not commit when a caller supplies a connection. For `POST /normalization`, use the existing transaction manager and perform read, normalize, publication updates, group projection/snapshots, and summary persistence in the same transaction. Add rollback-injection tests at a middle publication update, projection write, snapshot write, and summary write proving all changes roll back. Measure lock duration and contention; if unacceptable, stop and present a revision-checked alternative.

Add integration coverage for parallel GETs and an import occurring during a GET. Responses must be complete and internally consistent with a valid persisted corpus state; GET must not expose or create partial projection writes.

### 5. Test actual browser/API behavior

Use the existing frontend test conventions for loading/success/error rendering and a Playwright E2E against the actual FastAPI test server with a disposable SQLite-backed synthetic project. The first page load test must assert visible groups/readiness without manual reload and capture the corresponding real request. Include error states using controlled test-server responses, while keeping a separate successful real-backend first-load path. Never use production research data.

## Risks / Trade-offs

- [Normalization now holds SQLite's writer reservation while CPU work runs] → Measure transaction duration and busy/locked outcomes with synthetic corpora and concurrent operations; if unacceptable, stop and design a revision-checked alternative without weakening atomicity.
- [A failed materialization can leave publication state and source projection inconsistent] → Use one transaction/connection and rollback the full mutation on any projection or snapshot failure; prohibit post-commit best-effort repair as the correctness path.
- [Historical membership snapshots can have a PENDING status even when a decision now exists] → Keep immutable snapshot rows unchanged and use the persisted decision row, not the snapshot's first-observation status, as decision authority in the import-review fallback.
- [Some prior decisions have no membership snapshot] → Preserve the decision and do not fabricate/backfill historical members; report the known gap and ensure new group membership observations are recorded at mutation boundaries.
- [Runtime instrumentation could expose sensitive research data] → Emit only timings, status, counts, and non-content correlation identifiers; add tests/config review for field allowlists.
- [First-load failure may have a cause unrelated to GET writes] → Capture browser and server evidence first; do not claim success from improved error labels or read-only behavior alone.
- [Concurrent import and group calculation could observe different SQLite moments] → Exercise with controlled integration tests and use only an existing narrow connection/transaction facility; pause for review if a broader change is required.
- [Playwright test backend could drift from deployed UI/backend behavior] → Run E2E against the built frontend and the actual FastAPI application using disposable project data; record exact commands/results in the implementation report.

## Migration Plan

No schema migration or research-data migration is expected. Deploy only after local gates and CI pass; deployment is outside this proposal and requires the human release process. Rollback is application-code rollback to the prior read path; it does not require deleting or rewriting snapshots or source records. Since old and new versions can differ in how fresh source-record group metadata is, deploy only after the freshness policy is approved and compatibility is verified.

## Approved Architecture and Remaining Feasibility Gate

The user approved refreshing `duplicate_candidate_group_id` at publication-set mutation boundaries. The existing transaction manager makes normalization composition feasible without a new schema or algorithm: propagate its connection through the normalization and projection repositories, and save the normalization summary before the same transaction commits. Validate full rollback on injected mid-run errors. The remaining gate is performance: if the measured lock duration/contended writer behavior is unacceptable, stop this element and present a revision-checked alternative; do not ship partial freshness. Playwright is already configured in `frontend/playwright.config.ts` and `frontend/e2e`; no dependency addition is needed.



## Verify follow-up implementation evidence

`run_project_normalization` is the shared operation used by the normalization POST and rebuild. For SQLite rebuild, the caller owns one outer transaction spanning normalization, initial materialization/summary, the existing reconciliation, and final materialization from the reconciled state. Reconciliation accepts that connection for every read and deletion; its membership rules and sequence are unchanged. A failure after the final projection rolls back normalized rows, summary, both projection passes and the existing reconciliation changes. Default rebuild repositories bind to the supplied publication database. This closes the previously observed commit gap without a new reconciliation policy or schema.

The regression fixture now has three real source records; it asserts that historical group IDs exist before rebuild and are absent after successful reconciliation. Injecting failure after final projection compares publications, complete source records, snapshots, decisions, merges and execution summary with their pre-operation values.

The controlled import/read tests pause a GET after corpus read, force a prepared real import service to reach its uncommitted projection, then resume the reader before awaiting writer completion. Complete response equality with the pre-import response is checked in DELETE and WAL journal modes, followed by a complete post-import candidate/readiness check. Schemas are initialized before the forced interleaving; schema initialization itself may require a write lock in DELETE mode. These are bounded synthetic checks, not a guarantee for arbitrary production corpus sizes.

An ASGI route wrapper records status, byte count and elapsed time after the final response body is handed to `send`; it does not claim network receipt by the browser. A context-local random correlation token links it to endpoint and service-stage logs (including readiness). Internal mutation materializations use the non-identifying `internal` token. Playwright now serves `npm run build` through Vite preview and asserts actual group members, pending readiness and visible review state. The import acceptance scenario uses SPA navigation and verifies a document token survives navigation to Dashboard.
