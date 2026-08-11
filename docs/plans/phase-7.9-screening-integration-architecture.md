# Phase 7.9 — Screening Integration and Release
## Architecture / Integration Plan

> Status: ARCHITECTURE / INTEGRATION PLAN ONLY — DO NOT IMPLEMENT
>
> Version remains `0.3.3` until a separate release decision is approved.
> This document does not create migrations, change branches, or alter Phase 8.

## 1. Audit scope and evidence

The audit was performed read-only against:

- `ROADMAP.md`, `IMPLEMENTATION_PLAN.md`, `PROJECT_STATUS.md`;
- `docs/ARCHITECTURE.md`, `docs/DECISIONS.md`, `docs/data-model.md`;
- the current 7.8B worktree `/Users/jarek/Git/slr-platform`;
- the separate QA worktree `/Users/jarek/Git/slr-platform-qa` on
  `feature/quality-assessment`.

Current primary worktree facts:

- branch: `feature/screening-7.8b`;
- HEAD: `0d22b1d`;
- VERSION: `0.3.3`;
- 7.8B migrations present: `0015`, `0016`, `0017`;
- Phase 8 migrations and QA code are not present on this branch;
- the referenced `docs/plans/phase-7.8b-architecture.md` is not present in
  the current checkout. The 7.8B implementation and its accepted contracts
  are therefore treated as the implementation baseline, while the missing
  source document is recorded as a documentation reconciliation gap.

Phase 8 evidence:

- `feature/quality-assessment` is at `f23bb08` and diverged from the common
  `development` ancestor `07f5dd1`;
- it contains the QA domain, catalog/configuration services, execution service,
  API, GUI, tests, and migrations `0013` and `0014`;
- its QA execution service currently derives eligibility from the latest
  reviewer-specific `FULL_TEXT` decision;
- its GUI currently uses the existing reviewer local-storage contract directly;
- it has no project-level screening-outcome adapter.

## 2. Existing 7.8B baseline

The current branch already provides:

- `ConflictResolution`, `ProjectScreeningOutcome`, and
  `PublicationScreeningStatus`;
- append-only resolution persistence and decision-link rows;
- deterministic `decision_set_key` including project, publication, stage,
  active roster, latest decision IDs, and outcomes;
- `INCOMPLETE`, `AGREEMENT`, `CONFLICT`, `RESOLVED`, and
  `STALE_RESOLUTION` derivation;
- explicit resolver identity, rationale, resolution history, HTTP 409
  optimistic concurrency, reporting metrics, and tagged `DECISION | RESOLUTION`
  audit events;
- `useReviewerIdentity()` over the unchanged
  `slr_screening_reviewer_id` local-storage key;
- conflict-resolution GUI and API tests.

The 7.8B read model is the only source of truth for multi-reviewer project
outcomes. Phase 7.9 must call it; it must not reimplement conflict, stale, or
agreement logic.

Known integration limitation to address in 7.9: the current
`MultiReviewerScreeningService.project_outcome()` fallback is not an adequate
single-reviewer boundary when several free-text reviewer IDs exist without a
roster, because it selects the latest decision across all such IDs. The
integration adapter must preserve the established reviewer-specific behavior
for no-roster projects and must use 7.8B project outcomes only when the
relevant active roster exists.

## 3. Scope and non-goals

Phase 7.9 integrates already-built Screening and Quality Assessment modules.
It does not redesign either domain, add scientific automation, or add a new
workflow stage.

In scope:

- project-level T&A outcome driving Full-Text eligibility;
- all active Full-Text reviewers receiving a project-level T&A INCLUDE;
- project-level Full-Text outcome driving QA eligibility;
- explicit blocking for incomplete, unresolved, and stale screening;
- authoritative stage completion and workflow read models;
- Dashboard, WorkflowStepper, Sidebar, routing, and QA readiness UI;
- backend/frontend integration tests and browser-level E2E verification;
- safe merge of Phase 7 and Phase 8;
- documentation reconciliation and release verification.

