# Phase 9 — Data Extraction
## Comprehensive Architecture & Design Plan

> **System**: SLR Platform
> **Target Version**: `0.4.0` (Planned)
> **Status**: ARCHITECTURE & AUDIT ONLY — DO NOT IMPLEMENT
> **Domain Focus**: Universal Configurable Data Extraction Framework (Production Seed: Lean Energy v1)

---

## 1. Current Repository Baseline & Audit

### 1.1 Preflight State

| Property | Value |
|---|---|
| Repository Path | `/Users/jarek/Git/slr-platform` |
| Current Branch | `feature/screening-7.8a` |
| HEAD Commit | `ffdf401` |
| Version | `0.3.3` |
| Worktrees | `/Users/jarek/Git/slr-platform` (`feature/screening-7.8a`)<br/>`/Users/jarek/Git/slr-platform-qa` (`feature/quality-assessment`) |
| Highest Active Migration | `0016_screening_reviewer_assignments.sql` |
| Reserved Migrations | `0013`, `0014` (reserved on `feature/quality-assessment`) |
| Recommended Phase 9 Migration | `0018_data_extraction.sql` |

### 1.2 Subsystem Audits & Integration Baseline

1. **Phase 6 Deduplication**: Establishes durable canonical publications (`project_publications`) resulting from merged duplicate groups.
2. **Phase 7 Screening (7.8A/7.8B Baseline)**:
   - Append-only `ScreeningDecision` with reviewer attribution and criterion snapshots.
   - `MultiReviewerScreeningService` with reviewer roster (`screening_reviewer_assignments`) and conflict derivation (`INCOMPLETE`, `AGREEMENT`, `CONFLICT`, `RESOLVED`, `STALE_RESOLUTION`).
   - `ProjectScreeningOutcome` read model providing canonical stage outcomes (`INCLUDE`, `EXCLUDE`, `UNCERTAIN`).
3. **Phase 8 Quality Assessment (QA Baseline on `feature/quality-assessment`)**:
   - `QualityAssessmentTool` + `QualityAssessmentTemplate` (versioned, immutable criteria snapshots).
   - `ProjectQualityAssessmentConfiguration` linking project to tool/template.
   - `QualityAssessment` (append-only revisions by reviewer with criteria responses).
   - *Key Lesson for Phase 9*: QA uses a flat list of homogeneous criteria (YES / NO / CANNOT_DETERMINE). Phase 9 requires **heterogeneous typed fields** and **1:N repeating groups** (e.g. multiple Lean–EE relationships per study).

---

## 2. Actual Phase 9 Roadmap Scope

Per `ROADMAP.md`, Phase 9 — Data Extraction comprises:

- **Configurable Extraction Forms**: Template-driven extraction schemas decoupled from domain logic.
- **Structured Extraction Fields**: Strongly typed fields (text, numbers, units, enums, dates, identifiers, repeating groups).
- **Extracted-Value Provenance**: Location tracking (section, page, quote/locator) and reviewer notes for extracted evidence.
- **Reviewer Attribution**: Traceable record of which reviewer extracted or updated each field value.
- **Extraction History**: Append-only revision log ensuring 100% auditability and reproducibility.
- **Validation of Extracted Data**: Multi-level validation rules (field constraints, requiredness, missingness, repeating group bounds).
- **Extraction Workspace**: Interactive UI for data entry, side-by-side metadata review, and validation feedback.
- **Tabular and Form-Based Extraction Views**: Dual-mode UI supporting structured single-publication forms and cross-study comparison tables.
- **Exportable Structured Datasets**: Clean CSV/JSON export separating publication-level context from extracted relationship items.

---

## 3. Relevant SLR Protocol Requirements (PhD Protocol Analysis)

Analysis of `/Users/jarek/Git/PhD/protocol/sections/10_data_extraction.tex` yields the following mandatory methodological requirements for the first production template (Lean Energy v1):

1. **Primary Purpose**: Extract structured evidence linking Lean Management practices to Energy Efficiency (EE) outcomes, including underlying mechanisms, metrics, contextual conditions, and evidence strength.
2. **Strict Field Structure (E1–E14)**:
   - **E1**: Publication Identification (bound to canonical bibliographic record)
   - **E2**: Study Context (country/region, industry, company/process characteristics)
   - **E3**: Study Type & Method (empirical, case study, simulation, survey, etc.)
   - **E4**: Lean Practice / Tool (TPM, 5S, VSM, Kaizen, SMED, JIT, etc.)
   - **E5**: Lean Application Scope & Implementation Level
   - **E6**: Energy Effect / Indicator (kWh, %, peak demand, energy intensity)
   - **E7**: Energy Measurement Method & Units
   - **E8**: Effect Magnitude & Direction (quantitative change, +/-, %)
   - **E9**: Evidence Character (empirically demonstrated, qualitatively described, estimated, postulated, unstated)
   - **E10**: Lean–EE Impact Mechanism (pathway connecting Lean practice to energy outcome)
   - **E11**: Contextual Factors / Moderating Conditions
   - **E12**: Main Study Conclusions
   - **E13**: Study Limitations
   - **E14**: Research Gaps & Future Directions
3. **Cardinality & Repeating Groups (1:N Relationships)**: A single publication frequently analyzes *multiple distinct Lean practices* or *multiple energy effects* (e.g. SMED → idle power reduction vs 5S → behavioral energy saving). Each Lean–EE relationship **must be extracted as a distinct sub-record** rather than flattened into a single row.
4. **Explicit Missingness Semantics**: Distinguish `PRESENT` (value extracted), `NOT_REPORTED` (authors omitted information), and `NOT_APPLICABLE` (category does not apply). Researchers must never guess or fabricate missing data.
5. **Source Data vs. Reviewer Interpretation**: Clear boundary between author-reported data (`REPORTED`) and reviewer synthesis classification (`REVIEWER_CODED`).
6. **Data Integrity & Consistency Controls**: Support 3-stage validation: record completeness, cross-record classification consistency (controlled vocabularies), and primary source verification.

---

## 4. Architectural Principles

