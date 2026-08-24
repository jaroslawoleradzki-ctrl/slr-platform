export type StageStatus = 'completed' | 'in_progress' | 'pending_action' | 'pending' | 'error';

export type ManualSourceDatabase =
  | 'google_scholar_pop'
  | 'scopus'
  | 'web_of_science'
  | 'pubmed'
  | 'ebsco'
  | 'proquest'
  | 'other';

export const MANUAL_SOURCE_DATABASE_LABELS: Record<ManualSourceDatabase, string> = {
  google_scholar_pop: 'Google Scholar (Publish or Perish)',
  scopus: 'Scopus',
  web_of_science: 'Web of Science',
  pubmed: 'PubMed',
  ebsco: 'EBSCO',
  proquest: 'ProQuest',
  other: 'Other',
};

export interface ConceptGroup {
  id: string;
  name: string;
  terms: string[];
}

export interface SearchFilters {
  publicationYearFrom: number | null;
  publicationYearTo: number | null;
  languages: string[];
  publicationTypes: string[];
  fullTextOnly: boolean;
}

export interface EditableSearchStrategy {
  filters: SearchFilters;
  providers: string[];
  conceptGroups: ConceptGroup[];
}

export type BooleanOperator = 'and' | 'or';
export type SearchProviderId = 'openalex' | 'crossref' | 'semantic_scholar';

export interface SearchStrategyConceptGroup {
  group_id: string;
  name: string;
  terms: string[];
  operator: BooleanOperator;
}

export interface SearchStrategyConstraints {
  publication_year_from: number | null;
  publication_year_to: number | null;
  languages: string[];
  publication_types: string[];
  additional_limits: Record<string, string | number | boolean>;
}

export interface SearchTermExpression {
  node_type: 'term';
  value: string;
  field?: 'any' | 'title' | 'abstract' | 'keywords' | 'author' | 'venue';
  exact_phrase?: boolean;
}

export interface SearchGroupExpression {
  node_type: 'group';
  operator: 'and' | 'or' | 'not';
  children: SearchExpression[];
}

export type SearchExpression = SearchTermExpression | SearchGroupExpression;

export interface SearchQueryWrite {
  name: string;
  expression: SearchExpression;
  version?: number;
  description?: string | null;
}

export interface SearchQuery extends SearchQueryWrite {
  query_id: string;
  version: number;
  created_by: string | null;
  notes: string | null;
  created_at: string;
}

export interface SearchStrategyWriteRequest {
  strategy_id?: string;
  name: string;
  description?: string | null;
  research_questions: string[];
  concept_groups: SearchStrategyConceptGroup[];
  group_operator: BooleanOperator;
  constraints: SearchStrategyConstraints;
  providers: SearchProviderId[];
  queries: SearchQueryWrite[];
  version: number;
  created_at?: string;
}

export interface SearchStrategy extends Omit<SearchStrategyWriteRequest, 'queries'> {
  strategy_id: string;
  project_id: string;
  queries: SearchQuery[];
  created_at: string;
  updated_at: string;
}

export interface ProviderQuery {
  provider: string;
  rendered_query: string;
  is_lossless?: boolean;
  warnings?: string[];
}

export interface SearchExecutionResult {
  project_id: string;
  status: 'validated';
  rendered_query: string;
  provider_queries?: ProviderQuery[];
  providers: string[];
  publication_year_from: number;
  publication_year_to: number;
  executed_at: string;
  total_count: number;
  returned_count: number;
  next_cursor: string | null;
  has_more: boolean;
  results: SearchResultRecord[];
  provider_errors?: SearchProviderError[];
}

export interface SearchResultRecord {
  id: string;
  title: string;
  authors: string[];
  year: number;
  provider: 'openalex' | 'crossref';
  source_id: string;
  doi: string | null;
}

export interface SearchProviderError {
  provider: 'openalex' | 'crossref';
  message: string;
}

export interface SearchResultsImportResponse {
  project_id: string;
  imported_count: number;
  skipped_count: number;
  total_requested: number;
  working_collection_count: number;
}

export interface SearchResultsImportMetadata {
  provider?: 'openalex' | 'crossref';
  query?: string;
  total_available?: number;
}

