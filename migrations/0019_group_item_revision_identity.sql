-- Migration 0019: Support durable group_item_id across append-only extraction revisions.

PRAGMA foreign_keys = OFF;

CREATE TABLE IF NOT EXISTS extracted_group_items_new (
    revision_id TEXT NOT NULL REFERENCES extraction_revisions(revision_id) ON DELETE CASCADE,
    group_item_id TEXT NOT NULL,
    group_key TEXT NOT NULL,
    item_index INTEGER NOT NULL CHECK (item_index >= 1),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (revision_id, group_item_id),
    CONSTRAINT uq_extracted_group_items_seq UNIQUE (revision_id, group_key, item_index)
);

INSERT OR IGNORE INTO extracted_group_items_new (revision_id, group_item_id, group_key, item_index, created_at)
SELECT revision_id, group_item_id, group_key, item_index, created_at FROM extracted_group_items;

DROP TABLE IF EXISTS extracted_group_items;

ALTER TABLE extracted_group_items_new RENAME TO extracted_group_items;

CREATE INDEX IF NOT EXISTS idx_extracted_group_items_lookup ON extracted_group_items(revision_id, group_key);
CREATE INDEX IF NOT EXISTS idx_extracted_group_items_id ON extracted_group_items(group_item_id);

CREATE TABLE IF NOT EXISTS extracted_values_new (
    value_id TEXT PRIMARY KEY,
    revision_id TEXT NOT NULL REFERENCES extraction_revisions(revision_id) ON DELETE CASCADE,
    group_item_id TEXT,
    field_key TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('present', 'not_reported', 'not_applicable', 'unclear')),
    origin TEXT NOT NULL CHECK (origin IN ('reported', 'reviewer_coded')),
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

INSERT OR IGNORE INTO extracted_values_new (
    value_id, revision_id, group_item_id, field_key, status, origin,
    text_value, int_value, float_value, bool_value, unit_value, json_value,
    source_page, source_section, source_locator, source_quote, reviewer_note
)
SELECT
    value_id, revision_id, group_item_id, field_key, status, origin,
    text_value, int_value, float_value, bool_value, unit_value, json_value,
    source_page, source_section, source_locator, source_quote, reviewer_note
FROM extracted_values;

DROP TABLE IF EXISTS extracted_values;

ALTER TABLE extracted_values_new RENAME TO extracted_values;

CREATE INDEX IF NOT EXISTS idx_extracted_values_lookup ON extracted_values(revision_id, field_key);
CREATE INDEX IF NOT EXISTS idx_extracted_values_synthesis ON extracted_values(field_key, status) WHERE status = 'present';
CREATE INDEX IF NOT EXISTS idx_extracted_values_group_lookup ON extracted_values(revision_id, group_item_id);

PRAGMA foreign_keys = ON;
