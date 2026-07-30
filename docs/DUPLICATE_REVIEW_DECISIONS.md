# SLR Platform — Candidate Duplicate Review Decisions (Phase 6.4)

## 1. Overview

**Phase 6.4 — Duplicate Review Decisions** introduces the capability for human reviewers to record and retrieve decisions (`APPROVE` or `REJECT`) for candidate duplicate groups.

- **Storage Mode**: In-Memory (`InMemoryDuplicateReviewDecisionRepository`).
- **Persistence Boundary**: Decisions are stored in runtime memory to prepare the architecture for persistent storage in future phases. No database or disk files are modified.
- **Publication State**: Recording a decision does not merge publications, alter publication records, or delete candidate group records.

---

## 2. API Endpoints

### 2.1 Record Decision (`POST`)
- **URL**: `/projects/{project_id}/duplicate-groups/{group_id}/decision`
- **Request Body**:
  ```json
  {
    "decision": "APPROVE"
  }
  ```
  or
  ```json
  {
    "decision": "REJECT"
  }
  ```
- **Responses**:
  - `200 OK`:
    ```json
    {
      "group_id": "8a7c29e1-6b45-562a-89bc-31e9c2012345",
      "decision": "APPROVE"
    }
    ```
  - `404 NOT FOUND`: Project or duplicate group ID does not exist.
  - `422 UNPROCESSABLE ENTITY`: Invalid decision value (must be `"APPROVE"` or `"REJECT"`).

### 2.2 Read Decision (`GET`)
- **URL**: `/projects/{project_id}/duplicate-groups/{group_id}/decision`
- **Responses**:
  - `200 OK`:
    ```json
    {
      "group_id": "8a7c29e1-6b45-562a-89bc-31e9c2012345",
      "decision": "APPROVE"
    }
    ```
    *(Returns `"decision": "PENDING"` if no decision has been recorded for the group).*
  - `404 NOT FOUND`: Project or duplicate group ID does not exist.

---

## 3. Component Architecture & Dependency Injection

- **`InMemoryDuplicateReviewDecisionRepository`**: In-memory repository implementing `DuplicateReviewDecisionRepository`.
- **`ProjectDuplicateService`**: Injected with `ProjectPublicationRepository` and `DuplicateReviewDecisionRepository`. Validates group existence and handles decision recording and reading.
- **Frontend `DuplicateGroupCardPreview`**: Interactive UI component rendering active decision buttons (*Approve*, *Reject*), state indicators (*Saving...*, *Saved*, *Error*, *Retry*), and status badges (*Approved*, *Rejected*, *Pending*).
