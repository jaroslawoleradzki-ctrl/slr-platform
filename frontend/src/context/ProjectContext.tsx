import React, { createContext, useContext, useEffect, useRef, useState, useCallback } from 'react';
import {
  EditableSearchStrategy,
  BibliographicImportResponse,
  SearchExecutionResult,
  SearchResultsImportResponse,
  SLRProject,
  NormalizationResponse,
  WorkflowNavigationStatus,
  WorkflowStageState,
  ApiDuplicateGroupListResponse,
  DuplicateDecisionStatus,
  BibliographicImportHistoryRecord,
  SearchStrategy,
} from '../types';
import { projectApiService } from '../services/api/projectApi';
import { MOCK_PROJECTS } from '../mocks/projectData';

const neutralizeSourceData = (project: SLRProject): SLRProject => ({
  ...project,
  imports: [],
  normalization: [],
  providers: project.providers.map((provider) => ({
    ...provider,
    connected: false,
    status: 'idle',
    resultsCount: 0,
    lastRunTimestamp: null,
    errorMessage: undefined,
  })),
});

const computeWorkflowStatus = (
  searchStrategy: SearchStrategy | null,
  imports: BibliographicImportHistoryRecord[] | null,
  normalization: NormalizationResponse | null,
  deduplication: ApiDuplicateGroupListResponse | null,
  errors: { search?: boolean; sources?: boolean; normalization?: boolean; deduplication?: boolean } = {}
): WorkflowNavigationStatus => {
  // Stage 1: Search Strategy
  let searchState: WorkflowStageState = 'not_started';
  let searchCount: number | null = 0;
  let searchLabel: string | null = 'Brak grup';

  if (errors.search) {
    searchState = 'error';
    searchCount = null;
    searchLabel = 'Błąd';
  } else if (searchStrategy && searchStrategy.concept_groups && searchStrategy.concept_groups.length > 0) {
    searchState = 'completed';
    searchCount = searchStrategy.concept_groups.length;
    searchLabel = `${searchCount} grup`;
  }

  // Stage 2: Sources & Ingestion
  let sourcesState: WorkflowStageState = 'not_started';
  let sourcesCount: number | null = 0;
  let sourcesLabel: string | null = 'Brak danych';

  if (errors.sources) {
    sourcesState = 'error';
    sourcesCount = null;
    sourcesLabel = 'Błąd';
  } else if (imports && imports.length > 0) {
    const hasWarning = imports.some((i) => i.status === 'warning');
    sourcesState = hasWarning ? 'warning' : 'completed';
    sourcesCount = imports.length;
    sourcesLabel = `${imports.length} importów`;
  }

  // Stage 3: Normalization
  let normState: WorkflowStageState = 'not_started';
  let normCount: number | null = null;
  let normLabel: string | null = 'Pending';

  if (errors.normalization) {
    normState = 'error';
    normCount = null;
    normLabel = 'Błąd';
  } else if (normalization) {
    if (normalization.status === 'error' || normalization.errors_count > 0) {
      normState = 'error';
      normCount = normalization.errors_count;
      normLabel = `${normalization.errors_count} błędów`;
    } else if (normalization.status === 'warning' || normalization.warnings_count > 0) {
      normState = 'warning';
      normCount = normalization.warnings_count;
      normLabel = `${normalization.warnings_count} ostrzeżeń`;
    } else {
      normState = 'completed';
      normCount = 0;
      normLabel = 'OK';
    }
  }

  // Stage 4: Deduplication
  let dedupState: WorkflowStageState = 'not_started';
  let totalGroups = 0;
  let pendingGroups = 0;
  let approvedGroups = 0;
  let rejectedGroups = 0;
  let dedupLabel: string | null = null;

  if (errors.deduplication) {
    dedupState = 'error';
    dedupLabel = 'Błąd';
  } else if (deduplication) {
    totalGroups = deduplication.total_groups_count;
    pendingGroups = deduplication.groups.filter((g) => g.status === 'PENDING').length;
    approvedGroups = deduplication.groups.filter((g) => g.status === 'APPROVE').length;
    rejectedGroups = deduplication.groups.filter((g) => g.status === 'REJECT').length;

    if (pendingGroups > 0) {
      dedupState = 'pending_action';
      dedupLabel = `${pendingGroups} do oceny`;
    } else {
      dedupState = 'completed';
      dedupLabel = 'Oceniono';
    }
  }

  return {
    search: { state: searchState, count: searchCount, label: searchLabel },
    sources: { state: sourcesState, count: sourcesCount, label: sourcesLabel },
    normalization: { state: normState, count: normCount, label: normLabel },
    deduplication: {
      state: dedupState,
      totalGroups,
      pendingGroups,
      approvedGroups,
      rejectedGroups,
      label: dedupLabel,
    },
    screening: { state: 'not_available', label: 'Niedostępne' },
    qualityAssessment: { state: 'not_available', label: 'Niedostępne' },
    dataExtraction: { state: 'not_available', label: 'Niedostępne' },
    exports: { state: 'not_available', label: 'Niedostępne' },
  };
};

