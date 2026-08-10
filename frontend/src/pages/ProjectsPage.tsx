import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useProject } from '../context/ProjectContext';
import { ProjectsList } from '../components/projects/ProjectsList';
import { ProjectModal } from '../components/projects/ProjectModal';
import { ConfirmArchiveModal } from '../components/projects/ConfirmArchiveModal';
import { ConfirmDeleteModal } from '../components/projects/ConfirmDeleteModal';
import { Button } from '../components/common/Button';
import { EmptyState } from '../components/common/EmptyState';
import { ErrorAlert } from '../components/common/ErrorAlert';
import { LoadingSpinner } from '../components/common/LoadingSpinner';
import { SLRProject } from '../types';
import { FolderPlus, FolderCheck, Archive, RefreshCw, Layers } from 'lucide-react';


export const ProjectsPage: React.FC = () => {
  const navigate = useNavigate();
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
    deleteProject,
    refreshProjects,
  } = useProject();


  const [
    activeTab,
    setActiveTab,
  ] = useState<'active' | 'archived'>('active');
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingProject, setEditingProject] = useState<SLRProject | null>(null);
  const [archivingProject, setArchivingProject] = useState<SLRProject | null>(null);
  const [deletingProject, setDeletingProject] = useState<SLRProject | null>(null);

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

  const handleOpenProject = (project: SLRProject) => {
    if (activeProject?.id !== project.id) {
      setActiveProjectId(project.id);
    }
    navigate(`/projects/${project.id}/dashboard`);
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

  const handleRequestArchive = (project: SLRProject) => {
    setArchivingProject(project);
  };

  const handleConfirmArchive = async (id: string) => {
    await archiveProject(id);
    setArchivingProject(null);
  };

  const handleRestore = async (id: string) => {
    await restoreProject(id);
  };

  const handleRequestDelete = (project: SLRProject) => {
    setDeletingProject(project);
  };

  const handleConfirmDelete = async (id: string) => {
    await deleteProject(id);
    setDeletingProject(null);
    // If we just deleted the active project, navigate away
    if (activeProject?.id === id) {
      navigate('/projects');
    }
  };

  return (
    <div
      style={{
        maxWidth: '1200px',
        margin: '0 auto',
        padding: '24px 16px',
        display: 'flex',
        flexDirection: 'column',
        gap: '24px',
      }}
    >
      {/* Page Header */}
      <div
        style={{
          display: 'flex',
          flexDirection: 'row',
          alignItems: 'flex-start',
          justifyContent: 'space-between',
          gap: '16px',
          paddingBottom: '20px',
          borderBottom: '1px solid var(--border-subtle)',
          flexWrap: 'wrap',
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div
              style={{
                width: '36px',
                height: '36px',
                borderRadius: 'var(--radius-md)',
                backgroundColor: 'var(--bg-surface-elevated)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: 'var(--accent-primary)',
              }}
            >
              <Layers size={20} />
            </div>
            <h1 style={{ fontSize: '1.5rem', fontWeight: 800, color: 'var(--text-primary)' }}>
              Zarządzanie Projektami SLR
            </h1>
          </div>
          <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', marginTop: '6px' }}>
            Zarządzaj trwałymi przeglądami literatury, twórz nowe projekty i przełączaj aktywny kontekst roboczy.
          </p>
        </div>

        <Button
          variant="primary"
          icon={<FolderPlus size={18} />}
          onClick={handleOpenCreateModal}
        >
          + Utwórz Nowy Projekt
        </Button>
      </div>

      {/* Navigation Tabs & Refresh Bar */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '12px',
          flexWrap: 'wrap',
        }}
      >
        <div
          style={{
            display: 'inline-flex',
            backgroundColor: 'var(--bg-surface-elevated)',
            padding: '4px',
            borderRadius: 'var(--radius-md)',
            border: '1px solid var(--border-strong)',
            gap: '4px',
          }}
        >
          <button
            onClick={() => setActiveTab('active')}
            style={{
              padding: '6px 14px',
              borderRadius: 'var(--radius-sm)',
              fontSize: '0.85rem',
              fontWeight: 600,
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              backgroundColor: activeTab === 'active' ? 'var(--accent-primary)' : 'transparent',
              color: activeTab === 'active' ? '#ffffff' : 'var(--text-secondary)',
              transition: 'all 0.15s ease',
            }}
          >
            <FolderCheck size={15} />
            <span>Aktywne Projekty ({activeProjects.length})</span>
          </button>

          <button
            onClick={() => setActiveTab('archived')}
            style={{
              padding: '6px 14px',
              borderRadius: 'var(--radius-sm)',
              fontSize: '0.85rem',
              fontWeight: 600,
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              backgroundColor: activeTab === 'archived' ? 'var(--bg-surface-hover)' : 'transparent',
              color: activeTab === 'archived' ? 'var(--text-primary)' : 'var(--text-secondary)',
              transition: 'all 0.15s ease',
            }}
          >
            <Archive size={15} />
            <span>Zarchiwizowane ({archivedProjects.length})</span>
          </button>
        </div>

        <Button
          variant="outline"
          size="sm"
          icon={<RefreshCw size={14} />}
          onClick={() => void refreshProjects()}
        >
          Odśwież
        </Button>
      </div>

      {/* Error alert with retry */}
      {error && (
        <ErrorAlert
          title="Błąd ładowania projektów z bazy danych"
          message={error}
          onRetry={() => void refreshProjects()}
        />
      )}

      {/* Main Content Area */}
      {loading ? (
        <LoadingSpinner label="Pobieranie listy projektów z bazy danych..." />
      ) : displayedProjects.length === 0 ? (
        /* Empty State */
        <EmptyState
          title={activeTab === 'active' ? 'Brak aktywnych projektów' : 'Brak zarchiwizowanych projektów'}
          description={
            activeTab === 'active'
              ? 'Nie utworzono jeszcze żadnego projektu SLR. Utwórz swój pierwszy projekt przeglądu literatury.'
              : 'Wszystkie utworzone projekty znajdują się obecnie w zakładce aktywnych.'
          }
          action={
            activeTab === 'active' ? (
              <Button
                variant="primary"
                icon={<FolderPlus size={16} />}
                onClick={handleOpenCreateModal}
              >
                Utwórz Pierwszy Projekt
              </Button>
            ) : undefined
          }
        />
      ) : (
        /* Projects Cards Grid */
        <ProjectsList
          projects={displayedProjects}
          activeProjectId={activeProject?.id || null}
          onOpenProject={handleOpenProject}
          onEditProject={handleOpenEditModal}
          onArchiveProject={handleRequestArchive}
          onRestoreProject={handleRestore}
          onDeleteProject={handleRequestDelete}
        />

      )}

      {/* Create / Edit Project Modal */}
      <ProjectModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSubmit={handleModalSubmit}
        projectToEdit={editingProject}
      />

      {/* Confirmation Modal for Archiving */}
      <ConfirmArchiveModal
        isOpen={Boolean(archivingProject)}
        onClose={() => setArchivingProject(null)}
        onConfirm={handleConfirmArchive}
        project={archivingProject}
      />

      {/* Confirmation Modal for Hard Delete */}
      <ConfirmDeleteModal
        isOpen={Boolean(deletingProject)}
        onClose={() => setDeletingProject(null)}
        onConfirm={handleConfirmDelete}
        project={deletingProject}
      />

    </div>
  );
};
