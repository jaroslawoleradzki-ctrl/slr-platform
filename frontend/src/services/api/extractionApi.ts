import { API_BASE_URL } from '../../config/api';

export type ValueStatus = 'unassessed' | 'present' | 'not_reported' | 'not_applicable' | 'unclear';
export type ValueOrigin = 'reported' | 'reviewer_coded';
export type ExtractionCompletenessStatus = 'not_started' | 'in_progress' | 'complete' | 'needs_review';
export type ExtractionEligibilityStatus =
  | 'eligible'
  | 'no_extraction_configuration'
  | 'blocked_screening_incomplete'
  | 'blocked_screening_excluded'
  | 'blocked_screening_uncertain'
  | 'blocked_screening_conflict'
  | 'blocked_screening_stale_resolution'
  | 'blocked_qa_incomplete';

export type FieldDataType =
  | 'text'
  | 'long_text'
  | 'integer'
  | 'decimal'
  | 'boolean'
  | 'date'
  | 'enum'
  | 'multi_enum'
  | 'identifier'
  | 'url'
  | 'number_with_unit'
  | 'repeating_group';

export interface ProjectExtractionConfiguration {
  project_id: string;
  template_id: string;
  template_version: string;
  configured_at: string;
  updated_at: string;
}

export interface ExtractionEligibilityResult {
  publication_id: string;
  status: ExtractionEligibilityStatus;
  is_eligible: boolean;
  reason_details?: string | null;
}

export interface ExtractionEligibilityListResponse {
  project_id: string;
  total_publications: number;
  eligible_count: number;
  items: ExtractionEligibilityResult[];
}

export interface ExtractedValueStateDTO {
  value_id?: string | null;
  field_key: string;
  status: ValueStatus;
  origin?: ValueOrigin | null;
  text_value?: string | null;
  int_value?: number | null;
  float_value?: number | null;
  bool_value?: boolean | null;
  unit_value?: string | null;
  json_value?: string[] | null;
  source_page?: string | null;
  source_section?: string | null;
  source_locator?: string | null;
  source_quote?: string | null;
  reviewer_note?: string | null;
}

export interface ExtractedGroupItemStateDTO {
  group_item_id?: string | null;
  group_key: string;
  item_index: number;
  values: ExtractedValueStateDTO[];
}

export interface ExtractionRevisionSubmitRequestDTO {
  reviewer_id: string;
  publication_values: ExtractedValueStateDTO[];
  group_items: ExtractedGroupItemStateDTO[];
  mark_complete?: boolean;
}

export interface ExtractionRevisionResponseDTO {
  revision_id: string;
  record_id: string;
  project_id: string;
  publication_id: string;
  revision_index: number;
  reviewer_id: string;
  completeness_status: ExtractionCompletenessStatus;
  publication_values: ExtractedValueStateDTO[];
  group_items: ExtractedGroupItemStateDTO[];
  created_at: string;
}

export interface ExtractionRecordResponseDTO {
  record_id: string;
  project_id: string;
  publication_id: string;
  template_id: string;
  template_version: string;
  current_status: ExtractionCompletenessStatus;
  created_at: string;
  updated_at: string;
  latest_revision?: ExtractionRevisionResponseDTO | null;
}

export interface ExtractionRevisionHistoryResponseDTO {
  project_id: string;
  publication_id: string;
  total_revisions: number;
  revisions: ExtractionRevisionResponseDTO[];
}

export interface ExtractionFieldDefinition {
  field_key: string;
  name: string;
  data_type: FieldDataType;
  description?: string | null;
  is_required?: boolean;
  allowed_statuses?: ValueStatus[];
  allowed_values?: string[] | null;
  allow_custom_text?: boolean;
  allowed_units?: string[] | null;
  min_value?: number | null;
  max_value?: number | null;
  min_length?: number | null;
  max_length?: number | null;
  regex_pattern?: string | null;
  group_key?: string | null;
}

export interface ExtractionRepeatingGroupDefinition {
  group_key: string;
  name: string;
  description?: string | null;
  min_items: number;
  max_items?: number | null;
  field_definitions: ExtractionFieldDefinition[];
}

export interface ExtractionTemplateVersion {
  template_id: string;
  version: string;
  name: string;
  description?: string | null;
  is_published: boolean;
  is_active: boolean;
  publication_fields: ExtractionFieldDefinition[];
  repeating_groups: ExtractionRepeatingGroupDefinition[];
  created_at: string;
}

