# deduplication-screening-consistency Specification

## Purpose

Define one authoritative duplicate-readiness model so deduplication, screening,
workflow status, and PRISMA report the same duplicate state for the same active
research corpus.

## Requirements

### Requirement: Duplicate readiness has one authoritative source

Deduplication completion and screening readiness SHALL be derived from the same
duplicate-readiness projection.

#### Scenario: Workflow reads duplicate state

- **WHEN** deduplication, workflow status, screening readiness, or PRISMA reports duplicate state for a project
- **THEN** each view uses the same candidate groups, reviewer decisions, and persisted merges
- **AND** pending, approved-unmerged, merged, and rejected counts agree across those views

#### Scenario: Readiness is recalculated

- **WHEN** an import, duplicate decision, merge, pre-screening removal, or corpus finalization changes the active corpus
- **THEN** duplicate readiness is recalculated from persisted state rather than reused from stale client counts

### Requirement: Duplicate groups use the active canonical corpus

Candidate duplicate groups SHALL be constructed only from active canonical
publications.

#### Scenario: Superseded records are excluded

- **WHEN** a publication has been superseded by a duplicate merge
- **THEN** it does not participate in new candidate groups
- **AND** it cannot create a different screening group identifier after a later import

#### Scenario: Removed records are excluded

- **WHEN** a publication was removed during pre-screening or physically archived
- **THEN** it does not participate in duplicate readiness or screening input groups

#### Scenario: Historical merge remains visible

- **WHEN** a merge group no longer has multiple active members
- **THEN** its merge record remains available as audit history
- **AND** it does not block screening as an unresolved group

### Requirement: Pending groups block deduplication and screening

A candidate group without a human duplicate decision SHALL block both
deduplication completion and screening readiness.

#### Scenario: Pending group is present

- **WHEN** at least one active candidate group has no decision
- **THEN** deduplication is reported as pending review with the same group count shown by screening
- **AND** screening reports `unresolved_duplicates`
- **AND** screening decisions cannot be recorded for the blocked input set

### Requirement: Approved groups require a persisted merge

An approved duplicate group without a persisted merge SHALL block
deduplication completion and screening readiness.

#### Scenario: Group is approved but unmerged

- **WHEN** a group has an APPROVE decision and no persisted merge
- **THEN** deduplication is reported as `merge_required`, not completed
- **AND** screening reports `unmerged_duplicates`
- **AND** the UI explains that the approved group must be merged

#### Scenario: Approved group is merged

- **WHEN** the approved group has a persisted merge
- **THEN** the group no longer blocks screening
- **AND** the merge remains visible as audit history

### Requirement: Rejected groups do not block screening

A group with a recorded REJECT decision SHALL satisfy duplicate review without
requiring a merge.

#### Scenario: Group is rejected

- **WHEN** every active group has a REJECT decision or a completed merge
- **THEN** deduplication is reported as completed
- **AND** screening readiness is `ready` when no other blocker exists
- **AND** all rejected publications remain separate active canonical records

### Requirement: Dynamic groups remain consistent after imports

A later import that changes duplicate-group membership SHALL produce the same
pending state in deduplication and screening.

#### Scenario: Merge followed by a new matching import

- **WHEN** a group is merged and a later import adds an active publication sharing its strong identifier
- **THEN** deduplication shows one new pending group containing only the active canonical and the new publication
- **AND** screening reports the same unresolved group
- **AND** the earlier merge and decision remain historical audit without blocking screening

#### Scenario: Decision is recorded for the new group

- **WHEN** the new active group receives a decision and, if approved, a persisted merge
- **THEN** deduplication and screening both become consistent and unblocked
- **AND** no superseded member creates a phantom group

### Requirement: Screening explains the exact duplicate blocker

Screening readiness SHALL distinguish pending review from approved-unmerged
duplicates and SHALL not replace either with a generic conflict message.

#### Scenario: Screening is blocked by pending review

- **WHEN** screening readiness is `unresolved_duplicates`
- **THEN** the screening page states that duplicate groups require decisions
- **AND** it displays the blocking group count and a route to deduplication

#### Scenario: Screening is blocked by an unmerged approval

- **WHEN** screening readiness is `unmerged_duplicates`
- **THEN** the screening page states that approved duplicate groups require merging
- **AND** it displays the blocking group count and a route to deduplication
- **AND** it does not describe the condition as a metadata or canonical-input conflict

### Requirement: UI deduplication status follows backend readiness

The user interface SHALL present deduplication state from the authoritative
readiness projection and SHALL NOT report completion while screening is blocked
by duplicate work.

#### Scenario: Pending groups exist

- **WHEN** duplicate readiness is pending review
- **THEN** the deduplication stage shows the pending count and is not marked completed
- **AND** the same count appears in the screening workflow feedback

#### Scenario: Approved groups need merging

- **WHEN** duplicate readiness is approved-unmerged
- **THEN** the deduplication stage shows a merge-required state and is not marked completed
- **AND** the user is directed to the groups that need merging

#### Scenario: Optimistic decision update

- **WHEN** a reviewer records or changes a duplicate decision or completes a merge
- **THEN** the displayed deduplication and screening state is refreshed from backend state
- **AND** a failed request does not leave the stage marked completed

### Requirement: PRISMA reflects the same duplicate readiness

PRISMA duplicate-group reporting SHALL use the same readiness projection as
deduplication and screening.

#### Scenario: PRISMA reports duplicate blockers

- **WHEN** PRISMA metrics report pending duplicate groups
- **THEN** the pending count equals the count blocking screening
- **AND** approved-unmerged groups are reported separately from pending-review groups

#### Scenario: PRISMA after merge and later import

- **WHEN** a merged group is followed by a new matching import
- **THEN** PRISMA reports the new pending group
- **AND** it does not report the historical merge as an unresolved group

### Requirement: Duplicate readiness contracts remain compatible

Existing duplicate-review and workflow response contracts SHALL remain
backward compatible while adding readiness information.

#### Scenario: Existing duplicate client

- **WHEN** an existing client reads duplicate groups or workflow status
- **THEN** existing fields and endpoints remain present
- **AND** readiness information is additive

#### Scenario: No candidates

- **WHEN** the active corpus has no candidate duplicate groups
- **THEN** deduplication is completed and screening duplicate readiness is `ready`
- **AND** no transaction or research record is created merely by reading readiness
