-- Migration 0025: Research Gap Synthesis (Task 10.6)

CREATE TABLE IF NOT EXISTS synthesis_research_gaps (
    project_id TEXT NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
    gap_id TEXT NOT NULL,
    gap_type TEXT NOT NULL CHECK (gap_type IN ('thematic', 'mechanism', 'methodological', 'contextual', 'inconsistent_evidence')),
    title TEXT NOT NULL,
    rationale TEXT NOT NULL,
    researcher_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (project_id, gap_id)
);

CREATE TABLE IF NOT EXISTS synthesis_research_gap_links (
    link_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
    gap_id TEXT NOT NULL,
    link_type TEXT NOT NULL CHECK (link_type IN ('analytical_relation', 'mechanism_pathway', 'context_factor_link')),
    target_id TEXT NOT NULL,
    group_item_id TEXT NOT NULL,
    publication_id TEXT NOT NULL,
    latest_revision_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_synthesis_research_gap_link UNIQUE (project_id, gap_id, link_type, target_id),
    CONSTRAINT fk_synthesis_research_gap_link_gap FOREIGN KEY (project_id, gap_id)
        REFERENCES synthesis_research_gaps (project_id, gap_id)
);

CREATE INDEX IF NOT EXISTS idx_synthesis_research_gaps_proj ON synthesis_research_gaps(project_id, gap_type);
CREATE INDEX IF NOT EXISTS idx_synthesis_research_gap_links_proj ON synthesis_research_gap_links(project_id, gap_id);
CREATE INDEX IF NOT EXISTS idx_synthesis_research_gap_links_target ON synthesis_research_gap_links(project_id, link_type, target_id);
CREATE INDEX IF NOT EXISTS idx_synthesis_research_gap_links_pub ON synthesis_research_gap_links(project_id, publication_id);