1. **Domain-Agnostic Core**: The core data extraction engine knows nothing about Lean Management or Energy Efficiency. It executes arbitrary, versioned extraction templates.
2. **Template-Driven Configuration**: All fields, types, sections, controlled vocabularies, and repeating groups are defined in JSON/relational template manifests.
3. **Immutable Template Versioning**: Once an extraction template version is used in a project, its structure is permanently frozen (`v1.0.0`). Schema changes spawn a new immutable version (`v2.0.0`).
4. **Append-Only Extraction Revisions**: Edits to extracted data create new revision snapshots. Historical revisions are preserved for full auditability.
5. **Separation of Publication-Level and Item-Level Data**: Publication context (E1–E3, E12–E14) is captured once per study; repeating relationship entities (E4–E11) are captured in 1:N child items.
6. **Synthesis-Ready Storage**: Extracted values are stored in a normalized, queryable relational structure so Phase 10 (Evidence Synthesis) can query practices, outcomes, and mechanisms directly using SQL without parsing UI form JSON blobs.

---

## 5. Generic Domain Model

```
 ┌────────────────────────────────┐       1:N      ┌───────────────────────────────────────┐
 │       ExtractionTemplate       │───────────────>│       ExtractionTemplateVersion       │
 └────────────────────────────────┘                └───────────────────────────────────────┘
                                                                       │ 1:N
                                                                       ▼
                                                   ┌───────────────────────────────────────┐
                                                   │       ExtractionFieldDefinition       │
                                                   └───────────────────────────────────────┘
                                                                       │
                                                                       │ defines fields & groups
                                                                       ▼
 ┌────────────────────────────────┐       1:1      ┌───────────────────────────────────────┐
 │ ProjectExtractionConfiguration │───────────────>│           ExtractionRecord            │
 └────────────────────────────────┘                │    (per publication / project)        │
                                                   └───────────────────────────────────────┘
                                                                       │ 1:N
                                                                       ▼
                                                   ┌───────────────────────────────────────┐
                                                   │          ExtractionRevision           │
                                                   │          (append-only snapshot)       │
                                                   └───────────────────────────────────────┘
                                                                 │           │
                                                       1:N (pub) │           │ 1:N (groups)
                                                                 ▼           ▼
                                                   ┌────────────────┬──────────────────────┐
                                                   │ ExtractedValue │ ExtractedGroupItem   │
                                                   └────────────────┴──────────────────────┘
```

### Core Domain Value Objects & Entities

```python
class FieldDataType(StrEnum):
    TEXT = "text"
    LONG_TEXT = "long_text"
    INTEGER = "integer"
    DECIMAL = "decimal"
    BOOLEAN = "boolean"
    DATE = "date"
    ENUM = "enum"
    MULTI_ENUM = "multi_enum"
    IDENTIFIER = "identifier"
    URL = "url"
    NUMBER_WITH_UNIT = "number_with_unit"
    REPEATING_GROUP = "repeating_group"


class ValueStatus(StrEnum):
    PRESENT = "present"
    NOT_REPORTED = "not_reported"
    NOT_APPLICABLE = "not_applicable"
    UNCLEAR = "unclear"


class ValueOrigin(StrEnum):
    REPORTED = "reported"          # Directly stated by paper authors
    REVIEWER_CODED = "reviewer_coded"  # Categorized / interpreted by reviewer
    # Note: DERIVED (system-calculated/aggregated interpretation) is deferred to Phase 10 Evidence Synthesis.


class ExtractionCompletenessStatus(StrEnum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"
    NEEDS_REVIEW = "needs_review"
```

---

## 6. Template & Versioning Model

### 6.1 `ExtractionTemplate` & `ExtractionTemplateVersion`

- `ExtractionTemplate`: High-level identity (e.g. `template_id="lean_energy"`, `name="Lean Energy Data Extraction"`).
- `ExtractionTemplateVersion`: Immutable structural snapshot (`template_id`, `version="1.0.0"`, `is_active=True`, `schema_json`).

### 6.2 Structural Immutability Contract

1. When a template version is published (`is_published=True`), its fields, types, validation rules, and group definitions become **strictly immutable**.
2. If a project creates an `ExtractionRecord` using `v1.0.0`, `v1.0.0` can never be edited.
3. Schema additions or removals require creating `v2.0.0`. Historical records continue to reference `v1.0.0` and preserve exact structural interpretation.

---

## 7. Field Type System

Each field in an extraction template is defined by an `ExtractionFieldDefinition`:

| Field Type | Storage Representation | Validation Constraints | Example Use Case |
|---|---|---|---|
| `TEXT` | `text_value: str` | `max_length`, `regex` | Country, process name |
| `LONG_TEXT` | `text_value: str` | `max_length` | Mechanism description, conclusions |
| `INTEGER` | `int_value: int` | `min`, `max` | Sample size, year |
| `DECIMAL` | `float_value: float` | `min`, `max` | Effect size (-12.5) |
| `BOOLEAN` | `bool_value: bool` | None | Statistically significant (True/False) |
| `DATE` | `date_value: str (ISO)` | Format check | Study period start/end |
| `ENUM` | `text_value: str` | `allowed_values` list | Study type (Case Study, Survey) |
| `MULTI_ENUM` | `json_value: list[str]` | `allowed_values` list | Lean practices applied (TPM, 5S) |
| `IDENTIFIER` | `text_value: str` | DOI / PMID regex | Reference identifier |
| `URL` | `text_value: str` | URL scheme check | Dataset link |
| `NUMBER_WITH_UNIT` | `float_value: float`, `unit_value: str` | `allowed_units` list | Energy reduction (15.2, "kWh/unit") |
| `REPEATING_GROUP` | Child items in `extracted_group_items` | `min_items`, `max_items` | Lean–EE Relationship 1..N |

---

## 8. Missing-Value Semantics

Methodological integrity demands explicit modeling of why a field value is absent. Storing `NULL` or `""` (empty string) is ambiguous.

### 8.1 Typed Missingness Model

For every extracted field value:

```python
@dataclass(frozen=True, slots=True)
class ExtractedValueState:
    field_id: UUID
    status: ValueStatus  # PRESENT | NOT_REPORTED | NOT_APPLICABLE | UNCLEAR
    origin: ValueOrigin  # REPORTED | REVIEWER_CODED | DERIVED

    # Typed values (active only when status == PRESENT)
    text_value: str | None = None
    int_value: int | None = None
    float_value: float | None = None
    bool_value: bool | None = None
    unit_value: str | None = None
    json_value: list[str] | None = None

    # Provenance
    source_page: str | None = None
    source_section: str | None = None
    source_locator: str | None = None  # e.g. "Table 3, p. 14"
    source_quote: str | None = None    # Verbatim snippet note
    reviewer_note: str | None = None
```