Out of scope:

- changes to `QualityAssessment` domain objects, templates, response values,
  repositories, or QA tables;
- new screening or QA persistence tables;
- QA reviewer-roster redesign;
- Data Extraction, Phase 9, exports, PRISMA implementation, or synthesis;
- majority voting, automatic scientific decisions, authentication, or user
  management;
- a VERSION bump, tag, release, or merge during architecture review.

## 4. Normative transition contracts

### 4.1 Single-reviewer mode

No active roster for the relevant stage means legacy reviewer-specific mode.
For a requested reviewer ID, the latest append-only decision for that reviewer
is authoritative. Existing T&A and Full-Text queue behavior remains unchanged.
No adjudication row is required.

### 4.2 Multi-reviewer T&A → Full Text

When an active T&A roster exists, the project-level T&A outcome is authoritative:

```text
ProjectScreeningOutcome(TITLE_ABSTRACT).status in {AGREEMENT, RESOLVED}
and outcome == INCLUDE
    => publication is eligible for Full Text
```

Every active reviewer in the `FULL_TEXT` roster receives that publication in
the Full-Text queue, regardless of that reviewer's earlier T&A outcome. The
queue is derived on read; no queue-membership table is introduced.

### 4.3 Multi-reviewer Full Text → Quality Assessment

When an active Full-Text roster exists, QA publication eligibility is derived
from:

```text
ProjectScreeningOutcome(FULL_TEXT).status in {AGREEMENT, RESOLVED}
and outcome == INCLUDE
```

The QA execution service remains responsible for QA records, templates,
responses, history, and reviewer attribution. A thin screening eligibility
adapter supplies the project-level eligible publication set. No QA domain or
schema rebuild is permitted.

The adapter does not introduce a QA roster. Existing QA reviewer identity and
append-only QA assessment behavior remain available; the project-level outcome
controls whether a publication may enter QA.

### 4.4 Final outcomes versus downstream eligibility

`AGREEMENT INCLUDE` and current `RESOLVED INCLUDE` are final and advance to the
next stage. `AGREEMENT EXCLUDE`, `AGREEMENT UNCERTAIN`, `RESOLVED EXCLUDE`, and
`RESOLVED UNCERTAIN` are final screening outcomes but produce no next-stage
eligible publication. `INCOMPLETE`, unresolved `CONFLICT`, and
`STALE_RESOLUTION` are not final and block progression.

## 5. Integration adapter contract

Introduce one thin integration/readiness adapter, for example
`ScreeningEligibilityAdapter`, with no persistence:

```python
get_outcome(
    project_id: str,
    publication_id: UUID,
    stage: ScreeningStage,
    reviewer_id: str,
) -> ProjectScreeningOutcome

eligible_publications(
    project_id: str,
    source_stage: ScreeningStage,
    target_stage: ScreeningStage,
    reviewer_id: str,
) -> tuple[UUID, ...]

stage_readiness(
    project_id: str,
    stage: ScreeningStage,
    reviewer_id: str,
) -> ScreeningStageReadiness
```

Rules:

1. Validate project and canonical screening input through existing services.
2. Detect the active roster for the stage.
3. With no roster, delegate to the existing reviewer-specific latest-decision
   path.
4. With a roster, delegate to `MultiReviewerScreeningService` and
   `ProjectScreeningOutcome`; do not duplicate its status or key algorithm.
5. Batch-load stage outcomes for queues and workflow summaries. Do not call
   `project_outcome()` once per publication from a list endpoint.
6. Return a typed blocking reason (`input_not_ready`, `incomplete`,
   `unresolved_conflict`, `stale_resolution`, `no_eligible_publications`, or
   `not_configured`) suitable for both API and GUI.

The adapter may require a small 7.8B service API extension that accepts the
reviewer ID for the no-roster fallback. That is an integration compatibility
correction, not a second project-outcome implementation.

## 6. T&A → Full-Text implementation boundary

Extend `FullTextScreeningService` only at its eligibility boundary:

