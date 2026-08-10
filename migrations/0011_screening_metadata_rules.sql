-- Migration 0011: Generic metadata rules for screening criteria and auditable assessments.

ALTER TABLE screening_criteria
    ADD COLUMN evaluation_mode TEXT NOT NULL DEFAULT 'manual'
    CHECK (evaluation_mode IN ('manual', 'metadata_rule'));

ALTER TABLE screening_criteria
    ADD COLUMN metadata_rule TEXT;

ALTER TABLE screening_criterion_assessments
    ADD COLUMN evaluation_mode TEXT NOT NULL DEFAULT 'manual'
    CHECK (evaluation_mode IN ('manual', 'metadata_rule'));

ALTER TABLE screening_criterion_assessments
    ADD COLUMN metadata_rule TEXT;

ALTER TABLE screening_criterion_assessments
    ADD COLUMN evaluated_metadata_value TEXT;