### 8.2 Business Rules for Missingness

- If `status == PRESENT`: Exactly one typed value field (matching `FieldDataType`) **must be non-null**.
- If `status == NOT_REPORTED`: Typed value fields **must be null**. Means the paper authors did not provide this information.
- If `status == NOT_APPLICABLE`: Typed value fields **must be null**. Means the category is irrelevant for this study design.
- If `status == UNCLEAR`: Typed value fields may contain a tentative value, but `reviewer_note` is strongly encouraged to explain the ambiguity.
- **Completeness Impact**: Both `NOT_REPORTED` and `NOT_APPLICABLE` count as **completed assessments**, allowing the record status to reach `COMPLETE`.

---

## 9. Value Provenance Model

To prevent unverifiable extraction, every `ExtractedValue` includes lightweight source attribution metadata:

- `source_page`: Specific page number(s) in PDF/article (e.g. "p. 104-105").
- `source_section`: Section heading (e.g. "Section 4.2 Results").
- `source_locator`: Precise locator (e.g. "Table 2, row 3" or "Paragraph 4").
- `reviewer_note`: Annotations by the reviewer explaining how the value was extracted or coded.
- `source_quote` *(Optional)*: Short text snippet (optional excerpt, max 500 chars) capturing exact verbatim text.

*Completeness & Copyright Safety Rule*: `source_quote` is strictly **optional** and is **never required** for record completeness. Provenance relies primarily on `source_page`, `source_section`, `source_locator`, and `reviewer_note` to ensure reproducibility without storing copyrighted paper text.

---

## 10. Reviewer & Revision Model (Append-Only Revisions)

### 10.1 Comparison of Revision Strategies

| Criteria | Option A: Mutable Record + Audit Log | Option B: Append-Only Revisions (Chosen) |
|---|---|---|
| Architecture | UPDATE `extraction_records`, INSERT `audit_log` | INSERT new `ExtractionRevision` on save |
| Consistency with SLR Platform | Diverges from Screening (append-only decisions) and QA (append-only assessments) | 100% aligned with SLR Platform reproducibility invariants |
| Auditability | Difficult to reconstruct complete exact point-in-time form state | Trivial: query revision by `revision_index` |
| Point-in-Time Reproducibility | Partial | Absolute |
| **Recommendation** | ❌ Reject | ✅ **Adopt Option B** |

### 10.2 Revision Data Structure

```python
class ExtractionRecord(BaseModel):
    record_id: UUID
    project_id: str
    publication_id: UUID
    template_id: UUID
    template_version: str
    current_status: ExtractionCompletenessStatus
    created_at: datetime
    updated_at: datetime


class ExtractionRevision(BaseModel):
    revision_id: UUID
    record_id: UUID
    project_id: str
    publication_id: UUID
    revision_index: int  # 1, 2, 3...
    reviewer_id: str
    completeness_status: ExtractionCompletenessStatus
    created_at: datetime
    publication_values: list[ExtractedValueState]
    group_items: list[ExtractedGroupItemState]
```

---

## 11. Publication-Level vs. Relationship-Level Model

A critical methodological boundary separates study-wide metadata from entity-specific findings:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      PUBLICATION-LEVEL SCOPE                            │
│  • E1: Publication Identity & Metadata                                  │
│  • E2: Study Context (Country, Industry, Process)                       │
│  • E3: Study Type & Method                                              │
│  • E12: Main Study Conclusions                                          │
│  • E13: Study Limitations                                               │
│  • E14: Research Gaps & Future Directions                               │
└─────────────────────────────────────────────────────────────────────────┘
                                   │ 1:N
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                RELATIONSHIP-LEVEL SCOPE (Repeating Group)               │
│  • E4: Lean Practice / Tool (e.g. SMED vs 5S)                           │
│  • E5: Application Scope & Implementation Level                         │
│  • E6: Energy Effect / Indicator                                        │
│  • E7: Energy Measurement Method & Units                                │
│  • E8: Effect Magnitude & Direction (+12%, -5 kWh/unit)                 │
│  • E9: Evidence Character (Empirical vs Postulated)                     │
│  • E10: Lean–EE Impact Mechanism                                        │
│  • E11: Moderating Conditions & Context Factors                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 12. Multiple Lean–EE Relationships Solution (1:N)

### 12.1 Problem Analysis

If Publication A investigates SMED (reducing machine setup energy) **and** 5S (reducing waste heat from idle equipment), collapsing these into publication-level fields loses the causal link between SMED and setup energy.

### 12.2 Structural Architecture

- A template defines `repeating_groups` (e.g. `group_key="lean_ee_relationship"`).
- Each group has a definition: `name="Lean–EE Relationship"`, `min_items=1`, `max_items=50`.
- The group contains its own child `field_definitions` (E4–E11).
- In an `ExtractionRevision`, group items are stored as `ExtractedGroupItem`:
  - `group_item_id: UUID`
  - `group_key: str`
  - `item_index: int` (1, 2, 3...)
  - `values: list[ExtractedValueState]` (field values scoped to this specific relationship)

---

## 13. Source-Reported vs. Reviewer-Coded Evidence Distinction

To preserve scientific rigor, every field value tracks `value_origin`:

1. `REPORTED`: Direct verbatim or quantitative facts stated by study authors (e.g. "Authors report a 12% reduction in electricity consumption").
2. `REVIEWER_CODED`: Categorization applied by the reviewer during extraction (e.g. Reviewer maps "setup time reduction" to standard taxonomy code `SMED`).

*Scope Note*: Derived or calculated values (`DERIVED`) belong to Phase 10 (Evidence Synthesis) and are excluded from the active Phase 9 MVP. Phase 9 focuses strictly on separating author-reported evidence from reviewer-coded classification.

---

## 14. Multi-Level Validation Engine

Validation occurs across 4 tiers:

1. **Field-Level Validation**:
   - `TEXT` / `LONG_TEXT`: Min/max length, regex matching.
   - `INTEGER` / `DECIMAL`: Range bounds (`min_value <= x <= max_value`).
   - `ENUM` / `MULTI_ENUM`: Membership in controlled vocabulary.
   - `NUMBER_WITH_UNIT`: Value numeric check + unit membership check.
2. **Value Missingness Consistency**:
   - If `status == PRESENT`, typed value field must not be null.
   - If `status in (NOT_REPORTED, NOT_APPLICABLE)`, typed value fields must be null.
