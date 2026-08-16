export type ClassificationApprovalState = 'pending' | 'approved' | 'rejected';
export type TermType = 'lean_practice' | 'energy_effect';
export type RelationDirection = 'positive' | 'negative' | 'no_effect' | 'mixed' | 'cannot_determine';
export type EvidenceCharacter = 'empirical' | 'qualitative' | 'estimated' | 'postulated';

export interface Category {
  category_id: string;
  name: string;
  project_id: string;
  description: string | null;
  display_order: number;
}

export interface ClassifiedSourceTerm {
  project_id: string;
  term_type: TermType;
  source_value: string;
  occurrence_count: number;
  publication_count: number;
  analytical_category_id: string | null;
  analytical_category_name: string | null;
  approval_state: ClassificationApprovalState;
  approved_by: string | null;
  approved_at: string | null;
  mapping_id: string | null;
}

export interface ClassificationWorkspaceStats {
  total_lean_terms: number;
  total_energy_terms: number;
  total_terms: number;
  mapped_count: number;
  approved_count: number;
}

export interface TerminologyClassificationWorkspace {
  project_id: string;
  lean_categories: Category[];
  energy_categories: Category[];
  lean_terms: ClassifiedSourceTerm[];
  energy_terms: ClassifiedSourceTerm[];
  stats: ClassificationWorkspaceStats;
}

export interface TermMappingResponse {
  mapping_id: string;
  project_id: string;
  term_type: TermType;
  source_value: string;
  analytical_category_id: string;
  approval_state: ClassificationApprovalState;
  approved_by: string | null;
  approved_at: string | null;
}

// -------------------------------------------------------------------------
// Task 10.3: Analytical Matrix & Evidence Aggregation
// -------------------------------------------------------------------------

export interface ConvertedValue {
  transformed_value: number;
  transformed_unit: string;
  conversion_rule: string;
}

export interface MatrixCell {
  lean_category_id: string;
  lean_category_name: string;
  energy_category_id: string;
  energy_category_name: string;
  relation_count: number;
  publication_count: number;
  direction_distribution: Record<string, number>;
  evidence_character_distribution: Record<string, number>;
}

export interface SynthesisMatrix {
  project_id: string;
  lean_categories: Category[];
  energy_categories: Category[];
  cells: MatrixCell[];
  total_relations: number;
  total_publications: number;
  unclassified_relations_count: number;
}

export interface QACriterionAssessmentSummary {
  criterion_id: string;
  question_text: string;
  response_value: string;
  justification: string | null;
}

export interface QAProfileSummary {
  assessment_id: string;
  template_id: string;
  reviewer_id: string;
  criteria_assessments: QACriterionAssessmentSummary[];
}

export interface AnalyticalRelation {
  relation_id: string;
  project_id: string;
  publication_id: string;
  latest_revision_id: string;
  group_item_id: string;
  item_index: number;
  source_practice: string;
  analytical_lean_category_id: string | null;
  source_effect: string;
  analytical_energy_category_id: string | null;
  direction: RelationDirection;
  magnitude: number | null;
  original_unit: string | null;
  converted_value: ConvertedValue | null;
  evidence_character: EvidenceCharacter;
  context_summary: string | null;
  approval_state: ClassificationApprovalState;
  created_at: string;
  updated_at: string;
}

export interface AnalyticalRelationDetail {
  relation: AnalyticalRelation;
  publication_title: string | null;
  publication_year: number | null;
  source_quote: string | null;
  source_page: string | null;
  source_section: string | null;
  qa_profile: QAProfileSummary | null;
}

export interface MatrixCellDetail {
  lean_category: Category;
  energy_category: Category;
  relation_count: number;
  publication_count: number;
  direction_distribution: Record<string, number>;
  evidence_character_distribution: Record<string, number>;
  relations: AnalyticalRelationDetail[];
}

