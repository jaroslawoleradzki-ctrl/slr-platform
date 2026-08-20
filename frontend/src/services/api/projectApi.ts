import {
  SLRProject,
  ApiDuplicateGroupListResponse,
  ApiDuplicateGroupDecisionResponse,
  DuplicateDecisionType,
  EditableSearchStrategy,
  SearchExecutionResult,
  BibliographicImportResponse,
  BibliographicImportHistoryRecord,
  SourcesSummaryResponse,
  SearchResultRecord,
  SearchResultsImportMetadata,
  SearchResultsImportResponse,
  SearchStrategy,
  SearchStrategyWriteRequest,
  NormalizationResponse,
  ScreeningCriterionResponse,
  ScreeningCriterionListResponse,
  ScreeningCriterionCreatePayload,
  ScreeningCriterionUpdatePayload,
  ApiProjectResponse,
  ApiProjectListResponse,
  ProjectUpdatePayload,
  ApiProjectWorkflowStatusResponse,
  PrismaMetricsResponse,
  PrismaFunnelMetrics,
} from '../../types';
import { API_BASE_URL } from '../../config/api';

interface FastApiValidationError {
  loc?: unknown;
  msg?: unknown;
}

const formatFastApiError = async (
  response: Response,
  operation = 'wykonać strategii',
): Promise<string> => {
  const fallback = `Nie udało się ${operation} (HTTP ${response.status}).`;
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    return fallback;
  }
  if (!payload || typeof payload !== 'object' || !('detail' in payload)) return fallback;
  const detail = (payload as { detail?: unknown }).detail;
  if (typeof detail === 'string' && detail.trim()) {
    return `${detail.trim()} (HTTP ${response.status}).`;
  }
  if (Array.isArray(detail)) {
    const messages = detail.flatMap((item) => {
      if (!item || typeof item !== 'object') return [];
      const validationError = item as FastApiValidationError;
      if (typeof validationError.msg !== 'string' || !validationError.msg.trim()) return [];
      const location = Array.isArray(validationError.loc)
        ? validationError.loc.filter((part) => part !== 'body').map(String).join(' → ')
        : '';
      return [`${location ? `${location}: ` : ''}${validationError.msg.trim()}`];
    });
    if (messages.length) {
      return `Niepoprawne dane strategii: ${messages.join('; ')} (HTTP ${response.status}).`;
    }
  }
  return fallback;
};

export interface ProjectApiService {
  getProjects(includeArchived?: boolean): Promise<SLRProject[]>;
  getProjectById(id: string): Promise<SLRProject | null>;
  createProject(title: string, description: string, protocolVersion: string): Promise<SLRProject>;
  updateProject(id: string, payload: ProjectUpdatePayload): Promise<SLRProject>;
  archiveProject(id: string): Promise<SLRProject>;
  restoreProject(id: string): Promise<SLRProject>;
  deleteProject(id: string): Promise<void>;
  getDuplicateGroups(projectId: string): Promise<ApiDuplicateGroupListResponse>;
  postDuplicateGroupDecision(
    projectId: string,
    groupId: string,
    decision: DuplicateDecisionType,
    rationale?: string
  ): Promise<ApiDuplicateGroupDecisionResponse>;
  getDuplicateGroupDecision(
    projectId: string,
    groupId: string
  ): Promise<ApiDuplicateGroupDecisionResponse>;
  executeSearchStrategy(
    projectId: string,
    strategy: EditableSearchStrategy,
    cursor?: string,
  ): Promise<SearchExecutionResult>;
  getSearchStrategy(projectId: string): Promise<SearchStrategy | null>;
  saveSearchStrategy(
    projectId: string,
    strategy: SearchStrategyWriteRequest
  ): Promise<SearchStrategy>;
  importSearchResults(
    projectId: string,
    records: SearchResultRecord[],
    metadata?: SearchResultsImportMetadata,
  ): Promise<SearchResultsImportResponse>;
  importBibliographicFile(
    projectId: string,
    file: File,
  ): Promise<BibliographicImportResponse>;
  getBibliographicImports(
    projectId: string,
  ): Promise<BibliographicImportHistoryRecord[]>;
  getSourcesSummary(projectId: string): Promise<SourcesSummaryResponse>;
  getNormalization(projectId: string): Promise<NormalizationResponse | null>;
  runNormalization(projectId: string): Promise<NormalizationResponse>;
  listScreeningCriteria(
    projectId: string,
    activeOnly?: boolean
  ): Promise<ScreeningCriterionListResponse>;
  createScreeningCriterion(
    projectId: string,
    payload: ScreeningCriterionCreatePayload
  ): Promise<ScreeningCriterionResponse>;
  updateScreeningCriterion(
    projectId: string,
    criterionId: string,
    payload: ScreeningCriterionUpdatePayload
  ): Promise<ScreeningCriterionResponse>;
  deactivateScreeningCriterion(
    projectId: string,
    criterionId: string
  ): Promise<ScreeningCriterionResponse>;
  getWorkflowStatus(
    projectId: string,
    reviewerId?: string
  ): Promise<ApiProjectWorkflowStatusResponse | null>;
  getPrismaMetrics(projectId: string, reviewerId?: string): Promise<PrismaMetricsResponse>;
}

