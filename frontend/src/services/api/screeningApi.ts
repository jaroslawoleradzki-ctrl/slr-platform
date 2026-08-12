import { API_BASE_URL } from '../../config/api';

export type TitleAbstractStatus = 'unscreened' | 'included' | 'excluded' | 'uncertain';
export type ScreeningOutcome = 'include' | 'exclude' | 'uncertain';
export type AssessmentValue = 'met' | 'not_met' | 'uncertain' | 'not_assessed';
export type ReadinessStatus = 'ready' | 'unresolved_duplicates' | 'merge_conflict';
export type EvaluationMode = 'manual' | 'metadata_rule';
export type MetadataRuleField = 'publication_year' | 'language' | 'document_type' | 'open_access' | 'doi' | 'abstract';
export type MetadataRuleOperator = 'equals' | 'not_equals' | 'in' | 'not_in' | 'greater_than' | 'greater_than_or_equal' | 'less_than' | 'less_than_or_equal' | 'exists' | 'not_exists';
export interface MetadataRule { field: MetadataRuleField; operator: MetadataRuleOperator; value: number | string | boolean | Array<number | string | boolean> | null; }

export interface ScreeningCriterion {
  criterion_id: string;
  project_id: string;
  name: string;
  description: string | null;
  criterion_type: 'inclusion' | 'exclusion';
  screening_stage: 'title_abstract' | 'full_text' | 'both';
  display_order: number;
  is_active: boolean;
  is_required: boolean;
  evaluation_mode?: EvaluationMode;
  metadata_rule?: MetadataRule | null;
}

export interface CriterionAssessment {
  criterion_id: string;
  criterion_name: string;
  criterion_description?: string | null;
  criterion_type: 'inclusion' | 'exclusion';
  criterion_stage: 'title_abstract' | 'full_text' | 'both';
  criterion_is_required: boolean;
  assessment_value: AssessmentValue;
  notes: string | null;
  evaluation_mode?: EvaluationMode;
  metadata_rule?: MetadataRule | null;
  evaluated_metadata_value?: number | string | boolean | Array<number | string | boolean> | null;
}

export interface ScreeningDecision {
  decision_id: string;
  project_id: string;
  publication_id: string;
  stage: 'title_abstract' | 'full_text';
  outcome: ScreeningOutcome;
  reviewer_id: string;
  rationale: string | null;
  criterion_snapshot_schema_version?: number;
  criterion_assessments: CriterionAssessment[];
  exclusion_reason_criterion_ids?: string[];
  decided_at: string;
}

export type FullTextStatus = TitleAbstractStatus;
export type FullTextReadinessStatus = ReadinessStatus | 'waiting_for_title_abstract' | 'no_eligible_publications';
export type FullTextAvailabilityStatus = 'unknown' | 'to_retrieve' | 'available' | 'unavailable';
export interface FullTextAvailability { status: FullTextAvailabilityStatus; external_url: string | null; notes: string | null; }
export interface FullTextRecord extends Omit<TitleAbstractRecord, 'status'> {
  status: FullTextStatus;
  availability: FullTextAvailability;
}
export interface FullTextOverview {
  project_id: string; reviewer_id: string; ready: boolean; readiness_status: FullTextReadinessStatus;
  eligible_records_count: number; working_collection_count: number; canonical_records_count: number;
  unresolved_duplicate_groups: number; criteria: ScreeningCriterion[];
  progress: TitleAbstractOverview['progress'];
}
export interface FullTextRecordList { project_id: string; reviewer_id: string; ready: boolean; status_filter: FullTextStatus | null; total: number; offset: number; limit: number; items: FullTextRecord[]; }
export interface FullTextDecisionRequest extends TitleAbstractDecisionRequest { exclusion_reason_criterion_ids: string[]; }

export interface TitleAbstractRecord {
  publication_id: string;
  title: string;
  abstract: string | null;
  authors: string[];
  publication_year: number | null;
  publication_date: string | null;
  identifiers: Array<{ type: string; value: string; source: string | null }>;
  doi: string | null;
  venue: { name: string; type: string | null; publisher: string | null } | null;
  publisher: string | null;
  document_type: string | null;
  language: string | null;
  keywords: string[];
  urls: string[];
  open_access: boolean | null;
  status: TitleAbstractStatus;
  latest_decision: ScreeningDecision | null;
  automatic_assessments?: Array<{
    criterion_id: string;
    assessment_value: AssessmentValue;
    evaluated_metadata_value: number | string | boolean | Array<number | string | boolean> | null;
  }>;
}

export interface TitleAbstractOverview {
  project_id: string;
  reviewer_id: string;
  ready: boolean;
  readiness_status: ReadinessStatus;
  working_collection_count: number;
  canonical_records_count: number;
  unresolved_duplicate_groups: number;
  criteria: ScreeningCriterion[];
  progress: {
    total: number;
    unscreened: number;
    included: number;
    excluded: number;
    uncertain: number;
    completed: number;
  } | null;
}