export interface SearchProviderStatus {
  id: string;
  name: string;
  type: 'live_api' | 'manual_import';
  connected: boolean;
  status: 'completed' | 'running' | 'failed' | 'idle';
  resultsCount: number;
  lastRunTimestamp: string | null;
  errorMessage?: string;
}

export interface ImportFileRecord {
  id: string;
  sourceType?: 'file' | 'provider';
  filename: string | null;
  format: 'BibTeX' | 'RIS' | null;
  provider?: string | null;
  query?: string | null;
  totalAvailable?: number | null;
  recordsCount: number;
  importedAt: string;
  status: 'success' | 'warning' | 'failed' | 'error';
  warnings?: string[];
  sourceDatabase?: ManualSourceDatabase;
  sourceLabel?: string | null;
}

export interface BibliographicImportResponse {
  import_id: string;
  records_count: number;
  warnings: string[];
  status: 'success' | 'warning' | 'failed' | 'error';
}

export interface WorkingCollectionSummary {
  total_records: number;
}

export interface SourceSummaryItem {
  source: string;
  source_kind: 'provider' | 'file';
  successful_imports_count: number;
  warning_imports_count: number;
  failed_imports_count: number;
  records_added_count: number;
  last_import_at: string | null;
  last_import_status: 'success' | 'warning' | 'failed' | null;
}

export interface ImportHistoryItemDTO {
  import_id: string;
  source_type: 'provider' | 'file';
  filename: string | null;
  format: string | null;
  provider: string | null;
  query: string | null;
  records_count: number;
  status: 'success' | 'warning' | 'failed';
  warnings: string[];
  created_at: string;
  source_database?: ManualSourceDatabase;
  source_label?: string | null;
}

export interface SourcesSummaryResponse {
  project_id: string;
  working_collection: WorkingCollectionSummary;
  source_summaries: SourceSummaryItem[];
  import_history: ImportHistoryItemDTO[];
}

export interface BibliographicImportHistoryRecord {
  import_id: string;
  project_id: string;
  source_type: 'file' | 'provider';
  filename: string | null;
  format: 'BibTeX' | 'RIS' | null;
  provider: string | null;
  query: string | null;
  records_count: number;
  total_available: number | null;
  status: 'success' | 'warning' | 'failed' | 'error';
  created_at: string;
  warnings: string[];
  source_database?: ManualSourceDatabase;
  source_label?: string | null;
}

export interface NormalizationStatus {
  completed: boolean;
  status?: 'completed' | 'warning' | 'error';
  totalRecordsProcessed: number;
  cleanRecordsCount: number;
  warningsCount: number;
  errorsCount: number;
  warningsLog: string[];
  rulesApplied?: string[];
  executedAt?: string;
}

export interface NormalizationResponse {
  run_id: string;
  project_id: string;
  status: 'completed' | 'warning' | 'error';
  processed_records: number;
  clean_records: number;
  warnings_count: number;
  errors_count: number;
  rules_applied: string[];
  audit_trail: string[];
  started_at: string;
  completed_at: string;
  executed_at: string;
  error_message?: string | null;
}

export interface DeduplicationSummary {
  recordsBeforeDedup: number;
  identifierLinkedGroupsCount: number;
  recordsAfterResultMerger: number;
  candidateGroupsPendingUserReview: number;
  status: 'completed' | 'pending_action' | 'in_progress' | 'pending';
}

export interface DuplicateGroupPreview {
  groupId: string;
  similarityScore: number;
  reason: string;
  records: {
    id: string;
    title: string;
    authors: string;
    year: number;
    source: string;
    doi?: string;
  }[];
}

export interface ApiProvenanceEntry {
  source: string;
  source_record_id: string;
  retrieved_at?: string | null;
}

export interface ApiDuplicateRecordPreview {
  id: string;
  title: string;
  authors: string;
  year: number | null;
  source: string;
  venue?: string | null;
  doi?: string | null;
  pmid?: string | null;
  openalex_id?: string | null;
  provenance?: ApiProvenanceEntry[];
}

export interface ApiSharedIdentifier {
  identifier_type: string;
  value: string;
}

