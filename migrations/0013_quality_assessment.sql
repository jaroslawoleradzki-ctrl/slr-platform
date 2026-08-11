-- Migration 0013: Quality Assessment Domain Tables

-- 1. Global catalog of quality assessment tools (e.g. CASP-inspired, JBI, MMAT)
CREATE TABLE IF NOT EXISTS quality_assessment_tools (
    tool_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    created_at TEXT NOT NULL
);

-- 2. Versioned quality assessment templates (Content immutable per version; is_active mutable lifecycle metadata)
CREATE TABLE IF NOT EXISTS quality_assessment_templates (
    template_id TEXT PRIMARY KEY,
    tool_id TEXT NOT NULL REFERENCES quality_assessment_tools(tool_id) ON DELETE RESTRICT,
    template_key TEXT NOT NULL,
    name TEXT NOT NULL,
    version INTEGER NOT NULL CHECK (version > 0),
    description TEXT,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at TEXT NOT NULL,
    UNIQUE(tool_id, template_key, version)
);

-- 3. Criteria / questions for a specific template version (Content immutable)
CREATE TABLE IF NOT EXISTS quality_assessment_template_criteria (
    criterion_id TEXT PRIMARY KEY,
    template_id TEXT NOT NULL REFERENCES quality_assessment_templates(template_id) ON DELETE CASCADE,
    display_order INTEGER NOT NULL CHECK (display_order >= 0),
    question TEXT NOT NULL,
    guidance TEXT,
    is_required INTEGER NOT NULL DEFAULT 1 CHECK (is_required IN (0, 1)),
    created_at TEXT NOT NULL,
    UNIQUE(template_id, display_order)
);

-- 4. Publication quality assessment header (Append-only history trail)
CREATE TABLE IF NOT EXISTS quality_assessments (
    assessment_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    publication_id TEXT NOT NULL,
    reviewer_id TEXT NOT NULL,
    template_id TEXT NOT NULL REFERENCES quality_assessment_templates(template_id) ON DELETE RESTRICT,
    assessed_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_qa_project_pub_rev_time
ON quality_assessments(project_id, publication_id, reviewer_id, assessed_at DESC);

-- 5. Individual criterion responses with authoritative metadata snapshots
CREATE TABLE IF NOT EXISTS quality_assessment_responses (
    response_id TEXT PRIMARY KEY,
    assessment_id TEXT NOT NULL REFERENCES quality_assessments(assessment_id) ON DELETE CASCADE,
    criterion_id TEXT NOT NULL REFERENCES quality_assessment_template_criteria(criterion_id) ON DELETE RESTRICT,
    question_snapshot TEXT NOT NULL,
    guidance_snapshot TEXT,
    is_required_snapshot INTEGER NOT NULL CHECK (is_required_snapshot IN (0, 1)),
    response_value TEXT NOT NULL CHECK (response_value IN ('YES', 'NO', 'CANNOT_DETERMINE')),
    justification TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(assessment_id, criterion_id)
);
