import React, { useState } from 'react';
import { useProject } from '../context/ProjectContext';
import { ProjectsList } from '../components/projects/ProjectsList';
import { ProjectModal } from '../components/projects/ProjectModal';
import { SLRProject } from '../types';

export const ProjectsPage: React.FC = () => {
  const {
    projects,
    activeProject,
    loading,
    error,
    setActiveProjectId,
    createNewProject,
    updateProject,
    archiveProject,
    restoreProject,
    refreshProjects,
  } = useProject();

  const [activeTab, setActiveTab] = useState<'active' | 'archived'>('active');
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingProject, setEditingProject] = useState<SLRProject | null>(null);

  const activeProjects = projects.filter((p) => p.status !== 'archived');
  const archivedProjects = projects.filter((p) => p.status === 'archived');

  const displayedProjects = activeTab === 'active' ? activeProjects : archivedProjects;

  const handleOpenCreateModal = () => {
    setEditingProject(null);
    setIsModalOpen(true);
  };

  const handleOpenEditModal = (project: SLRProject) => {
    setEditingProject(project);
    setIsModalOpen(true);
  };

  const handleModalSubmit = async (title: string, description: string, protocolVersion: string) => {
    if (editingProject) {
      await updateProject(editingProject.id, {
        title,
        description,
        protocol_version: protocolVersion,
      });
    } else {
      await createNewProject(title, description, protocolVersion);
    }
  };

  const handleArchive = async (id: string) => {
    if (window.confirm('Czy na pewno chcesz zarchiwizować ten projekt? Dane projektu nie zostaną usunięte.')) {
      await archiveProject(id);
    }
  };

  const handleRestore = async (id: string) => {
    await restoreProject(id);
  };

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      {/* Header section */}
      <div className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between border-b border-slate-700/80 pb-5">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Zarządzanie Projektami SLR</h1>
          <p className="text-sm text-slate-400 mt-1">
            Zarządzaj trwałymi przeglądami literatury, twórz nowe projekty i zmieniaj aktywny projekt.
          </p>
        </div>

        <button
          onClick={handleOpenCreateModal}
          className="inline-flex items-center justify-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow-md hover:bg-indigo-500 transition-colors"
        >
          <span>+ Utwórz Nowy Projekt</span>
        </button>
      </div>

      {/* Tabs and counts */}
      <div className="mb-6 flex items-center justify-between">
        <div className="flex gap-2 rounded-lg bg-slate-900/60 p-1 border border-slate-800">
          <button
            onClick={() => setActiveTab('active')}
            className={`rounded-md px-4 py-1.5 text-sm font-medium transition-colors ${
              activeTab === 'active'
                ? 'bg-slate-800 text-slate-100 shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Aktywne Projekty ({activeProjects.length})
          </button>
          <button
            onClick={() => setActiveTab('archived')}
            className={`rounded-md px-4 py-1.5 text-sm font-medium transition-colors ${
              activeTab === 'archived'
                ? 'bg-slate-800 text-slate-100 shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Zarchiwizowane ({archivedProjects.length})
          </button>
        </div>

        <button
          onClick={() => void refreshProjects()}
          className="text-xs text-slate-400 hover:text-slate-200 underline"
        >
          Odśwież Listę
        </button>
      </div>

      {/* Error display */}
      {error && (
        <div className="mb-6 rounded-xl border border-rose-500/20 bg-rose-500/10 p-4 text-sm text-rose-300">
          <p className="font-semibold">Błąd ładowania projektów:</p>
          <p>{error}</p>
        </div>
      )}

      {/* Loading state */}
      {loading ? (
        <div className="flex flex-col items-center justify-center py-16">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-indigo-500 border-t-transparent mb-4" />
          <p className="text-sm text-slate-400">Ładowanie trwałej listy projektów z bazy danych...</p>
        </div>
      ) : displayedProjects.length === 0 ? (
        /* Empty State */
        <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-slate-700 bg-slate-800/40 py-16 px-4 text-center">
          <div className="mb-3 rounded-full bg-slate-700/50 p-3 text-slate-400">
            📁
          </div>
          <h3 className="text-lg font-semibold text-slate-200 mb-1">
            {activeTab === 'active' ? 'Brak aktywnych projektów' : 'Brak zarchiwizowanych projektów'}
          </h3>
          <p className="max-w-md text-sm text-slate-400 mb-6">
            {activeTab === 'active'
              ? 'Nie utworzono jeszcze żadnego projektu SLR. Kliknij poniższy przycisk, aby rozpocząć nowy przegląd.'
              : 'Wszystkie utworzone projekty są w tej chwili aktywne.'}
          </p>
          {activeTab === 'active' && (
            <button
              onClick={handleOpenCreateModal}
              className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500"
            >
              + Utwórz Pierwszy Projekt
            </button>
          )}
        </div>
      ) : (
        /* Project Grid */
        <ProjectsList
          projects={displayedProjects}
          activeProjectId={activeProject?.id || null}
          onSelectProject={setActiveProjectId}
          onEditProject={handleOpenEditModal}
          onArchiveProject={handleArchive}
          onRestoreProject={handleRestore}
        />
      )}

      {/* Create / Edit Modal */}
      <ProjectModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSubmit={handleModalSubmit}
        projectToEdit={editingProject}
      />
    </div>
  );
};
