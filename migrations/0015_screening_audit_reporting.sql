-- Phase 7.7: decision-level criterion snapshot versioning and reporting lookup.

ALTER TABLE screening_decisions
    ADD COLUMN criterion_snapshot_schema_version INTEGER NOT NULL DEFAULT 1
    CHECK (criterion_snapshot_schema_version >= 1);

ALTER TABLE screening_criterion_assessments
    ADD COLUMN criterion_description TEXT;

CREATE INDEX IF NOT EXISTS idx_screening_decisions_reviewer_stage_latest
    ON screening_decisions (
        project_id,
        reviewer_id,
        stage,
        publication_id,
        decided_at DESC,
        decision_id DESC
    );
