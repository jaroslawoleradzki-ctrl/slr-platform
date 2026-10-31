CREATE TABLE IF NOT EXISTS import_skip_audit (
    skip_audit_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    import_id TEXT NOT NULL,
    source_filename TEXT,
    source_record_index INTEGER NOT NULL,
    source_title TEXT NOT NULL,
    source_doi TEXT,
    matched_publication_id TEXT,
    match_type TEXT NOT NULL,
    match_reason TEXT NOT NULL,
    proposed_action TEXT NOT NULL,
    review_required INTEGER NOT NULL DEFAULT 0 CHECK (review_required IN (0, 1)),
    recovery_status TEXT NOT NULL DEFAULT 'pending_review',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (project_id, import_id, source_record_index)
);

CREATE INDEX IF NOT EXISTS idx_import_skip_audit_project
    ON import_skip_audit(project_id);
CREATE INDEX IF NOT EXISTS idx_import_skip_audit_import
    ON import_skip_audit(import_id);
CREATE INDEX IF NOT EXISTS idx_import_skip_audit_match
    ON import_skip_audit(project_id, matched_publication_id);