export interface ExtractionProgressResponseDTO {
  project_id: string;
  total_eligible_publications: number;
  not_started_count: number;
  in_progress_count: number;
  complete_count: number;
  needs_review_count: number;
  completion_percentage: number;
}

export interface ExtractionRecordSummaryDTO {
  publication_id: string;
  title: string;
  authors: string[];
  publication_year?: number | null;
  extraction_status: ExtractionCompletenessStatus;
  latest_revision_index?: number | null;
  latest_reviewer_id?: string | null;
  latest_updated_at?: string | null;
}

export interface ExtractionRecordListResponseDTO {
  project_id: string;
  total_records: number;
  items: ExtractionRecordSummaryDTO[];
}

export interface ExtractionMatrixRowDTO {
  publication_id: string;
  publication_title: string;
  group_key: string;
  group_name: string;
  group_item_id: string;
  item_index: number;
  values: ExtractedValueStateDTO[];
}

export interface ExtractionMatrixResponseDTO {
  project_id: string;
  template_id: string;
  template_version: string;
  total_relationships: number;
  group_keys: string[];
  items: ExtractionMatrixRowDTO[];
}

export class ExtractionApiError extends Error {
  statusCode: number;
  detail: string | string[];

  constructor(statusCode: number, detail: string | string[]) {
    const message = Array.isArray(detail) ? detail.join('; ') : detail;
    super(message);
    this.name = 'ExtractionApiError';
    this.statusCode = statusCode;
    this.detail = detail;
  }
}

const EXTRACTION_API_BASE_URL = `${API_BASE_URL}/projects`;

