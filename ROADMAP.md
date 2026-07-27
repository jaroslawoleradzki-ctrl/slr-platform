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

Harmonization — Phase 5.5 Cross-provider mapping contract tests.

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
- [ ] 5.5 Cross-provider mapping contract tests

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

---

## Phase 3 — Search Engine

- [ ] execute queries
- [ ] multiple providers
- [ ] merge results
- [ ] raw response archive
- [ ] provenance tracking

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
