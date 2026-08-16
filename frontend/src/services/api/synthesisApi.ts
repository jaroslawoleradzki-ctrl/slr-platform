import { API_BASE_URL } from '../../config/api';
import {
  AnalyticalRelation,
  AssignContextByGroupItemRequest,
  AssignContextToRelationRequest,
  Category,
  ContextAssignment,
  ContextCategory,
  ContextSynthesisSummary,
  ContextWorkspaceData,
  ConvertedValue,
  CreateResearchGapRequest,
  CreateSnapshotRequest,
  LinkEvidenceRequest,
  MatrixCellDetail,
  MechanismPathway,
  MechanismSynthesisPathway,
  MechanismWorkspaceData,
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
  getMechanismWorkspace: (projectId: string): Promise<MechanismWorkspaceData> => {
    return request<MechanismWorkspaceData>(`/projects/${projectId}/synthesis/mechanisms`);
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
  ): Promise<MechanismPathway> => {
    return request<MechanismPathway>(`/projects/${projectId}/synthesis/mechanisms/pathways/${pathwayId}/assign`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  approveMechanismPathway: (
    projectId: string,
    pathwayId: string,
    reviewerId: string
  ): Promise<MechanismPathway> => {
    return request<MechanismPathway>(`/projects/${projectId}/synthesis/mechanisms/pathways/${pathwayId}/approve`, {
      method: 'POST',
      body: JSON.stringify({ reviewer_id: reviewerId }),
    });
  },

  getMechanismSynthesis: (projectId: string): Promise<MechanismSynthesisPathway[]> => {
    return request<MechanismSynthesisPathway[]>(`/projects/${projectId}/synthesis/mechanisms/synthesis`);
  },

  // Context Synthesis & Moderating Factors (Task 10.5)
  getContextWorkspace: (projectId: string): Promise<ContextWorkspaceData> => {
    return request<ContextWorkspaceData>(`/projects/${projectId}/synthesis/context/synthesize`, {
      method: 'POST',
    });
  },

  getContextCategories: (projectId: string): Promise<ContextCategory[]> => {
    return request<ContextCategory[]>(`/projects/${projectId}/synthesis/context/categories`);
  },

  createContextCategory: (
    projectId: string,
    data: { category_id: string; name: string; description?: string | null; display_order?: number }
  ): Promise<ContextCategory> => {
    return request<ContextCategory>(`/projects/${projectId}/synthesis/context/categories`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  updateContextCategory: (
    projectId: string,
    categoryId: string,
    data: { name: string; description?: string | null; display_order?: number }
  ): Promise<ContextCategory> => {
    return request<ContextCategory>(`/projects/${projectId}/synthesis/context/categories/${categoryId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  },

  deleteContextCategory: (projectId: string, categoryId: string): Promise<void> => {
    return request<void>(`/projects/${projectId}/synthesis/context/categories/${categoryId}`, {
      method: 'DELETE',
    });
  },

  assignContextByGroupItem: (
    projectId: string,
    data: AssignContextByGroupItemRequest
  ): Promise<ContextAssignment> => {
    const body = new URLSearchParams();
    body.set('categoryId', data.categoryId);
    body.set('contextImpact', data.contextImpact);
    body.set('groupItemId', data.groupItemId);
    body.set('publicationId', data.publicationId);
    body.set('latestRevisionId', data.latestRevisionId);
    body.set('sourceContextText', data.sourceContextText);
    return request<ContextAssignment>(`/projects/${projectId}/synthesis/context/assign-by-group-item`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: body.toString(),
    });
  },

  remapContextAssignment: (
    projectId: string,
    linkId: string,
    data: AssignContextToRelationRequest
  ): Promise<ContextAssignment> => {
    const params = new URLSearchParams({ linkId, projectId });
    return request<ContextAssignment>(`/projects/${projectId}/synthesis/context/remap?${params.toString()}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  },

  unassignContext: (projectId: string, linkId: string): Promise<ContextAssignment> => {
    const params = new URLSearchParams({ projectId });
    return request<ContextAssignment>(
      `/projects/${projectId}/synthesis/context/unassign/${linkId}?${params.toString()}`,
      {
        method: 'PUT',
      }
    );
  },

  getContextSummary: (projectId: string): Promise<ContextSynthesisSummary> => {
    return request<ContextSynthesisSummary>(`/projects/${projectId}/synthesis/context/summary`);
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
