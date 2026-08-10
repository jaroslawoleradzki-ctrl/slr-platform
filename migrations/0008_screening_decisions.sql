-- Migration 0008: Screening Decisions and Criterion Assessments

CREATE TABLE IF NOT EXISTS screening_decisions (
    decision_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    publication_id TEXT NOT NULL,
    stage TEXT NOT NULL,
    outcome TEXT NOT NULL,
    reviewer_id TEXT NOT NULL,
    rationale TEXT,
    decided_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS screening_criterion_assessments (
    decision_id TEXT NOT NULL REFERENCES screening_decisions(decision_id) ON DELETE CASCADE,
    criterion_id TEXT NOT NULL,
    criterion_name TEXT NOT NULL,
    criterion_type TEXT NOT NULL,
    criterion_stage TEXT NOT NULL,
    criterion_is_required INTEGER NOT NULL,
    assessment_value TEXT NOT NULL,
    notes TEXT,
    PRIMARY KEY (decision_id, criterion_id)
);

CREATE INDEX IF NOT EXISTS idx_screening_decisions_lookup 
ON screening_decisions(project_id, publication_id, stage, reviewer_id, decided_at DESC);

CREATE INDEX IF NOT EXISTS idx_screening_decisions_project_stage 
ON screening_decisions(project_id, stage);

CREATE INDEX IF NOT EXISTS idx_screening_assessments_decision 
ON screening_criterion_assessments(decision_id);
