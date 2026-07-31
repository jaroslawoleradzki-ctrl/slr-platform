CREATE TABLE IF NOT EXISTS duplicate_review_decisions (
    project_id TEXT NOT NULL,
    group_id TEXT NOT NULL,
    decision TEXT NOT NULL CHECK (decision IN ('APPROVE', 'REJECT')),
    rationale TEXT,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (project_id, group_id)
);

CREATE INDEX IF NOT EXISTS idx_duplicate_review_decisions_project
    ON duplicate_review_decisions(project_id);