const mapApiProjectToSLRProject = (p: ApiProjectResponse): SLRProject => ({
  id: p.project_id,
  title: p.title,
  description: p.description || '',
  protocolVersion: p.protocol_version,
  status: p.status,
  createdAt: p.created_at,
  updatedAt: p.updated_at,
  nextAction: {
    title: 'Konfiguracja Strategii Wyszukiwania',
    description: 'Brak zdefiniowanych grup pojęciowych.',
    targetStageId: 'search',
    actionLabel: 'Edytuj Strategię',
    severity: 'normal',
  },
  conceptGroups: [],
  searchFilters: {
    publicationYearFrom: 2018,
    publicationYearTo: 2026,
    languages: ['en'],
    publicationTypes: ['article', 'review'],
    fullTextOnly: false,
  },
  providers: [
    {
      id: 'openalex',
      name: 'OpenAlex Works API',
      type: 'live_api',
      connected: true,
      status: 'idle',
      resultsCount: 0,
      lastRunTimestamp: null,
    },
    {
      id: 'crossref',
      name: 'Crossref REST API',
      type: 'live_api',
      connected: true,
      status: 'idle',
      resultsCount: 0,
      lastRunTimestamp: null,
    },
    {
      id: 'semantic_scholar',
      name: 'Semantic Scholar Graph API',
      type: 'live_api',
      connected: true,
      status: 'idle',
      resultsCount: 0,
      lastRunTimestamp: null,
    },
  ],
  imports: [],
  normalization: [],
  deduplication: {
    recordsBeforeDedup: 0,
    identifierLinkedGroupsCount: 0,
    recordsAfterResultMerger: 0,
    candidateGroupsPendingUserReview: 0,
    status: 'pending',
  },
  duplicateGroups: [],
  screening: {
    titleAbstract: { pending: 0, included: 0, excluded: 0, unresolved: 0, total: 0 },
    fullText: { pending: 0, included: 0, excluded: 0, unresolved: 0, total: 0 },
    status: 'pending',
  },
  qualityAssessment: {
    totalToAssess: 0,
    completedAssessments: 0,
    reviewerConflictsCount: 0,
    status: 'pending',
  },
  prismaMetrics: {
    recordsIdentifiedProviders: 0,
    recordsIdentifiedImports: 0,
    totalIdentified: 0,
    recordsAfterNormalization: 0,
    recordsBeforeDedup: 0,
    recordsAfterTechnicalMerger: 0,
    duplicateGroupsPendingReview: 0,
    recordsScreenedTitleAbstract: 0,
    recordsScreenedFullText: 0,
    studiesIncludedSynthesis: 0,
  },
});