interface ProjectContextType {
  projects: SLRProject[];
  activeProject: SLRProject | null;
  loading: boolean;
  error: string | null;
  workflowStatus: WorkflowNavigationStatus | null;
  workflowStatusLoading: boolean;
  workflowStatusError: string | null;
  duplicateData: ApiDuplicateGroupListResponse | null;
  duplicateGroupError: string | null;
  setActiveProjectId: (id: string) => void;
  createNewProject: (title: string, description: string, protocolVersion: string) => Promise<SLRProject>;
  refreshProjects: () => Promise<void>;
  refreshWorkflowStatus: (projectId?: string) => Promise<void>;
  updateGroupDecision: (groupId: string, newStatus: DuplicateDecisionStatus, newRationale?: string | null) => void;
  currentSearchStrategy: EditableSearchStrategy | null;
  lastExecutedSearchStrategy: EditableSearchStrategy | null;
  searchExecutionResult: SearchExecutionResult | null;
  selectedSearchResultIds: string[];
  setCurrentSearchStrategy: (strategy: EditableSearchStrategy) => void;
  setSelectedSearchResultIds: (ids: string[]) => void;
  executeSearchStrategy: (strategy: EditableSearchStrategy) => Promise<SearchExecutionResult>;
  loadMoreSearchResults: () => Promise<SearchExecutionResult | null>;
  searchLoadingMore: boolean;
  searchPaginationError: string | null;
  importSelectedSearchResults: () => Promise<SearchResultsImportResponse | null>;
  importBibliographicFile: (file: File) => Promise<BibliographicImportResponse>;
  runNormalization: () => Promise<NormalizationResponse>;
  lastSearchImportResult: SearchResultsImportResponse | null;
}

const ProjectContext = createContext<ProjectContextType | undefined>(undefined);

