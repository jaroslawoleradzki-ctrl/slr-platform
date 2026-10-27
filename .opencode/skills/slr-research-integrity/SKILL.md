---
name: SLR Research Integrity
description: Use for HIGH-risk work touching imports, provenance, RIS/BibTeX, DOI normalization, duplicate review, screening, quality assessment, extraction, synthesis, PRISMA accounting, or research-data migrations.
---

# SLR Research Integrity

## Activation criteria

Activate for any change that can affect what a review includes, excludes,
counts, merges, attributes, or reports. Examples:

- RIS/BibTeX/CSV import, source records, or import history;
- DOI, identifier, provenance, or raw-response handling;
- duplicate candidate detection, merge, or review decisions;
- PRISMA identification, screening, inclusion, or exclusion counts;
- title/abstract or full-text screening decisions;
- quality assessment criteria, records, or snapshots;
- extraction fields, field-state contracts, or datasets;
- synthesis records, eligibility, or immutable snapshots;
- migrations or reconciliation scripts over research data.

When in doubt, treat the change as HIGH risk.

## Required context

Read `AGENTS.md`, then:

- `docs/adr/0005-provenance-first-data-model.md`;
- `docs/adr/0006-no-autonomous-scientific-decisions.md`;
- `docs/adr/0007-extraction-field-state-contract.md`;
- `docs/EXPORTS_PRISMA.md`, `docs/data-model.md`, and
  `docs/DUPLICATE_REVIEW_DECISIONS.md`;
- the affected service, repository, migration, and integrity tests;
- the project fixtures and any published release/review report for the area.

## Workflow

1. Name the research population and the exact records affected.
2. Trace each record's source identity and provenance from import to output.
3. Check identifier handling, especially canonical DOI normalization in
   `app/normalization/doi.py`.
4. Check decision semantics: who decides, when, with what rationale, and
   whether the decision is append-only and attributed.
5. Check counting: identification, pre-screening removals, screening,
   eligibility, inclusion, and synthesis must remain distinct PRISMA stages.
6. Check preservation: archival/removal paths must retain the record, reason,
   provenance, and audit trail instead of deleting it.
7. Require deterministic tests for the invariant, not just the happy path.
8. Review the implementation independently. A blocker must be fixed or
   explicitly accepted by a human before merge.

## Safety constraints

- Never auto-merge uncertain duplicates.
- Never auto-decide inclusion, exclusion, quality, extraction, or synthesis.
- Never fabricate metadata or provenance.
- Never silently change a criterion, protocol, population, or count.
- Never delete or overwrite a research record to resolve an inconsistency.
- Never replace a human decision with an AI recommendation.
- Never read or mutate the real research database from an agent shell; use
  `bash scripts/agent/safe_pytest.sh` or a read-only inspection path.
- Never accept a green test suite as proof if the test does not exercise the
  integrity invariant.

## Validation

- Targeted integrity tests pass.
- PRISMA counts reconcile across the affected stages.
- Duplicate/screening/QA decisions remain append-only and attributable.
- Provenance and source identity survive import, normalization, merge, and
  export.
- Migration tests cover the prior schema and the new schema.
- The implementation report states residual research risk.

## Expected outputs

- Integrity findings ordered by severity, each with file/line evidence.
- Explicit PASS, PASS WITH CONDITIONS, or BLOCK recommendation.
- Required fixes and re-test scope.
- Count/provenance reconciliation notes.
- Sign-off statement that no scientific decision was automated.

## References

- `AGENTS.md` section C
- `docs/adr/0005-provenance-first-data-model.md`
- `docs/adr/0006-no-autonomous-scientific-decisions.md`
- `docs/adr/0007-extraction-field-state-contract.md`
- `docs/EXPORTS_PRISMA.md`
- `docs/data-model.md`
- `docs/DUPLICATE_REVIEW_DECISIONS.md`
- `app/normalization/doi.py`
- `app/services/prisma_metrics_service.py`
- `app/repositories/`, `migrations/`, `tests/`
