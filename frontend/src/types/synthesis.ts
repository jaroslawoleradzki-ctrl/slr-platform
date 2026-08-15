export type ClassificationApprovalState = 'pending' | 'approved' | 'rejected';
export type TermType = 'lean_practice' | 'energy_effect';

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
