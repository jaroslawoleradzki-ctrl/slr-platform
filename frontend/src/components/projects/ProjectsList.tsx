import React from 'react';
import { SLRProject } from '../../types';
import { Badge } from '../common/Badge';
import { Button } from '../common/Button';
import {
  FolderCheck, CheckCircle2, Edit3,
  Archive, RotateCcw, Tag, ArrowRight, Trash2
} from 'lucide-react';

interface ProjectsListProps {
  projects: SLRProject[];
  activeProjectId: string | null;
  onOpenProject: (project: SLRProject) => void;
  onEditProject: (project: SLRProject) => void;
  onArchiveProject: (project: SLRProject) => void;
  onRestoreProject: (id: string) => void;
  onDeleteProject: (project: SLRProject) => void;
}

export const ProjectsList: React.FC<ProjectsListProps> = ({
  projects,
  activeProjectId,
  onOpenProject,
  onEditProject,
  onArchiveProject,
  onRestoreProject,
  onDeleteProject,
}) => {
  return (
    <div
      style={{
        backgroundColor: 'var(--bg-surface)',
        border: '1px solid var(--border-subtle)',
        borderRadius: 'var(--radius-lg)',
        overflow: 'hidden',
        boxShadow: 'var(--shadow-sm)',
      }}
    >
      <div style={{ overflowX: 'auto' }}>
        <table
          style={{
            width: '100%',
            borderCollapse: 'collapse',
            textAlign: 'left',
            fontSize: '0.875rem',
          }}
        >
          <thead>
            <tr
              style={{
                backgroundColor: 'var(--bg-surface-elevated)',
                borderBottom: '1px solid var(--border-subtle)',
                color: 'var(--text-secondary)',
                fontSize: '0.8rem',
                textTransform: 'uppercase',
                letterSpacing: '0.05em',
              }}
            >
              <th style={{ padding: '14px 18px', fontWeight: 600 }}>Projekt</th>
              <th style={{ padding: '14px 18px', fontWeight: 600 }}>Opis Zakresu</th>
              <th style={{ padding: '14px 18px', fontWeight: 600, width: '110px' }}>Protokół</th>
              <th style={{ padding: '14px 18px', fontWeight: 600, width: '190px' }}>Status</th>
              <th style={{ padding: '14px 18px', fontWeight: 600, textAlign: 'right', width: '280px' }}>Akcje</th>
            </tr>
          </thead>
          <tbody>
            {projects.map((project) => {
              const isActive = project.id === activeProjectId;
              const isArchived = project.status === 'archived';

              return (
                <tr
                  key={project.id}
                  onClick={() => {
                    if (!isArchived) {
                      onOpenProject(project);
                    }
                  }}
                  style={{
                    borderBottom: '1px solid var(--border-subtle)',
                    backgroundColor: isActive
                      ? 'rgba(99, 102, 241, 0.05)'
                      : isArchived
                      ? 'rgba(15, 23, 42, 0.4)'
                      : 'transparent',
                    cursor: isArchived ? 'default' : 'pointer',
                    transition: 'background-color 0.15s ease',
                  }}
                >
                  {/* Title & Project ID */}
                  <td style={{ padding: '16px 18px', verticalAlign: 'top' }}>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                      <span
                        style={{
                          fontWeight: 700,
                          fontSize: '0.95rem',
                          color: 'var(--text-primary)',
                          lineHeight: 1.3,
                        }}
                      >
                        {project.title}
                      </span>
                      <code
                        style={{
                          fontSize: '0.75rem',
                          fontFamily: 'var(--font-mono)',
                          color: 'var(--text-muted)',
                        }}
                      >
                        ID: {project.id}
                      </code>
                    </div>
                  </td>

                  {/* Description */}
                  <td style={{ padding: '16px 18px', verticalAlign: 'top', color: 'var(--text-secondary)' }}>
                    <div
                      style={{
                        display: '-webkit-box',
                        WebkitLineClamp: 2,
                        WebkitBoxOrient: 'vertical',
                        overflow: 'hidden',
                        lineHeight: 1.45,
                        maxWidth: '380px',
                      }}
                    >
                      {project.description || 'Brak opisu dla tego projektu.'}
                    </div>
                  </td>

                  {/* Protocol Version */}
                  <td style={{ padding: '16px 18px', verticalAlign: 'top' }}>
                    <span
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '4px',
                        fontSize: '0.75rem',
                        fontFamily: 'var(--font-mono)',
                        color: 'var(--text-secondary)',
                        backgroundColor: 'var(--bg-primary)',
                        padding: '2px 8px',
                        borderRadius: 'var(--radius-sm)',
                        border: '1px solid var(--border-subtle)',
                      }}
                    >
                      <Tag size={11} style={{ color: 'var(--accent-primary)' }} />
                      v{project.protocolVersion || '1.0'}
                    </span>
                  </td>

                  {/* Status Badges */}
                  <td style={{ padding: '16px 18px', verticalAlign: 'top' }}>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', alignItems: 'flex-start' }}>
                      {isArchived ? (
                        <Badge variant="pending_action" icon={<Archive size={12} />}>
                          Zarchiwizowany
                        </Badge>
                      ) : (
                        <Badge variant="completed" icon={<FolderCheck size={12} />}>
                          Aktywny
                        </Badge>
                      )}

                      {isActive && (
                        <Badge variant="info" icon={<CheckCircle2 size={12} />}>
                          Wybrany Projekt
                        </Badge>
                      )}
                    </div>
                  </td>

                  {/* Actions Row */}
                  <td style={{ padding: '16px 18px', verticalAlign: 'top', textAlign: 'right' }}>
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'flex-end',
                        gap: '6px',
                        flexWrap: 'wrap',
                      }}
                    >
                      {!isArchived && (
                        <Button
                          variant="primary"
                          size="sm"
                          onClick={(e) => {
                            e.stopPropagation();
                            onOpenProject(project);
                          }}
                          icon={<ArrowRight size={13} />}
                        >
                          Otwórz
                        </Button>
                      )}

                      <Button
                        variant="outline"
                        size="sm"
                        onClick={(e) => {
                          e.stopPropagation();
                          onEditProject(project);
                        }}
                        icon={<Edit3 size={13} />}
                        title="Edytuj dane projektu"
                      >
                        Edytuj
                      </Button>

                      {isArchived ? (
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={(e) => {
                            e.stopPropagation();
                            onRestoreProject(project.id);
                          }}
                          icon={<RotateCcw size={13} />}
                          title="Przywróć projekt"
                        >
                          Przywróć
                        </Button>
                      ) : (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={(e) => {
                            e.stopPropagation();
                            onArchiveProject(project);
                          }}
                          icon={<Archive size={13} />}
                          title="Zarchiwizuj projekt"
                        >
                          Archiwizuj
                        </Button>
                      )}

                      <Button
                        variant="danger"
                        size="sm"
                        onClick={(e) => {
                          e.stopPropagation();
                          onDeleteProject(project);
                        }}
                        icon={<Trash2 size={13} />}
                        title="Usuń projekt trwale"
                      >
                        Usuń trwale
                      </Button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};
