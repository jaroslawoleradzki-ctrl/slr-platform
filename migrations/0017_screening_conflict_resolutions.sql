-- Phase 7.8B: append-only conflict adjudication history.
CREATE TABLE screening_conflict_resolutions (
 resolution_id TEXT PRIMARY KEY,
 project_id TEXT NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
 publication_id TEXT NOT NULL,
 stage TEXT NOT NULL CHECK (stage IN ('title_abstract', 'full_text')),
 decision_set_key TEXT NOT NULL,
 resolved_outcome TEXT NOT NULL CHECK (resolved_outcome IN ('include', 'exclude', 'uncertain')),
 resolver_id TEXT NOT NULL,
 rationale TEXT NOT NULL CHECK (LENGTH(TRIM(rationale)) > 0),
 resolved_at TEXT NOT NULL
);
CREATE INDEX idx_conflict_resolutions_lookup ON screening_conflict_resolutions (project_id, publication_id, stage, resolved_at DESC, resolution_id DESC);
CREATE INDEX idx_conflict_resolutions_project ON screening_conflict_resolutions (project_id);
CREATE TABLE screening_conflict_resolution_decisions (
 resolution_id TEXT NOT NULL REFERENCES screening_conflict_resolutions(resolution_id) ON DELETE CASCADE,
 decision_id TEXT NOT NULL,
 reviewer_id TEXT NOT NULL,
 outcome TEXT NOT NULL CHECK (outcome IN ('include', 'exclude', 'uncertain')),
 PRIMARY KEY (resolution_id, decision_id)
);
