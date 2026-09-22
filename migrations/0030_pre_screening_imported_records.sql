-- Migration 0030: Pre-Screening Imported Records Review
-- Adds import_id and pre_screening_status to project_publications
-- Creates pre_screening_decisions table for auditable pre-screening corpus preparation removals

ALTER TABLE project_publications ADD COLUMN import_id TEXT DEFAULT NULL;
ALTER TABLE project_publications ADD COLUMN pre_screening_status TEXT NOT NULL DEFAULT 'retained';

CREATE INDEX IF NOT EXISTS idx_project_publications_import
    ON project_publications(project_id, import_id);

CREATE INDEX IF NOT EXISTS idx_project_publications_pre_screen
    ON project_publications(project_id, pre_screening_status);

CREATE TABLE IF NOT EXISTS pre_screening_decisions (
    decision_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    record_id TEXT NOT NULL,
    import_id TEXT,
    status TEXT NOT NULL CHECK (status IN ('retained', 'removed')),
    reason TEXT,
    notes TEXT,
    reviewer_id TEXT NOT NULL DEFAULT 'default_reviewer',
    decided_at TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_pre_screening_decisions_lookup
    ON pre_screening_decisions(project_id, record_id, decided_at DESC);

CREATE INDEX IF NOT EXISTS idx_pre_screening_decisions_import
    ON pre_screening_decisions(project_id, import_id);