export type DuplicateDecisionType = 'APPROVE' | 'REJECT';
export type DuplicateDecisionStatus = 'PENDING' | 'APPROVE' | 'REJECT';
export type DuplicateGroupStatus = 'PENDING' | 'APPROVED' | 'REJECTED' | 'MERGED';

export interface ApiDuplicateGroupDecisionResponse {
  project_id: string;
  group_id: string;
  decision: DuplicateDecisionStatus;
  rationale?: string | null;
}

export interface ApiDuplicateGroupMergeResponse {
  project_id: string;
  group_id: string;
  status: 'MERGED';
  canonical_record_id: string;
  merged_publication_ids: string[];
  merged_at: string;
}

export interface ApiDuplicateGroup {
  group_id: string;
  reason: string;
  records_count: number;
  status: DuplicateGroupStatus;
  rationale?: string | null;
  canonical_record_id?: string | null;
  merged_publication_ids?: string[] | null;
  merged_at?: string | null;
  shared_identifiers: ApiSharedIdentifier[];
  records: ApiDuplicateRecordPreview[];
}

export interface ApiDuplicateGroupListResponse {
  project_id: string;
  total_groups_count: number;
  groups: ApiDuplicateGroup[];
}

export type ScreeningCriterionType = 'inclusion' | 'exclusion';
export type ScreeningCriterionStage = 'title_abstract' | 'full_text' | 'both';
export type ScreeningCriterionEvaluationMode = 'manual' | 'metadata_rule';
export type MetadataRuleField = 'publication_year' | 'language' | 'document_type' | 'open_access' | 'doi' | 'abstract';
export type MetadataRuleOperator = 'equals' | 'not_equals' | 'in' | 'not_in' | 'greater_than' | 'greater_than_or_equal' | 'less_than' | 'less_than_or_equal' | 'exists' | 'not_exists';
export type MetadataRuleValue = number | string | boolean | Array<number | string | boolean>;

export interface MetadataRule {
  field: MetadataRuleField;
  operator: MetadataRuleOperator;
  value?: MetadataRuleValue | null;
}

export interface ScreeningCriterionResponse {
  criterion_id: string;
  project_id: string;
  name: string;
  description: string | null;
  criterion_type: ScreeningCriterionType;
  screening_stage: ScreeningCriterionStage;
  display_order: number;
  is_active: boolean;
  is_required: boolean;
  evaluation_mode?: ScreeningCriterionEvaluationMode;
  metadata_rule?: MetadataRule | null;
}

export interface ScreeningCriterionListResponse {
  items: ScreeningCriterionResponse[];
  total: number;
}

export interface ScreeningCriterionCreatePayload {
  name: string;
  description?: string | null;
  criterion_type: ScreeningCriterionType;
  screening_stage: ScreeningCriterionStage;
  display_order: number;
  is_active?: boolean;
  is_required?: boolean;
  evaluation_mode?: ScreeningCriterionEvaluationMode;
  metadata_rule?: MetadataRule | null;
}

export interface ScreeningCriterionUpdatePayload {
  name: string;
  description?: string | null;
  criterion_type: ScreeningCriterionType;
  screening_stage: ScreeningCriterionStage;
  display_order: number;
  is_active: boolean;
  is_required: boolean;
  evaluation_mode?: ScreeningCriterionEvaluationMode;
  metadata_rule?: MetadataRule | null;
}

export interface ScreeningStatus {
  titleAbstract: {
    pending: number;
    included: number;
    excluded: number;
    unresolved: number;
    total: number;
  };
  fullText: {
    pending: number;
    included: number;
    excluded: number;
    unresolved: number;
    total: number;
  };
  status: 'in_progress' | 'pending' | 'completed';
}

export interface QualityAssessmentStatus {
  totalToAssess: number;
  completedAssessments: number;
  reviewerConflictsCount: number;
  status: 'in_progress' | 'pending' | 'completed';
}

