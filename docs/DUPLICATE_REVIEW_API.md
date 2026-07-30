# SLR Platform — Candidate Duplicate Review Read API (Phase 6.3)

## 1. Overview

The **Candidate Duplicate Review Read API** exposes candidate duplicate publication groups detected by the backend using strong canonical identifiers (DOI, PMID, OpenAlex ID).

- **HTTP Method**: `GET`
- **Endpoint**: `/projects/{project_id}/duplicate-groups`
- **Read-Only Boundary**: Does not write decisions, modify records, or alter project state. Decision writing is deferred to Phase 6.4.
- **Repository Boundary**: Uses `ProjectPublicationRepository` interface. Demonstrations currently rely on `DemoProjectPublicationRepository` as a temporary in-memory adapter until persistent project storage is introduced in future phases.

---

## 2. Response Schema (`DuplicateGroupListResponse`)

```json
{
  "project_id": "lean_energy",
  "total_groups_count": 2,
  "groups": [
    {
      "group_id": "8a7c29e1-6b45-562a-89bc-31e9c2012345",
      "reason": "Zgodność identyfikatorów (DOI: 10.1016/j.jclepro.2021.102834, OPENALEX: W3128349201)",
      "records_count": 2,
      "shared_identifiers": [
        {
          "identifier_type": "doi",
          "value": "10.1016/j.jclepro.2021.102834"
        },
        {
          "identifier_type": "openalex",
          "value": "W3128349201"
        }
      ],
      "records": [
        {
          "id": "00000000-0000-0000-0000-000000000101",
          "title": "Energy reduction through lean production in auto manufacturing: A systematic review",
          "authors": "Smith, J., Kowalski, P.",
          "year": 2021,
          "source": "OpenAlex",
          "doi": "10.1016/j.jclepro.2021.102834",
          "pmid": null,
          "openalex_id": "W3128349201"
        },
        {
          "id": "00000000-0000-0000-0000-000000000102",
          "title": "Energy reduction through lean production in automotive manufacturing: Systematic Review",
          "authors": "Smith, John, Kowalski, Piotr",
          "year": 2021,
          "source": "Crossref",
          "doi": "10.1016/j.jclepro.2021.102834",
          "pmid": null,
          "openalex_id": "W3128349201"
        }
      ]
    }
  ]
}
```

---

## 3. HTTP Status Codes

- `200 OK`: Successful retrieval of duplicate candidate groups (returns `groups: []` if 0 candidate groups are found or if the project has 0 publications).
- `404 NOT FOUND`: Project ID does not exist in the repository (`ProjectNotFoundError`).
- `500 INTERNAL SERVER ERROR`: Unexpected server error during duplicate group building.

---

## 4. Architectural Boundaries

1. **No Hardcoded Project Logic**: `ProjectDuplicateService` receives a `ProjectPublicationRepository` dependency and is agnostic to project IDs.
2. **Structured Identifiers**: `shared_identifiers` provides structured `{ identifier_type, value }` objects rather than plain text strings.
3. **No Similarity Scoring**: `similarity_score` is removed from DTOs as matching relies on exact strong identifier equality.
4. **Configuration Isolation**: API connection config is located in `frontend/src/config/api.ts`.
