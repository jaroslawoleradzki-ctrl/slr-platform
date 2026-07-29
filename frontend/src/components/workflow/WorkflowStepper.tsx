import React from 'react';
import { NavLink, useParams } from 'react-router-dom';
import { CheckCircle2, AlertCircle, Clock, Circle } from 'lucide-react';
import { useProject } from '../../context/ProjectContext';

export const WorkflowStepper: React.FC = () => {
  const { projectId } = useParams<{ projectId?: string }>();
  const { activeProject } = useProject();
  const currentId = projectId || activeProject?.id || 'lean_energy';

  const steps = [
    {
      id: 'search',
      label: 'Search Strategy',
      path: `/projects/${currentId}/search`,
      status: activeProject?.conceptGroups?.length ? 'completed' : 'in_progress',
    },
    {
      id: 'sources',
      label: 'Sources & Ingestion',
      path: `/projects/${currentId}/sources`,
      status: activeProject?.providers?.some((p) => p.status === 'completed') ? 'completed' : 'pending',
    },
    {
      id: 'normalize',
      label: 'Normalization',
      path: `/projects/${currentId}/normalize`,
      status: activeProject?.normalization?.[0]?.completed ? 'completed' : 'pending',
    },
    {
      id: 'dedup',
      label: 'Deduplication',
      path: `/projects/${currentId}/dedup`,
      status: activeProject?.deduplication?.candidateGroupsPendingUserReview ? 'pending_action' : 'completed',
      alertCount: activeProject?.deduplication?.candidateGroupsPendingUserReview,
    },
    {
      id: 'screen',
      label: 'Screening',
      path: `/projects/${currentId}/screen`,
      status: activeProject?.screening?.titleAbstract?.included ? 'in_progress' : 'pending',
    },
    {
      id: 'qa',
      label: 'Quality Assessment',
      path: `/projects/${currentId}/qa`,
      status: 'pending',
    },
    {
      id: 'extract',
      label: 'Data Extraction',
      path: `/projects/${currentId}/extract`,
      status: 'pending',
    },
    {
      id: 'exports',
      label: 'Exports & PRISMA',
      path: `/projects/${currentId}/exports`,
      status: 'pending',
    },
  ];

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle2 size={14} style={{ color: 'var(--status-success-text)' }} />;
      case 'pending_action':
        return <AlertCircle size={14} style={{ color: 'var(--status-warning-text)' }} />;
      case 'in_progress':
        return <Circle size={14} style={{ color: 'var(--status-info-text)' }} />;
      default:
        return <Clock size={14} style={{ color: 'var(--text-muted)' }} />;
    }
  };

  return (
    <div
      style={{
        backgroundColor: 'var(--bg-surface)',
        borderBottom: '1px solid var(--border-subtle)',
        padding: '8px 24px',
        overflowX: 'auto',
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          minWidth: 'max-content',
        }}
      >
        {steps.map((step, idx) => (
          <React.Fragment key={step.id}>
            {idx > 0 && (
              <div
                style={{
                  width: '16px',
                  height: '1px',
                  backgroundColor: 'var(--border-subtle)',
                }}
              />
            )}
            <NavLink
              to={step.path}
              style={({ isActive }) => ({
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '4px 10px',
                borderRadius: 'var(--radius-full)',
                fontSize: '0.75rem',
                fontWeight: isActive ? 600 : 500,
                color: isActive ? 'var(--text-primary)' : 'var(--text-secondary)',
                backgroundColor: isActive
                  ? 'var(--bg-surface-elevated)'
                  : 'transparent',
                border: isActive
                  ? '1px solid var(--border-strong)'
                  : '1px solid transparent',
              })}
            >
              {getStatusIcon(step.status)}
              <span>
                {idx + 1}. {step.label}
              </span>
              {step.alertCount ? (
                <span
                  style={{
                    backgroundColor: 'var(--status-warning-border)',
                    color: '#fff',
                    borderRadius: 'var(--radius-full)',
                    fontSize: '0.65rem',
                    padding: '0 5px',
                    fontWeight: 700,
                  }}
                >
                  {step.alertCount}
                </span>
              ) : null}
            </NavLink>
          </React.Fragment>
        ))}
      </div>
    </div>
  );
};
