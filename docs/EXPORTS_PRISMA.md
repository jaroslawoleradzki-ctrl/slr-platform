# SLR Platform v0.6.1 — Research Exports & PRISMA 2020 Flow Specification

## 1. Overview

SLR Platform v0.6.1 completes Stage 9 (Exports & Reporting) by providing seven research-grade export formats, an authoritative PRISMA 2020 flow model, and server-side vector (SVG) and document (PDF) diagram renderers.

All export operations are strictly read-only, execute without mutating project state, and strictly exclude superseded duplicate records.

---

## 2. Supported Export Formats

| Format | Endpoint | Media Type | Reviewer Scoped | Description |
|---|---|---|---|---|
| **BibTeX** | `GET /api/v1/projects/{id}/exports/bibtex` | `application/x-bibtex` | No (Project Canonical) | Canonical active Working Collection bibliography for LaTeX and reference managers. |
| **RIS** | `GET /api/v1/projects/{id}/exports/ris` | `application/x-research-info-systems` | No (Project Canonical) | Standard bibliographic interchange format for EndNote, Zotero, Mendeley, and RefMan. |
| **XLSX Matrix** | `GET /api/v1/projects/{id}/exports/xlsx` | `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` | Yes | Multi-sheet research synthesis matrix covering publications, screening, QA, extraction, and PRISMA summary. |
| **CSV Dataset** | `GET /api/v1/projects/{id}/extraction/export?format=csv` | `text/csv` | Yes | Structured Phase 9.8 extraction dataset with formula-injection neutralization. |
| **JSON Dataset** | `GET /api/v1/projects/{id}/extraction/export?format=json` | `application/json` | Yes | Structured Phase 9.8 extraction dataset read model. |
| **PRISMA SVG** | `GET /api/v1/projects/{id}/prisma/flow.svg` | `image/svg+xml` | Yes | Standalone, deterministic vector PRISMA 2020 flow diagram. |
| **PRISMA PDF** | `GET /api/v1/projects/{id}/prisma/flow.pdf` | `application/pdf` | Yes | Standalone, printable PRISMA 2020 flow diagram PDF with embedded DejaVu Unicode fonts. |

---

## 3. Architecture & Data Flow

```
Persisted Project State (SQLite)
   │
   ├──> ExportDatasetService (Read-Only Facade)
   │       ├──> get_active_publications() ──> [0 superseded records]
   │       ├──> BibTeX Writer (pure serializer)
   │       ├──> RIS Writer (pure serializer)
   │       └──> XLSX Workbook Builder (openpyxl)
   │
   └──> PrismaMetricsService (Authoritative Single Counting Path)
           │
           └──> PrismaFlowModel (Presentation-Neutral Domain Model)
                   │
                   └──> Shared Layout Geometry (layout.py)
                           ├──> SVG Renderer (xml.sax escaping)
                           └──> PDF Renderer (fpdf2 + DejaVu Sans)
```

---

## 4. Reviewer Scoping & Isolation

- **Publication-Level Exports (BibTeX, RIS)**: Represent the active canonical project collection and are independent of individual reviewers.
- **Reviewer-Sensitive Exports (XLSX, CSV, JSON, PRISMA SVG, PRISMA PDF)**: Accept an optional `reviewer_id` parameter. When specified (e.g. from the frontend reviewer identity), records, decisions, and metrics are strictly filtered to that reviewer. If omitted or empty, the platform applies standard default reviewer behavior.

---

## 5. Provenance & Reproducibility

Every export artifact carries authoritative provenance:

### HTTP Response Headers
- `X-Project-Id`: Target project UUID/identifier.
- `X-Protocol-Version`: Project protocol version (e.g. `0.6.0`).
- `X-Application-Version`: Platform application release version (from `VERSION`).
- `X-Generated-At`: ISO 8601 UTC timestamp of export generation.

### JSON Flow Model Metadata
The `GET /api/v1/projects/{id}/prisma/flow` model carries a `metadata` payload containing `project_id`, `project_title`, `protocol_version`, `application_version`, `generated_at`, and `counts_echo`.

### Determinism
- **BibTeX, RIS, CSV, PRISMA SVG**: Byte-identical for unchanged project state.
- **XLSX, PRISMA PDF**: Semantically deterministic (verified row values, sheet layout, and text extraction).

---

## 6. Security & Hardening Controls

1. **Formula Injection Neutralization**:
   - CSV and XLSX cell writers prepend a `'` prefix to any string starting with `=`, `+`, `-`, `@`, `\t`, or `\r`.
2. **Control Character Stripping**:
   - Unprintable characters (`\x00-\x08\x0B\x0C\x0E-\x1F\x7F`) are stripped across all serializers.
3. **Overlong Text Handling**:
   - XLSX cells exceeding 32,767 characters are safely truncated with `…[truncated]`.
   - SVG and PDF titles are gracefully clamped and XML-escaped.
4. **Input-Safe Filenames**:
   - Attachment filenames are strictly constructed from `project_id` and static format literals (e.g. `{project_id}_publications.xlsx`), preventing header injection.
5. **Unicode & Polish Diacritics**:
   - Full UTF-8 support preserved across all formats with bundled DejaVu Sans fonts for PDF rendering.
6. **Mutation Safety**:
   - All export endpoints are GET-only and invoke read-only repository methods.

---

## 7. Known Design Choices & Limitations

- **D4 Synthesis Included Definition**: `studies_included_synthesis` in PRISMA 2020 reflects the final Full-Text INCLUDE population, matching `quality_assessment.eligible_count`.
- **D5 Bibliographic Fields**: Volume, issue, and page numbers are currently omitted as they are not part of the core domain model.
- **D10 QA Roster Awareness**: Multi-reviewer QA roster awareness is decoupled from PRISMA reporting and scheduled for future QA enhancements.