- retain its existing criteria, availability, assessment validation, decision
  persistence, and exclusion-reason behavior;
- replace only `_eligible_publications` input derivation with the adapter;
- in no-roster mode, preserve the existing reviewer-specific T&A INCLUDE rule;
- in active multi-reviewer mode, use project-level T&A INCLUDE;
- if T&A is incomplete, unresolved, or stale at project gate level, return a
  typed not-ready response and do not expose records for the blocked stage;
- when eligible, hydrate records with the requesting reviewer's own Full-Text
  decision, so independent Full-Text review remains append-only and blind-aware.

For an active Full-Text roster, the service must validate that queue access is
for an active roster reviewer. If no Full-Text roster exists, the existing
free-text reviewer workflow remains compatible.

## 7. Full-Text → QA implementation boundary

On the Phase 8 branch after merge, update only the eligibility seam of
`DefaultQualityAssessmentExecutionService`:

- preserve configuration lookup, template selection, QA response validation,
  snapshots, append-only assessment history, and existing error semantics;
- replace reviewer-specific FULL_TEXT INCLUDE lookup with the adapter when an
  active Full-Text roster exists;
- retain the old reviewer-specific lookup when no Full-Text roster exists;
- make `check_readiness`, `get_overview`, `list_eligible_records`,
  `get_record_detail`, and `save_assessment` use the same adapter contract;
- re-check eligibility on every read and write, so changing a Full-Text
  decision or resolution immediately revokes QA access;
- expose a typed `WAITING_FOR_SCREENING`/blocking reason without changing the
  QA domain enum or persistence schema. The integration router may map this to
  the existing QA readiness response.

## 8. Blocking and revocation matrix

| Source stage state | Project outcome | Next-stage access |
|---|---|---|
| `INCOMPLETE` | none | blocked |
| unresolved `CONFLICT` | none | blocked |
| `STALE_RESOLUTION` | none | blocked |
| `AGREEMENT INCLUDE` | include | allowed |
| `RESOLVED INCLUDE` | include | allowed |
| `AGREEMENT EXCLUDE` | exclude | no eligible publications |
| `AGREEMENT UNCERTAIN` | uncertain | no eligible publications |
| `RESOLVED EXCLUDE` | exclude | no eligible publications |
| `RESOLVED UNCERTAIN` | uncertain | no eligible publications |

Blocking applies at project stage-gate level. A stale or unresolved publication
must never be silently treated as excluded or included. If a currently eligible
publication becomes stale, it is removed from the derived next-stage queue and
QA access is revoked immediately, while all historical decisions and
resolutions remain visible in audit.

## 9. Stage completion definitions

The backend must expose authoritative completion, not infer it from a single
reviewer's progress card.

### T&A completed

The canonical input is ready and every canonical publication is either:

- single-reviewer: has a latest decision for the requested reviewer; or
- multi-reviewer: has all expected active T&A decisions and derived status
  `AGREEMENT` or current `RESOLVED`.

No publication may be `INCOMPLETE`, `CONFLICT`, or `STALE_RESOLUTION`. An empty
ready canonical input is reported as completed with zero records and an
explicit `no_eligible_publications` detail.

### Full Text completed

T&A must be completed. For every publication whose project-level T&A outcome is
INCLUDE (or legacy single-reviewer T&A INCLUDE):

- single-reviewer: the requested reviewer has a latest Full-Text decision;
- multi-reviewer: every active Full-Text reviewer has a decision and the
  derived Full-Text status is `AGREEMENT` or current `RESOLVED`.

No eligible publication may be incomplete, conflicted, or stale. Zero eligible
publications after a completed T&A stage is a completed empty Full-Text stage,
not a QA bypass.

### Quality Assessment completed

QA configuration is present, Full Text is completed, and every project-level
Full-Text INCLUDE publication has the required QA completion state for the
configured QA execution context. A missing configuration is `not_configured`,
not `completed`.

## 10. Project workflow read model and API

