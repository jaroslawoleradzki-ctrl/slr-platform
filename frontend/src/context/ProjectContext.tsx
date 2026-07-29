import React, { createContext, useContext, useEffect, useState } from 'react';
import { SLRProject } from '../types';
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
}

const ProjectContext = createContext<ProjectContextType | undefined>(undefined);

export const ProjectProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [projects, setProjects] = useState<SLRProject[]>(MOCK_PROJECTS);
  const [activeProjectId, setActiveProjectIdState] = useState<string>('lean_energy');
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const refreshProjects = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await projectApiService.getProjects();
      setProjects(data);
      if (data.length > 0 && !data.some((p) => p.id === activeProjectId)) {
        setActiveProjectIdState(data[0].id);
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
      setActiveProjectIdState(id);
    }
  };

  const createNewProject = async (title: string, description: string, protocolVersion: string) => {
    const created = await projectApiService.createProject(title, description, protocolVersion);
    await refreshProjects();
    setActiveProjectIdState(created.id);
    return created;
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
        refreshProjects
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
