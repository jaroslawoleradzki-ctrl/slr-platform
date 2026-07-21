# SLR Platform — Project Status

_Last updated: 2026-07-21_

## Current status

Project is in active development.

Infrastructure and project architecture are considered stable.

Current version:

v0.1.0

---

# Completed

## Infrastructure

- Python project initialized
- FastAPI running
- pytest configured
- development scripts
- Docker-ready architecture
- GitHub repository
- HomeLab mirror
- SSH authentication to GitHub
- single `git push` pushes to GitHub and HomeLab

## Documentation

Completed:

- ADR documents
- logging standard
- testing standard
- data model draft
- JSON schema
- project architecture

## Refactoring

Completed migration:

app/

    domain/
    providers/
    services/
    storage/
    config/

Old architecture removed.

Tests passing.

---

# Current architecture

FastAPI

↓

Workflow

↓

Services

↓

Providers

↓

Domain models

↓

Storage

---

# Development principles

The project follows:

- Clean Architecture
- Domain Driven Design (lightweight)
- provenance-first
- reproducible science
- plugin providers
- YAML configuration
- OpenAlex first

Every feature must:

- have tests
- be documented
- preserve provenance
- avoid hidden AI decisions

---

# Next milestone

Implement canonical domain model.

Target objects:

- Publication
- Author
- Venue
- Identifier
- SearchRun
- SearchQuery
- Provenance
- ScreeningDecision

After that:

OpenAlex provider.

---

# Important notes

Infrastructure is considered finished.

Future work focuses on scientific functionality, not framework development.

Every larger change should be implemented as a reviewable PR-sized increment.