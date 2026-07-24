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
- [ ] provider mapping to `Publication`
- [ ] provenance
- [ ] unit tests for remaining increments

Current active increment:

Crossref — provider mapping to `Publication`.

### Semantic Scholar

- [ ] implementation

### Google Scholar Import

- [ ] RIS
- [ ] BibTeX

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
