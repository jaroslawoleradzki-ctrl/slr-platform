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

### Requirement: Duplicate group reads do not mutate project state

The duplicate-groups read operation SHALL return groups and readiness from persisted project state without writing source-record metadata, reviewer decisions, merge records, or candidate-group snapshots.

#### Scenario: Read groups with candidates

- **WHEN** a client reads duplicate groups for a project with candidate groups
- **THEN** the response is derived from the active corpus, persisted reviewer decisions, and persisted merges
- **AND** source-record values and audit/history rows remain unchanged by the read

### Requirement: Candidate group metadata follows publication-set mutations atomically

The system SHALL refresh source-record candidate group IDs and materialize newly observed group membership snapshots at the same transaction boundary as each operation that changes active duplicate-group inputs.

#### Scenario: A publication-set mutation changes candidate groups

- **WHEN** an import, import rejection, pre-screening removal or restoration, merge, or normalization changes the active corpus or duplicate matching inputs
- **THEN** the existing deduplication algorithm produces the same deterministic groups
- **AND** source-record candidate group IDs and immutable group snapshots reflect that committed group set before the operation succeeds

#### Scenario: Projection or snapshot update fails

- **WHEN** group metadata or snapshot persistence fails while a publication-set mutation is in progress
- **THEN** the publication-set mutation, group metadata update, and snapshot write are rolled back together
- **AND** no partial publication or candidate-group projection is committed

#### Scenario: Normalization fails after updating an active publication

- **WHEN** normalization or group materialization fails after one or more active publications have been processed
- **THEN** normalized publication rows, the normalization execution summary, candidate group IDs, and snapshots are committed together or rolled back together
- **AND** no reviewer decision is remapped, rewritten, or deleted by normalization projection materialization

#### Scenario: A mutation cannot share a safe transaction

- **WHEN** a publication-set mutation cannot safely include group metadata and snapshot materialization in its transaction
- **THEN** the system does not commit a stale or partially refreshed projection as if the operation succeeded
- **AND** implementation stops for an explicit architectural resolution

### Requirement: Group snapshots remain immutable membership observations

Candidate-group snapshots SHALL preserve their existing schema, uniqueness, first-write immutability, and membership/status observation fields; existing snapshots and reviewer-decision history SHALL NOT be rewritten or backfilled by this change.

#### Scenario: A group membership is materialized

- **WHEN** a publication-set mutation produces a candidate group
- **THEN** the immutable snapshot records the same group ID, sorted member IDs, match metadata, status, and observation time fields as the current snapshot contract
- **AND** a later read or mutation does not overwrite an existing snapshot for the same project, group, and membership

#### Scenario: Historical membership protects an import-review decision

- **WHEN** the current corpus no longer reconstructs a prior decided group but an immutable membership snapshot and persisted reviewer decision exist
- **THEN** import-review safety checks use the snapshot membership together with the persisted decision
- **AND** a first-observation `PENDING` snapshot does not erase or override that decision
- **AND** the reviewer decision and snapshot rows remain unchanged

### Requirement: First duplicate-page load exposes the actual request state

The deduplication interface SHALL initiate and present the backend result for the selected project on its first page load, with loading, success, and failure states that do not report stale data as current.

#### Scenario: First request succeeds

- **WHEN** a user opens deduplication for a project and its first duplicate-groups request succeeds
- **THEN** the interface displays the response groups and readiness without requiring a browser refresh

#### Scenario: First request fails

- **WHEN** the first duplicate-groups request fails or exceeds the configured client wait
- **THEN** the interface presents a recoverable error state distinct from loading and success
- **AND** it does not present the failure as an empty or completed duplicate result

### Requirement: Duplicate endpoint performance is observable

The system SHALL measure duplicate-groups request latency and outcome at the backend and measure first-visible-result/render latency in the client without recording publication content or identifiers.

#### Scenario: Runtime diagnostics are collected

- **WHEN** duplicate-groups requests and deduplication page loads are observed over a measurement interval
- **THEN** diagnostics provide p50, p95, and p99 response latency, first-load latency, timeout count, HTTP 5xx count, and UI render latency
- **AND** diagnostics identify request stages sufficiently to distinguish database reads, group computation, serialization, and response delivery
- **AND** diagnostics contain no titles, DOI values, publication identifiers, or other research content
