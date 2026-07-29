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

## Phase 6 — GUI Foundation and Duplicate Review

Establish the reusable graphical application foundation and provide the first functional review workflow for duplicate publications.

Features:

- application shell
- routing and navigation
- shared layout
- API client foundation
- loading, empty and error states
- reusable forms and tables
- frontend module structure
- duplicate groups view
- duplicate comparison view
- merge candidate review
- provenance visibility
- user confirmation of duplicate decisions

This phase does not represent the full GUI MVP. Its purpose is to establish the interface foundation and deliver the first complete module supporting deduplication.

---

## Phase 7 — Screening

Support systematic review screening through a backend workflow and a dedicated user interface.

Features:

- inclusion and exclusion decisions
- screening criteria
- screening rationale
- title and abstract screening
- full-text screening
- screening history
- conflict detection
- multiple reviewers
- screening queue and progress view
- screening decision interface

---

## Phase 8 — Quality Assessment

Support methodological quality assessment of included studies.

Features:

- configurable quality criteria
- assessment forms
- scoring or rating schemes
- reviewer attribution
- assessment rationale
- assessment history
- reviewer agreement and disagreement visibility
- quality assessment interface
- assessment progress view

---

## Phase 9 — Data Extraction

Support structured extraction of research data from included studies.

Features:

- configurable extraction forms
- structured extraction fields
- extracted-value provenance
- reviewer attribution
- extraction history
- validation of extracted data
- extraction workspace
- tabular and form-based extraction views
- exportable structured datasets

---

## Phase 10 — Evidence Synthesis

Support organization, analysis and synthesis of extracted evidence.

Features:

- qualitative synthesis support
- thematic grouping
- evidence tables
- bibliometric analysis support
- research-gap identification
- synthesis traceability
- synthesis workspace
- comparison and aggregation views

---

## Phase 11 — Integrated GUI MVP

Integrate the previously developed graphical modules into the first complete end-to-end application.

Features:

- unified workflow navigation
- integrated search and import views
- integrated deduplication workflow
- integrated screening workflow
- integrated quality assessment workflow
- integrated data extraction workflow
- integrated evidence synthesis workflow
- common state management
- consistent validation and error handling
- basic settings
- complete end-to-end user journey

The GUI MVP is not built from scratch. It integrates, unifies and completes the graphical modules developed in earlier phases.

---

## Phase 12 — Reporting & Export

Generate research outputs.

Examples:

- PRISMA flow
- CSV
- BibTeX
- RIS
- Excel
- JSON

---

## Phase 13 — Project Management

Research project management.

Examples:

- saved searches
- protocols
- search history
- project metadata
- audit trail

---

## Phase 14 — User Experience

Application refinement.

Examples:

- UX
- accessibility
- performance
- responsive layouts
- keyboard shortcuts

---

## Phase 15 — AI Assistance

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