export interface TitleAbstractRecordList {
  project_id: string;
  reviewer_id: string;
  ready: boolean;
  status_filter: TitleAbstractStatus | null;
  total: number;
  offset: number;
  limit: number;
  items: TitleAbstractRecord[];
}

export interface TitleAbstractDecisionRequest {
  publication_id: string;
  reviewer_id: string;
  outcome: ScreeningOutcome;
  rationale?: string | null;
  criterion_assessments: Array<{
    criterion_id: string;
    assessment_value: AssessmentValue;
    notes?: string | null;
  }>;
}
export interface ScreeningStageProgress { total_eligible: number; screened: number; remaining: number; included: number; excluded: number; uncertain: number; }
export interface ScreeningTransitions { canonical_input: number; title_abstract_screened: number; title_abstract_included: number; full_text_eligible: number; full_text_screened: number; full_text_included: number; }
export interface ScreeningReasonAggregation { criterion_id: string; criterion_snapshot_key: string; snapshot_schema_version: number; snapshot_complete: boolean; count: number; criterion_assessment: CriterionAssessment; }
export interface MultiReviewerMetrics { incomplete: number; agreement: number; conflict: number; resolved?: number; stale_resolution?: number; agreement_rate: number | null; resolution_rate?: number | null; }
export interface ScreeningReport { project_id: string; reviewer_id: string; ready: boolean; readiness_status: string; working_collection_count: number; canonical_records_count: number; title_abstract: ScreeningStageProgress | null; full_text: ScreeningStageProgress | null; transitions: ScreeningTransitions | null; full_text_exclusion_reasons: ScreeningReasonAggregation[]; title_abstract_multi_reviewer?: MultiReviewerMetrics | null; full_text_multi_reviewer?: MultiReviewerMetrics | null; }
export interface ScreeningAuditDecisionEvent { event_type: 'DECISION'; decision: ScreeningDecision; publication_title: string | null; revision_index: number; previous_outcome: ScreeningOutcome | null; is_latest_for_reviewer: boolean; }
export interface ScreeningAuditResolutionEvent { event_type: 'RESOLUTION'; resolution_id: string; publication_id: string; publication_title: string | null; stage: 'title_abstract' | 'full_text'; resolver_id: string; resolved_outcome: ScreeningOutcome; rationale: string; resolved_at: string; decision_set_key: string; is_current: boolean; status: 'CURRENT' | 'STALE'; reviewer_outcomes: Array<{ decision_id: string; reviewer_id: string; outcome: ScreeningOutcome }>; }
export type ScreeningAuditEvent = ScreeningAuditDecisionEvent | ScreeningAuditResolutionEvent;
export interface ScreeningAuditPage { total: number; offset: number; limit: number; items: ScreeningAuditEvent[]; }
export interface ReviewerAssignment { project_id: string; stage: 'title_abstract' | 'full_text'; reviewer_id: string; is_active: boolean; }
export interface ConflictResolution { resolution_id: string; project_id: string; publication_id: string; stage: 'title_abstract' | 'full_text'; decision_set_key: string; resolved_outcome: ScreeningOutcome; resolver_id: string; rationale: string; resolved_at: string; decision_ids: string[]; reviewer_outcomes?: Array<{ decision_id: string; reviewer_id: string; outcome: ScreeningOutcome }>; is_current?: boolean; }
export interface ScreeningConflict { publication_id: string; publication_title: string | null; stage: 'title_abstract' | 'full_text'; status: 'incomplete' | 'agreement' | 'conflict' | 'resolved' | 'stale_resolution'; expected_reviewers: string[]; pending_reviewers: string[]; latest_decisions: Array<{ reviewer_id: string; outcome: ScreeningOutcome; decision_id: string; decided_at: string; decision?: ScreeningDecision | null }>; current_decision_set_key?: string; resolution?: ConflictResolution | null; }

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly code?: string,
    public readonly readinessStatus?: ReadinessStatus,
    public readonly validationDetail?: unknown,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

const request = async <T>(path: string, init?: RequestInit): Promise<T> => {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: { Accept: 'application/json', ...init?.headers },
    });
  } catch {
    throw new ApiError('Nie udało się połączyć z backendem. Sprawdź połączenie i spróbuj ponownie.', 0);
  }
  if (response.ok) return response.json() as Promise<T>;

  let detail: unknown;
  try {
    detail = (await response.json() as { detail?: unknown }).detail;
  } catch {
    detail = undefined;
  }
  const objectDetail = detail && typeof detail === 'object' && !Array.isArray(detail)
    ? detail as { code?: string; readiness_status?: ReadinessStatus }
    : undefined;
  const message = typeof detail === 'string'
    ? detail
    : response.status === 422
      ? 'Niepoprawne lub niekompletne dane decyzji.'
      : `Żądanie screeningu nie powiodło się (HTTP ${response.status}).`;
  throw new ApiError(message, response.status, objectDetail?.code, objectDetail?.readiness_status, detail);
};

