# Spec Delta

## ADDED Requirements

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
