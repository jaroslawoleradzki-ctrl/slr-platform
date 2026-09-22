-- Migration 0031: Corpus Finalization and Screening Boundary
-- Persists immutable corpus finalization events and admitted member snapshots.

CREATE TABLE IF NOT EXISTS corpus_finalizations (
    finalization_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    finalized_by TEXT NOT NULL DEFAULT 'default_reviewer',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    source_records_count INTEGER NOT NULL,
    duplicates_removed_count INTEGER NOT NULL,
    prescreening_removed_count INTEGER NOT NULL,
    retained_count INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'finalized'
);

CREATE INDEX IF NOT EXISTS idx_corpus_finalizations_project
    ON corpus_finalizations(project_id, created_at DESC);

CREATE TABLE IF NOT EXISTS corpus_finalization_members (
    finalization_id TEXT NOT NULL REFERENCES corpus_finalizations(finalization_id) ON DELETE CASCADE,
    record_id TEXT NOT NULL,
    disposition TEXT NOT NULL,
    removal_reason TEXT,
    admitted_to_screening INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (finalization_id, record_id)
);

CREATE INDEX IF NOT EXISTS idx_corpus_finalization_members_lookup
    ON corpus_finalization_members(finalization_id, admitted_to_screening);

CREATE INDEX IF NOT EXISTS idx_corpus_finalization_members_record
    ON corpus_finalization_members(record_id);
