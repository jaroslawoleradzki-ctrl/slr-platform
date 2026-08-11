-- Migration 0012: Full Text workflow metadata and immutable exclusion-reason links.

CREATE TABLE IF NOT EXISTS full_text_availability (
    project_id TEXT NOT NULL,
    publication_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('unknown', 'to_retrieve', 'available', 'unavailable')),
    external_url TEXT,
    notes TEXT,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (project_id, publication_id)
);

CREATE TABLE IF NOT EXISTS screening_decision_exclusion_reasons (
    decision_id TEXT NOT NULL,
    criterion_id TEXT NOT NULL,
    PRIMARY KEY (decision_id, criterion_id),
    FOREIGN KEY (decision_id, criterion_id)
        REFERENCES screening_criterion_assessments(decision_id, criterion_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_screening_exclusion_reasons_criterion
    ON screening_decision_exclusion_reasons (criterion_id, decision_id);
