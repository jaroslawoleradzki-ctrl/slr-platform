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

## Planned API Boundary & Mock Data Strategy

- **Mock Data Layer**: Implemented in `src/mocks/projectData.ts`, loading real config schema matching `projects/lean_energy/config.yaml`. Status badge in Header indicates `Mock API / Demo Data` status explicitly until Phase 6.2.
- **API Boundary**: Abstracted in `src/services/api/projectApi.ts` (`ProjectApiService`).
- **Backend as Source of Truth**: Candidate duplicate groups are detected based on strong identifiers (DOI, PMID, OpenAlex ID). The frontend performs zero domain merging or automated decision writing. Buttons are set to preview mode (`disabled`).

---

## Quality Gate Verification Results

- **TypeScript Compilation**: `npm run type-check` (0 errors)
- **Frontend Test Suite**: `npm run test` (5/5 tests passing)
- **Production Bundle**: `npm run build` (Succeeded)
- **Backend Test Suite**: `.venv/bin/pytest` (815/815 tests passing)
