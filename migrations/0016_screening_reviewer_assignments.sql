CREATE TABLE screening_reviewer_assignments (
    project_id TEXT NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
    stage TEXT NOT NULL CHECK (stage IN ('title_abstract', 'full_text')),
    reviewer_id TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (project_id, stage, reviewer_id)
);

CREATE INDEX idx_screening_reviewer_assignments_active
    ON screening_reviewer_assignments (project_id, stage, is_active, reviewer_id);
