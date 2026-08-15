# SLR Platform — Data Extraction v0.4.9 Handoff

## Current release state

- Production/main version: **0.4.9**.
- Package A — Extraction Correctness Foundation — is integrated and deployed.
- Package A commit: `19856a644478bd60a3180a99c5f8459bdf4d860b`.
- `development`: `a6c6c89e71d5dbc6dffae61c9ce40941bab3fcbe`.
- `main`: `e9b7915b873bd101da4b0eb1a345cc99b312c87b`.
- `origin/main` and `homelab/main` match `main`.
- Portainer deploys `main`.
- Phase 10 remains isolated and untouched.

## Package A verified results

The independent final re-review passed. Verified behavior includes:

- ADR-0007 extraction field-state contract and persisted `UNASSESSED` state;
- nullable origin and server-authoritative Draft/Complete validation;
- exact revision-1 DTO/read-model → revision-2 save;
- service-owned fresh `value_id` generation;
- durable `group_item_id` across revisions;
- atomic first submission and rollback of failed later revisions;
- migration 0023 safety;
- narrow legacy v0.4.8 hydration compatibility;
- `unit_value` not counting as evidence by itself;
- provenance restrictions, `allowed_statuses`, and empty origin → `null`.

Quality gates before release:

- backend: 1315 passed;
- frontend: 220 passed;
- Ruff: PASS;
- mypy: PASS;
- frontend type-check: PASS;
- production build: PASS;
- `git diff --check`: PASS.

## Current production extraction state

Project: **test 2**.

After explicit configuration with **Lean Energy Data Extraction 1.0.0**:

- 20 project publications are visible;
- 4 are eligible for Data Extraction;
- remaining publications stay blocked by existing screening/QA gates.

This eligibility behavior is working correctly.

## Known UX gaps

Low-contrast controls are easy to miss:

- `Skonfiguruj ekstrakcję danych`;
- `Zapisz konfigurację`;
- `Zmień szablon`;
- `+ Proweniencja`.

These are UX defects, not Package A correctness blockers. Template creation,
editing, version cloning, and publishing UI are still missing and belong to a
separate future task; do not auto-assign `lean_energy`.

The extraction workspace primarily identifies publications by internal UUID,
for example `33f636f1-6ea2-5c98-95d3-f05b1022f761`. Future UX should prefer
existing title/authors/year/DOI metadata where available. The form is long;
the E4–E11 repeating-group structure itself is correct and supports multiple
Lean–Energy relations through separate group items.

## Current unresolved validation UX issue

After deploying v0.4.9, an existing publication extraction showed the generic
message:

> Walidacja nie powiodła się. Popraw błędy w formularzu.

The visible state included, for example, E2 = `PRESENT` + `REPORTED` with an
empty value. That state is invalid under ADR-0007 because `PRESENT` requires a
value. Therefore COMPLETE rejection may be correct, and DRAFT rejection may
also be correct when the form contains structurally invalid states. The UI
currently does not identify the invalid field or reason.

It is not yet proven whether this was a fresh v0.4.9 extraction or persisted
pre-Package-A state. A fresh untouched form must initialize fields as
`UNASSESSED`, not `NOT_REPORTED` or `PRESENT`.

## First checks for the next session

Before changing code:

1. Select another eligible publication that has never started extraction.
2. Open the extraction form without editing it.
3. Verify E2/E3/etc. initially show `UNASSESSED`.
4. Click `Zapisz Szkic`; it should save an `IN_PROGRESS` draft.
5. On a fresh untouched form click `Oznacz jako Zakończone`; it should reject
   completion because required fields remain `UNASSESSED`.

If untouched DRAFT fails, classify it as a real Package A/P1 regression. If
DRAFT works and only invalid edited states fail, implement validation UX:
field-level errors such as `E2: status PRESENT requires a value`, invalid
control highlighting, focus/scroll to the first error, preserved form data,
and a clear distinction between Draft structural validation and Complete
validation.

## Phase 10 boundary

Phase 10 remains separate: 10.1, 10.2, and 10.3 are complete, while 10.4 is
active in its isolated worktree. Do not merge Phase 10 until the full phase is
complete. Any later compatibility review should account for `UNASSESSED`,
nullable origin, and COMPLETE-only synthesis inputs; no Phase 10 code has been
modified here.

## Immediate priorities

1. Verify fresh untouched DRAFT behavior.
2. Verify fresh untouched COMPLETE rejection.
3. Classify the observed failure as legacy persisted state, initialization
   regression, Draft backend regression, or missing field-level feedback.
4. Fix correctness issues before UX improvements.
5. After the manual workflow is stable, address template-editor and automation
   ideas separately.

## End-to-end manual target

Prove:

`eligible publication → fresh UNASSESSED form → incomplete DRAFT → reopen →
edit E2–E14 → add multiple E4–E11 relations → revision 2 → history → specific
invalid COMPLETE errors → valid COMPLETE → updated table status → next
publication`.
