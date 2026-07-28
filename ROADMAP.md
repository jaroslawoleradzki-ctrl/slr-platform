# SLR Platform Roadmap

## Phase 0 — Foundation ✅

- [x] Repository
- [x] GitHub
- [x] HomeLab mirror
- [x] Python
- [x] FastAPI
- [x] pytest
- [x] Docker readiness
- [x] ADR documentation
- [x] Architecture
- [x] Refactoring

---

## Phase 1 — Domain Model ✅

- [x] Publication
- [x] Author
- [x] Affiliation
- [x] Venue
- [x] Identifier
- [x] SearchRun
- [x] SearchQuery
- [x] Provenance
- [x] ScreeningDecision
- [x] screening decision enum
- [x] decision rationale
- [x] reviewer or supporting agent attribution
- [x] audit trail
- [x] backward compatibility contract tests

Deliverable:

Canonical publication and review-process model.

---

## Phase 2 — Search Providers

### OpenAlex

- [x] client
- [x] pagination
- [x] retries
- [x] rate limiting
- [x] provenance ✅ Completed
- [x] unit tests for completed increments

### Crossref

- [x] asynchronous Works API client
- [x] retries
- [x] rate limiting
- [x] cursor pagination
- [x] provider mapping to `Publication`
- [x] provenance
- [x] unit tests for completed increments

Current active increment:

Phase 3.2 — Multi-provider orchestration.

### Semantic Scholar

- [x] basic client and single-page search
- [x] offset pagination
- [x] provider mapping to Publication
- [x] provenance

### Google Scholar Import

- [x] 3.1 RIS parser
- [x] 3.2 RIS -> Publication mapping
- [x] 3.3 Google Scholar RIS import
- [x] ImportProvider abstraction

### BibTeX Import

- [x] 4.1 BibTeX parser
- [x] 4.2 BibTeX -> Publication mapping
- [x] 4.3 BibTeX ImportProvider
- [x] 4.4 Contract tests

### Harmonization

Goal:

Bring all search providers to the same canonical mapping quality before starting the review workflow.

Planned work:

- [x] 5.1 Canonical mapping parity specification
- [x] 5.2 OpenAlex provider mapping parity
- [x] 5.3 Cross-provider normalization consistency
- [x] 5.4 Shared mapper utilities
- [x] 5.5 Cross-provider mapping contract tests

Increment scope:

- **5.1 Canonical mapping parity specification** — compare OpenAlex, Crossref, and Semantic Scholar mappings and define a canonical `Publication` field matrix covering title, abstract, authors, affiliations, publication year and date, identifiers, venue, publisher, document type, language, URLs, and provenance. Classify fields as required, optional, or provider-data-dependent, and add tests describing current gaps without changing provider production code or creating shared helpers.
- **5.2 OpenAlex provider mapping parity** — extend OpenAlex mapping to the agreed canonical quality using only fields actually available in OpenAlex responses. Keep its API client separate from domain mapping and change HTTP behavior only where mapping directly requires it.
- **5.3 Cross-provider normalization consistency** — align provider-boundary handling for trimming, blank values, DOI, ORCID, ISSN, URLs, language, document types, author names, venue, and publisher across OpenAlex, Crossref, and Semantic Scholar. This does not include deduplication or the later global Normalization phase.
- **5.4 Shared mapper utilities** — extract only demonstrated repeated mapping logic, such as non-blank value selection, identifier normalization, safe URL construction, and basic shared structure mapping. Do not introduce a mapper framework, provider base class, or coupling between HTTP clients and domain mappers.
- **5.5 Cross-provider mapping contract tests** — add shared canonical mapping regression tests for OpenAlex, Crossref, and Semantic Scholar while retaining provider-specific behavior in focused tests and avoiding HTTP clients in mapping-only tests. Completion closes Harmonization.

Notes:

- Use the richer Crossref implementation as a reference, not as the sole automatic specification.
- Extract reusable mapping helpers only after actual duplication is identified.
- Keep provider-specific API clients separated from canonical domain mapping.
- No new functionality; architectural consolidation only.
- Harmonization completed across Phases 5.1–5.5.

---

## Phase 3 — Search Engine

### Goal

Build a provider-independent search orchestration layer capable of executing literature searches across one or more providers while preserving canonical Publication mapping, complete execution provenance, and raw provider responses.