export interface PrismaFunnelMetrics {
  recordsIdentifiedProviders: number;
  recordsIdentifiedImports: number;
  totalIdentified: number;
  recordsAfterNormalization: number;
  recordsBeforeDedup: number;
  recordsAfterTechnicalMerger: number;
  duplicateGroupsPendingReview: number;
  recordsScreenedTitleAbstract: number;
  recordsScreenedFullText: number;
  studiesIncludedSynthesis: number;
  manualSourceBreakdown: Record<string, number>;
}

export type ProjectStatusType = 'active' | 'archived';

export interface ApiProjectResponse {
  project_id: string;
  title: string;
  description: string | null;
  protocol_version: string;
  status: ProjectStatusType;
  created_at: string;
  updated_at: string;
}

export interface ApiProjectListResponse {
  items: ApiProjectResponse[];
  total: number;
}

export interface ProjectCreatePayload {
  title: string;
  description?: string | null;
  protocol_version?: string;
}

export interface ProjectUpdatePayload {
  title: string;
  description?: string | null;
  protocol_version: string;
}

export interface SLRProject {
  id: string;
  title: string;
  description: string;
  protocolVersion: string;
  status: ProjectStatusType;
  createdAt: string;
  updatedAt: string;
  nextAction: {
    title: string;
    description: string;
    targetStageId: string;
    actionLabel: string;
    severity: 'urgent' | 'normal';
  };
  conceptGroups: ConceptGroup[];
  searchFilters: SearchFilters;
  providers: SearchProviderStatus[];
  imports: ImportFileRecord[];
  normalization: NormalizationStatus[];
  deduplication: DeduplicationSummary;
  duplicateGroups: DuplicateGroupPreview[];
  screening: ScreeningStatus;
  qualityAssessment: QualityAssessmentStatus;
  prismaMetrics: PrismaFunnelMetrics;
}

export type WorkflowStageState =
  | 'not_started'
  | 'in_progress'
  | 'pending_action'
  | 'completed'
  | 'warning'
  | 'error'
  | 'not_available';

export interface WorkflowNavigationStatus {
  search: {
    state: WorkflowStageState;
    count: number | null;
    label: string | null;
  };
  sources: {
    state: WorkflowStageState;
    count: number | null;
    label: string | null;
  };
  normalization: {
    state: WorkflowStageState;
    count: number | null;
    label: string | null;
  };
  deduplication: {
    state: WorkflowStageState;
    totalGroups: number;
    pendingGroups: number;
    approvedGroups: number;
    rejectedGroups: number;
    label: string | null;
  };
  screening: {
    state: WorkflowStageState;
    count: number | null;
    total: number | null;
    label: string | null;
  };
  fullTextScreening: {
    state: WorkflowStageState;
    count: number | null;
    total: number | null;
    label: string | null;
  };
  qualityAssessment: {
    state: WorkflowStageState;
    count?: number | null;
    total?: number | null;
    label: string;
  };
  dataExtraction: {
    state: WorkflowStageState;
    count?: number | null;
    total?: number | null;
    label: string;
  };
  exports: {
    state: WorkflowStageState;
    label: string;
  };
}

export interface PrismaMetricsResponse {
  project_id: string;
  records_identified_providers: number;
  records_identified_imports: number;
  total_identified: number;
  records_after_normalization: number;
  records_before_dedup: number;
  records_after_technical_merger: number;
  duplicate_groups_pending_review: number;
  records_screened_title_abstract: number;
  records_screened_full_text: number;
  studies_included_synthesis: number;
  manual_source_breakdown: Record<string, number>;
}

export interface ApiProjectWorkflowStatusResponse {
  project_id: string;
  title_abstract_screening: {
    status: 'not_started' | 'in_progress' | 'completed' | 'unresolved_conflict' | 'stale_resolution';
    evaluated_count: number;
    total_count: number;
    conflict_count: number;
    resolved_count: number;
  };
  full_text_screening: {
    status: 'waiting_for_title_abstract' | 'ready' | 'in_progress' | 'completed' | 'unresolved_conflict' | 'stale_resolution';
    eligible_count: number;
    evaluated_count: number;
    conflict_count: number;
    resolved_count: number;
  };
  quality_assessment: {
    status: 'waiting_for_full_text' | 'ready' | 'in_progress' | 'completed';
    eligible_count: number;
  };
}

export * from './synthesis';