const query = (values: Record<string, string | number | null | undefined>) => {
  const params = new URLSearchParams();
  Object.entries(values).forEach(([key, value]) => {
    if (value !== null && value !== undefined) params.set(key, String(value));
  });
  return params.toString();
};

export const screeningApi = {
  getOverview(projectId: string, reviewerId: string) {
    return request<TitleAbstractOverview>(
      `/projects/${projectId}/screening/title-abstract?${query({ reviewer_id: reviewerId })}`,
    );
  },
  listRecords(projectId: string, reviewerId: string, status: TitleAbstractStatus | null, offset: number, limit: number) {
    return request<TitleAbstractRecordList>(
      `/projects/${projectId}/screening/title-abstract/records?${query({ reviewer_id: reviewerId, status, offset, limit })}`,
    );
  },
  getRecord(projectId: string, publicationId: string, reviewerId: string) {
    return request<TitleAbstractRecord>(
      `/projects/${projectId}/screening/title-abstract/records/${publicationId}?${query({ reviewer_id: reviewerId })}`,
    );
  },
  saveDecision(projectId: string, payload: TitleAbstractDecisionRequest) {
    return request<ScreeningDecision>(`/projects/${projectId}/screening/title-abstract/decisions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  },
  getFullTextOverview(projectId: string, reviewerId: string) {
    return request<FullTextOverview>(`/projects/${projectId}/screening/full-text?${query({ reviewer_id: reviewerId })}`);
  },
  listFullTextRecords(projectId: string, reviewerId: string, status: FullTextStatus | null, offset: number, limit: number) {
    return request<FullTextRecordList>(`/projects/${projectId}/screening/full-text/records?${query({ reviewer_id: reviewerId, status, offset, limit })}`);
  },
  getFullTextRecord(projectId: string, publicationId: string, reviewerId: string) {
    return request<FullTextRecord>(`/projects/${projectId}/screening/full-text/records/${publicationId}?${query({ reviewer_id: reviewerId })}`);
  },
  saveFullTextAvailability(projectId: string, publicationId: string, payload: FullTextAvailability & { reviewer_id: string }) {
    return request<FullTextAvailability>(`/projects/${projectId}/screening/full-text/records/${publicationId}/availability`, {
      method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
    });
  },
  saveFullTextDecision(projectId: string, payload: FullTextDecisionRequest) {
    return request<ScreeningDecision>(`/projects/${projectId}/screening/full-text/decisions`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
    });
  },
  listDecisionHistory(projectId: string, publicationId: string, reviewerId: string) {
    return request<{ items: ScreeningDecision[]; total: number }>(`/projects/${projectId}/screening/decisions/history?${query({ publication_id: publicationId, stage: 'full_text', reviewer_id: reviewerId })}`);
  },
  getReport(projectId: string, reviewerId: string) { return request<ScreeningReport>(`/projects/${projectId}/screening/report?${query({ reviewer_id: reviewerId })}`); },
  getAudit(projectId: string, reviewerId: string | null, offset: number, limit: number, stage?: string | null, outcome?: string | null) {
    return request<ScreeningAuditPage>(`/projects/${projectId}/screening/audit?${query({ reviewer_id: reviewerId, offset, limit, stage, outcome })}`);
  },
  getReviewerRoster(projectId: string, stage: 'title_abstract' | 'full_text') { return request<ReviewerAssignment[]>(`/projects/${projectId}/screening/reviewers?${query({ stage })}`); },
  saveReviewerRoster(projectId: string, stage: 'title_abstract' | 'full_text', reviewerIds: string[]) { return request<ReviewerAssignment[]>(`/projects/${projectId}/screening/reviewers?${query({ stage })}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ reviewer_ids: reviewerIds }) }); },
  getConflicts(projectId: string, stage: 'title_abstract' | 'full_text', status?: string | null, offset = 0, limit = 50, viewerReviewerId?: string | null, adjudication = false) { return request<{ total: number; offset: number; limit: number; items: ScreeningConflict[] }>(`/projects/${projectId}/screening/conflicts?${query({ stage, status, offset, limit, viewer_reviewer_id: viewerReviewerId, adjudication: adjudication ? 'true' : undefined })}`); },
  getConflictMetrics(projectId: string, stage: 'title_abstract' | 'full_text') { return request<MultiReviewerMetrics>(`/projects/${projectId}/screening/conflict-metrics?${query({ stage })}`); },
  saveConflictResolution(projectId: string, payload: { publication_id: string; stage: 'title_abstract' | 'full_text'; resolved_outcome: ScreeningOutcome; resolver_id: string; rationale: string; expected_decision_set_key: string }) { return request<ConflictResolution>(`/projects/${projectId}/screening/conflict-resolutions`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) }); },
  getConflictResolutionHistory(projectId: string, publicationId: string, stage: 'title_abstract' | 'full_text') { return request<{ publication_id: string; stage: string; current_decision_set_key: string; total: number; offset: number; limit: number; resolutions: ConflictResolution[] }>(`/projects/${projectId}/screening/conflict-resolutions/${publicationId}/history?${query({ stage, offset: 0, limit: 100 })}`); },
};