The current `ProjectContext` derives only stages 1–4 plus reviewer-specific T&A
progress, and the current Dashboard hardcodes Full Text as available and QA as
unavailable. Phase 7.9 must add one backend-authoritative project workflow
read model rather than extending client-side calculations.

Recommended endpoint:

```text
GET /projects/{project_id}/workflow-status
```

The response contains:

- project ID and canonical-input readiness;
- `search`, `sources`, `normalization`, `deduplication` states;
- T&A and Full-Text stage state, completed/total/eligible counts;
- unresolved, incomplete, and stale counts by stage;
- current project-level INCLUDE/EXCLUDE/UNCERTAIN counts;
- QA state (`not_configured`, `blocked`, `ready`, `in_progress`, `completed`);
- typed blocking reasons and a deterministic `next_action` route;
- a generated-at timestamp and response schema version.

This endpoint reuses existing sources, deduplication, screening reporting,
7.8B multi-reviewer, and QA services. It is a read model, not a new workflow
database. Existing reviewer-scoped report and audit endpoints remain intact.

API rules:

- all project and stage boundaries are enforced server-side;
- project switching cannot reuse a previous project's response;
- unresolved and stale states are represented explicitly, not as HTTP 404;
- loading/error/readiness details are stable enough for UI and integration tests;
- no per-publication database round trips for list/status endpoints;
- a `GET` is safe to repeat and does not create decisions, resolutions, or QA
  assessments.

## 11. Dashboard integration

`ProjectDashboardPage` should consume the workflow-status read model and render:

- stage cards for T&A, Full Text, and QA with state, counts, and blocking reason;
- conflict/stale badges with counts and a direct route to the relevant conflict
  or adjudication workspace;
- “next action” derived from the same backend response;
- explicit empty, loading, and error states;
- no hardcoded `Dostępne` or `Niedostępne` state for executable stages;
- project-switch request cancellation/version protection.

Dashboard must distinguish:

- screening still in progress;
- screening blocked by conflict or stale resolution;
- screening complete with no eligible next-stage publications;
- Full Text ready;
- QA blocked by screening;
- QA not configured;
- QA ready or complete.

Dashboard cards link to canonical routes and never mutate screening state.

## 12. WorkflowStepper and Sidebar

Extend the existing `WorkflowNavigationStatus` / `useWorkflowNavigationStatus`
single-source pattern rather than adding duplicate calculations to
`WorkflowStepper`, `Sidebar`, and Dashboard.

Required dynamic steps:

1. Search Strategy
2. Sources & Imports
3. Normalization
4. Deduplication
5. Title & Abstract Screening
6. Full-Text Screening
7. Quality Assessment
8. Data Extraction (not started/not available)
9. Exports & PRISMA (not started/not available)

The stepper and sidebar consume state, label, count, and route from the read
model. Conflict and stale counts are alert badges; they are not success
counts. QA must not appear completed merely because a template is configured.

## 13. Routing and navigation

Retain the current project-scoped route family:

```text
/projects/:projectId/screen/title-abstract
/projects/:projectId/screen/full-text
/projects/:projectId/screen/audit
/projects/:projectId/screen/conflicts
/projects/:projectId/screen/conflict-resolution
/projects/:projectId/quality-assessment
/projects/:projectId/quality-assessment/configuration
/projects/:projectId/quality-assessment/:publicationId
```

The QA branch currently uses both a real `quality-assessment` route and a
legacy `qa` route. The integrated app should make `quality-assessment` the
canonical route and keep `/qa` as a redirect for compatibility. Screening
routes remain under `screen`; no 7.9 route should expose Phase 9.

Project switch must reset reviewer-scoped and project-scoped read models and
ignore late responses from the previous project.

## 14. QA readiness and GUI

Merge the real Phase 8 QA page and panels, replacing the current placeholder
page. Wire it to the adapter-backed QA endpoints and retain the existing
configuration and execution flows.

Readiness presentation:

