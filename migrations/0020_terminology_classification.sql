-- Migration 0020: Terminology Classification Persistence (Task 10.2)

CREATE TABLE IF NOT EXISTS synthesis_lean_categories (
    project_id TEXT NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
    category_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    display_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (project_id, category_id)
);

CREATE TABLE IF NOT EXISTS synthesis_energy_categories (
    project_id TEXT NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
    category_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    display_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (project_id, category_id)
);

CREATE TABLE IF NOT EXISTS synthesis_term_mappings (
    mapping_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
    term_type TEXT NOT NULL CHECK (term_type IN ('lean_practice', 'energy_effect')),
    source_value TEXT NOT NULL,
    analytical_category_id TEXT NOT NULL,
    approval_state TEXT NOT NULL CHECK (approval_state IN ('pending', 'approved', 'rejected')),
    approved_by TEXT,
    approved_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_synthesis_term_mapping UNIQUE (project_id, term_type, source_value)
);

CREATE INDEX IF NOT EXISTS idx_synthesis_lean_categories_proj ON synthesis_lean_categories(project_id, display_order);
CREATE INDEX IF NOT EXISTS idx_synthesis_energy_categories_proj ON synthesis_energy_categories(project_id, display_order);
CREATE INDEX IF NOT EXISTS idx_synthesis_term_mappings_lookup ON synthesis_term_mappings(project_id, term_type);