export const extractionApi = {
  async exportDataset(
    projectId: string,
    format: 'json' | 'csv',
    dataset: 'publications' | 'relationships',
  ): Promise<Blob> {
    const query = `?format=${format}&dataset=${dataset}`;
    const res = await fetch(`${EXTRACTION_API_BASE_URL}/${projectId}/extraction/export${query}`);
    if (!res.ok) {
      const errData = await res.json().catch(() => ({ detail: res.statusText }));
      throw new ExtractionApiError(res.status, errData.detail || 'Failed to export extraction dataset');
    }
    return res.blob();
  },

  async getProjectConfiguration(projectId: string): Promise<ProjectExtractionConfiguration | null> {
    const res = await fetch(`${EXTRACTION_API_BASE_URL}/${projectId}/extraction/configuration`);
    if (res.status === 404) return null;
    if (!res.ok) {
      const errData = await res.json().catch(() => ({ detail: res.statusText }));
      throw new ExtractionApiError(res.status, errData.detail || 'Failed to fetch project configuration');
    }
    return res.json();
  },

  async listExtractionTemplates(): Promise<ExtractionTemplateVersion[]> {
    const res = await fetch(`${API_BASE_URL}/extraction-templates`);
    if (!res.ok) {
      const errData = await res.json().catch(() => ({ detail: res.statusText }));
      throw new ExtractionApiError(res.status, errData.detail || 'Failed to fetch extraction templates');
    }
    return res.json();
  },

  async getExtractionTemplateVersion(
    templateId: string,
    version: string,
  ): Promise<ExtractionTemplateVersion> {
    const res = await fetch(
      `${API_BASE_URL}/extraction-templates/${encodeURIComponent(templateId)}/versions/${encodeURIComponent(version)}`,
    );
    if (!res.ok) {
      const errData = await res.json().catch(() => ({ detail: res.statusText }));
      throw new ExtractionApiError(res.status, errData.detail || 'Failed to fetch extraction template version');
    }
    return res.json();
  },

  async setProjectConfiguration(
    projectId: string,
    templateId: string,
    templateVersion: string,
  ): Promise<ProjectExtractionConfiguration> {
    const res = await fetch(`${EXTRACTION_API_BASE_URL}/${projectId}/extraction/configuration`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ template_id: templateId, template_version: templateVersion }),
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({ detail: res.statusText }));
      throw new ExtractionApiError(res.status, errData.detail || 'Failed to update project configuration');
    }
    return res.json();
  },

  async getExtractionEligibility(
    projectId: string,
    reviewerId: string = ''
  ): Promise<ExtractionEligibilityListResponse> {
    const query = reviewerId ? `?reviewer_id=${encodeURIComponent(reviewerId)}` : '';
    const res = await fetch(`${EXTRACTION_API_BASE_URL}/${projectId}/extraction/eligibility${query}`);
    if (!res.ok) {
      const errData = await res.json().catch(() => ({ detail: res.statusText }));
      throw new ExtractionApiError(res.status, errData.detail || 'Failed to fetch extraction eligibility');
    }
    return res.json();
  },

  async getProjectTemplate(projectId: string): Promise<ExtractionTemplateVersion | null> {
    const res = await fetch(`${EXTRACTION_API_BASE_URL}/${projectId}/extraction/template`);
    if (res.status === 404) return null;
    if (!res.ok) {
      const errData = await res.json().catch(() => ({ detail: res.statusText }));
      throw new ExtractionApiError(res.status, errData.detail || 'Failed to fetch extraction template');
    }
    return res.json();
  },

  async getExtractionRecord(
    projectId: string,
    publicationId: string
  ): Promise<ExtractionRecordResponseDTO> {
    const res = await fetch(`${EXTRACTION_API_BASE_URL}/${projectId}/extraction/records/${publicationId}`);
    if (!res.ok) {
      const errData = await res.json().catch(() => ({ detail: res.statusText }));
      throw new ExtractionApiError(res.status, errData.detail || 'Failed to fetch extraction record');
    }
    return res.json();
  },

  async submitRevision(
    projectId: string,
    publicationId: string,
    payload: ExtractionRevisionSubmitRequestDTO
  ): Promise<ExtractionRevisionResponseDTO> {
    const res = await fetch(`${EXTRACTION_API_BASE_URL}/${projectId}/extraction/records/${publicationId}/revisions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({ detail: res.statusText }));
      throw new ExtractionApiError(res.status, errData.detail || 'Failed to submit extraction revision');
    }
    return res.json();
  },

  async getExtractionHistory(
    projectId: string,
    publicationId: string
  ): Promise<ExtractionRevisionHistoryResponseDTO> {
    const res = await fetch(`${EXTRACTION_API_BASE_URL}/${projectId}/extraction/records/${publicationId}/history`);
    if (res.status === 404) {
      return { project_id: projectId, publication_id: publicationId, total_revisions: 0, revisions: [] };
    }
    if (!res.ok) {
      const errData = await res.json().catch(() => ({ detail: res.statusText }));
      throw new ExtractionApiError(res.status, errData.detail || 'Failed to fetch extraction history');
    }
    return res.json();
  },

  async getExtractionProgress(
    projectId: string,
    reviewerId: string = ''
  ): Promise<ExtractionProgressResponseDTO> {
    const query = reviewerId ? `?reviewer_id=${encodeURIComponent(reviewerId)}` : '';
    const res = await fetch(`${EXTRACTION_API_BASE_URL}/${projectId}/extraction/progress${query}`);
    if (!res.ok) {
      const errData = await res.json().catch(() => ({ detail: res.statusText }));
      throw new ExtractionApiError(res.status, errData.detail || 'Failed to fetch extraction progress');
    }
    return res.json();
  },

  async listExtractionRecords(
    projectId: string,
    reviewerId: string = ''
  ): Promise<ExtractionRecordListResponseDTO> {
    const query = reviewerId ? `?reviewer_id=${encodeURIComponent(reviewerId)}` : '';
    const res = await fetch(`${EXTRACTION_API_BASE_URL}/${projectId}/extraction/records${query}`);
    if (!res.ok) {
      const errData = await res.json().catch(() => ({ detail: res.statusText }));
      throw new ExtractionApiError(res.status, errData.detail || 'Failed to fetch extraction records queue');
    }
    return res.json();
  },

  async getExtractionMatrix(
    projectId: string,
    reviewerId: string = ''
  ): Promise<ExtractionMatrixResponseDTO> {
    const query = reviewerId ? `?reviewer_id=${encodeURIComponent(reviewerId)}` : '';
    const res = await fetch(`${EXTRACTION_API_BASE_URL}/${projectId}/extraction/matrix${query}`);
    if (!res.ok) {
      const errData = await res.json().catch(() => ({ detail: res.statusText }));
      throw new ExtractionApiError(res.status, errData.detail || 'Failed to fetch extraction matrix');
    }
    return res.json();
  },
};
