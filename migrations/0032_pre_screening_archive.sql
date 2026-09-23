-- Migration 0032: Pre-Screening Removed Records Archive
-- Provides durable, reproducible archival storage for retrieval artefacts removed during Import Review.

CREATE TABLE IF NOT EXISTS pre_screening_archive (
    archive_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    record_id TEXT NOT NULL,
    import_id TEXT,
    provider TEXT,
    title TEXT NOT NULL,
    publication_year INTEGER,
    authors TEXT NOT NULL CHECK (json_valid(authors)),
    identifiers TEXT NOT NULL CHECK (json_valid(identifiers)),
    document_type TEXT,
    language TEXT,
    provenance TEXT NOT NULL CHECK (json_valid(provenance)),
    document TEXT NOT NULL CHECK (json_valid(document)),
    removal_reason TEXT NOT NULL,
    removal_notes TEXT,
    removed_by TEXT NOT NULL DEFAULT 'default_reviewer',
    removed_at TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_pre_screening_archive_proj_rec UNIQUE (project_id, record_id)
);

CREATE INDEX IF NOT EXISTS idx_pre_screening_archive_project
    ON pre_screening_archive(project_id, import_id);

CREATE INDEX IF NOT EXISTS idx_pre_screening_archive_reason
    ON pre_screening_archive(project_id, removal_reason);

CREATE INDEX IF NOT EXISTS idx_pre_screening_archive_record
    ON pre_screening_archive(record_id);
