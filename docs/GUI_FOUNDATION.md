# SLR Platform — GUI Foundation Documentation (Phase 6.1)

_Updated: Phase 6.1 — GUI Foundation & Duplicate Review Teaser_

## Overview

The `frontend/` application provides the modern, scientific graphical user interface for **SLR Platform** (`jaroslawoleradzki-ctrl/slr-platform`). It visualizes the complete Systematic Literature Review (SLR) lifecycle across 10 defined stages, adhering to scientific standards like **PRISMA 2020**.

---

## Technical Stack & Architecture

- **Framework**: React 18 + TypeScript + Vite
- **Router**: React Router v6 (`react-router-dom`)
- **Styling**: Scientific Design System Tokens (`src/index.css`) with CSS custom properties
- **Icons**: Lucide React (`lucide-react`)
- **Testing**: Vitest + React Testing Library + JSDOM
- **Build Tool**: Vite (`npm run build`), injecting root `VERSION` via `__APP_VERSION__` constant

---

## Directory Structure

```
frontend/
├── src/
│   ├── assets/               # Static assets & icons
│   ├── components/
│   │   ├── common/           # Badge, Card, Modal, EmptyState, ErrorAlert, LoadingSpinner
│   │   ├── layout/           # AppShell, Header, Sidebar
│   │   ├── workflow/         # WorkflowStepper, LivePrismaFlowChart, NextActionCard
│   │   ├── search/           # ConceptGroupQueryBuilder, SearchLimitsForm, ProviderStatusCard
│   │   ├── imports/          # FileDropzone
│   │   ├── deduplication/    # DeduplicationSummaryCard, DuplicateGroupCardPreview
│   │   ├── screening/        # ScreeningPipelineOverview
│   │   └── exports/          # Export cards & PRISMA preview
│   ├── context/              # ProjectContext (Active project state & switcher)
│   ├── mocks/                # Mock projects dataset (lean_energy, AI SLR demo)
│   ├── pages/
│   │   ├── ProjectsListPage.tsx
│   │   ├── ProjectDashboardPage.tsx
│   │   ├── SearchStrategyPage.tsx
│   │   ├── SourcesIngestionPage.tsx
│   │   ├── NormalizationPage.tsx
│   │   ├── DeduplicationPage.tsx
│   │   ├── ScreeningPage.tsx
│   │   ├── QualityAssessmentPage.tsx
│   │   ├── DataExtractionPlaceholderPage.tsx
│   │   └── ExportsPage.tsx
│   ├── services/             # API Service interface & mock implementation
│   ├── types/                # TypeScript domain models
│   ├── App.tsx               # Application routing
│   ├── index.css             # Scientific design tokens
│   └── main.tsx              # Application entry point
├── tests/                    # Vitest unit & component test suite
├── package.json
├── tsconfig.json
├── vite.config.ts
└── vitest.config.ts
```

---

## Routing & Information Architecture

| Route | View Component | Description |
| :--- | :--- | :--- |
| `/projects` | `ProjectsListPage` | List of SLR projects & New Project Modal |
| `/projects/:id/dashboard` | `ProjectDashboardPage` | **Dashboard**: Next Action block, Live PRISMA 2020 Flow diagram |
| `/projects/:id/search` | `SearchStrategyPage` | Concept Group Query Builder & Search Scope Limits |
| `/projects/:id/sources` | `SourcesIngestionPage` | Live API Providers (OpenAlex, Crossref, S2) & File Dropzone (BibTeX, RIS) |
| `/projects/:id/normalize` | `NormalizationPage` | Field canonicalization health & warnings audit trail |
| `/projects/:id/dedup` | `DeduplicationPage` | Identifier-linked deduplication summary & candidate duplicate groups awaiting human review |
| `/projects/:id/screen` | `ScreeningPage` | Title & Abstract triage vs Full-Text eligibility pipeline |
| `/projects/:id/qa` | `QualityAssessmentPage` | Quality assessment appraisal & reviewer conflict tracking |
| `/projects/:id/extract` | `DataExtractionPlaceholderPage` | Future Workflow Step placeholder page |
| `/projects/:id/exports` | `ExportsPage` | Formats export workspace & PRISMA Flow export |

---

## Hybrid API Integration & Read-Only Duplicate Review (Phase 6.3)

- **Read-Only API Endpoint**: Candidate duplicate groups are fetched directly from FastAPI backend (`GET /projects/{project_id}/duplicate-groups`).
- **Hybrid Data Mode**: Header and About modal reflect `Hybrid Data Mode (Deduplication API + Demo Data)` to indicate live backend connectivity for Duplicate Review alongside demo data for other views.
- **State Management**: `DeduplicationPage` handles `loading`, `success`, `empty` (0 candidate groups), and `error` (with retry button).
- **Backend as Source of Truth**: Candidate duplicate groups are detected based on strong identifiers (DOI, PMID, OpenAlex ID). The frontend performs zero domain merging or automated decision writing. Buttons remain in preview mode (`disabled`) with tooltips indicating decision persistence is planned for Phase 6.4.

---

## Persistent Search Strategy workflow (v0.1.8)

The Search Strategy screen uses
`GET/PUT /projects/{project_id}/search-strategy` as its only strategy data
source. Project demonstration data remains available to unfinished screens but
does not initialize or persist the Search Strategy form.

The screen supports the complete backend contract: name, research questions,
concept groups, terms, AND/OR operators, years, languages, publication types,
additional constraints, provider selection, and a generic Boolean preview.
UI state distinguishes initial loading, no saved strategy, unsaved changes,
save in progress, saved state, validation failures, read failures, and write
failures.

The terminal action is `Szukaj`. It saves the current strategy and navigates to
Sources Ingestion only after a successful response. It does not execute
OpenAlex, Crossref, Semantic Scholar, or any background provider request.

---

## Quality Gate Verification Results

- **TypeScript Compilation**: `npm run type-check` (0 errors)
- **Frontend Test Suite**: `npm run test` (5/5 tests passing)
- **Production Bundle**: `npm run build` (Succeeded)
- **Backend Test Suite**: `.venv/bin/pytest` (815/815 tests passing)
