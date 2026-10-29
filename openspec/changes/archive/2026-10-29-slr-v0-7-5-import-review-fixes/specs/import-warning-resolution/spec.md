# Spec Delta

## ADDED Requirements

### Requirement: Decision completion is independent of read-model refresh

A successful import-review decision SHALL be presented as complete without
waiting for the Sources summary or shared workflow status to refresh. The
decision response SHALL be the authoritative source for the active import row
and the dialog's updated state.

#### Scenario: Decision succeeds while refresh is slow

- **WHEN** the backend commits an accept or reject decision
- **THEN** the active import row displays the server-confirmed effective status and the dialog closes without waiting for the Sources summary or workflow refresh
- **AND** the refresh continues without keeping the decision controls or the dialog in a pending state

#### Scenario: Decision succeeds while refresh fails

- **WHEN** the backend commits a decision and the subsequent read-model refresh fails
- **THEN** the decision remains applied and is not reported as a failed decision
- **AND** the dialog remains closed
- **AND** the Sources view displays a visible, non-blocking refresh error with a retry action

#### Scenario: Decision request fails

- **WHEN** the backend rejects the decision request
- **THEN** the dialog remains open with the error and any structured blockers
- **AND** the import does not display a successful effective status

### Requirement: Decision actions expose independent pending feedback

The dialog SHALL identify which decision action is in flight and SHALL prevent
duplicate or conflicting submissions without blocking non-decision dismissal
after the request settles.

#### Scenario: Accept is in flight

- **WHEN** a reviewer selects `Akceptuję`
- **THEN** only the accept action presents a loading indicator
- **AND** both decision actions are disabled until the request settles

#### Scenario: Reject is in flight

- **WHEN** a reviewer confirms rejection
- **THEN** only the rejection action presents a loading indicator
- **AND** both decision actions are disabled until the request settles

#### Scenario: Reviewer repeats the decision

- **WHEN** a reviewer activates the same decision again before the first request settles
- **THEN** the system submits at most one decision request

#### Scenario: Decision request settles

- **WHEN** the decision request succeeds or fails
- **THEN** the dialog's close control is available again
- **AND** the dialog is not left permanently visible because of the pending state

### Requirement: Acceptance updates only warning-derived counters

A successful acceptance SHALL update the active import row to the effective
status `Zaimportowano` and SHALL change only counters derived from the import's
effective status. Canonical, source-record, working-collection, and PRISMA
populations SHALL remain unchanged.

#### Scenario: Sources counters after acceptance

- **WHEN** a warning import is accepted and the Sources summary refresh succeeds
- **THEN** the active import row displays `Zaimportowano`
- **AND** the source summary's successful-import count increases by one
- **AND** the source summary's warning-import count decreases by one
- **AND** the records-added count, working-collection total, canonical-publication count, source-record count, and PRISMA populations remain unchanged
- **AND** the Sources stage no longer reports the accepted import as a warning

#### Scenario: Refresh failure does not present stale counters as current

- **WHEN** the Sources summary refresh fails while a previously loaded summary is displayed
- **THEN** the view displays an error and a retry action
- **AND** it does not silently present the previous counters as the result of the decision

#### Scenario: Acceptance preserves research state

- **WHEN** a warning import is accepted
- **THEN** its imported publications, duplicate-review decisions, screening decisions, quality assessments, extraction records, synthesis records, and PRISMA stage populations remain unchanged