3. **Record-Level Completeness**:
   - Every required publication-level field must have a valid value state (`PRESENT`, `NOT_REPORTED`, or `NOT_APPLICABLE`).
4. **Repeating Group Validation**:
   - Group item count must satisfy `min_items <= count <= max_items`.
   - Every item within a group must validate its required child fields.

---

## 15. Completeness Model

```python
class ExtractionCompletenessStatus(StrEnum):
    NOT_STARTED = "not_started"      # No extraction record / revision exists
    IN_PROGRESS = "in_progress"      # Saved draft with unfulfilled required fields
    COMPLETE = "complete"            # All required fields satisfied (values or conscious missingness)
    NEEDS_REVIEW = "needs_review"    # Flagged for secondary check / audit
```

### Completion Logic

A record is `COMPLETE` if and only if:
1. All required publication-level fields have `status != None`.
2. All repeating groups have `count >= min_items`.
3. All required fields within every repeating group item have `status != None`.
4. Zero validation errors exist.

*Note*: Selecting `NOT_REPORTED` or `NOT_APPLICABLE` for a required field **satisfies the requirement** because the reviewer has consciously evaluated the field.

---

## 16. Controlled Vocabularies & Extensibility

Templates specify controlled vocabularies directly in field definitions:

```json
{
  "field_key": "lean_practice",
  "data_type": "enum",
  "allowed_values": [
    "5S", "TPM", "VSM", "Kaizen", "SMED", "JIT", "Kanban",
    "Standardized_Work", "Poka_Yoke", "Heijunka", "Cellular_Manufacturing", "Other"
  ],
  "allow_custom_text": true
}
```

- If `allow_custom_text=True` and the user selects `"Other"`, an auxiliary text input is activated.
- Controlled vocabularies are versioned inside the `ExtractionTemplateVersion`.

---

## 17. Units & Quantitative Value Model

For quantitative measurements (e.g. E7/E8 energy effects), the `NUMBER_WITH_UNIT` data type provides structured storage:

```python
@dataclass(frozen=True, slots=True)
class QuantitativeValue:
    numeric_value: float | None
    unit: str | None
    measurement_type: str | None  # ABSOLUTE | PERCENTAGE | SPECIFIC_INTENSITY
```

Supported energy units in Lean Energy v1 seed:
- **Absolute**: `kWh`, `MWh`, `GJ`, `MJ`, `therms`, `m3_gas`
- **Relative / Percentage**: `%_reduction`, `%_improvement`
- **Specific Intensity**: `kWh/unit`, `kWh/kg`, `kWh/m2`, `MJ/ton`

---

## 18. Eligibility Contract & Workflow Integration

### 18.1 Pipeline Funnel Position

```
Working Collection ➔ Normalization ➔ Deduplication ➔ Screening (T&A + Full-Text) ➔ Quality Assessment ➔ DATA EXTRACTION
```

### 18.2 Entry Eligibility Rules

A publication `pub_id` in project `project_id` is eligible for Data Extraction if:
1. **Screening Gate**:
   - Single-reviewer mode: Reviewer's latest `FULL_TEXT` decision outcome is `INCLUDE`.
   - Multi-reviewer mode: `ProjectScreeningOutcome(FULL_TEXT)` is `AGREEMENT` or `RESOLVED` with outcome `INCLUDE`.
2. **Quality Assessment Gate**:
   - If QA is configured for the project: A `QualityAssessment` record exists for `pub_id`. *(Note: Low QA score does NOT automatically exclude a study unless configured by project policy; QA completion is the gate).*
   - If QA is not configured/bypassed for the project: Screening `INCLUDE` outcome is sufficient.

---

## 19. Extraction Workspace UX Design

The workspace provides an intuitive, split-pane layout designed for high-density scholarly data entry:

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│  Data Extraction Workspace  —  Project: Lean-EE SLR 2026                                         │
│  Publication: Smith et al. (2024) "Energy reduction via SMED in automotive stamping"             │
├────────────────────────────────────────┬─────────────────────────────────────────────────────────┤
│ ◄ BACK TO QUEUE    Status: IN_PROGRESS │  EXTRACTION FORM (Template: Lean Energy v1.0.0)         │
├────────────────────────────────────────┼─────────────────────────────────────────────────────────┤
│ PUBLICATION METADATA                   │ ▼ SECTION 1: STUDY CONTEXT & METHODOLOGY                │
│ Title: Energy reduction via SMED...    │   E2. Country / Region: [ Germany             ▼] (PRESENT)  │
│ Authors: J. Smith, M. Weber            │   E2. Industry Sector:  [ Automotive          ▼] (PRESENT)  │
│ Year: 2024                             │   E3. Study Method:    [ Empirical Case Study ▼] (PRESENT)  │
│ Source: J. Clean. Prod. (DOI: 10.1016) │                                                         │
│                                        │ ▼ SECTION 2: LEAN–EE RELATIONSHIPS (1:N REPEATING GROUP) │
│ ────────────────────────────────────── │   ┌─ Relationship #1 ─────────────────────────────────┐ │
│ EXTRACTION PROGRESS                    │   │ E4. Lean Practice:   [ SMED               ▼]      │ │
│ • Publication Context: 100% Complete   │   │ E6. Energy Effect:   [ Peak Demand Power   ▼]      │ │
│ • Relationships Extracted: 2           │   │ E8. Effect Size:     [ -15.2 ] Unit: [ %   ▼]      │ │
│ • Record Status: [ IN_PROGRESS  ▼]     │   │ E9. Evidence Type:   [ Empirically Measured ▼]     │ │
│                                        │   │ E10. Mechanism:      [ Reduced idle heating during │ │
│ QUICK JUMP                             │   │                       die changeover ]            │ │
│ [1. Context]  [2. Relationships]       │   │ Source Locator:      [ Section 4.1, Table 2, p.8 ] │ │
│ [3. Conclusions & Limitations]         │   └───────────────────────────────────────────────────┘ │
│                                        │   [ + Add Another Lean–EE Relationship ]                │
│                                        │                                                         │
│                                        │ ▼ SECTION 3: CONCLUSIONS & OVERALL FINDINGS             │
│                                        │   E12. Main Conclusions: [ text area... ]              │
│                                        │   E13. Limitations:      [ NOT_REPORTED  ▼]            │
│                                        │                                                         │
│                                        │ [ 💾 Save Draft ]               [ ✔ Complete Extraction ]│
└────────────────────────────────────────┴─────────────────────────────────────────────────────────┘
```

---

## 20. Form View UX

- **Section Accordions**: Organizes long templates into collapsable thematic sections.
- **Status Toggles**: Every field has an inline status selector: `[PRESENT | NOT_REPORTED | NOT_APPLICABLE | UNCLEAR]`.
- **Dynamic Input Activation**: Input fields disable/enable dynamically based on the selected `ValueStatus`.
- **Inline Provenance Drawer**: Clicking a location icon `📌` expands fields for `source_page`, `source_locator`, `source_quote`, and `reviewer_note`.
- **Repeating Group Manager**: Add/duplicate/remove controls for Lean–EE relationship sub-cards.

---

## 21. Table View UX (Dual-View Strategy)

To satisfy the tabular view requirement, Phase 9 provides two complementary table views:

1. **Publication Summary Table**:
   - Columns: Publication, Authors, Year, Extraction Status, Reviewer, Relationship Count, Actions.
   - Purpose: Overview of extraction progress across the study collection.
2. **Relationship Comparison Matrix**:
   - Columns: Publication, Lean Practice (E4), Energy Effect (E6), Effect Size (E8), Evidence Character (E9), Mechanism (E10), Industry (E2).
   - Purpose: Cross-study analysis of all extracted Lean–EE relationships in a single flat grid.

---

## 22. Progress Reporting Model

`ExtractionProgressSummary` read model:

```python
@dataclass(frozen=True, slots=True)
class ExtractionProgressSummary:
    project_id: str
    total_eligible_publications: int
    not_started_count: int
    in_progress_count: int
    complete_count: int
    needs_review_count: int
    total_relationships_extracted: int
    completion_rate: float  # complete_count / total_eligible_publications
