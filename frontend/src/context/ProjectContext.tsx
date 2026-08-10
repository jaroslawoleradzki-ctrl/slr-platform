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
  ProjectUpdatePayload,
} from '../types';
import { MOCK_PROJECTS } from '../mocks/projectData';
import { projectApiService } from '../services/api/projectApi';

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
  updateProject: (id: string, payload: ProjectUpdatePayload) => Promise<SLRProject>;
  archiveProject: (id: string) => Promise<SLRProject>;
  restoreProject: (id: string) => Promise<SLRProject>;
  deleteProject: (id: string) => Promise<void>;
  refreshProjects: () => Promise<void>;
  refreshWorkflowStatus: (projectId?: string) => Promise<void>;
  runDeduplication: () => Promise<ApiDuplicateGroupListResponse>;
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
  const [projects, setProjects] = useState<SLRProject[]>(() => [...MOCK_PROJECTS]);
  const [activeProjectId, setActiveProjectIdState] = useState<string>(
    () => localStorage.getItem('slr_active_project_id') || 'lean_energy'
  );
  const activeProjectIdRef = useRef(activeProjectId);
  const [loading, setLoading] = useState<boolean>(true);
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

  const refreshProjects = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const list = await projectApiService.getProjects(true);
      setProjects(list);

      const activeList = list.filter((p) => p.status === 'active');
      let targetId = activeProjectIdRef.current;

      const currentActiveObj = list.find((p) => p.id === targetId);
      if (!currentActiveObj || currentActiveObj.status !== 'active') {
        targetId = activeList.length > 0 ? activeList[0].id : '';
      }

      if (targetId) {
        setActiveProjectIdState(targetId);
        activeProjectIdRef.current = targetId;
        localStorage.setItem('slr_active_project_id', targetId);
        void refreshWorkflowStatus(targetId);
      } else {
        setActiveProjectIdState('');
        activeProjectIdRef.current = '';
        localStorage.removeItem('slr_active_project_id');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Błąd pobierania projektów');
    } finally {
      setLoading(false);
    }
  }, [refreshWorkflowStatus]);

  useEffect(() => {
    void refreshProjects();
  }, [refreshProjects]);

  const setActiveProjectId = useCallback((id: string) => {
    if (activeProjectIdRef.current === id) return;
    setActiveProjectIdState(id);
    activeProjectIdRef.current = id;
    localStorage.setItem('slr_active_project_id', id);

    setCurrentSearchStrategy(null);
    setLastExecutedSearchStrategy(null);
    setSearchExecutionResult(null);
    setSelectedSearchResultIds([]);
    setLastSearchImportResult(null);

    setWorkflowStatus(null);
    void refreshWorkflowStatus(id);
  }, [refreshWorkflowStatus]);

  const activeProject = projects.find((p) => p.id === activeProjectId) || null;

  const createNewProject = async (
    title: string,
    description: string,
    protocolVersion: string
  ): Promise<SLRProject> => {
    const created = await projectApiService.createProject(title, description, protocolVersion);
    await refreshProjects();
    setActiveProjectId(created.id);
    return created;
  };

  const updateProject = async (
    id: string,
    payload: ProjectUpdatePayload
  ): Promise<SLRProject> => {
    const updated = await projectApiService.updateProject(id, payload);
    await refreshProjects();
    return updated;
  };

  const archiveProject = async (id: string): Promise<SLRProject> => {
    const archived = await projectApiService.archiveProject(id);
    await refreshProjects();
    return archived;
  };

  const restoreProject = async (id: string): Promise<SLRProject> => {
    const restored = await projectApiService.restoreProject(id);
    await refreshProjects();
    return restored;
  };

  const deleteProject = async (id: string): Promise<void> => {
    await projectApiService.deleteProject(id);
    await refreshProjects();
  };

  const executeSearchStrategy = async (strategy: EditableSearchStrategy): Promise<SearchExecutionResult> => {
    const targetProjectId = activeProjectIdRef.current;
    searchExecutionVersionRef.current += 1;
    const currentVersion = searchExecutionVersionRef.current;
    setSearchLoadingMore(false);
    setSearchPaginationError(null);
    setSelectedSearchResultIds([]);
    setLastSearchImportResult(null);

    const result = await projectApiService.executeSearchStrategy(targetProjectId, strategy);
    if (activeProjectIdRef.current !== targetProjectId || searchExecutionVersionRef.current !== currentVersion) {
      return result;
    }
    setLastExecutedSearchStrategy(strategy);
    setSearchExecutionResult(result);
    void refreshWorkflowStatus(targetProjectId);
    return result;
  };

  const loadMoreSearchResults = async (): Promise<SearchExecutionResult | null> => {
    const targetProjectId = activeProjectIdRef.current;
    if (!lastExecutedSearchStrategy || !searchExecutionResult?.next_cursor || searchLoadingMoreRef.current) {
      return null;
    }

    const currentVersion = searchExecutionVersionRef.current;
    searchLoadingMoreRef.current = true;
    setSearchLoadingMore(true);
    setSearchPaginationError(null);

    try {
      const pageResult = await projectApiService.executeSearchStrategy(
        targetProjectId,
        lastExecutedSearchStrategy,
        searchExecutionResult.next_cursor
      );

      if (activeProjectIdRef.current !== targetProjectId || searchExecutionVersionRef.current !== currentVersion) {
        return null;
      }

      const existingSourceIds = new Set(searchExecutionResult.results.map((r) => r.source_id));
      const newResults = pageResult.results.filter((r) => !existingSourceIds.has(r.source_id));
      const mergedResults = [...searchExecutionResult.results, ...newResults];

      const mergedResult: SearchExecutionResult = {
        ...pageResult,
        results: mergedResults,
        returned_count: mergedResults.length,
      };

      setSearchExecutionResult(mergedResult);
      return pageResult;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Nie udało się pobrać kolejnych wyników.';
      if (activeProjectIdRef.current === targetProjectId && searchExecutionVersionRef.current === currentVersion) {
        setSearchPaginationError(message);
      }
      throw err;
    } finally {
      if (activeProjectIdRef.current === targetProjectId && searchExecutionVersionRef.current === currentVersion) {
        searchLoadingMoreRef.current = false;
        setSearchLoadingMore(false);
      }
    }
  };

  const importSelectedSearchResults = async (): Promise<SearchResultsImportResponse | null> => {
    const targetProjectId = activeProjectIdRef.current;
    if (!searchExecutionResult || selectedSearchResultIds.length === 0) return null;

    const selectedRecords = searchExecutionResult.results.filter((rec) =>
      selectedSearchResultIds.includes(rec.id)
    );
    if (selectedRecords.length === 0) return null;

    const metadata = {
      query: lastExecutedSearchStrategy
        ? lastExecutedSearchStrategy.conceptGroups
            .map((g) => `(${g.terms.join(' OR ')})`)
            .join(' AND ')
        : undefined,
      providers: lastExecutedSearchStrategy ? lastExecutedSearchStrategy.providers : undefined,
    };

    const importResult = await projectApiService.importSearchResults(targetProjectId, selectedRecords, metadata);
    if (activeProjectIdRef.current === targetProjectId) {
      setLastSearchImportResult(importResult);
      setSelectedSearchResultIds([]);
      void refreshWorkflowStatus(targetProjectId);
    }
    return importResult;
  };

  const importBibliographicFile = async (file: File): Promise<BibliographicImportResponse> => {
    const targetProjectId = activeProjectIdRef.current;
    const result = await projectApiService.importBibliographicFile(targetProjectId, file);
    if (activeProjectIdRef.current === targetProjectId) {
      void refreshWorkflowStatus(targetProjectId);
    }
    return result;
  };

  const runNormalization = async (): Promise<NormalizationResponse> => {
    const targetProjectId = activeProjectIdRef.current;
    const result = await projectApiService.runNormalization(targetProjectId);
    if (activeProjectIdRef.current === targetProjectId) {
      void refreshWorkflowStatus(targetProjectId);
    }
    return result;
  };

  const updateGroupDecision = (
    groupId: string,
    newStatus: DuplicateDecisionStatus,
    newRationale?: string | null
  ) => {
    setDuplicateData((current) => {
      if (!current) return current;
      const updatedGroups = current.groups.map((group) =>
        group.group_id === groupId
          ? {
              ...group,
              status: newStatus,
              rationale: newRationale !== undefined ? newRationale : group.rationale,
            }
          : group
      );
      const pendingCount = updatedGroups.filter((g) => g.status === 'PENDING').length;
      return {
        ...current,
        groups: updatedGroups,
        pending_review_count: pendingCount,
      };
    });

    setWorkflowStatus((current) => {
      if (!current || !duplicateData) return current;
      const updatedGroups = duplicateData.groups.map((group) =>
        group.group_id === groupId ? { ...group, status: newStatus } : group
      );
      const pendingGroups = updatedGroups.filter((g) => g.status === 'PENDING').length;
      const approvedGroups = updatedGroups.filter((g) => g.status === 'APPROVE').length;
      const rejectedGroups = updatedGroups.filter((g) => g.status === 'REJECT').length;

      return {
        ...current,
        deduplication: {
          ...current.deduplication,
          state: pendingGroups > 0 ? 'pending_action' : 'completed',
          pendingGroups,
          approvedGroups,
          rejectedGroups,
          label: pendingGroups > 0 ? `${pendingGroups} do oceny` : 'Oceniono',
        },
      };
    });
  };

  const runDeduplication = async (): Promise<ApiDuplicateGroupListResponse> => {
    const targetProjectId = activeProjectIdRef.current;
    setWorkflowStatusLoading(true);
    setDuplicateGroupError(null);

    try {
      const result = await projectApiService.getDuplicateGroups(targetProjectId);
      if (activeProjectIdRef.current !== targetProjectId) return result;

      setDuplicateData(result);
      const pendingGroups = result.groups.filter((g) => g.status === 'PENDING').length;
      const approvedGroups = result.groups.filter((g) => g.status === 'APPROVE').length;
      const rejectedGroups = result.groups.filter((g) => g.status === 'REJECT').length;

      setWorkflowStatus((current) => current ? {
        ...current,
        deduplication: {
          state: pendingGroups > 0 ? 'pending_action' : 'completed',
          totalGroups: result.total_groups_count,
          pendingGroups,
          approvedGroups,
          rejectedGroups,
          label: pendingGroups > 0 ? `${pendingGroups} do oceny` : 'Oceniono',
        },
      } : current);
      return result;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Nie udało się uruchomić deduplikacji.';
      if (activeProjectIdRef.current === targetProjectId) setDuplicateGroupError(message);
      throw err;
    } finally {
      if (activeProjectIdRef.current === targetProjectId) setWorkflowStatusLoading(false);
    }
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
        updateProject,
        archiveProject,
        restoreProject,
        deleteProject,
        refreshProjects,
        refreshWorkflowStatus,
        runDeduplication,
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
