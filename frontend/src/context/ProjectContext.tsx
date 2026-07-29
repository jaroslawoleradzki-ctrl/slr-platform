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
  const [selectedSearchResultIds, setSelectedSearchResultIds] = useState<string[]>([]);
  const [lastSearchImportResult, setLastSearchImportResult] =
    useState<SearchResultsImportResponse | null>(null);

  const changeActiveProject = (id: string) => {
    if (id === activeProjectId) return;
    setCurrentSearchStrategy(null);
    setLastExecutedSearchStrategy(null);
    setSearchExecutionResult(null);
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
    setSearchExecutionResult(null);
    setSelectedSearchResultIds([]);
    const result = await projectApiService.executeSearchStrategy(targetProjectId, executionStrategy);
    if (activeProjectIdRef.current !== targetProjectId) return result;
    setLastExecutedSearchStrategy(executionStrategy);
    setSearchExecutionResult(result);
    return result;
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