```

---

## 23. REST API Specification

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/extraction-templates` | List available extraction templates in global catalog |
| `GET` | `/api/v1/extraction-templates/{template_id}/versions/{version}` | Get specific template version definition |
| `GET` | `/api/v1/projects/{project_id}/extraction/configuration` | Get project's active extraction configuration |
| `PUT` | `/api/v1/projects/{project_id}/extraction/configuration` | Set/update project's active template configuration |
| `GET` | `/api/v1/projects/{project_id}/extraction/progress` | Get extraction progress summary metrics |
| `GET` | `/api/v1/projects/{project_id}/extraction/records` | List eligible publications with extraction status |
| `GET` | `/api/v1/projects/{project_id}/extraction/records/{publication_id}` | Get latest extraction record & values for publication |
| `POST` | `/api/v1/projects/{project_id}/extraction/records/{publication_id}/revisions` | Submit a new extraction revision (Save Draft / Complete) |
| `GET` | `/api/v1/projects/{project_id}/extraction/records/{publication_id}/history` | Get append-only revision history log |
| `GET` | `/api/v1/projects/{project_id}/extraction/export` | Download structured dataset (CSV / JSON) |

---

## 24. Relational SQLite Schema & DDL

```sql
-- Migration: 0018_data_extraction.sql

-- 1. Global Template Catalog
CREATE TABLE extraction_templates (
    template_id         TEXT PRIMARY KEY,
    name                TEXT NOT NULL,
    description         TEXT,
    created_at          TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 2. Template Versions (Immutable definitions)
CREATE TABLE extraction_template_versions (
    template_id         TEXT NOT NULL REFERENCES extraction_templates(template_id) ON DELETE CASCADE,
    version             TEXT NOT NULL,
    description         TEXT,
    is_active           INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    is_published        INTEGER NOT NULL DEFAULT 1 CHECK (is_published IN (0, 1)),
    schema_json         TEXT NOT NULL, -- Full structural JSON definition backup
    created_at          TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (template_id, version)
);

-- 3. Project Extraction Configuration
CREATE TABLE project_extraction_configurations (
    project_id          TEXT PRIMARY KEY REFERENCES projects(project_id) ON DELETE CASCADE,
    template_id         TEXT NOT NULL,
    template_version    TEXT NOT NULL,
    configured_at       TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (template_id, template_version) REFERENCES extraction_template_versions(template_id, version)
);

-- 4. Extraction Records (Header per publication/project)
CREATE TABLE extraction_records (
    record_id           TEXT PRIMARY KEY,
    project_id          TEXT NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
    publication_id      TEXT NOT NULL,
    template_id         TEXT NOT NULL,
    template_version    TEXT NOT NULL,
    current_status      TEXT NOT NULL CHECK (current_status IN ('not_started', 'in_progress', 'complete', 'needs_review')),
    created_at          TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_extraction_records_pub UNIQUE (project_id, publication_id)
);

-- 5. Append-Only Extraction Revisions
CREATE TABLE extraction_revisions (
    revision_id         TEXT PRIMARY KEY,
    record_id           TEXT NOT NULL REFERENCES extraction_records(record_id) ON DELETE CASCADE,
    project_id          TEXT NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
    publication_id      TEXT NOT NULL,
    revision_index      INTEGER NOT NULL CHECK (revision_index >= 1),
    reviewer_id         TEXT NOT NULL CHECK (LENGTH(TRIM(reviewer_id)) > 0),
    completeness_status TEXT NOT NULL CHECK (completeness_status IN ('in_progress', 'complete', 'needs_review')),
    created_at          TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_extraction_revisions_seq UNIQUE (record_id, revision_index)
);

-- 6. Extracted Field Values (Normalized EAV for Publication-Level & Group-Level Fields)
CREATE TABLE extracted_values (
    value_id            TEXT PRIMARY KEY,
    revision_id         TEXT NOT NULL REFERENCES extraction_revisions(revision_id) ON DELETE CASCADE,
    group_item_id       TEXT, -- NULL for publication-level fields; FK to extracted_group_items for repeating groups
    field_key           TEXT NOT NULL,
    status              TEXT NOT NULL CHECK (status IN ('present', 'not_reported', 'not_applicable', 'unclear')),
    origin              TEXT NOT NULL CHECK (origin IN ('reported', 'reviewer_coded')),

    -- Typed Value Storage
    text_value          TEXT,
    int_value           INTEGER,
    float_value         REAL,
    bool_value          INTEGER CHECK (bool_value IN (0, 1)),
    unit_value          TEXT,
    json_value          TEXT, -- Used for multi_enum arrays

    -- Provenance Metadata
    source_page         TEXT,
    source_section      TEXT,
    source_locator      TEXT,
    source_quote        TEXT,
    reviewer_note       TEXT
);

-- 7. Extracted Group Items (1:N Repeating Group Instances)
CREATE TABLE extracted_group_items (
    group_item_id       TEXT PRIMARY KEY,
    revision_id         TEXT NOT NULL REFERENCES extraction_revisions(revision_id) ON DELETE CASCADE,
    group_key           TEXT NOT NULL,
    item_index          INTEGER NOT NULL CHECK (item_index >= 1),
    created_at          TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_extracted_group_items_seq UNIQUE (revision_id, group_key, item_index)
);

-- Indexes for Fast Querying
CREATE INDEX idx_extraction_records_project ON extraction_records(project_id, current_status);
CREATE INDEX idx_extraction_revisions_lookup ON extraction_revisions(project_id, publication_id, revision_index DESC);
CREATE INDEX idx_extracted_values_lookup ON extracted_values(revision_id, field_key);
CREATE INDEX idx_extracted_values_synthesis ON extracted_values(field_key, status) WHERE status = 'present';
CREATE INDEX idx_extracted_group_items_lookup ON extracted_group_items(revision_id, group_key);
```