- `NO_QUALITY_ASSESSMENT_CONFIGURATION`: configure a tool/template;
- `WAITING_FOR_SCREENING`: show the stage blocking reason and link to the
  relevant screening or conflict route;
- `NO_ELIGIBLE_PUBLICATIONS`: Full Text completed with no project-level INCLUDE;
- `READY`: show the eligible count and enable execution;
- `IN_PROGRESS`/`COMPLETED`: show QA assessment progress from the existing QA
  service.

The QA GUI uses `useReviewerIdentity()` and retains the existing reviewer
identity persistence semantics. It must not add authentication or QA roster
management.

## 15. Merge strategy evaluation

### A — Phase 7 into development, then Phase 8

This gives screening integration first, but Phase 8 later overlaps
`app/services/project_deletion_service.py`, `frontend/src/App.tsx`, and shared
documentation. It creates a second conflict-resolution pass and temporarily
leaves QA routes absent.

### B — Phase 8 into development, then Phase 7

This preserves the numeric migration order (`0013`, `0014`, then `0015`–`0017`)
and makes QA available first. It still leaves the known four-file overlap and
requires resolving it directly on `development`, which is less reversible.

### C — temporary integration branch (selected)

Use a temporary `integration/phase-7.9` branch from the current `development`
ancestor:

1. merge `feature/quality-assessment` first;
2. merge `feature/screening-7.8b` second;
3. resolve the documented overlaps once, preserving QA cleanup/router/routes
   and 7.8B conflict cleanup/router/routes;
4. run the combined baseline suites;
5. implement 7.9 integration on this branch;
6. run full backend/frontend/E2E gates;
7. merge the reviewed result into `development` only after explicit approval.

Option C is selected because the audit found overlap in
`IMPLEMENTATION_PLAN.md`, `ROADMAP.md`, `app/services/project_deletion_service.py`,
and `frontend/src/App.tsx`, while the branches have no ancestry relationship.
It isolates conflict resolution and keeps both source branches recoverable.

## 16. Migration and schema integration

No 7.9 migration is planned. After the selected merge sequence, the expected
chain is:

```text
0001–0012  existing platform and screening prerequisites
0013       Phase 8 quality assessment
0014       Phase 8 QA configuration
0015       Phase 7.7 screening audit/reporting
0016       Phase 7.8A reviewer assignments
0017       Phase 7.8B conflict resolutions
```

The repository migration runners sort migration filenames and record applied
names in `schema_migrations`. Integration must verify a fresh database and an
upgrade database that already contains `0001`–`0012`, `0013`–`0014`, or
`0015`–`0017`. No renumbering, editing, or new `0018` is allowed in 7.9.

Project hard delete must combine both branches' cleanup in one transaction:
QA assessment/configuration rows, screening decisions, assignments,
resolution rows/links, publications, and other project-scoped data are deleted
before the project row. Project B and global QA catalog data must remain.

## 17. Backend integration test plan

Add a dedicated integration suite, for example
`tests/integration/test_screening_pipeline_integration.py`, using real SQLite
repositories and the actual FastAPI dependency graph.

Required scenarios:

1. single reviewer: canonical input → T&A INCLUDE → Full Text queue → Full Text
   INCLUDE → QA eligible;
2. single reviewer EXCLUDE/UNCERTAIN: no downstream publication and no
   regression to existing reviewer-specific behavior;
3. multi reviewer agreement INCLUDE: project outcome and all active FT queue
   memberships;
4. multi reviewer conflict: T&A and FT queues blocked until explicit resolution;
5. current RESOLVED INCLUDE: all active FT reviewers receive the publication;
6. reviewer decision change after resolution: stale status, queue revocation,
   QA revocation, audit/history retained;
7. roster add/remove: decision-set changes and downstream revocation;
8. multi-reviewer Full Text agreement/resolution INCLUDE: project-level QA
   eligibility;
9. Full Text unresolved/stale/EXCLUDE/UNCERTAIN: QA blocked or empty;
10. QA configuration absent/present and append-only QA assessment behavior;
11. project and stage isolation, missing project/publication, and hard delete;
12. batch/read-model query behavior and no per-publication N+1 access pattern.

