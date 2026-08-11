import { API_BASE_URL } from '../../config/api';

export type QualityAssessmentResponseValue = 'YES' | 'NO' | 'CANNOT_DETERMINE';
export type QualityAssessmentReadiness = 'ready' | 'no_quality_assessment_configuration' | 'no_eligible_publications';
export type QualityAssessmentStatusFilter = 'all' | 'unassessed' | 'assessed';

export interface QualityAssessmentToolCriterion {
  criterion_id: string;
  template_id: string;
  display_order: number;
  question: string;
  guidance: string | null;
  is_required: boolean;
}

export interface QualityAssessmentTemplate {
  template_id: string;
  tool_id: string;
  template_key: string;
  name: string;
  version: number;
  description: string | null;
  is_active: boolean;
  criteria: QualityAssessmentToolCriterion[];
}

export interface QualityAssessmentTool {
  tool_id: string;
  name: string;
  description: string | null;
  is_active: boolean;
  templates: QualityAssessmentTemplate[];
}

export interface ProjectQualityAssessmentConfiguration {
  project_id: string;
  tool_id: string;
  template_id: string;
  template_key: string;
  template_name: string;
  version: number;
  configured_at: string;
}

export interface QualityAssessmentOverview {
  readiness: QualityAssessmentReadiness;
  tool_id: string | null;
  template_id: string | null;
  template_version: number | null;
  total_eligible: number;
  total_assessed: number;
  total_remaining: number;
}

export interface QualityAssessmentResponse {
  response_id: string;
  assessment_id: string;
  criterion_id: string;
  response_value: QualityAssessmentResponseValue;
  justification: string;
  question_snapshot: string;
  guidance_snapshot: string | null;
  is_required_snapshot: boolean;
}

export interface QualityAssessment {
  assessment_id: string;
  project_id: string;
  publication_id: string;
  reviewer_id: string;
  template_id: string;
  responses: QualityAssessmentResponse[];
  assessed_at: string;
}

export interface PublicationAuthor {
  display_name: string;
  given_name?: string | null;
  family_name?: string | null;
}

export interface PublicationVenue {
  name: string;
}

export interface PublicationRecord {
  record_id: string;
  title: string;
  authors: PublicationAuthor[];
  publication_year: number | null;
  venue: PublicationVenue | null;
  doi: string | null;
  abstract: string | null;
  urls: string[];
}

export interface EligiblePublicationRecord {
  publication: PublicationRecord;
  has_assessment: boolean;
  latest_assessment: QualityAssessment | null;
}

export interface QualityAssessmentRecordList {
  items: EligiblePublicationRecord[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface QualityAssessmentRecordDetail {
  project_id: string;
  publication: PublicationRecord;
  reviewer_id: string;
  is_currently_eligible: boolean;
  template: QualityAssessmentTemplate;
  latest_assessment: QualityAssessment | null;
  history: QualityAssessment[];
}

export interface CriterionResponseInput {
  criterion_id: string;
  response_value: QualityAssessmentResponseValue;
  justification: string;
}

export interface SaveQualityAssessmentRequest {
  reviewer_id: string;
  publication_id: string;
  responses: CriterionResponseInput[];
}

export class QualityAssessmentApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public details?: unknown
  ) {
    super(message);
    this.name = 'QualityAssessmentApiError';
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE_URL}${path}`;
  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  });

  if (!response.ok) {
    let errorMessage = `HTTP ${response.status} ${response.statusText}`;
    let details: unknown = null;
    try {
      const data = await response.json();
      if (data && typeof data === 'object') {
        details = data;
        if ('detail' in data) {
          if (typeof data.detail === 'string') {
            errorMessage = data.detail;
          } else if (Array.isArray(data.detail)) {
            errorMessage = data.detail.map((d: { msg?: string }) => d.msg || JSON.stringify(d)).join('; ');
          }
        }
      }
    } catch {
      // JSON parse error fallback
    }
    throw new QualityAssessmentApiError(response.status, errorMessage, details);
  }

  return response.json() as Promise<T>;
}

export const qualityAssessmentApi = {
  getTools: async (): Promise<QualityAssessmentTool[]> => {
    const tools = await request<QualityAssessmentTool[]>('/quality-assessment/tools');
    const toolsWithTemplates = await Promise.all(
      tools.map(async (tool) => {
        try {
          const templates = await request<QualityAssessmentTemplate[]>(
            `/quality-assessment/tools/${tool.tool_id}/templates`
          );
          return { ...tool, templates };
        } catch {
          return { ...tool, templates: [] };
        }
      })
    );
    return toolsWithTemplates;
  },

  getConfiguration: async (projectId: string): Promise<ProjectQualityAssessmentConfiguration | null> => {
    try {
      return await request<ProjectQualityAssessmentConfiguration | null>(`/projects/${projectId}/quality-assessment/configuration`);
    } catch (err) {
      if (
        err instanceof QualityAssessmentApiError &&
        (err.status === 404 || err.message.toLowerCase().includes('no active'))
      ) {
        return null;
      }
      throw err;
    }
  },

  updateConfiguration: (
    projectId: string,
    toolId: string,
    templateId: string,
    confirmTemplateChange = false
  ): Promise<ProjectQualityAssessmentConfiguration> => {
    return request<ProjectQualityAssessmentConfiguration>(`/projects/${projectId}/quality-assessment/configuration`, {
      method: 'PUT',
      body: JSON.stringify({
        tool_id: toolId,
        template_id: templateId,
        confirm_template_change: confirmTemplateChange,
      }),
    });
  },

  getOverview: (projectId: string, reviewerId: string): Promise<QualityAssessmentOverview> => {
    const params = new URLSearchParams({ reviewer_id: reviewerId });
    return request<QualityAssessmentOverview>(`/projects/${projectId}/quality-assessment/overview?${params.toString()}`);
  },

  listRecords: (
    projectId: string,
    reviewerId: string,
    statusFilter: QualityAssessmentStatusFilter = 'all',
    page = 1,
    pageSize = 20
  ): Promise<QualityAssessmentRecordList> => {
    const params = new URLSearchParams({
      reviewer_id: reviewerId,
      status: statusFilter,
      page: page.toString(),
      page_size: pageSize.toString(),
    });
    return request<QualityAssessmentRecordList>(`/projects/${projectId}/quality-assessment/records?${params.toString()}`);
  },

  getRecordDetail: (
    projectId: string,
    publicationId: string,
    reviewerId: string
  ): Promise<QualityAssessmentRecordDetail> => {
    const params = new URLSearchParams({ reviewer_id: reviewerId });
    return request<QualityAssessmentRecordDetail>(`/projects/${projectId}/quality-assessment/records/${publicationId}?${params.toString()}`);
  },

  saveAssessment: (
    projectId: string,
    requestBody: SaveQualityAssessmentRequest
  ): Promise<QualityAssessment> => {
    return request<QualityAssessment>(`/projects/${projectId}/quality-assessment/assessments`, {
      method: 'POST',
      body: JSON.stringify(requestBody),
    });
  },

  getHistory: (
    projectId: string,
    publicationId: string,
    reviewerId: string
  ): Promise<QualityAssessment[]> => {
    const params = new URLSearchParams({ reviewer_id: reviewerId });
    return request<QualityAssessment[]>(`/projects/${projectId}/quality-assessment/records/${publicationId}/history?${params.toString()}`);
  },
};
