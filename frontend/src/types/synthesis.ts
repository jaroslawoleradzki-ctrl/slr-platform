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
