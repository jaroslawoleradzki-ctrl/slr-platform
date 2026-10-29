# Spec Delta

## Purpose

Defines how project workflow status is computed, refreshed after import-review
decisions, loaded incrementally, and optimized only where measurements show a
real bottleneck, without changing research data or PRISMA semantics.

## ADDED Requirements

### Requirement: Import review decision updates shared workflow status

When an import review decision is committed, the shared workflow status used by
the sidebar and dashboard SHALL reflect the new effective status without
waiting for a full status refresh to complete.

#### Scenario: Accept decision updates workflow status

- **WHEN** a warning import is accepted
- **THEN** the shared workflow status no longer treats that import as a warning
- **AND** the update happens before the full status refresh completes

#### Scenario: Reject decision updates workflow status

- **WHEN** a warning import is rejected
- **THEN** the shared workflow status reflects the resulting effective status
- **AND** the update happens before the full status refresh completes

### Requirement: Import review decision updates source-summary counters

When an import review decision is committed, the source-summary counters derived
from the import's effective status SHALL update to match the decision.

#### Scenario: Source counters after acceptance

- **WHEN** a warning import is accepted
- **THEN** the source's successful-import count increases by one
- **AND** the source's warning-import count decreases by one

#### Scenario: Source counters after rejection

- **WHEN** a warning import is rejected
- **THEN** the source-summary counters reflect the resulting effective status

### Requirement: Sources stage completes when no warnings remain

The Sources stage SHALL report `completed` only when no import has an effective
status of `warning`. Accepting or rejecting imports SHALL NOT change the
import count.

#### Scenario: Last warning resolved

- **WHEN** the final warning import is accepted or rejected
- **THEN** the Sources stage transitions to `completed`
- **AND** the import count remains unchanged

#### Scenario: Warnings remain

- **WHEN** at least one import still has an effective status of `warning`
- **THEN** the Sources stage remains `warning`
- **AND** the import count remains unchanged

### Requirement: Workflow status refresh is incremental

The system SHALL update the workflow status as each status endpoint resolves,
rather than waiting for all endpoints to complete.

#### Scenario: Slow endpoint does not block ready stages

- **WHEN** one status endpoint is slower than the others
- **THEN** stages whose endpoints have already resolved display their status
- **AND** the UI does not wait for the slowest endpoint before showing them

### Requirement: Status endpoints have bounded wait times

Each status endpoint SHALL be subject to a timeout, and a timed-out or failed
endpoint SHALL yield partial results instead of blocking the whole refresh.

#### Scenario: Endpoint times out

- **WHEN** a status endpoint does not respond within the configured timeout
- **THEN** the refresh continues with the remaining endpoints
- **AND** the affected stage shows an error or pending state

### Requirement: Progressive loading indicator

The UI SHALL show loading state per stage instead of a single global message
while workflow status is being loaded.

#### Scenario: Partial loading display

- **WHEN** workflow status is loading
- **THEN** ready stages display their status
- **AND** loading stages display a per-stage loading indicator

### Requirement: Heavy read models are memoized

Repeated navigation SHALL reuse in-flight or recently completed results for
heavy read models instead of issuing duplicate requests.

#### Scenario: Repeated navigation reuses result

- **WHEN** the user navigates away and back within the memoization window
- **THEN** no duplicate request is issued for the heavy read model
- **AND** the displayed status remains consistent

### Requirement: Research data is unchanged by status refresh

Status refresh, decision propagation, and performance optimization SHALL NOT
modify research data, PRISMA populations, working collection, canonical
publications, source records, or deduplication decisions.

#### Scenario: Non-destructive refresh

- **WHEN** workflow status is refreshed or an import is accepted or rejected
- **THEN** working collection count, canonical publication count, source record
  count, and PRISMA populations remain unchanged

### Requirement: Backend optimization is measurement-gated

Performance optimizations to backend hot paths SHALL be applied only where
measurements confirm a bottleneck, and SHALL preserve API contracts and
counting semantics.

#### Scenario: Optimization preserves contracts

- **WHEN** a backend hot path is optimized
- **THEN** its API response shape and values remain unchanged
- **AND** its counting semantics remain unchanged

### Requirement: Integration tests use a real backend

The change SHALL include integration tests that exercise the status refresh and
decision propagation flow against a real backend, not only mocked responses.

#### Scenario: Real-backend decision propagation

- **WHEN** an import is accepted in an integration test against a real backend
- **THEN** the shared workflow status reflects the decision
- **AND** source-summary counters update

### Requirement: Performance tests are included

The change SHALL include performance tests that measure status refresh duration
on a dataset with at least 100 duplicate groups and 1000 screening records.

#### Scenario: Performance threshold

- **WHEN** status refresh runs on the large dataset
- **THEN** the measured duration is recorded
- **AND** the test fails if it exceeds the agreed threshold
