import React from 'react';
import { SLRProject } from '../../types';

interface ProjectsListProps {
  projects: SLRProject[];
  activeProjectId: string | null;
  onSelectProject: (id: string) => void;
  onEditProject: (project: SLRProject) => void;
  onArchiveProject: (id: string) => void;
  onRestoreProject: (id: string) => void;
}

export const ProjectsList: React.FC<ProjectsListProps> = ({
  projects,
  activeProjectId,
  onSelectProject,
  onEditProject,
  onArchiveProject,
  onRestoreProject,
}) => {
  return (
    <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
      {projects.map((project) => {
        const isActive = project.id === activeProjectId;
        const isArchived = project.status === 'archived';

        return (
          <div
            key={project.id}
            className={`relative flex flex-col justify-between rounded-xl border p-5 transition-all shadow-md ${
              isActive
                ? 'border-indigo-500 bg-slate-800/90 ring-1 ring-indigo-500'
                : isArchived
                ? 'border-slate-700 bg-slate-900/50 opacity-75'
                : 'border-slate-700 bg-slate-800 hover:border-slate-600'
            }`}
          >
            <div>
              <div className="mb-3 flex items-start justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span
                    className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                      isArchived
                        ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                        : 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                    }`}
                  >
                    {isArchived ? 'Zarchiwizowany' : 'Aktywny'}
                  </span>
                  {isActive && (
                    <span className="inline-flex items-center rounded-full bg-indigo-500/20 px-2.5 py-0.5 text-xs font-semibold text-indigo-300 border border-indigo-500/30">
                      Wybrany
                    </span>
                  )}
                </div>
                <span className="text-xs font-mono text-slate-400">
                  v{project.protocolVersion}
                </span>
              </div>

              <h3 className="text-lg font-bold text-slate-100 mb-2 line-clamp-2">
                {project.title}
              </h3>

              <p className="text-sm text-slate-400 mb-4 line-clamp-3">
                {project.description || 'Brak opisu dla tego przeglądu.'}
              </p>
            </div>

            <div className="space-y-3 pt-3 border-t border-slate-700/60">
              <div className="flex items-center justify-between text-xs text-slate-400">
                <span>ID: <code className="font-mono text-slate-300">{project.id}</code></span>
                <span>{new Date(project.createdAt).toLocaleDateString()}</span>
              </div>

              <div className="flex items-center justify-between gap-2 pt-1">
                {!isArchived && (
                  <button
                    onClick={() => onSelectProject(project.id)}
                    disabled={isActive}
                    className={`flex-1 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                      isActive
                        ? 'bg-slate-700 text-slate-400 cursor-default'
                        : 'bg-indigo-600 text-white hover:bg-indigo-500'
                    }`}
                  >
                    {isActive ? 'Aktywny Projekt' : 'Otwórz Projekt'}
                  </button>
                )}

                <button
                  onClick={() => onEditProject(project)}
                  className="rounded-lg border border-slate-600 px-2.5 py-1.5 text-xs font-medium text-slate-300 hover:bg-slate-700"
                  title="Edytuj dane projektu"
                >
                  Edytuj
                </button>

                {isArchived ? (
                  <button
                    onClick={() => onRestoreProject(project.id)}
                    className="rounded-lg border border-amber-600/50 bg-amber-500/10 px-2.5 py-1.5 text-xs font-medium text-amber-300 hover:bg-amber-500/20"
                    title="Przywróć projekt"
                  >
                    Przywróć
                  </button>
                ) : (
                  <button
                    onClick={() => onArchiveProject(project.id)}
                    className="rounded-lg border border-slate-600 px-2.5 py-1.5 text-xs font-medium text-slate-400 hover:border-amber-600/50 hover:text-amber-300"
                    title="Zarchiwizuj projekt"
                  >
                    Zarchiwizuj
                  </button>
                )}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
};