const mapPrismaMetricsResponseToFunnel = (p: PrismaMetricsResponse): PrismaFunnelMetrics => ({
  recordsIdentifiedProviders: p.records_identified_providers,
  recordsIdentifiedImports: p.records_identified_imports,
  totalIdentified: p.total_identified,
  recordsAfterNormalization: p.records_after_normalization,
  recordsBeforeDedup: p.records_before_dedup,
  recordsAfterTechnicalMerger: p.records_after_technical_merger,
  duplicateGroupsPendingReview: p.duplicate_groups_pending_review,
  recordsScreenedTitleAbstract: p.records_screened_title_abstract,
  recordsScreenedFullText: p.records_screened_full_text,
  studiesIncludedSynthesis: p.studies_included_synthesis,
});

class MixedProjectApiService implements ProjectApiService {
  async getProjects(includeArchived = true): Promise<SLRProject[]> {
    let response: Response;
    try {
      response = await fetch(`${API_BASE_URL}/projects?include_archived=${includeArchived}`, {
        headers: { Accept: 'application/json' },
      });
    } catch {
      throw new Error('Nie udało się połączyć z backendem. Sprawdź połączenie.');
    }
    if (!response.ok) throw new Error(await formatFastApiError(response, 'pobrać listę projektów'));
    const data = (await response.json()) as ApiProjectListResponse;
    return data.items.map(mapApiProjectToSLRProject);
  }

  async getProjectById(id: string): Promise<SLRProject | null> {
    let response: Response;
    try {
      response = await fetch(`${API_BASE_URL}/projects/${id}`, {
        headers: { Accept: 'application/json' },
      });
    } catch {
      throw new Error('Nie udało się połączyć z backendem. Sprawdź połączenie.');
    }
    if (response.status === 404) return null;
    if (!response.ok) throw new Error(await formatFastApiError(response, 'pobrać projekt'));
    const data = (await response.json()) as ApiProjectResponse;
    return mapApiProjectToSLRProject(data);
  }

