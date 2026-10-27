-- Forward-compatible v0.7.3 recovery audit and approval storage.
-- Earlier 0034/0035 schemas are repaired non-destructively by
-- SqliteImportSourceRecordRepository._ensure_import_schema().

CREATE TABLE IF NOT EXISTS import_recovery_approvals (
    approval_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    source_record_id TEXT NOT NULL,
    reviewer_identity TEXT NOT NULL,
    decision TEXT NOT NULL CHECK (decision IN ('approved', 'rejected')),
    rationale TEXT NOT NULL,
    approved_at TEXT NOT NULL,
    recovery_executed_at TEXT,
    recovery_outcome TEXT,
    canonical_publication_id TEXT,
    UNIQUE (project_id, source_record_id)
);

CREATE TABLE IF NOT EXISTS import_recovery_audit (
    recovery_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    source_record_id TEXT NOT NULL,
    approval_id TEXT NOT NULL,
    reviewer_identity TEXT NOT NULL,
    executed_at TEXT NOT NULL,
    outcome TEXT NOT NULL,
    canonical_publication_id TEXT,
    detail TEXT,
    FOREIGN KEY (project_id, source_record_id)
        REFERENCES import_recovery_approvals(project_id, source_record_id)
);

CREATE INDEX IF NOT EXISTS idx_import_recovery_approvals_project
    ON import_recovery_approvals(project_id, decision);
CREATE INDEX IF NOT EXISTS idx_import_recovery_audit_project
    ON import_recovery_audit(project_id, executed_at);
