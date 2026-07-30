CREATE TABLE IF NOT EXISTS project_publications (
    project_id TEXT NOT NULL,
    record_id TEXT NOT NULL,
    position INTEGER NOT NULL CHECK (position >= 0),
    title TEXT NOT NULL,
    title_normalized TEXT,
    publication_year INTEGER,
    authors TEXT NOT NULL CHECK (json_valid(authors)),
    identifiers TEXT NOT NULL CHECK (json_valid(identifiers)),
    provenance TEXT NOT NULL CHECK (json_valid(provenance)),
    created_at TEXT NOT NULL,
    document TEXT NOT NULL CHECK (json_valid(document)),
    PRIMARY KEY (project_id, record_id)
);

CREATE INDEX IF NOT EXISTS idx_project_publications_project_position
    ON project_publications(project_id, position);
