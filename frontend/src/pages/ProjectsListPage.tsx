import React from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowRight, Activity, Calendar } from 'lucide-react';
import { useProject } from '../context/ProjectContext';
import { Card } from '../components/common/Card';

export const ProjectsListPage: React.FC = () => {
  const { projects, setActiveProjectId } = useProject();
  const navigate = useNavigate();

  const handleSelectProject = (id: string) => {
    setActiveProjectId(id);
    navigate(`/projects/${id}/dashboard`);
  };

  return (
    <div style={{ maxWidth: '1000px', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h2 style={{ fontSize: '1.4rem', fontWeight: 800, color: 'var(--text-primary)' }}>
            Systematyczne Przeglądy Literatury (SLR Projects)
          </h2>
          <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
            Zarządzaj swoimi badaniami, protokołami przeglądu oraz bazami publikacji.
          </p>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
        {projects.map((project) => (
          <Card
            key={project.id}
            title={project.title}
            subtitle={`Wersja Protokołu: v${project.protocolVersion}`}
            action={
              <button
                onClick={() => handleSelectProject(project.id)}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px',
                  padding: '6px 12px',
                  borderRadius: 'var(--radius-md)',
                  backgroundColor: 'var(--accent-primary)',
                  color: '#fff',
                  fontSize: '0.8rem',
                  fontWeight: 600,
                }}
              >
                <span>Otwórz</span>
                <ArrowRight size={14} />
              </button>
            }
          >
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                {project.description}
              </p>

              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  paddingTop: '12px',
                  borderTop: '1px solid var(--border-subtle)',
                  fontSize: '0.75rem',
                  color: 'var(--text-muted)',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <Activity size={14} style={{ color: 'var(--accent-primary)' }} />
                  <span>Zidentyfikowane: <strong>{project.prismaMetrics.totalIdentified}</strong></span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <Calendar size={14} />
                  <span>{new Date(project.updatedAt).toLocaleDateString('pl-PL')}</span>
                </div>
              </div>

              {project.nextAction && (
                <div
                  style={{
                    backgroundColor: 'var(--bg-primary)',
                    padding: '8px 12px',
                    borderRadius: 'var(--radius-md)',
                    border: '1px solid var(--border-strong)',
                    fontSize: '0.75rem',
                    color: 'var(--text-secondary)',
                  }}
                >
                  <strong style={{ color: 'var(--status-warning-text)' }}>Next Action:</strong> {project.nextAction.title}
                </div>
              )}
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
};
