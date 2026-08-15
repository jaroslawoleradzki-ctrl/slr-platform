import { API_BASE_URL } from '../../config/api';
import {
  Category,
  TerminologyClassificationWorkspace,
  TermMappingResponse,
  TermType,
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
};
