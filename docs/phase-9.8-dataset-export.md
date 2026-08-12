# Phase 9.8 — Structured Dataset Export

Phase 9.8 completes the Phase 9 read boundary for Phase 10. It exposes
publication and relationship datasets without exposing SQLite or EAV storage
details.

## E1 identity decision

E1 publication identity comes from canonical publication metadata. The Lean
Energy v1 template therefore does not ask reviewers to re-enter title or year.
The read model and exports expose `canonical_title`, `canonical_authors`, and
`canonical_publication_year`. This prevents contradictory duplicate identity
values while retaining complete E1 coverage.

## Read and dataset grain

`PublicationExtractionReadModel` is one object per publication and includes
canonical metadata, template ID/version, completeness, latest revision index and
ID, reviewer and timestamp metadata, publication values, and repeating-group
items.

`RelationshipExtractionReadModel` is one object per repeating-group item. A
publication with two items produces two relationship records, while remaining
one publication record in the publication dataset.

Only the latest append-only revision is active. The default Phase 10 contract
includes `COMPLETE` revisions and excludes `NOT_STARTED`, `IN_PROGRESS`, and
`NEEDS_REVIEW`. A service caller may explicitly request all available revision
statuses for audit use; this does not change the default synthesis contract.

## Export API

```text
GET /api/v1/projects/{project_id}/extraction/export
    ?format=json&dataset=publications
GET /api/v1/projects/{project_id}/extraction/export
    ?format=csv&dataset=publications
GET /api/v1/projects/{project_id}/extraction/export
    ?format=csv&dataset=relationships
```

The default is JSON publications with `COMPLETE` filtering. Invalid format or
dataset values return `422`; missing project/configuration returns `404`; a
valid project with no included records returns an empty JSON list or a CSV with
headers.

CSV field columns use stable keys plus `<field>__status`, `<field>__origin`,
and provenance companions (`__source_page`, `__source_section`,
`__source_locator`, `__source_quote`, `__reviewer_note`). Number-with-unit
fields also have `<field>__unit`. Missing values retain explicit
`NOT_REPORTED`/`NOT_APPLICABLE` status and are never represented as `N/A`.

JSON retains the typed value slots, `ValueOrigin` (`REPORTED` or
`REVIEWER_CODED`), repeating groups, and complete provenance. Multi-enum lists,
values, rows, and columns are ordered deterministically.

Phase 10 derivation, correlations, synthesis, and meta-analysis remain out of
scope.
