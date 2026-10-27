# import-warning-resolution Specification

## Purpose

Define how reviewers inspect warning imports, explicitly accept or reject them,
and how the system protects publications, research decisions, PRISMA accounting,
and audit history when a rejected import leaves active use.

## Requirements

### Requirement: Warning import decision workflow

The import history SHALL offer an explicit decision workflow for each warning
import and SHALL identify the affected import, its persisted warnings, and the
available decisions.

#### Scenario: Reviewer opens a warning

- **WHEN** a reviewer activates the warning label for an import
- **THEN** the system displays the import identity, source file or provider, import date, imported and skipped counts, warning details, and the `Akceptuję` and `Odrzucam` decisions

#### Scenario: Successful import has no warning decision

- **WHEN** an import completed without warnings
- **THEN** the system does not require an accept or reject decision for it

### Requirement: Acceptance records a non-destructive decision

Accepting a warning SHALL record a durable decision and SHALL change only the
import's effective display status to `Zaimportowano`.

#### Scenario: Warning is accepted

- **WHEN** a reviewer selects `Akceptuję` for a warning import
- **THEN** the system records the decision, reviewer identity, timestamp, and warning snapshot
- **AND** the import displays the effective status `Zaimportowano`
- **AND** the original warning status and warnings remain available in audit history

#### Scenario: Acceptance preserves research state

- **WHEN** a warning import is accepted
- **THEN** its imported publications, duplicate-review decisions, screening decisions, quality assessments, extraction records, synthesis records, and PRISMA stage populations remain unchanged

#### Scenario: Acceptance is terminal

- **WHEN** an import has already been accepted
- **THEN** another accept request returns the existing decision without duplicate audit rows
- **AND** a later reject request is refused as a conflicting decision

### Requirement: Rejection requires explicit confirmation

Rejecting an import SHALL require a confirmation dialog in the user interface
and an explicit confirmation flag in the rejection request.

#### Scenario: Reviewer cancels the confirmation

- **WHEN** a reviewer opens the rejection confirmation and selects `Anuluj`
- **THEN** no decision is recorded and no import data is removed

#### Scenario: Reviewer confirms rejection

- **WHEN** a reviewer selects `Potwierdź odrzucenie` in the confirmation dialog
- **THEN** the system submits an explicitly confirmed rejection request
- **AND** the request does not proceed unless the confirmation flag is present

### Requirement: Rejection validates publication ownership

Rejection SHALL proceed only when every publication to be removed is owned
solely by the selected import and no other import references it.

#### Scenario: Publication is shared with another import

- **WHEN** a canonical publication from the selected import is referenced by a source record from another import
- **THEN** rejection is blocked
- **AND** the response explains that the publication is shared and identifies the blocker count without exposing another project's data

#### Scenario: Publication is owned only by the selected import

- **WHEN** every affected canonical publication is owned and referenced only by the selected import
- **THEN** ownership validation passes for those publications

#### Scenario: Historical ownership is unverifiable

- **WHEN** an import reports records but has no authoritative publication ownership evidence
- **THEN** destructive rejection is blocked with an explanation that the import cannot be safely removed

### Requirement: Rejection protects downstream research decisions

Rejection SHALL be blocked when an affected publication is part of a duplicate
merge, has a duplicate review decision, or is referenced by a downstream
research record.

#### Scenario: Publication belongs to a duplicate merge

- **WHEN** an affected publication is a canonical or member record of a persisted duplicate merge or supersession chain
- **THEN** rejection is blocked and the response identifies the merge conflict

#### Scenario: Publication has a duplicate review decision

- **WHEN** an affected publication belongs to a duplicate group with a recorded human decision
- **THEN** rejection is blocked and the response identifies the existing duplicate decision

#### Scenario: Publication has downstream research records

- **WHEN** an affected publication has a pre-screening decision or archive entry, corpus finalization membership, screening decision, full-text availability record, quality assessment, extraction record, or synthesis record
- **THEN** rejection is blocked and the response identifies each blocking category with counts

#### Scenario: Blocker explanation is actionable

- **WHEN** rejection is blocked
- **THEN** the UI displays a clear explanation that the import was not changed and that dependent research decisions must be resolved separately
- **AND** the destructive action is not presented as successful

### Requirement: Rejection is atomic and idempotent

Rejection SHALL remove active import data and record its decision in one
transaction, and any failure SHALL leave all state unchanged.

