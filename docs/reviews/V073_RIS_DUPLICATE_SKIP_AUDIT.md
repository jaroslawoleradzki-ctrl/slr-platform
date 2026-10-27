# SLR Platform v0.7.3 — RIS Import Deduplication Audit

## Exact matching algorithm

RIS records are mapped to `Publication` objects with provenance:

- `source = "ris"` (or `source_database` if supplied)
- `source_record_id = normalized DOI` when a DOI is present
- otherwise `source_record_id = record title`

During import, `SqliteProjectPublicationRepository.import_source_publications`
compares each incoming publication's `_source_key`:

```
(provenance.source.strip().casefold(), provenance.source_record_id.strip())
```

against the same key for all publications already in the project. If the key
already exists, the incoming record is skipped and counted in
`skipped_count`. The key is added to the in-memory set after each accepted
record, so duplicates inside the same import are also skipped.

Therefore:

- Duplicate detection is exact, not fuzzy.
- DOI-based duplicates are matched by normalized DOI.
- Records without DOI are matched by exact stripped title string.
- Matching is performed against the whole existing project corpus, including
  records from previous RIS imports and any other sources with the same
  `ris` provenance source.
- Skipped records are not persisted as publications, but their skip count is
  persisted in `import_history.warnings`.
- Metadata from skipped records is not retained in `project_publications`.

## Source-by-source accounting

Production import history for project `lean-green-phd-d05d3d`:

| File | Imported | Skipped duplicates |
|---|---:|---:|
| GS01.ris | 378 | 2 |
| GS2.ris | 11 | 4 |
| GS3.ris | 19 | 10 |
| GS4.ris | 5 | 3 |
| GS5.ris | 14 | 6 |
| GS6.ris | 6 | 11 |
| GS7.ris | 2 | 17 |
| GS8.ris | 11 | 9 |
| Total | 446 | 62 |

The 446 imported RIS records currently present in the project all have distinct
`source_record_id` values and distinct titles. Only 75 of the 446 imported RIS
records contain a DOI.

## Evidence for skipped records

Individual skipped records cannot be reconstructed from production data. Skipped
records are not stored in `project_publications`, and the original RIS files are
not retained in the production deployment. Only aggregate skip counts and warning
strings are persisted in `import_history`.

## Potential false positives

Methodological risk is concentrated in the no-DOI path. Because 371 of the 446
imported RIS records have no DOI, duplicate detection for those records relies on
exact title equality. This can incorrectly collapse distinct works that share an
identical title, including:

- conference papers and journal articles with the same title,
- preprints and published versions,
- records with identical titles but different publication years,
- Google Scholar records with incomplete or inconsistent metadata.

The mechanism does not compare authors, year, venue, document type, or DOI
presence. It also does not route ambiguous candidates to the manual
deduplication review workflow.

## Impact on SLR corpus and PRISMA

- 62 RIS records were not added to the Working Collection.
- If any of those records were distinct studies, the SLR corpus is incomplete
  and PRISMA identification counts may be understated.
- The existing imported RIS records remain auditable through `import_history`
  and `project_publications`.
- No screening decisions or deduplication decisions are affected by this audit.

## Recommended changes

1. Make RIS import duplicate detection DOI-first and title-fallback only when no
   DOI is available.
2. For no-DOI records, require additional exact metadata agreement (at minimum
   publication year and authors) before automatic skipping.
3. Route ambiguous or no-DOI duplicate candidates to the manual deduplication
   review workflow instead of silently skipping them.
4. Persist enough skipped-record metadata (title, DOI, year, source file) to
   make future audits reconstructable.
5. Make the import warning UI clearly state that duplicates were skipped by
   source/DOI or exact-title matching.

## Required regression tests

- RIS import with a DOI duplicate is skipped.
- RIS import with a no-DOI exact-title duplicate is skipped.
- RIS import with the same title but different year is not skipped.
- RIS import with the same title but different authors is not skipped.
- Duplicate records inside one RIS file are handled deterministically.
- Skipped record metadata is auditable or explicitly reported as unavailable.
- Import warnings are displayed with the correct count.

ALL 62 SKIPS VERIFIED: NO
FALSE POSITIVES FOUND: Not individually verifiable; risk exists for no-DOI exact-title matches.
METHODOLOGICAL RISK: MEDIUM
CODE CHANGE REQUIRED: YES
SAFE TO RELEASE v0.7.3: NO