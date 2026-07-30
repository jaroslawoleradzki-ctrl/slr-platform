CREATE TABLE search_strategies (
    project_id TEXT PRIMARY KEY,
    strategy_id TEXT NOT NULL UNIQUE,
    version INTEGER NOT NULL CHECK (version >= 1),
    document TEXT NOT NULL CHECK (json_valid(document)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX idx_search_strategies_updated_at
    ON search_strategies(updated_at);