The Search Engine is responsible for orchestration only. It must not contain provider-specific mapping logic, HTTP implementation details, or deduplication algorithms.

### Phase 3.1 — Execute queries through a single provider

Scope

- [x] Implement the Search Engine entry point.
- [x] Execute a single SearchQuery.
- [x] Invoke exactly one configured search provider.
- [x] Create a SearchRun.
- [x] Return canonical Publication objects.
- [x] Add complete unit tests.

Out of scope

* Multiple providers.
* Result merging.
* Raw response archive.
* Deduplication.
* Search-level provenance aggregation.

### Phase 3.2 — Multi-provider orchestration

Scope

- [ ] Execute the same query against multiple providers.
- [ ] Configure provider execution order.
- [ ] Collect provider results independently.
- [ ] Continue execution when one provider fails.
- [ ] Aggregate provider outputs without merging records.

Out of scope

* Deduplication.
* Raw response persistence.
* Global execution provenance.

### Phase 3.3 — Raw response archive

Scope

- [ ] Archive complete provider responses.
- [ ] Associate every archive entry with the corresponding SearchRun.
- [ ] Store provider metadata, execution timestamp, rendered query, and execution status.
- [ ] Preserve responses for later replay and diagnostics.

Out of scope

* Result merging.
* Response interpretation.
* Deduplication.

### Phase 3.4 — Merge provider results

Scope

- [ ] Combine results returned by all successfully executed providers.
- [ ] Preserve every canonical Publication.
- [ ] Produce deterministic ordering.
- [ ] Keep provider provenance intact.

Out of scope

* DOI matching.
* Title similarity.
* Duplicate detection.
* Confidence scoring.

⸻

### Phase 3.5 — Search provenance tracking

Scope

- [ ] Record complete search execution provenance.
- [ ] Store provider execution status.
- [ ] Store execution duration.
- [ ] Store provider result counts.
- [ ] Associate every result with its originating provider and SearchRun.

Out of scope

* Deduplication.
* Ranking.

### Phase 3.6 — Search Engine contract tests

Scope

- [ ] End-to-end orchestration tests.
- [ ] Single-provider execution.
- [ ] Multi-provider execution.
- [ ] Partial provider failures.
- [ ] Raw response archive verification.
- [ ] Result merge verification.
- [ ] Search provenance verification.
- [ ] No real HTTP requests.

Completion of Phase 3.6 closes the Search Engine implementation.

### Architectural rules

The following rules apply throughout Phase 3:

* Search Engine performs orchestration only.
* Providers remain completely independent.
* Provider HTTP clients remain isolated.
* Provider mappers remain isolated.
* Canonical Publication mapping is not duplicated.
* No global normalization before Phase 4.
* No deduplication before Phase 5.
* Every increment includes:
    * unit and contract tests,
    * documentation updates,
    * implementation commit,
    * documentation commit.

---

## Phase 4 — Normalization

- [ ] DOI normalization
- [ ] title normalization
- [ ] author normalization
- [ ] identifier normalization

---

## Phase 5 — Deduplication

- [ ] DOI matching
- [ ] title similarity
- [ ] author similarity
- [ ] confidence score
- [ ] provenance

---

## Phase 6 — Screening

- [ ] title screening
- [ ] abstract screening
- [ ] inclusion criteria
- [ ] exclusion criteria
- [ ] decision log

---

## Phase 7 — Quality Assessment

- [ ] checklist
- [ ] scoring
- [ ] reviewer agreement

---

## Phase 8 — Export

- [ ] CSV
- [ ] RIS
- [ ] BibTeX
- [ ] PRISMA flow
- [ ] Excel

---

## Phase 9 — AI Assistance

- [ ] local Ollama
- [ ] reviewer suggestions
- [ ] explainability
- [ ] confidence estimation

---

## Phase 10 — GUI

- [ ] dashboard
- [ ] project management
- [ ] search history
- [ ] review interface

---

## Phase 11 — Release

- [ ] Docker image
- [ ] documentation
- [ ] tutorial
- [ ] example project

---

# Roadmap governance

The roadmap defines the agreed sequence of implementation.

Additional engineering activities, such as integration testing, should be included within an existing roadmap item unless a deliberate decision is made to change the roadmap.

---

# Long-term ideas

- Scopus connector
- Web of Science connector
- Lens.org
- ORCID
- Zotero synchronization
- n8n integration
- MCP server
- local RAG
