CREATE TABLE IF NOT EXISTS import_source_records (
    project_id TEXT NOT NULL,
    source_record_id TEXT NOT NULL,
    import_id TEXT NOT NULL,
    source_filename TEXT,
    source_file_hash TEXT,
    source_record_index INTEGER NOT NULL,
    title TEXT NOT NULL,
    publication_year INTEGER,
    original_doi TEXT,
    normalized_doi TEXT,
    authors_json TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(authors_json)),
    document_type TEXT,
    provenance_json TEXT NOT NULL CHECK (json_valid(provenance_json)),
    canonical_publication_id TEXT,
    duplicate_match_type TEXT,
    duplicate_match_reason TEXT,
    duplicate_candidate_group_id TEXT,
    recovery_status TEXT NOT NULL DEFAULT 'not_needed',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (project_id, source_record_id),
    UNIQUE (project_id, import_id, source_record_index)
);

CREATE INDEX IF NOT EXISTS idx_import_source_records_project
    ON import_source_records(project_id);
CREATE INDEX IF NOT EXISTS idx_import_source_records_import
    ON import_source_records(project_id, import_id);
CREATE INDEX IF NOT EXISTS idx_import_source_records_canonical
    ON import_source_records(project_id, canonical_publication_id);
CREATE INDEX IF NOT EXISTS idx_import_source_records_doi
    ON import_source_records(project_id, normalized_doi);
CREATE INDEX IF NOT EXISTS idx_import_source_records_file_hash
    ON import_source_records(project_id, source_file_hash);
