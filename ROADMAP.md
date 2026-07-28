# SLR Platform Roadmap

## Vision

SLR Platform is an open-source application supporting the complete lifecycle of a Systematic Literature Review (SLR).

The long-term goal is to provide a transparent, reproducible and AI-assisted workflow that follows evidence-based research principles while remaining provider-independent.

The project is developed incrementally, with every phase ending in a usable and stable application.

---

# Product Roadmap

## Phase 1 — Domain Model ✅

Core domain objects.

- Publication
- Author
- Venue
- Identifiers
- Provenance
- Search Query
- Search Results

---

## Phase 2 — Search Providers 🚧

Search integration.

Current providers:

- OpenAlex
- Crossref
- Semantic Scholar

Future:

- Europe PMC
- OpenAIRE
- Lens
- CORE

---

## Phase 3 — Import Providers 🚧

Import bibliographic files.

Supported:

- BibTeX
- RIS

Future:

- EndNote XML
- CSL JSON

---

## Phase 4 — Normalization ✅

Provider-independent normalization layer.

Completed:

- DOI
- Title
- Author
- ORCID
- Publication normalization pipeline

---

## Phase 5 — Deduplication

Deterministic publication deduplication.

Goals:

- duplicate detection
- merge strategy
- provenance preservation

---

## Phase 6 — Screening Engine

Support for systematic review screening.

Features:

- inclusion/exclusion decisions
- screening history
- conflict detection
- multiple reviewers

---

## Phase 7 — GUI MVP

First usable graphical application.

Features:

- search
- import
- results
- deduplication
- screening
- export

Focus:

- functionality over appearance

---

## Phase 8 — Reporting & Export

Generate research outputs.

Examples:

- PRISMA flow
- CSV
- BibTeX
- RIS
- Excel
- JSON

---

## Phase 9 — Project Management

Research project management.

Examples:

- saved searches
- protocols
- search history
- project metadata
- audit trail

---

## Phase 10 — User Experience

Application refinement.

Examples:

- UX
- accessibility
- performance
- responsive layouts
- keyboard shortcuts

---

## Phase 11 — AI Assistance

AI features built on top of a stable platform.

Potential capabilities:

- article summarization
- relevance suggestions
- duplicate suggestions
- keyword extraction
- quality assessment support
- evidence synthesis support

AI is intentionally scheduled after the core platform to ensure transparency, reproducibility and provider independence.

---

# Release Strategy

The project follows incremental releases.

Typical flow:

Feature
→ Tests
→ Documentation
→ Stable Release

Every completed phase results in a usable application.