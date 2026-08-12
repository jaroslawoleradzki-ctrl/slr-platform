-- Phase 9.2: generic, versioned data-extraction persistence.

CREATE TABLE extraction_templates (
    template_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE extraction_template_versions (
    template_id TEXT NOT NULL REFERENCES extraction_templates(template_id) ON DELETE CASCADE,
    version TEXT NOT NULL,
    description TEXT,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    is_published INTEGER NOT NULL DEFAULT 0 CHECK (is_published IN (0, 1)),
    schema_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (template_id, version)
);

-- Schema foundation only. Configuration behaviour belongs to Phase 9.3.
CREATE TABLE project_extraction_configurations (
    project_id TEXT PRIMARY KEY REFERENCES projects(project_id) ON DELETE CASCADE,
    template_id TEXT NOT NULL,
    template_version TEXT NOT NULL,
    configured_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (template_id, template_version)
        REFERENCES extraction_template_versions(template_id, version)
);

CREATE TABLE extraction_records (
    record_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
    publication_id TEXT NOT NULL,
    template_id TEXT NOT NULL,
    template_version TEXT NOT NULL,
    current_status TEXT NOT NULL CHECK (current_status IN ('not_started', 'in_progress', 'complete', 'needs_review')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_extraction_records_pub UNIQUE (project_id, publication_id),
    FOREIGN KEY (template_id, template_version)
        REFERENCES extraction_template_versions(template_id, version)
);

CREATE TABLE extraction_revisions (
    revision_id TEXT PRIMARY KEY,
    record_id TEXT NOT NULL REFERENCES extraction_records(record_id) ON DELETE CASCADE,
    project_id TEXT NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
    publication_id TEXT NOT NULL,
    revision_index INTEGER NOT NULL CHECK (revision_index >= 1),
    reviewer_id TEXT NOT NULL CHECK (LENGTH(TRIM(reviewer_id)) > 0),
    completeness_status TEXT NOT NULL CHECK (completeness_status IN ('in_progress', 'complete', 'needs_review')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_extraction_revisions_seq UNIQUE (record_id, revision_index)
);

CREATE TABLE extracted_group_items (
    group_item_id TEXT PRIMARY KEY,
    revision_id TEXT NOT NULL REFERENCES extraction_revisions(revision_id) ON DELETE CASCADE,
    group_key TEXT NOT NULL,
    item_index INTEGER NOT NULL CHECK (item_index >= 1),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_extracted_group_items_seq UNIQUE (revision_id, group_key, item_index)
);

CREATE TABLE extracted_values (
    value_id TEXT PRIMARY KEY,
    revision_id TEXT NOT NULL REFERENCES extraction_revisions(revision_id) ON DELETE CASCADE,
    group_item_id TEXT REFERENCES extracted_group_items(group_item_id) ON DELETE CASCADE,
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
    reviewer_note TEXT
);

CREATE INDEX idx_extraction_records_project ON extraction_records(project_id, current_status);
CREATE INDEX idx_extraction_revisions_lookup ON extraction_revisions(project_id, publication_id, revision_index DESC);
CREATE INDEX idx_extracted_values_lookup ON extracted_values(revision_id, field_key);
CREATE INDEX idx_extracted_values_synthesis ON extracted_values(field_key, status) WHERE status = 'present';
CREATE INDEX idx_extracted_group_items_lookup ON extracted_group_items(revision_id, group_key);