The existing Phase 8 unit/integration suite remains a required regression suite;
7.9 tests are additive and do not weaken its contracts.

## 18. Frontend integration test plan

Add `frontend/tests/ScreeningIntegration.test.tsx` using the existing Vitest
and Testing Library setup. Cover:

- project workflow read-model loading, empty, blocked, ready, and error states;
- Dashboard stage cards and next-action links;
- WorkflowStepper and Sidebar state/badge parity;
- T&A INCLUDE enabling Full Text for all active FT reviewers;
- conflict and stale badges linking to the correct workspace;
- QA readiness messages for configuration, blocked screening, empty eligible
  set, ready, in-progress, and completed states;
- canonical `quality-assessment` route and `/qa` compatibility redirect;
- project switch safety and stale-response suppression;
- reviewer identity hook compatibility in QA and screening pages;
- no client-side majority vote or mutation caused by navigation/status reads.

Existing 7.8B conflict-resolution GUI tests, existing 7.5/7.6 screening tests,
and all Phase 8 GUI tests must remain green.

## 19. E2E plan

The repository currently has no committed Playwright/Cypress harness. Add the
chosen browser test harness only as a 7.9 test dependency, after reviewing its
CI/runtime implications. Playwright is preferred for deterministic browser
navigation and network interception.

The minimum browser scenario is:

1. create a project and import a small fixture;
2. complete deduplication and configure criteria;
3. run two T&A reviewer identities with disagreeing outcomes;
4. verify conflict queue and Full-Text blocking;
5. resolve explicitly as INCLUDE with resolver and rationale;
6. verify both active Full-Text reviewers see the publication;
7. complete Full Text as required and verify project-level QA readiness;
8. configure QA, open the included publication, submit required responses;
9. change a source decision, verify stale revocation and reload warning;
10. switch projects and verify no data/state leakage.

The E2E environment must use a disposable SQLite database and fixture data; it
must not call external bibliographic providers.

## 20. Performance and consistency requirements

- Derive project outcomes in batch for status, dashboard, and queue endpoints.
- Reuse 7.8B batch latest-decision/latest-resolution queries.
- Do not call one outcome query per publication from a list endpoint.
- Keep project status response bounded to aggregate counts plus a bounded list of
  blocking reasons/publication IDs, with pagination for detailed queues.
- Use request-version or cancellation guards for project and stage switching.
- Re-check eligibility server-side at every decision/assessment write.
- Verify fresh and upgraded SQLite databases, including migration idempotence.

## 21. Documentation reconciliation after implementation

Only after code and tests are complete:

- `ROADMAP.md`: mark 7.9 completed and Phase 7 completed; leave Phase 8 status
  truthful and mark Phase 9 next only if the roadmap workflow requires it;
- `IMPLEMENTATION_PLAN.md`: record 7.9 completion and the selected integration
  strategy;
- `PROJECT_STATUS.md`: reconcile branch/status/version with actual merged state;
- `docs/ARCHITECTURE.md`: document the project-level transition boundary;
- `docs/DECISIONS.md`: record the approved project-outcome transition decision;
- preserve the 7.8B source-of-truth document once restored/committed; do not
  silently recreate or alter it during implementation without review.

Documentation updates are not part of this architecture-only task.

## 22. Release boundary

7.9 implementation ends at a tested, reviewable integration branch. It does
not itself authorize merge, VERSION modification, tag, or release.

- Release boundary: next release version — to be determined during final release review.
- Current `VERSION` remains `0.3.3` until full E2E, integration, and final release review are completed.
- Release verification must include:
  - explicit version decision;
  - full backend and frontend gates;
  - migration upgrade/fresh-database checks;
  - manual acceptance checklist;
  - release notes and documentation consistency;
  - confirmation that Phase 9/Data Extraction was not started.

## 23. Manual acceptance checklist

