import { API_BASE_URL } from '../../config/api';
import {
  AnalyticalRelation,
  Category,
  ConvertedValue,
  CreateResearchGapRequest,
  CreateSnapshotRequest,
  LinkEvidenceRequest,
  MatrixCellDetail,
  ResearchGap,
  ResearchGapDetail,
  ResearchGapEvidenceCandidate,
  ResearchGapLink,
  ResearchGapWorkspaceData,
  SnapshotExport,
  SynthesisMatrix,
  SynthesisSnapshot,
  SynthesisSnapshotDetail,
  TerminologyClassificationWorkspace,
  TermMappingResponse,
  TermType,
  UpdateResearchGapRequest,
} from '../../types/synthesis';

export class SynthesisApiError extends Error {
  status?: number;

  constructor(message: string, status?: number) {
    super(message);
    this.name = 'SynthesisApiError';
    this.status = status;
  }
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {}),
  };

  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
    try {
      const errorJson = await response.json();
      if (errorJson.detail) {
        errorMessage = errorJson.detail;
      }
    } catch {
      // Ignore json parse error
    }
    throw new SynthesisApiError(errorMessage, response.status);
  }

  if (response.status === 204) {
    return {} as T;
  }

  return response.json();
}

export const synthesisApi = {
  // Classification Workspace
  getWorkspace: (projectId: string): Promise<TerminologyClassificationWorkspace> => {
    return request<TerminologyClassificationWorkspace>(`/projects/${projectId}/synthesis/classifications`);
  },

  createLeanCategory: (
    projectId: string,
    data: { category_id: string; name: string; description?: string | null; display_order?: number }
  ): Promise<Category> => {
    return request<Category>(`/projects/${projectId}/synthesis/categories/lean`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  updateLeanCategory: (
    projectId: string,
    categoryId: string,
    data: { name: string; description?: string | null; display_order?: number }
  ): Promise<Category> => {
    return request<Category>(`/projects/${projectId}/synthesis/categories/lean/${categoryId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  },

  deleteLeanCategory: (projectId: string, categoryId: string): Promise<void> => {
    return request<void>(`/projects/${projectId}/synthesis/categories/lean/${categoryId}`, {
      method: 'DELETE',
    });
  },

  createEnergyCategory: (
    projectId: string,
    data: { category_id: string; name: string; description?: string | null; display_order?: number }
  ): Promise<Category> => {
    return request<Category>(`/projects/${projectId}/synthesis/categories/energy`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  updateEnergyCategory: (
    projectId: string,
    categoryId: string,
    data: { name: string; description?: string | null; display_order?: number }
  ): Promise<Category> => {
    return request<Category>(`/projects/${projectId}/synthesis/categories/energy/${categoryId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  },

  deleteEnergyCategory: (projectId: string, categoryId: string): Promise<void> => {
    return request<void>(`/projects/${projectId}/synthesis/categories/energy/${categoryId}`, {
      method: 'DELETE',
    });
  },

  setTermMapping: (
    projectId: string,
    data: { term_type: TermType; source_value: string; analytical_category_id: string }
  ): Promise<TermMappingResponse> => {
    return request<TermMappingResponse>(`/projects/${projectId}/synthesis/classifications`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  },

  approveTermMapping: (
    projectId: string,
    data: { term_type: TermType; source_value: string; reviewer_id: string }
  ): Promise<TermMappingResponse> => {
    return request<TermMappingResponse>(`/projects/${projectId}/synthesis/classifications/approve`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  // Matrix & Evidence Aggregation
  getMatrix: (projectId: string): Promise<SynthesisMatrix> => {
    return request<SynthesisMatrix>(`/projects/${projectId}/synthesis/matrix`);
  },

  getCellDetail: (
    projectId: string,
    leanCategoryId: string,
    energyCategoryId: string
  ): Promise<MatrixCellDetail> => {
    const params = new URLSearchParams({
      leanCategoryId,
      energyCategoryId,
    });
    return request<MatrixCellDetail>(`/projects/${projectId}/synthesis/matrix/cell-detail?${params.toString()}`);
  },

  convertUnit: (
    projectId: string,
    relationId: string,
    targetUnit: string
  ): Promise<ConvertedValue> => {
    return request<ConvertedValue>(`/projects/${projectId}/synthesis/relations/${relationId}/convert-unit`, {
      method: 'POST',
      body: JSON.stringify({ target_unit: targetUnit }),
    });
  },

  saveConvertedUnit: (
    projectId: string,
    relationId: string,
    targetUnit: string
  ): Promise<AnalyticalRelation> => {
    return request<AnalyticalRelation>(
      `/projects/${projectId}/synthesis/relations/${relationId}/save-converted-unit`,
      {
        method: 'POST',
        body: JSON.stringify({ target_unit: targetUnit }),
      }
    );
  },

  // Mechanism Synthesis & Pathways (Task 10.4)
  getMechanismWorkspace: (projectId: string): Promise<any> => {
    return request<any>(`/projects/${projectId}/synthesis/mechanisms`);
  },

  listMechanismCategories: (projectId: string): Promise<Category[]> => {
    return request<Category[]>(`/projects/${projectId}/synthesis/mechanisms/categories`);
  },

  createMechanismCategory: (
    projectId: string,
    data: { category_id: string; name: string; description?: string | null; display_order?: number }
  ): Promise<Category> => {
    return request<Category>(`/projects/${projectId}/synthesis/mechanisms/categories`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  updateMechanismCategory: (
    projectId: string,
    categoryId: string,
    data: { name: string; description?: string | null; display_order?: number }
  ): Promise<Category> => {
    return request<Category>(`/projects/${projectId}/synthesis/mechanisms/categories/${categoryId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  },

  deleteMechanismCategory: (projectId: string, categoryId: string): Promise<void> => {
    return request<void>(`/projects/${projectId}/synthesis/mechanisms/categories/${categoryId}`, {
      method: 'DELETE',
    });
  },

  assignMechanismPathway: (
    projectId: string,
    pathwayId: string,
    data: { category_id: string | null; is_review_synthesized?: boolean; notes?: string | null }
  ): Promise<any> => {
    return request<any>(`/projects/${projectId}/synthesis/mechanisms/pathways/${pathwayId}/assign`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  approveMechanismPathway: (
    projectId: string,
    pathwayId: string,
    reviewerId: string
  ): Promise<any> => {
    return request<any>(`/projects/${projectId}/synthesis/mechanisms/pathways/${pathwayId}/approve`, {
      method: 'POST',
      body: JSON.stringify({ reviewer_id: reviewerId }),
    });
  },

  getMechanismSynthesis: (projectId: string): Promise<any[]> => {
    return request<any[]>(`/projects/${projectId}/synthesis/mechanisms/synthesis`);
  },

  // Research Gap Synthesis (Task 10.6)
  getResearchGapWorkspace: (projectId: string): Promise<ResearchGapWorkspaceData> => {
    return request<ResearchGapWorkspaceData>(`/projects/${projectId}/synthesis/research-gaps`);
  },

  getResearchGap: (projectId: string, gapId: string): Promise<ResearchGapDetail> => {
    return request<ResearchGapDetail>(`/projects/${projectId}/synthesis/research-gaps/${gapId}`);
  },

  createResearchGap: (projectId: string, data: CreateResearchGapRequest): Promise<ResearchGap> => {
    return request<ResearchGap>(`/projects/${projectId}/synthesis/research-gaps`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  updateResearchGap: (
    projectId: string,
    gapId: string,
    data: UpdateResearchGapRequest
  ): Promise<ResearchGap> => {
    return request<ResearchGap>(`/projects/${projectId}/synthesis/research-gaps/${gapId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  },

  deleteResearchGap: (projectId: string, gapId: string): Promise<void> => {
    return request<void>(`/projects/${projectId}/synthesis/research-gaps/${gapId}`, {
      method: 'DELETE',
    });
  },

  getResearchGapEvidenceCandidates: (projectId: string): Promise<ResearchGapEvidenceCandidate[]> => {
    return request<ResearchGapEvidenceCandidate[]>(
      `/projects/${projectId}/synthesis/research-gaps/evidence-candidates`
    );
  },

  linkResearchGapEvidence: (
    projectId: string,
    gapId: string,
    data: LinkEvidenceRequest
  ): Promise<ResearchGapLink> => {
    return request<ResearchGapLink>(`/projects/${projectId}/synthesis/research-gaps/${gapId}/links`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  unlinkResearchGapEvidence: (projectId: string, gapId: string, linkId: string): Promise<void> => {
    return request<void>(`/projects/${projectId}/synthesis/research-gaps/${gapId}/links/${linkId}`, {
      method: 'DELETE',
    });
  },

  // Synthesis Snapshots (Task 10.7)
  createSnapshot: (projectId: string, data: CreateSnapshotRequest): Promise<SynthesisSnapshotDetail> => {
    return request<SynthesisSnapshotDetail>(`/projects/${projectId}/synthesis/snapshots`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  listSnapshots: (projectId: string): Promise<SynthesisSnapshot[]> => {
    return request<SynthesisSnapshot[]>(`/projects/${projectId}/synthesis/snapshots`);
  },

  getSnapshot: (projectId: string, version: number): Promise<SynthesisSnapshotDetail> => {
    return request<SynthesisSnapshotDetail>(`/projects/${projectId}/synthesis/snapshots/${version}`);
  },

  exportSnapshot: (projectId: string, version: number, format: 'json' | 'csv'): Promise<SnapshotExport> => {
    return request<SnapshotExport>(
      `/projects/${projectId}/synthesis/snapshots/${version}/export?format=${format}`
    );
  },
};