export interface MechanismPathway {
  pathway_id: string;
  project_id: string;
  analytical_relation_id: string;
  group_item_id: string;
  publication_id: string;
  latest_revision_id: string;
  source_mechanism_text: string | null;
  analytical_mechanism_category_id: string | null;
  is_review_synthesized: boolean;
  approval_state: ClassificationApprovalState;
  approved_by: string | null;
  approved_at: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface MechanismPathwayDetail {
  pathway: MechanismPathway;
  publication_title: string | null;
  publication_year: number | null;
  source_practice: string;
  source_effect: string;
  analytical_lean_category_id: string | null;
  analytical_lean_category_name: string | null;
  analytical_energy_category_id: string | null;
  analytical_energy_category_name: string | null;
  analytical_mechanism_category_name: string | null;
  direction: RelationDirection;
  evidence_character: EvidenceCharacter;
  qa_profile: QAProfileSummary | null;
}

export interface MechanismSynthesisPathway {
  lean_category_id: string;
  lean_category_name: string;
  mechanism_category_id: string;
  mechanism_category_name: string;
  energy_category_id: string;
  energy_category_name: string;
  pathway_count: number;
  publication_count: number;
  relation_count: number;
  pathways: MechanismPathwayDetail[];
}

export interface MechanismWorkspaceStats {
  total_pathways: number;
  mapped_count: number;
  unmapped_count: number;
  approved_count: number;
  total_publications: number;
}

export interface MechanismWorkspaceData {
  project_id: string;
  categories: Category[];
  pathways: MechanismPathwayDetail[];
  synthesis_chains: MechanismSynthesisPathway[];
  stats: MechanismWorkspaceStats;
}

export interface AssignMechanismCategoryRequest {
  category_id: string | null;
  is_review_synthesized?: boolean;
  notes?: string | null;
}

// -------------------------------------------------------------------------
// Task 10.5: Context & Moderating Factors
// -------------------------------------------------------------------------

export type ContextImpact = 'ENABLE' | 'STRENGTHEN' | 'WEAKEN' | 'CONDITION';

export interface ContextCategory {
  category_id: string;
  name: string;
  project_id: string;
  description: string | null;
  display_order: number;
}

export interface ContextAssignment {
  assignment_id: string;
  project_id: string;
  analytical_relation_id: string;
  group_item_id: string;
  publication_id: string;
  latest_revision_id: string;
  source_context_text: string;
  analytical_context_category_id: string | null;
  context_impact: ContextImpact;
  approval_state: ClassificationApprovalState;
  approved_by: string | null;
  approved_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ContextSynthesisSummary {
  context_evidence_count: number;
  distinct_publication_count: number;
  distinct_analytical_relation_count: number;
  distinct_mechanism_pathway_count: number;
}

export interface ContextWorkspaceData {
  project_id: string;
  categories: ContextCategory[];
  assignments: ContextAssignment[];
  stats: ContextSynthesisSummary;
}

export interface AssignContextToRelationRequest {
  category_id: string;
  context_impact: ContextImpact;
}

export interface AssignContextByGroupItemRequest {
  categoryId: string;
  contextImpact: ContextImpact;
  groupItemId: string;
  publicationId: string;
  latestRevisionId: string;
  sourceContextText: string;
}

// -------------------------------------------------------------------------
// Task 10.6: Research Gap Synthesis
// -------------------------------------------------------------------------

export type ResearchGapType =
  | 'thematic'
  | 'mechanism'
  | 'methodological'
  | 'contextual'
  | 'inconsistent_evidence';

export type ResearchGapLinkType = 'analytical_relation' | 'mechanism_pathway' | 'context_factor_link';

export interface ResearchGap {
  gap_id: string;
  project_id: string;
  gap_type: ResearchGapType;
  title: string;
  rationale: string;
  researcher_id: string;
  created_at: string;
  updated_at: string;
}

export interface ResearchGapLink {
  link_id: string;
  project_id: string;
  gap_id: string;
  link_type: ResearchGapLinkType;
  target_id: string;
  group_item_id: string;
  publication_id: string;
  latest_revision_id: string;
  created_at: string;
}

export interface ResearchGapDetail {
  gap: ResearchGap;
  links: ResearchGapLink[];
}

export interface ResearchGapWorkspaceStats {
  total_gaps: number;
  thematic_count: number;
  mechanism_count: number;
  methodological_count: number;
  contextual_count: number;
  inconsistent_evidence_count: number;
  linked_publication_count: number;
}

export interface ResearchGapWorkspaceData {
  project_id: string;
  gaps: ResearchGapDetail[];
  stats: ResearchGapWorkspaceStats;
}

export interface ResearchGapEvidenceCandidate {
  link_type: ResearchGapLinkType;
  target_id: string;
  group_item_id: string;
  publication_id: string;
  latest_revision_id: string;
  traceable: boolean;
  label: string;
  publication_title: string | null;
  publication_year: number | null;
  qa_profile: QAProfileSummary | null;
}

export interface CreateResearchGapRequest {
  gap_type: ResearchGapType;
  title: string;
  rationale: string;
  researcher_id: string;
}

export interface UpdateResearchGapRequest {
  gap_type?: ResearchGapType;
  title?: string;
  rationale?: string;
}

export interface LinkEvidenceRequest {
  link_type: ResearchGapLinkType;
  target_id: string;
}

export const RESEARCH_GAP_TYPE_LABELS: Record<ResearchGapType, string> = {
  thematic: 'Thematic Gap',
  mechanism: 'Mechanism Gap',
  methodological: 'Methodological Gap',
  contextual: 'Contextual Gap',
  inconsistent_evidence: 'Inconsistent Evidence Gap',
};

export const RESEARCH_GAP_LINK_TYPE_LABELS: Record<ResearchGapLinkType, string> = {
  analytical_relation: 'Analytical Relation',
  mechanism_pathway: 'Mechanism Pathway',
  context_factor_link: 'Context Factor Link',
};

// -------------------------------------------------------------------------
// Task 10.7: Synthesis Snapshots
// -------------------------------------------------------------------------

export interface SynthesisSnapshotContent {
  project_id: string;
  relations: AnalyticalRelation[];
  mechanism_pathways: MechanismPathway[];
  context_assignments: ContextAssignment[];
  research_gaps: ResearchGap[];
  research_gap_links: ResearchGapLink[];
  term_mappings: TermMappingResponse[];
  lean_categories: Category[];
  energy_categories: Category[];
  mechanism_categories: Category[];
  context_categories: ContextCategory[];
  qa_profiles: QAProfileSummary[];
}

export interface SynthesisSnapshot {
  snapshot_id: string;
  project_id: string;
  version: number;
  actor: string;
  extraction_dataset_hash: string;
  classification_version: string;
  content_hash: string;
  created_at: string;
}

export interface SynthesisSnapshotDetail extends SynthesisSnapshot {
  content: SynthesisSnapshotContent;
}

export interface SnapshotExport {
  snapshot_id: string;
  project_id: string;
  version: number;
  actor: string;
  created_at: string;
  format: string;
  extraction_dataset_hash: string | null;
  classification_version: string | null;
  content_hash: string | null;
  content: SynthesisSnapshotContent | null;
  content_csv: string | null;
}

export interface CreateSnapshotRequest {
  actor: string;
}