export const ProjectProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [projects, setProjects] = useState<SLRProject[]>(MOCK_PROJECTS.map(neutralizeSourceData));
  const [activeProjectId, setActiveProjectIdState] = useState<string>('lean_energy');
  const activeProjectIdRef = useRef(activeProjectId);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const [workflowStatus, setWorkflowStatus] = useState<WorkflowNavigationStatus | null>(null);
  const workflowStatusRef = useRef<WorkflowNavigationStatus | null>(null);
  workflowStatusRef.current = workflowStatus;

  const [workflowStatusLoading, setWorkflowStatusLoading] = useState<boolean>(true);
  const [workflowStatusError, setWorkflowStatusError] = useState<string | null>(null);
  const [duplicateData, setDuplicateData] = useState<ApiDuplicateGroupListResponse | null>(null);
  const [duplicateGroupError, setDuplicateGroupError] = useState<string | null>(null);

  const [currentSearchStrategy, setCurrentSearchStrategy] = useState<EditableSearchStrategy | null>(null);
  const [lastExecutedSearchStrategy, setLastExecutedSearchStrategy] = useState<EditableSearchStrategy | null>(null);
  const [searchExecutionResult, setSearchExecutionResult] = useState<SearchExecutionResult | null>(null);
  const [searchLoadingMore, setSearchLoadingMore] = useState(false);
  const [searchPaginationError, setSearchPaginationError] = useState<string | null>(null);
  const searchLoadingMoreRef = useRef(false);
  const searchExecutionVersionRef = useRef(0);
  const [selectedSearchResultIds, setSelectedSearchResultIds] = useState<string[]>([]);
  const [lastSearchImportResult, setLastSearchImportResult] =
    useState<SearchResultsImportResponse | null>(null);

  const refreshWorkflowStatus = useCallback(async (projectId?: string) => {
    const targetProjectId = projectId || activeProjectIdRef.current;
    if (!targetProjectId) return;

    setWorkflowStatusLoading(true);
    setWorkflowStatusError(null);
    setDuplicateGroupError(null);

    const [searchRes, importsRes, normRes, dedupRes] = await Promise.allSettled([
      projectApiService.getSearchStrategy(targetProjectId),
      projectApiService.getBibliographicImports(targetProjectId),
      projectApiService.getNormalization(targetProjectId),
      projectApiService.getDuplicateGroups(targetProjectId),
    ]);

    if (activeProjectIdRef.current !== targetProjectId) return;

    const searchStrategy = searchRes.status === 'fulfilled' ? searchRes.value : null;
    const imports = importsRes.status === 'fulfilled' ? importsRes.value : null;
    const normalization = normRes.status === 'fulfilled' ? normRes.value : null;
    const deduplication = dedupRes.status === 'fulfilled' ? dedupRes.value : null;

    if (searchRes.status === 'fulfilled' && searchStrategy) {
      const conceptGroups = searchStrategy.concept_groups.map((cg) => ({
        id: cg.group_id,
        name: cg.name,
        terms: cg.terms,
      }));
      setProjects((currentProjects) => currentProjects.map((project) => (
        project.id === targetProjectId ? { ...project, conceptGroups } : project
      )));
    }

    if (importsRes.status === 'fulfilled' && imports) {
      const importRecords = imports.map((item) => ({
        id: item.import_id,
        sourceType: item.source_type,
        filename: item.filename,
        format: item.format,
        provider: item.provider,
        query: item.query,
        totalAvailable: item.total_available,
        recordsCount: item.records_count,
        importedAt: item.created_at,
        status: item.status,
        warnings: item.warnings,
      }));
      setProjects((currentProjects) => currentProjects.map((project) => (
        project.id === targetProjectId ? { ...project, imports: importRecords } : project
      )));
    }

    if (normRes.status === 'fulfilled') {
      const result = normRes.value;
      setProjects((currentProjects) => currentProjects.map((project) => (
        project.id === targetProjectId
          ? {
              ...project,
              normalization: result ? [{
                completed: result.status === 'completed' || result.status === 'warning',
                status: result.status,
                totalRecordsProcessed: result.processed_records,
                cleanRecordsCount: result.clean_records,
                warningsCount: result.warnings_count,
                errorsCount: result.errors_count,
                warningsLog: result.audit_trail,
                rulesApplied: result.rules_applied,
                executedAt: result.executed_at,
              }] : [],
            }
          : project
      )));
    }

    if (dedupRes.status === 'fulfilled') {
      setDuplicateData(dedupRes.value);
      setDuplicateGroupError(null);
    } else {
      setDuplicateData(null);
      const errMsg = dedupRes.reason instanceof Error ? dedupRes.reason.message : 'Nie udało się pobrać grup duplikatów.';
      setDuplicateGroupError(errMsg);
    }

    const errors = {
      search: searchRes.status === 'rejected',
      sources: importsRes.status === 'rejected',
      normalization: normRes.status === 'rejected',
      deduplication: dedupRes.status === 'rejected',
    };

    const status = computeWorkflowStatus(
      searchStrategy,
      imports,
      normalization,
      deduplication,
      errors
    );

    setWorkflowStatus(status);
    setWorkflowStatusLoading(false);
  }, []);

  const updateGroupDecision = useCallback(
    (groupId: string, newStatus: DuplicateDecisionStatus, newRationale?: string | null) => {
      setDuplicateData((prev) => {
        if (!prev) return prev;
        const nextGroups = prev.groups.map((g) =>
          g.group_id === groupId
            ? { ...g, status: newStatus, rationale: newRationale ?? g.rationale }
            : g
        );
        const nextDuplicateData = { ...prev, groups: nextGroups };

        setWorkflowStatus((prevStatus) => {
          if (!prevStatus) return prevStatus;
          const totalGroups = nextDuplicateData.total_groups_count;
          const pendingGroups = nextGroups.filter((g) => g.status === 'PENDING').length;
          const approvedGroups = nextGroups.filter((g) => g.status === 'APPROVE').length;
          const rejectedGroups = nextGroups.filter((g) => g.status === 'REJECT').length;

          let dedupState: WorkflowStageState = 'not_started';
          let dedupLabel: string | null = null;

          if (pendingGroups > 0) {
            dedupState = 'pending_action';
            dedupLabel = `${pendingGroups} do oceny`;
          } else {
            dedupState = 'completed';
            dedupLabel = 'Oceniono';
          }

          return {
            ...prevStatus,
            deduplication: {
              state: dedupState,
              totalGroups,
              pendingGroups,
              approvedGroups,
              rejectedGroups,
              label: dedupLabel,
            },
          };
        });

        return nextDuplicateData;
      });
    },
    []
  );

  const changeActiveProject = useCallback((id: string) => {
    if (id === activeProjectIdRef.current && workflowStatusRef.current !== null) return;
    setCurrentSearchStrategy(null);
    setLastExecutedSearchStrategy(null);
    setSearchExecutionResult(null);
    setSearchPaginationError(null);
    setSearchLoadingMore(false);
    searchLoadingMoreRef.current = false;
    searchExecutionVersionRef.current += 1;
    setSelectedSearchResultIds([]);
    setLastSearchImportResult(null);

    setWorkflowStatus(null);
    setDuplicateData(null);
    setDuplicateGroupError(null);
    setWorkflowStatusLoading(true);

    activeProjectIdRef.current = id;
    setActiveProjectIdState(id);
    void refreshWorkflowStatus(id);
  }, [refreshWorkflowStatus]);

  const refreshProjects = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await projectApiService.getProjects();
      setProjects(data.map(neutralizeSourceData));
      await refreshWorkflowStatus(activeProjectIdRef.current);
      if (data.length > 0 && !data.some((p) => p.id === activeProjectIdRef.current)) {
        changeActiveProject(data[0].id);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Nie udało się pobrać listy projektów');
    } finally {
      setLoading(false);
    }
  }, [changeActiveProject, refreshWorkflowStatus]);

  useEffect(() => {
    void refreshProjects();
  }, []); // Run initial load once on mount

  const activeProject = projects.find((p) => p.id === activeProjectId) || projects[0] || null;

  const setActiveProjectId = useCallback((id: string) => {
    if (projects.some((p) => p.id === id) || id) {
      changeActiveProject(id);
    }
  }, [changeActiveProject, projects]);

  const createNewProject = async (title: string, description: string, protocolVersion: string) => {
    const created = await projectApiService.createProject(title, description, protocolVersion);
    await refreshProjects();
    changeActiveProject(created.id);
    return created;
  };

  const executeSearchStrategy = async (strategy: EditableSearchStrategy) => {
    if (!activeProject) throw new Error('Brak aktywnego projektu.');
    const targetProjectId = activeProjectIdRef.current;
    const executionStrategy = structuredClone(strategy);
    const executionVersion = searchExecutionVersionRef.current + 1;
    searchExecutionVersionRef.current = executionVersion;
    setSearchExecutionResult(null);
    setSearchPaginationError(null);
    setLastExecutedSearchStrategy(null);
    setSearchLoadingMore(false);
    searchLoadingMoreRef.current = false;
    setSelectedSearchResultIds([]);
    const result = await projectApiService.executeSearchStrategy(targetProjectId, executionStrategy);
    if (
      activeProjectIdRef.current !== targetProjectId
      || searchExecutionVersionRef.current !== executionVersion
    ) return result;
    setLastExecutedSearchStrategy(executionStrategy);
    setSearchExecutionResult(result);
    return result;
  };

  const loadMoreSearchResults = async (): Promise<SearchExecutionResult | null> => {
    const current = searchExecutionResult;
    if (!current || !current.has_more || searchLoadingMoreRef.current) return null;
    if (!current.next_cursor) {
      setSearchPaginationError('Nie można pobrać kolejnych wyników: brak cursoru.');
      setSearchExecutionResult({ ...current, next_cursor: null, has_more: false });
      return null;
    }
    const strategy = lastExecutedSearchStrategy;
    if (!strategy) {
      setSearchPaginationError('Nie można pobrać kolejnych wyników: brak strategii.');
      return null;
    }
    const targetProjectId = activeProjectIdRef.current;
    const executionVersion = searchExecutionVersionRef.current;
    searchLoadingMoreRef.current = true;
    setSearchLoadingMore(true);
    setSearchPaginationError(null);
    try {
      const page = await projectApiService.executeSearchStrategy(
        targetProjectId,
        strategy,
        current.next_cursor,
      );
      if (
        activeProjectIdRef.current !== targetProjectId
        || searchExecutionVersionRef.current !== executionVersion
      ) return page;
      if (page.has_more && !page.next_cursor) {
        throw new Error('Nie można pobrać kolejnych wyników: brak cursoru.');
      }
      const seen = new Set<string>();
      const merged = [...current.results, ...page.results].filter((record) => {
        const key = record.source_id
          ? `${record.provider}:${record.source_id}`
          : record.doi
            ? `doi:${record.doi.toLowerCase()}`
            : `id:${record.id}`;
        if (seen.has(key)) return false;
        seen.add(key);
        return true;
      });
      const mergedResult = {
        ...page,
        results: merged,
        returned_count: merged.length,
      };
      setSearchExecutionResult(mergedResult);
      return mergedResult;
    } catch (error) {
      if (searchExecutionVersionRef.current !== executionVersion) return null;
      setSearchPaginationError(
        error instanceof Error ? error.message : 'Nie udało się pobrać kolejnych wyników.',
      );
      return null;
    } finally {
      if (searchExecutionVersionRef.current === executionVersion) {
        searchLoadingMoreRef.current = false;
        setSearchLoadingMore(false);
      }
    }
  };

  const importSelectedSearchResults = async () => {
    if (!activeProject || !searchExecutionResult) return null;
    const targetProjectId = activeProjectIdRef.current;
    const selected = searchExecutionResult.results.filter((record) =>
      selectedSearchResultIds.includes(record.id)
    );
    if (selected.length === 0) return null;
    const result = await projectApiService.importSearchResults(
      targetProjectId,
      selected,
      {
        provider: (searchExecutionResult.providers && searchExecutionResult.providers.length > 0)
          ? (searchExecutionResult.providers[0] as 'openalex' | 'crossref')
          : (selected[0]?.provider as 'openalex' | 'crossref' | undefined),
        query: searchExecutionResult.rendered_query,
        total_available: searchExecutionResult.total_count,
      },
    );
    if (activeProjectIdRef.current !== targetProjectId) return result;
    setSelectedSearchResultIds([]);
    setLastSearchImportResult(result);
    await refreshProjects();
    await refreshWorkflowStatus(targetProjectId);
    return result;
  };

  const importBibliographicFile = async (file: File) => {
    const targetProjectId = activeProjectIdRef.current;
    const result = await projectApiService.importBibliographicFile(
      targetProjectId,
      file,
    );
    await refreshWorkflowStatus(targetProjectId);
    return result;
  };

  const runNormalization = async () => {
    const targetProjectId = activeProjectIdRef.current;
    const result = await projectApiService.runNormalization(targetProjectId);
    await refreshWorkflowStatus(targetProjectId);
    return result;
  };

  return (
    <ProjectContext.Provider
      value={{
        projects,
        activeProject,
        loading,
        error,
        workflowStatus,
        workflowStatusLoading,
        workflowStatusError,
        duplicateData,
        duplicateGroupError,
        setActiveProjectId,
        createNewProject,
        refreshProjects,
        refreshWorkflowStatus,
        updateGroupDecision,
        currentSearchStrategy,
        lastExecutedSearchStrategy,
        searchExecutionResult,
        selectedSearchResultIds,
        setCurrentSearchStrategy,
        setSelectedSearchResultIds,
        executeSearchStrategy,
        loadMoreSearchResults,
        searchLoadingMore,
        searchPaginationError,
        importSelectedSearchResults,
        importBibliographicFile,
        runNormalization,
        lastSearchImportResult,
      }}
    >
      {children}
    </ProjectContext.Provider>
  );
};

export const useProject = (): ProjectContextType => {
  const context = useContext(ProjectContext);
  if (!context) {
    throw new Error('useProject must be used within a ProjectProvider');
  }
  return context;
};

export const useWorkflowNavigationStatus = (explicitProjectId?: string) => {
  const { workflowStatus, workflowStatusLoading, workflowStatusError, activeProject, refreshWorkflowStatus } = useProject();
  const targetId = explicitProjectId || activeProject?.id;

  useEffect(() => {
    if (targetId && activeProject?.id === targetId && !workflowStatus) {
      void refreshWorkflowStatus(targetId);
    }
  }, [targetId, activeProject?.id, workflowStatus, refreshWorkflowStatus]);

  return {
    status: workflowStatus,
    loading: workflowStatusLoading,
    error: workflowStatusError,
    refresh: refreshWorkflowStatus,
  };
};
