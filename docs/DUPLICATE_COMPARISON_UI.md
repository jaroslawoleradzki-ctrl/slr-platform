# SLR Platform — Candidate Duplicate Comparison & Review UI (Phase 6.5)

## 1. Overview

**Phase 6.5 — Duplicate Comparison and Review UI** provides a detailed side-by-side comparison interface for publications belonging to candidate duplicate groups. It builds directly upon Phase 6.4 review decisions without altering existing deduplication or storage boundaries.

- **Interface Layout**: Expandable side-by-side comparative table view for all member records of a candidate group.
- **Deterministic Field Matching**: Evaluates exact similarity across titles, authors, publication years, venues, identifiers (DOI, PMID, OpenAlex), and provenance details.
- **Decision Rationale (`rationale`)**: Allows reviewers to attach optional text rationale to decisions (`APPROVE` or `REJECT`) with server-side length validation (max 1000 characters) and trimming.
- **Accessibility & UX**: Includes `aria-expanded` attributes on comparison toggle controls, distinct text badges alongside color indicators, explicit button labels, and transactional feedback states (*Saving...*, *Saved*, *Error*, *Retry*).
- **Merge Boundary**: No physical merge, record deletion, or publication modification is executed in Phase 6.5.

---

## 2. Deterministic Field Matching Rules

For each compared attribute across candidate group records, the interface computes a deterministic comparison status:

| Status | Code / Badge | Condition | Visual Indicator |
| :--- | :--- | :--- | :--- |
| **Identical** | `MATCH` | All publications have the exact same non-empty value. | Green badge + Check icon |
| **Different** | `DIFFERENT` | Publications contain differing non-empty values. | Red/Purple badge + Alert icon |
| **Partial** | `PARTIAL` | Value is present in some records but missing in others. | Amber badge + Help icon |
| **Missing** | `UNAVAILABLE` | Attribute is missing/null across all group records. | Gray badge + Minus icon |

---

## 3. Provenance & Identifier Display

- **Canonical Identifiers**: Exposes DOI, PMID, OpenAlex ID, and shared canonical identifier pills.
- **Provenance Tracing**: Renders source system, source record ID, and retrieval timestamp (`retrieved_at`) directly from `ProvenanceEntryResponse`.

---

## 4. Decision Rationale & REST API

### 4.1 Record Decision Request (`POST`)
- **Endpoint**: `POST /projects/{project_id}/duplicate-groups/{group_id}/decision`
- **Request Payload**:
  ```json
  {
    "decision": "APPROVE",
    "rationale": "Verified full text agreement between Crossref and OpenAlex records."
  }
  ```
- **Validation**:
  - `rationale` is optional.
  - Whitespace-only rationale is trimmed to `null`.
  - Rationale exceeding 1000 characters triggers `422 UNPROCESSABLE ENTITY`.

### 4.2 Read Decision Response (`GET`)
- **Endpoint**: `GET /projects/{project_id}/duplicate-groups/{group_id}/decision`
- **Response Payload**:
  ```json
  {
    "project_id": "lean_energy",
    "group_id": "8a7c29e1-6b45-562a-89bc-31e9c2012345",
    "decision": "APPROVE",
    "rationale": "Verified full text agreement between Crossref and OpenAlex records."
  }
  ```