- [ ] create project, import fixture, normalize, and complete deduplication;
- [ ] single reviewer T&A INCLUDE appears in that reviewer's Full-Text queue;
- [ ] single reviewer Full-Text INCLUDE becomes QA eligible;
- [ ] single reviewer EXCLUDE/UNCERTAIN does not create downstream eligibility;
- [ ] configure active T&A and Full-Text rosters;
- [ ] agreement INCLUDE gives project-level T&A INCLUDE;
- [ ] all active FT reviewers receive an adjudicated T&A INCLUDE, even if one
      previously voted EXCLUDE at T&A;
- [ ] unresolved conflict blocks Full Text;
- [ ] current resolution INCLUDE unblocks Full Text;
- [ ] decision change makes resolution stale and revokes downstream access;
- [ ] re-resolution restores access only after a fresh expected key;
- [ ] Full-Text agreement/resolution INCLUDE enables QA at project level;
- [ ] Full-Text conflict/stale/EXCLUDE/UNCERTAIN blocks or yields no QA records;
- [ ] QA config, assessment save, history, and readiness messages work;
- [ ] Dashboard, Stepper, Sidebar, and routes agree without refresh-only drift;
- [ ] project switch has no stale data leakage;
- [ ] hard delete removes project-scoped screening/QA data and preserves another
      project and global QA catalog data.

## 24. 7.9 delivery increments

Splitting 7.9 is justified by the audit's real boundary between backend
eligibility/QA integration and cross-cutting UI/release integration:

### 7.9A — Screening-to-QA integration contract

- merge Phase 8 and 7.8B on the temporary integration branch;
- implement the screening eligibility adapter;
- update Full-Text eligibility and all-active-reviewer queue hydration;
- update QA eligibility seam and readiness error mapping;
- combine hard-delete cleanup;
- add backend integration and contract tests.

### 7.9B — Workflow surfaces and release verification

- add project workflow-status read model/API;
- wire Dashboard, WorkflowStepper, Sidebar, QA GUI, and canonical routes;
- add frontend integration tests and browser E2E;
- run performance, migration, documentation, and manual acceptance gates;
- prepare a reviewable release candidate without changing VERSION until
  explicitly authorized.

This is sequencing, not a new product scope or a new domain boundary.

## 25. Files expected to change during implementation

Backend integration candidates:

- `app/services/full_text_screening_service.py`;
- a new thin screening eligibility/workflow read-model service;
- `app/services/quality_assessment_execution_service.py` after Phase 8 merge;
- corresponding DTO/router and project deletion composition;
- integration and contract tests.

Frontend integration candidates:

- `frontend/src/context/ProjectContext.tsx` and `frontend/src/types/index.ts`;
- `ProjectDashboardPage.tsx`, `WorkflowStepper.tsx`, `Sidebar.tsx`;
- the Phase 8 `QualityAssessmentPage` and its API client;
- `useReviewerIdentity()` adoption in QA;
- route compatibility and integration tests.

No migration file is expected for 7.9.

## 26. Risk register and mitigations

| Risk | Mitigation |
|---|---|
| Reviewer-specific logic accidentally remains in multi FT eligibility | Adapter contract tests with prior T&A EXCLUDE reviewer |
| Single-reviewer behavior changes | Explicit no-roster branch tests using multiple free-text IDs |
| Stale resolution bypasses a gate | Every queue/readiness/write path recomputes current 7.8B outcome |
| QA domain is rebuilt or forked | Adapter only; preserve QA models, repositories, and migrations |
| Phase 8/7.8B merge conflict loses cleanup | Temporary branch and combined project-delete test |
| Dashboard calculates different state than backend | One workflow-status endpoint and one frontend status consumer |
| N+1 status queries | Batch outcome/readiness queries and aggregate response |
| Route drift between branches | Canonical `quality-assessment` route plus `/qa` redirect |
| Browser E2E depends on external providers | Disposable local fixture and provider-free setup |
| Release accidentally starts Phase 9 | Explicit route/status boundary and review checklist |