  async createProject(
    title: string,
    description: string,
    protocolVersion: string
  ): Promise<SLRProject> {
    let response: Response;
    try {
      response = await fetch(`${API_BASE_URL}/projects`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify({
          title,
          description: description || null,
          protocol_version: protocolVersion || '1.0',
        }),
      });
    } catch {
      throw new Error('Nie udało się połączyć z backendem. Sprawdź połączenie.');
    }
    if (!response.ok) throw new Error(await formatFastApiError(response, 'utworzyć projekt'));
    const data = (await response.json()) as ApiProjectResponse;
    return mapApiProjectToSLRProject(data);
  }

  async updateProject(id: string, payload: ProjectUpdatePayload): Promise<SLRProject> {
    let response: Response;
    try {
      response = await fetch(`${API_BASE_URL}/projects/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify(payload),
      });
    } catch {
      throw new Error('Nie udało się połączyć z backendem. Sprawdź połączenie.');
    }
    if (!response.ok) throw new Error(await formatFastApiError(response, 'zaktualizować projekt'));
    const data = (await response.json()) as ApiProjectResponse;
    return mapApiProjectToSLRProject(data);
  }

  async archiveProject(id: string): Promise<SLRProject> {
    let response: Response;
    try {
      response = await fetch(`${API_BASE_URL}/projects/${id}/archive`, {
        method: 'PATCH',
        headers: { Accept: 'application/json' },
      });
    } catch {
      throw new Error('Nie udało się połączyć z backendem. Sprawdź połączenie.');
    }
    if (!response.ok) throw new Error(await formatFastApiError(response, 'zarchiwizować projekt'));
    const data = (await response.json()) as ApiProjectResponse;
    return mapApiProjectToSLRProject(data);
  }
  async deleteProject(id: string): Promise<void> {
    let response: Response;
    try {
      response = await fetch(`${API_BASE_URL}/projects/${id}`, {
        method: 'DELETE',
        headers: { Accept: 'application/json' },
      });
    } catch {
      throw new Error('Nie udało się połączyć z backendem. Sprawdź połączenie.');
    }
    if (!response.ok) throw new Error(await formatFastApiError(response, 'usunąć projekt'));
    // No content expected
  }


  async restoreProject(id: string): Promise<SLRProject> {
    let response: Response;
    try {
      response = await fetch(`${API_BASE_URL}/projects/${id}/restore`, {
        method: 'PATCH',
        headers: { Accept: 'application/json' },
      });
    } catch {
      throw new Error('Nie udało się połączyć z backendem. Sprawdź połączenie.');
    }
    if (!response.ok) throw new Error(await formatFastApiError(response, 'przywrócić projekt'));
    const data = (await response.json()) as ApiProjectResponse;
    return mapApiProjectToSLRProject(data);
  }

  async getSearchStrategy(projectId: string): Promise<SearchStrategy | null> {
    let response: Response;
    try {
      response = await fetch(`${API_BASE_URL}/projects/${projectId}/search-strategy`, {
        headers: { Accept: 'application/json' },
      });
    } catch {
      throw new Error('Nie udało się połączyć z backendem. Sprawdź połączenie i spróbuj ponownie.');
    }
    if (response.status === 404) return null;
    if (!response.ok) throw new Error(await formatFastApiError(response, 'pobrać strategii'));
    return response.json() as Promise<SearchStrategy>;
  }

  async saveSearchStrategy(
    projectId: string,
    strategy: SearchStrategyWriteRequest
  ): Promise<SearchStrategy> {
    let response: Response;
    try {
      response = await fetch(`${API_BASE_URL}/projects/${projectId}/search-strategy`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify(strategy),
      });
    } catch {
      throw new Error('Nie udało się połączyć z backendem. Sprawdź połączenie i spróbuj ponownie.');
    }
    if (!response.ok) throw new Error(await formatFastApiError(response, 'zapisać strategii'));
    return response.json() as Promise<SearchStrategy>;
  }

  async executeSearchStrategy(
    projectId: string,
    strategy: EditableSearchStrategy,
    cursor?: string,
  ): Promise<SearchExecutionResult> {
    let response: Response;
    try {
      response = await fetch(
        `${API_BASE_URL}/projects/${projectId}/search-strategy/executions`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
          body: JSON.stringify({
            publication_year_from: strategy.filters.publicationYearFrom,
            publication_year_to: strategy.filters.publicationYearTo,
            languages: strategy.filters.languages,
            publication_types: strategy.filters.publicationTypes,
            open_access: strategy.filters.fullTextOnly,
            providers: strategy.providers,
            concept_groups: strategy.conceptGroups,
            ...(cursor ? { cursor } : {}),
          }),
        }
      );
    } catch {
      throw new Error('Nie udało się połączyć z backendem. Sprawdź połączenie i spróbuj ponownie.');
    }
    if (!response.ok) {
      throw new Error(await formatFastApiError(response));
    }
    return response.json() as Promise<SearchExecutionResult>;
  }

  async importSearchResults(
    projectId: string,
    records: SearchResultRecord[],
    metadata?: SearchResultsImportMetadata,
  ): Promise<SearchResultsImportResponse> {
    const response = await fetch(
      `${API_BASE_URL}/projects/${projectId}/search-results/imports`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify({ records, ...metadata }),
      }
    );
    if (!response.ok) {
      throw new Error(await formatFastApiError(response));
    }
    return response.json() as Promise<SearchResultsImportResponse>;
  }

  async importBibliographicFile(
    projectId: string,
    file: File,
  ): Promise<BibliographicImportResponse> {
    const formData = new FormData();
    formData.append('file', file);
    let response: Response;
    try {
      response = await fetch(`${API_BASE_URL}/projects/${projectId}/imports`, {
        method: 'POST',
        body: formData,
      });
    } catch {
      throw new Error('Nie udało się połączyć z backendem. Sprawdź połączenie i spróbuj ponownie.');
    }
    if (!response.ok) {
      throw new Error(await formatFastApiError(response, 'zaimportować pliku'));
    }
    return response.json() as Promise<BibliographicImportResponse>;
  }

  async getBibliographicImports(
    projectId: string,
  ): Promise<BibliographicImportHistoryRecord[]> {
    let response: Response;
    try {
      response = await fetch(`${API_BASE_URL}/projects/${projectId}/imports`, {
        headers: { Accept: 'application/json' },
      });
    } catch {
      throw new Error('Nie udało się pobrać historii importów.');
    }
    if (!response.ok) {
      throw new Error(await formatFastApiError(response, 'pobrać historii importów'));
    }
    return response.json() as Promise<BibliographicImportHistoryRecord[]>;
  }

  async getSourcesSummary(projectId: string): Promise<SourcesSummaryResponse> {
    let response: Response;
    try {
      response = await fetch(`${API_BASE_URL}/projects/${projectId}/sources-summary`, {
        headers: { Accept: 'application/json' },
      });
    } catch {
      throw new Error('Nie udało się pobrać podsumowania źródeł.');
    }
    if (!response.ok) {
      throw new Error(await formatFastApiError(response, 'pobrać podsumowania źródeł'));
    }
    return response.json() as Promise<SourcesSummaryResponse>;
  }

  async getNormalization(projectId: string): Promise<NormalizationResponse | null> {
    let response: Response;
    try {
      response = await fetch(`${API_BASE_URL}/projects/${projectId}/normalization`, {
        headers: { Accept: 'application/json' },
      });
    } catch {
      throw new Error('Nie udało się pobrać stanu normalizacji.');
    }
    if (response.status === 404) return null;
    if (!response.ok) throw new Error(await formatFastApiError(response, 'pobrać stanu normalizacji'));
    return response.json() as Promise<NormalizationResponse>;
  }

  async runNormalization(projectId: string): Promise<NormalizationResponse> {
    let response: Response;
    try {
      response = await fetch(`${API_BASE_URL}/projects/${projectId}/normalization`, {
        method: 'POST',
        headers: { Accept: 'application/json' },
      });
    } catch {
      throw new Error('Nie udało się uruchomić normalizacji.');
    }
    if (!response.ok) throw new Error(await formatFastApiError(response, 'uruchomić normalizacji'));
    return response.json() as Promise<NormalizationResponse>;
  }

  async listScreeningCriteria(
    projectId: string,
    activeOnly?: boolean
  ): Promise<ScreeningCriterionListResponse> {
    const url = `${API_BASE_URL}/projects/${projectId}/screening/criteria${activeOnly ? '?active_only=true' : ''}`;
    let response: Response;
    try {
      response = await fetch(url, {
        headers: { Accept: 'application/json' },
      });
    } catch {
      throw new Error('Nie udało się pobrać kryteriów screeningu.');
    }
    if (!response.ok) {
      throw new Error(await formatFastApiError(response, 'pobrać kryteriów screeningu'));
    }
    return response.json() as Promise<ScreeningCriterionListResponse>;
  }

  async createScreeningCriterion(
    projectId: string,
    payload: ScreeningCriterionCreatePayload
  ): Promise<ScreeningCriterionResponse> {
    let response: Response;
    try {
      response = await fetch(`${API_BASE_URL}/projects/${projectId}/screening/criteria`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify(payload),
      });
    } catch {
      throw new Error('Nie udało się utworzyć kryterium screeningu.');
    }
    if (!response.ok) {
      throw new Error(await formatFastApiError(response, 'utworzyć kryterium screeningu'));
    }
    return response.json() as Promise<ScreeningCriterionResponse>;
  }

  async updateScreeningCriterion(
    projectId: string,
    criterionId: string,
    payload: ScreeningCriterionUpdatePayload
  ): Promise<ScreeningCriterionResponse> {
    let response: Response;
    try {
      response = await fetch(
        `${API_BASE_URL}/projects/${projectId}/screening/criteria/${criterionId}`,
        {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
          body: JSON.stringify(payload),
        }
      );
    } catch {
      throw new Error('Nie udało się zaktualizować kryterium screeningu.');
    }
    if (!response.ok) {
      throw new Error(await formatFastApiError(response, 'zaktualizować kryterium screeningu'));
    }
    return response.json() as Promise<ScreeningCriterionResponse>;
  }

  async deactivateScreeningCriterion(
    projectId: string,
    criterionId: string
  ): Promise<ScreeningCriterionResponse> {
    let response: Response;
    try {
      response = await fetch(
        `${API_BASE_URL}/projects/${projectId}/screening/criteria/${criterionId}/deactivate`,
        {
          method: 'PATCH',
          headers: { Accept: 'application/json' },
        }
      );
    } catch {
      throw new Error('Nie udało się dezaktywować kryterium screeningu.');
    }
    if (!response.ok) {
      throw new Error(await formatFastApiError(response, 'dezaktywować kryterium screeningu'));
    }
    return response.json() as Promise<ScreeningCriterionResponse>;
  }

  async getDuplicateGroups(projectId: string): Promise<ApiDuplicateGroupListResponse> {
    const response = await fetch(`${API_BASE_URL}/projects/${projectId}/duplicate-groups`, {
      headers: {
        Accept: 'application/json',
      },
    });

    if (!response.ok) {
      if (response.status === 404) {
        throw new Error(`Projekt '${projectId}' nie został odnaleziony w API backendu.`);
      }
      throw new Error(`Błąd serwera API backend (HTTP ${response.status}): Nie udało się pobrać grup duplikatów.`);
    }

    const data: ApiDuplicateGroupListResponse = await response.json();
    return data;
  }

  async postDuplicateGroupDecision(
    projectId: string,
    groupId: string,
    decision: DuplicateDecisionType,
    rationale?: string
  ): Promise<ApiDuplicateGroupDecisionResponse> {
    const response = await fetch(
      `${API_BASE_URL}/projects/${projectId}/duplicate-groups/${groupId}/decision`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'application/json',
        },
        body: JSON.stringify({ decision, rationale: rationale || null }),
      }
    );

    if (!response.ok) {
      if (response.status === 404) {
        throw new Error(`Grupa lub projekt nie zostały odnalezione (HTTP 404).`);
      }
      if (response.status === 422) {
        throw new Error(`Niepoprawny format decyzji w żądaniu (HTTP 422).`);
      }
      throw new Error(`Nie udało się zapisać decyzji w API backendu (HTTP ${response.status}).`);
    }

    const data: ApiDuplicateGroupDecisionResponse = await response.json();
    return data;
  }

  async getDuplicateGroupDecision(
    projectId: string,
    groupId: string
  ): Promise<ApiDuplicateGroupDecisionResponse> {
    const response = await fetch(
      `${API_BASE_URL}/projects/${projectId}/duplicate-groups/${groupId}/decision`,
      {
        headers: {
          Accept: 'application/json',
        },
      }
    );

    if (!response.ok) {
      throw new Error(`Błąd pobierania decyzji dla grupy ${groupId} (HTTP ${response.status}).`);
    }

    const data: ApiDuplicateGroupDecisionResponse = await response.json();
    return data;
  }

  async getWorkflowStatus(
    projectId: string,
    reviewerId = 'default_reviewer'
  ): Promise<ApiProjectWorkflowStatusResponse | null> {
    let response: Response;
    try {
      response = await fetch(
        `${API_BASE_URL}/projects/${projectId}/workflow-status?reviewer_id=${encodeURIComponent(reviewerId)}`,
        { headers: { Accept: 'application/json' } }
      );
    } catch {
      return null;
    }
    if (!response.ok) return null;
    return response.json() as Promise<ApiProjectWorkflowStatusResponse>;
  }

  async getPrismaMetrics(
    projectId: string,
    reviewerId = 'default_reviewer'
  ): Promise<PrismaMetricsResponse> {
    let response: Response;
    try {
      response = await fetch(
        `${API_BASE_URL}/projects/${projectId}/prisma/metrics?reviewer_id=${encodeURIComponent(reviewerId)}`,
        { headers: { Accept: 'application/json' } }
      );
    } catch {
      throw new Error('Nie udało się połączyć z backendem. Sprawdź połączenie.');
    }
    if (!response.ok) throw new Error(await formatFastApiError(response, 'pobrać metryk PRISMA'));
    return response.json() as Promise<PrismaMetricsResponse>;
  }
}

export const projectApiService: ProjectApiService = new MixedProjectApiService();
export { mapPrismaMetricsResponseToFunnel };
