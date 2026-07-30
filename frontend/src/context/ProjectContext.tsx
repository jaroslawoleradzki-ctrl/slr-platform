import React, { createContext, useContext, useEffect, useRef, useState } from 'react';
import {
  EditableSearchStrategy,
  SearchExecutionResult,
  SearchResultsImportResponse,
  SLRProject,
} from '../types';
import { projectApiService } from '../services/api/projectApi';
import { MOCK_PROJECTS } from '../mocks/projectData';

interface ProjectContextType {
  projects: SLRProject[];
  activeProject: SLRProject | null;
  loading: boolean;
  error: string | null;
  setActiveProjectId: (id: string) => void;
  createNewProject: (title: string, description: string, protocolVersion: string) => Promise<SLRProject>;
  refreshProjects: () => Promise<void>;
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
  lastSearchImportResult: SearchResultsImportResponse | null;
}

const ProjectContext = createContext<ProjectContextType | undefined>(undefined);

export const ProjectProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [projects, setProjects] = useState<SLRProject[]>(MOCK_PROJECTS);
  const [activeProjectId, setActiveProjectIdState] = useState<string>('lean_energy');
  const activeProjectIdRef = useRef(activeProjectId);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
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

  const changeActiveProject = (id: string) => {
    if (id === activeProjectId) return;
    setCurrentSearchStrategy(null);
    setLastExecutedSearchStrategy(null);
    setSearchExecutionResult(null);
    setSearchPaginationError(null);
    setSearchLoadingMore(false);
    searchLoadingMoreRef.current = false;
    searchExecutionVersionRef.current += 1;
    setSelectedSearchResultIds([]);
    setLastSearchImportResult(null);
    activeProjectIdRef.current = id;
    setActiveProjectIdState(id);
  };

  const refreshProjects = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await projectApiService.getProjects();
      setProjects(data);
      if (data.length > 0 && !data.some((p) => p.id === activeProjectId)) {
        changeActiveProject(data[0].id);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Nie udało się pobrać listy projektów');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refreshProjects();
  }, []);

  const activeProject = projects.find((p) => p.id === activeProjectId) || projects[0] || null;

  const setActiveProjectId = (id: string) => {
    if (projects.some((p) => p.id === id)) {
      changeActiveProject(id);
    }
  };

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
      selected
    );
    if (activeProjectIdRef.current !== targetProjectId) return result;
    setSelectedSearchResultIds([]);
    setLastSearchImportResult(result);
    await refreshProjects();
    return result;
  };

  return (
    <ProjectContext.Provider
      value={{
        projects,
        activeProject,
        loading,
        error,
        setActiveProjectId,
        createNewProject,
        refreshProjects,
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