---

## 25. JSON vs. Relational Values Decision

### 25.1 Options Analysis

- **Option A (Pure JSON document per revision)**: Fast to save/load UI forms, but terrible for Phase 10 Synthesis. SQL queries for "all SMED practices with >10% energy reduction" require SQLite `json_extract()` with poor index performance.
- **Option B (Pure EAV row-per-value)**: Highly queryable, but can be verbose for simple forms.
- **Option C (Hybrid: Normalized EAV relational values + Revisions + JSON schema definition)**: Extracted values and group items are stored as relational EAV rows linked to immutable revisions. Template schema is JSON.

### 25.2 Recommendation

**Adopt Option C (Hybrid Normalized EAV)**.
- **Why**: Phase 10 (Evidence Synthesis) requires querying structured fields directly across hundreds of studies. Storing values in normalized `extracted_values` and `extracted_group_items` tables enables high-performance SQL indexing and aggregation, while preserving exact UI form fidelity via revision linking.

---

## 26. Phase 10 Output & Read Contract

Phase 9 exposes clean, optimized read models for Phase 10 (Evidence Synthesis):

```python
@dataclass(frozen=True, slots=True)
class PublicationExtractionReadModel:
    project_id: str
    publication_id: UUID
    title: str
    authors: str
    publication_year: int | None
    completeness_status: ExtractionCompletenessStatus
    publication_values: dict[str, ExtractedValueState]
    relationships: list[RelationshipExtractionReadModel]


@dataclass(frozen=True, slots=True)
class RelationshipExtractionReadModel:
    relationship_id: UUID
    item_index: int
    lean_practice: str | None          # E4
    application_scope: str | None      # E5
    energy_effect: str | None          # E6
    measurement_method: str | None     # E7
    effect_magnitude: float | None     # E8 numeric
    effect_unit: str | None            # E8 unit
    evidence_character: str | None     # E9
    impact_mechanism: str | None       # E10
    moderating_conditions: str | None  # E11
    values: dict[str, ExtractedValueState]
```

Phase 10 can consume this contract directly without knowing anything about Phase 9 UI form layouts or SQLite migration history.

---

## 27. Exportable Structured Datasets

Phase 9 includes built-in dataset export functionality generating two decoupled CSV/JSON artifacts:

1. **`publications_dataset.csv`**: One row per publication containing E1–E3, E12–E14, extraction status, and reviewer ID.
2. **`relationships_dataset.csv`**: One row per extracted Lean–EE relationship containing publication ID, E4–E11 relationship attributes, magnitude, units, and provenance notes.

*Decoupling Rationale*: Exporting separate publication and relationship datasets prevents 1:N data duplication while remaining compatible with R, Python (Pandas), Excel, and SPSS.

---

## 28. Template Immutability & Lifecycle

```
[ Draft Template ] ➔ [ Publish Version v1.0.0 ] ➔ [ Active for Project Selection ]
                                                         │
                                                         ▼ (Project extracts data)
                                              [ FROZEN & IMMUTABLE ]
                                                         │
                                                         ▼ (Schema change required)
                                           [ Create & Publish Version v2.0.0 ]
```

---

## 29. Project Configuration

Projects bind to an extraction template version via `project_extraction_configurations`:
- Projects can select any active, published template version from the catalog.
- Once configured, all extractions in that project use the configured `(template_id, version)`.

---

## 30. Lean Energy Data Extraction v1 Seed Design

The seed catalog template `lean_energy` version `1.0.0` will be registered as the baseline production template.

- **Template Key**: `lean_energy`
- **Version**: `1.0.0`
- **Name**: `Lean Energy Data Extraction Template`
- **Description**: `Standardized template for extracting Lean Management practices, energy efficiency effects, impact mechanisms, and contextual conditions per SLR Protocol Chapter 10.`

---

## 31. Exact E1–E14 Field Mapping

Detailed definition of the 14 protocol fields for Lean Energy v1:

