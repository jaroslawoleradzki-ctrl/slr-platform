-- ADR-0007: persist UNASSESSED and allow NULL origin only where no value exists.
-- Existing snapshots are copied verbatim.
PRAGMA foreign_keys = OFF;
BEGIN IMMEDIATE;

CREATE TABLE extracted_values_new (
    value_id TEXT PRIMARY KEY,
    revision_id TEXT NOT NULL REFERENCES extraction_revisions(revision_id) ON DELETE CASCADE,
    group_item_id TEXT,
    field_key TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('unassessed', 'present', 'not_reported', 'not_applicable', 'unclear')),
    origin TEXT CHECK (origin IS NULL OR origin IN ('reported', 'reviewer_coded')),
    text_value TEXT,
    int_value INTEGER,
    float_value REAL,
    bool_value INTEGER CHECK (bool_value IN (0, 1)),
    unit_value TEXT,
    json_value TEXT,
    source_page TEXT,
    source_section TEXT,
    source_locator TEXT,
    source_quote TEXT,
    reviewer_note TEXT,
    FOREIGN KEY (revision_id, group_item_id) REFERENCES extracted_group_items(revision_id, group_item_id) ON DELETE CASCADE
);

INSERT INTO extracted_values_new (
    value_id, revision_id, group_item_id, field_key, status, origin,
    text_value, int_value, float_value, bool_value, unit_value, json_value,
    source_page, source_section, source_locator, source_quote, reviewer_note
)
SELECT
    value_id, revision_id, group_item_id, field_key, status, origin,
    text_value, int_value, float_value, bool_value, unit_value, json_value,
    source_page, source_section, source_locator, source_quote, reviewer_note
FROM extracted_values;

DROP TABLE extracted_values;
ALTER TABLE extracted_values_new RENAME TO extracted_values;
CREATE INDEX idx_extracted_values_lookup ON extracted_values(revision_id, field_key);
CREATE INDEX idx_extracted_values_synthesis ON extracted_values(field_key, status) WHERE status = 'present';
CREATE INDEX idx_extracted_values_group_lookup ON extracted_values(revision_id, group_item_id);

COMMIT;
PRAGMA foreign_keys = ON;
