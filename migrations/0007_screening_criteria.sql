CREATE TABLE IF NOT EXISTS screening_criteria (
    criterion_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    criterion_type TEXT NOT NULL CHECK (criterion_type IN ('inclusion', 'exclusion')),
    screening_stage TEXT NOT NULL CHECK (screening_stage IN ('title_abstract', 'full_text', 'both')),
    display_order INTEGER NOT NULL DEFAULT 0 CHECK (display_order >= 0),
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    is_required INTEGER NOT NULL DEFAULT 1 CHECK (is_required IN (0, 1))
);

CREATE INDEX IF NOT EXISTS idx_screening_criteria_project
    ON screening_criteria(project_id, display_order, criterion_id);