#### Scenario: All validation passes

- **WHEN** rejection passes ownership and downstream checks
- **THEN** the transaction removes only the safe import-owned publications, records the rejection decision, invalidates affected derived state, and commits once

#### Scenario: Transaction fails

- **WHEN** any write or decision record fails during rejection
- **THEN** every publication deletion, derived-state change, and decision write is rolled back
- **AND** the import remains active and unchanged

#### Scenario: Rejection is repeated

- **WHEN** an import has already been rejected
- **THEN** repeating the same rejection returns the existing decision without additional deletion or audit rows

### Requirement: Rejected imports retain non-active audit

Rejected imports SHALL remain queryable as non-active audit, and their source
records, skip audit, original warnings, and rejection decision SHALL NOT be
deleted.

#### Scenario: Rejection succeeds

- **WHEN** an import is rejected
- **THEN** its import-history row, source records, skip-audit rows, warning snapshot, reviewer identity, timestamp, affected publication identifiers, and rejection decision remain available to audit
- **AND** its canonical publications are removed from the active project corpus

#### Scenario: Audit view includes rejected imports

- **WHEN** a reviewer requests import history with rejected imports included
- **THEN** the rejected import is shown with its rejection status and decision details
- **AND** it is not counted as an active import

### Requirement: Rejected imports leave active populations

Rejected imports SHALL be excluded from active import history, the active
corpus, screening, extraction, synthesis, and export populations.

#### Scenario: Sources view after rejection

- **WHEN** rejection succeeds
- **THEN** the active import list, source summaries, working-collection count, and warning counters are refreshed without the rejected import
- **AND** other imports and their publications remain unchanged

#### Scenario: Downstream views after rejection

- **WHEN** screening, extraction, synthesis, or exports read the project after rejection
- **THEN** no publication from the rejected import appears in those active populations

### Requirement: Rejected imports remain in PRISMA identification history

Rejected source records SHALL remain in PRISMA identification history and SHALL
be reported separately as `removed before screening — rejected import`.

#### Scenario: PRISMA metrics after rejection

- **WHEN** PRISMA metrics are calculated after a rejection
- **THEN** identified source records still include the rejected import's source records
- **AND** the rejected records are reported in a distinct removal category labelled `removed before screening — rejected import`
- **AND** the active corpus and all later PRISMA screening stages exclude those records

#### Scenario: PRISMA counts reconcile

- **WHEN** rejected-import removals are added to the other pre-screening removals
- **THEN** the identified, removed, canonical, screened, and included counts reconcile without double counting

### Requirement: Import review API errors are explicit

The import review API SHALL return explicit outcomes for missing imports,
invalid decisions, conflicting decisions, and blocked rejection.

#### Scenario: Import does not exist

- **WHEN** a review request names an import that does not exist in the project
- **THEN** the API returns a not-found response

#### Scenario: Rejection is blocked

- **WHEN** a confirmed rejection fails ownership or downstream validation
- **THEN** the API returns a conflict response containing machine-readable blocker codes and human-readable explanations
- **AND** no research data is modified

#### Scenario: Decision conflicts with an existing decision

- **WHEN** a request attempts to change an accepted import to rejected or a rejected import to accepted
- **THEN** the API returns a conflict response and preserves the existing decision

### Requirement: Import review is project-scoped and attributed

Every import review action SHALL be scoped to one project and SHALL record a
non-blank reviewer identity.

#### Scenario: Cross-project import identifier

- **WHEN** a reviewer submits an import identifier that belongs to another project
- **THEN** the request is treated as not found and no project data is exposed or changed

#### Scenario: Reviewer identity is missing

- **WHEN** a review request omits a reviewer identity or supplies only whitespace
- **THEN** the request is rejected as invalid and no decision is recorded

### Requirement: Existing import contracts remain compatible

Import history and source-record contracts SHALL remain backward compatible
while exposing review state and effective status.

#### Scenario: Existing client reads import history

- **WHEN** an existing client requests import history
- **THEN** previously available fields and endpoints remain present
- **AND** active responses may add review and effective-status fields without renaming or removing existing fields

#### Scenario: Accepted warning status is backward compatible

- **WHEN** an accepted warning import is read through an existing status field
- **THEN** the original warning remains available for traceability
- **AND** the effective status used for active workflow presentation is `Zaimportowano`