## 27. Definition of Done — Phase 7.9

1. Single-reviewer T&A and Full-Text behavior is backward compatible without a
   roster.
2. Multi-reviewer T&A eligibility uses the 7.8B project-level outcome.
3. Project-level T&A INCLUDE hydrates all active Full-Text reviewers.
4. Multi-reviewer Full-Text eligibility for QA uses the project-level outcome.
5. Incomplete, unresolved, and stale states block downstream access and stale
   changes revoke access immediately.
6. Agreement/resolution INCLUDE, EXCLUDE, and UNCERTAIN semantics are distinct
   and tested.
7. QA domain and persistence remain unchanged; the adapter is the sole bridge.
8. Dashboard, WorkflowStepper, Sidebar, routing, and QA readiness consume one
   backend-authoritative workflow read model.
9. Project and stage isolation, hard delete, migration upgrade, and no-N+1
   behavior are covered by tests.
10. Backend integration, frontend integration, Phase 8 regression, and browser
    E2E suites pass.
11. Manual acceptance checklist passes.
12. Documentation is reconciled only after implementation; no VERSION bump,
    merge, tag, release, or Phase 9 work occurs without explicit approval.

## 28. Definition of Done — Phase 7 boundary

Phase 7 may be marked complete only after 7.9's integration gates pass:

- configurable criteria, append-only decisions, Full-Text screening,
  multi-reviewer conflict/resolution, project-level transitions, and audit are
  all reachable through the project workflow;
- Quality Assessment entry is project-level correct while its domain remains
  independently durable;
- Dashboard and navigation show authoritative live stage states;
- single-reviewer compatibility and multi-reviewer adjudication are both
  demonstrated end-to-end;
- no Data Extraction, Phase 9, or unrelated release scope was started.

## 29. Required final questions (A–H)

### A. Do single-reviewer projects continue to work without a roster?

Yes. The adapter must preserve the current reviewer-specific latest-decision
paths whenever the relevant active roster is empty. This explicit branch is
required because the current generic 7.8B fallback is not sufficient for an
arbitrary set of free-text reviewer IDs.

### B. Does multi-reviewer T&A transition use project-level outcome?

Yes. With an active T&A roster, only `AGREEMENT` or current `RESOLVED` project
outcomes are authoritative, and only project-level INCLUDE creates Full-Text
eligibility.

### C. Does unresolved or stale conflict block the next stage?

Yes. `INCOMPLETE`, unresolved `CONFLICT`, and `STALE_RESOLUTION` have no
authoritative outcome and block. A decision-set change revokes derived access
without deleting history.

### D. Do all active next-stage reviewers receive project-level INCLUDE?

Yes for the Full-Text roster. Every active `FULL_TEXT` reviewer receives the
publication after project-level T&A INCLUDE, independently of their earlier T&A
vote. No queue-membership persistence is introduced.

### E. Does multi-reviewer Full Text → QA use project-level outcome?

Yes. With an active Full-Text roster, project-level Full-Text AGREEMENT or
current RESOLVED INCLUDE supplies QA eligibility. QA assessment records remain
reviewer-attributed and append-only under the existing Phase 8 model.

### F. Does the QA domain remain untouched?

Yes. The integration changes only the eligibility/readiness seam and retains
QA domain objects, repository contracts, templates, response values, and
migrations.

### G. Can 7.9 be completed without new persistence tables?

Yes. The plan uses derived read models and the existing `0001`–`0017` chain.
No 7.9 migration is planned.

### H. Is Phase 7 complete after this plan is implemented?

Only after the Phase 7.9 Definition of Done, backend/frontend/E2E gates,
manual acceptance, migration verification, and documentation reconciliation
pass. This architecture document alone does not mark Phase 7 complete.

---

**PHASE 7.9 ARCHITECTURE READY FOR REVIEW**

This document is a plan only. No implementation, migration, VERSION change,
commit, push, merge, release, or Phase 9 work is authorized by it.