| Code | Field Name | Scope | Proposed Field Type | Statuses Allowed | Repeatable? | Provenance |
|---|---|---|---|---|---|---|
| **E1** | Publication Identity | Publication | `SYSTEM_BOUND` (Derived from `publication_id` & publication metadata) | `PRESENT` (System) | No | Auto |
| **E2** | Study Context | Publication | `TEXT` / `ENUM` (Country, Industry) | `PRESENT`, `NOT_REPORTED`, `NOT_APPLICABLE` | No | Yes |
| **E3** | Study Type & Method | Publication | `ENUM` (Case Study, Survey, Empirical, etc.) | `PRESENT`, `NOT_REPORTED` | No | Yes |
| **E4** | Lean Practice / Tool | Relationship | `ENUM` + `TEXT` (5S, TPM, VSM, SMED, Kaizen...) | `PRESENT` | **Yes (1:N)** | Yes |
| **E5** | Lean Application Scope | Relationship | `TEXT` (Machine, Line, Plant-wide) | `PRESENT`, `NOT_REPORTED` | **Yes (1:N)** | Yes |
| **E6** | Energy Effect / Indicator | Relationship | `ENUM` (Electricity, Gas, Peak Power, Heat) | `PRESENT` | **Yes (1:N)** | Yes |
| **E7** | Measurement Method & Units| Relationship | `TEXT` / `ENUM` (Direct Metering, Utility Bill) | `PRESENT`, `NOT_REPORTED` | **Yes (1:N)** | Yes |
| **E8** | Effect Magnitude & Direction | Relationship | `NUMBER_WITH_UNIT` (Value + %, kWh, etc.) | `PRESENT`, `NOT_REPORTED`, `UNCLEAR` | **Yes (1:N)** | Yes |
| **E9** | Evidence Character | Relationship | `ENUM` (Empirical, Qualitative, Postulated...) | `PRESENT`, `NOT_REPORTED` | **Yes (1:N)** | Yes |
| **E10** | Impact Mechanism | Relationship | `LONG_TEXT` (Causal pathway description) | `PRESENT`, `NOT_REPORTED`, `UNCLEAR` | **Yes (1:N)** | Yes |
| **E11** | Moderating Conditions | Relationship | `LONG_TEXT` (Organizational/tech factors) | `PRESENT`, `NOT_REPORTED`, `NOT_APPLICABLE` | **Yes (1:N)** | Yes |
| **E12** | Main Conclusions | Publication | `LONG_TEXT` (Authors' key findings) | `PRESENT` | No | Yes |
| **E13** | Study Limitations | Publication | `LONG_TEXT` (Author-stated limitations) | `PRESENT`, `NOT_REPORTED` | No | Yes |
| **E14** | Research Gaps & Directions| Publication | `LONG_TEXT` (Future research recommendations) | `PRESENT`, `NOT_REPORTED` | No | Yes |

---

## 32. Migration & Parallel Branch Strategy

To ensure zero merge conflicts across parallel branches (`feature/screening-7.8b`, `feature/quality-assessment`):

1. **Migration Isolation**: Phase 9 will use migration `0018_data_extraction.sql`.
2. **Directory Isolation**: All backend code resides strictly in `app/domain/extraction.py`, `app/services/extraction_*.py`, `app/repositories/extraction_*.py`, and `app/api/routers/extraction.py`.
3. **Frontend Isolation**: All GUI code resides in `frontend/src/pages/DataExtractionPage.tsx` and `frontend/src/components/extraction/`.

---

## 33. Project Hard Delete Semantics

`ON DELETE CASCADE` is configured across all relational tables:

```
projects (project_id)
   ├── ON DELETE CASCADE ➔ project_extraction_configurations
   └── ON DELETE CASCADE ➔ extraction_records
                              └── ON DELETE CASCADE ➔ extraction_revisions
                                                         ├── ON DELETE CASCADE ➔ extracted_values
                                                         └── ON DELETE CASCADE ➔ extracted_group_items
```

Calling `ProjectService.hard_delete(project_id)` completely purges all extraction records, revisions, values, relationships, and project configurations in a single atomic transaction. Global template seeds remain untouched.

---

## 34. Performance & N+1 Prevention Strategy

1. **Batch Hydration**: `SqliteExtractionRepository.get_latest_revision_batch()` loads all values and repeating groups for a page of 50 publications using **3 SQL queries total** (Records query, Batch Revisions query, Batch Values/Groups query using `IN (...)`), avoiding N+1 overhead.
2. **Synthesis Indexing**: Partial index `idx_extracted_values_synthesis` on `(field_key, status) WHERE status = 'present'` supports queryability for Phase 10 synthesis without parsing UI form JSON blobs.
3. **Performance Requirement**:
   - Relationally queryable structure.
   - Phase 10 does not parse UI JSON blobs.
   - Indexed for expected synthesis queries.
   - Zero N+1 query patterns across queue, workspace, and exports.
   - Formal performance benchmarks to be executed during integration testing.

---

## 35. Comprehensive Test Strategy

- **Domain Tests** (`tests/unit/domain/test_extraction.py`):
  - Template structural validation, field type checking, missingness state rules, repeating group bounds, value origin tracking.
- **Repository Tests** (`tests/unit/repositories/test_extraction_repository.py`):
  - DDL creation, CRUD, append-only revision incrementing, batch hydration, project cascade deletion.
- **Service Tests** (`tests/unit/services/test_extraction_service.py`):
  - Revision submission, validation error propagation, completeness calculation, progress aggregation.
- **API Tests** (`tests/integration/api/test_extraction_api.py`):
  - Endpoint contracts, REST DTO validation, JSON/CSV dataset export, HTTP 404/422/409 handling.
- **Frontend GUI Tests** (`frontend/tests/DataExtraction.test.tsx`):
  - Workspace rendering, accordion navigation, inline provenance drawer, 1:N relationship add/remove, save draft, mark complete.

---

## 36. Logical Implementation Increments

Phase 9 is structured into 8 independent, reviewable increments:

- **9.1 Domain Model & Value System**: `ExtractionTemplate`, `ExtractionFieldDefinition`, `ExtractedValue`, `ValueStatus`, `ValueOrigin`, `ExtractionRevision` domain models & validation rules.
- **9.2 Persistence & Template Catalog**: DDL migration `0018`, `SqliteExtractionTemplateRepository`, `SqliteExtractionRepository`, append-only revision storage.
- **9.3 Project Configuration & Eligibility**: `ProjectExtractionConfiguration`, `ExtractionEligibilityService` linking Screening/QA gates to Extraction.
- **9.4 Execution Backend & Validation Service**: `ExtractionExecutionService` handling revision submission, validation checks, completeness calculation, and revision history.
- **9.5 Form-Based Extraction Workspace GUI**: `DataExtractionPage`, form accordions, field status selectors, inline provenance drawers, 1:N relationship manager.
- **9.6 Tabular View & Progress Reporting**: Publication Summary Table, Cross-Study Relationship Matrix, progress bar and summary cards.
- **9.7 Lean Energy Extraction v1 Template Seed**: Idempotent production catalog seed for Lean Energy v1 (E1–E14).
- **9.8 Structured Dataset Export & Phase 10 Read Contract**: CSV/JSON dataset export endpoints, `PublicationExtractionReadModel`, integration tests, and release documentation.

---

## 37. Optimal Implementation Order

```
9.1 Domain Model ➔ 9.2 Persistence ➔ 9.3 Config & Eligibility ➔ 9.4 Execution Backend
                                                                         │
9.8 Dataset Export & Phase 10 Contract ◄─ 9.7 Lean Energy Seed ◄─ 9.6 Table View & Progress ◄─ 9.5 Workspace GUI
```

---

## 38. Target Files & Module Architecture

### New Files

- `app/domain/extraction.py`
- `app/repositories/extraction_repository.py`
- `app/repositories/extraction_template_repository.py`
- `app/services/extraction_execution_service.py`
- `app/services/extraction_eligibility_service.py`
- `app/api/dto/extraction.py`
- `app/api/routers/extraction.py`
- `migrations/0018_data_extraction.sql`
- `frontend/src/pages/DataExtractionPage.tsx`
- `frontend/src/components/extraction/ExtractionFormView.tsx`
- `frontend/src/components/extraction/ExtractionTableView.tsx`
- `frontend/src/components/extraction/RelationshipManager.tsx`
- `frontend/src/components/extraction/ProvenanceDrawer.tsx`
- `frontend/src/api/extractionApi.ts`
- `tests/unit/domain/test_extraction.py`
- `tests/unit/repositories/test_extraction_repository.py`
- `tests/unit/services/test_extraction_service.py`
- `tests/integration/api/test_extraction_api.py`

### Modified Files (Minimal Integration Boundaries)

- `app/main.py` (Register `extraction` API router)
- `frontend/src/App.tsx` (Add Data Extraction route)
- `frontend/src/components/layout/Navigation.tsx` (Enable Data Extraction navigation item)
- `app/services/project_deletion_service.py` (Add extraction tables to hard delete transaction)

---

## 39. Architectural Risk Matrix & Mitigations

| Risk | Likelihood | Impact | Mitigation Strategy |
|---|---|---|---|
| **EAV Performance Overhead** | Medium | High | Index `extracted_values(revision_id, field_key)` and `(field_key, status)`; use batch hydration for lists (3 SQL queries max). |
| **Complex 1:N Relationship UI** | High | Medium | Provide clean card-based repeating group manager with add/duplicate/remove buttons and collapse/expand states. |
| **Schema Evolution Stagnation** | Medium | High | Enforce strict template version immutability (`v1.0.0`). New fields spawn `v2.0.0`; historical data remains locked to `v1.0.0`. |
| **Ambiguous Missing Data** | High | High | Require explicit `ValueStatus` (`PRESENT`, `NOT_REPORTED`, `NOT_APPLICABLE`). Prevent null string ambiguity. |
| **Over-engineered Template Builder** | Medium | Medium | Defer Template Builder GUI to post-MVP. Seed templates via JSON/Python catalog files in MVP. |

---

## 40. Integration Risks (Phases 7 / 8 / 10)

1. **Screening (Phase 7) Integration**:
   - *Risk*: Screening outcomes might change after data extraction has started.
   - *Mitigation*: If a study's screening outcome changes from `INCLUDE` to `EXCLUDE`, its extraction record status is flagged as `NEEDS_REVIEW` or hidden from active queue, but historical revisions are preserved.
2. **Quality Assessment (Phase 8) Integration**:
   - *Risk*: QA branch (`feature/quality-assessment`) is currently separate from main development.
   - *Mitigation*: Extraction eligibility checks whether QA configuration exists; if not, it gracefully degrades to checking Screening outcome only.
3. **Evidence Synthesis (Phase 10) Integration**:
   - *Risk*: Phase 10 might require complex JSON parsing if extraction data is un-normalized.
   - *Mitigation*: Extracted values are stored in normalized relational EAV format, exposing `PublicationExtractionReadModel` and `RelationshipExtractionReadModel` for direct SQL synthesis queries.

---

## 41. Explicit OUT OF SCOPE List for Phase 9

To prevent scope creep, the following capabilities are explicitly **DEFERRED to future phases**:

- ❌ **Evidence Synthesis & Meta-Analysis** (Phase 10)
- ❌ **Automatic AI Article Data Extraction / LLM Parsing** (Phase 15)
- ❌ **Graphical Template Builder GUI** (Post-MVP Phase 9 extension)
- ❌ **Multi-Reviewer Dual-Extraction Reconciliation Workflow** (Post-MVP extension)
- ❌ **Full Copyrighted PDF Document Storage / Reader** (Out of platform scope)
- ❌ **Automated Cross-Unit Conversion Engine** (Phase 10 / 12)
- ❌ **PRISMA Diagram Generation** (Phase 12 Reporting)

---

## 42. Final Architectural Verification (A–H)

| Verification Question | Status | Architectural Justification |
|---|---|---|
| **A. Is the proposed Data Extraction framework domain-agnostic?** | ✅ **YES** | Core framework executes arbitrary versioned JSON/relational templates with zero hardcoded Lean/Energy logic. |
| **B. Are Lean Energy E1–E14 fields seed data rather than hardcoded domain logic?** | ✅ **YES** | E1–E14 fields are defined entirely in `lean_energy_v1` catalog template definition. |
| **C. Can a single publication have multiple independent Lean–EE relationships?** | ✅ **YES** | Supported natively via `REPEATING_GROUP` field type and `extracted_group_items` child tables (1:N). |
| **D. Can reported evidence be distinguished from reviewer interpretation?** | ✅ **YES** | Every extracted value tracks `value_origin` (`REPORTED` vs `REVIEWER_CODED` vs `DERIVED`). |
| **E. Is NOT_REPORTED distinguished from NOT_APPLICABLE and unassessed empty fields?** | ✅ **YES** | Explicit `ValueStatus` enum (`PRESENT`, `NOT_REPORTED`, `NOT_APPLICABLE`, `UNCLEAR`) separates missingness reasons. |
| **F. Does template v1 remain historically interpretable after creating v2?** | ✅ **YES** | Template versions are strictly immutable. Records reference exact `(template_id, version)` tuple. |
| **G. Can Phase 10 query extracted data efficiently without parsing UI forms?** | ✅ **YES** | Values are stored in normalized EAV relational tables (`extracted_values`, `extracted_group_items`) with synthesis indexes. |
| **H. Does Phase 9 remain independent of any specific SLR research domain?** | ✅ **YES** | The entire engine, API, database schema, and GUI are 100% universal and template-driven. |

---

> [!NOTE]
> **ARCHITECTURE PLAN COMPLETE — DO NOT IMPLEMENT**
> This design plan is frozen and ready for user review. No code, migrations, commits, or branch modifications have been made.
