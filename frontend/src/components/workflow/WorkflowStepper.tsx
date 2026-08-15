import React from 'react';
import { NavLink, useParams } from 'react-router-dom';
import { CheckCircle2, AlertCircle, Clock, Circle } from 'lucide-react';
import { useProject } from '../../context/ProjectContext';
import { WorkflowStageState } from '../../types';

export const WorkflowStepper: React.FC = () => {
  const { projectId } = useParams<{ projectId?: string }>();
  const { activeProject, workflowStatus } = useProject();
  const currentId = projectId || activeProject?.id || 'lean_energy';

  const steps = [
    {
      id: 'search',
      label: 'Search Strategy',
      path: `/projects/${currentId}/search`,
      status: workflowStatus?.search.state || 'not_started',
      alertCount: null,
    },
    {
      id: 'sources',
      label: 'Sources & Ingestion',
      path: `/projects/${currentId}/sources`,
      status: workflowStatus?.sources.state || 'not_started',
      alertCount: null,
    },
    {
      id: 'normalize',
      label: 'Normalization',
      path: `/projects/${currentId}/normalize`,
      status: workflowStatus?.normalization.state || 'not_started',
      alertCount: null,
    },
    {
      id: 'dedup',
      label: 'Deduplication',
      path: `/projects/${currentId}/dedup`,
      status: workflowStatus?.deduplication.state || 'not_started',
      alertCount:
        workflowStatus?.deduplication && workflowStatus.deduplication.pendingGroups > 0
          ? workflowStatus.deduplication.pendingGroups
          : null,
    },
    {
      id: 'screen',
      label: 'Screening',
      path: `/projects/${currentId}/screen/title-abstract`,
      status: workflowStatus?.screening.state || 'not_started',
      alertCount: null,
    },
    {
      id: 'qa',
      label: 'Quality Assessment',
      path: `/projects/${currentId}/qa`,
      status: workflowStatus?.qualityAssessment.state || 'not_available',
      alertCount: null,
    },
    {
      id: 'extract',
      label: 'Data Extraction',
      path: `/projects/${currentId}/extract`,
      status: 'not_available' as const,
      alertCount: null,
    },
    {
      id: 'synthesis',
      label: 'Evidence Synthesis',
      path: `/projects/${currentId}/synthesis`,
      status: 'in_progress' as const,
      alertCount: null,
    },
    {
      id: 'exports',
      label: 'Exports & PRISMA',
      path: `/projects/${currentId}/exports`,
      status: 'not_available' as const,
      alertCount: null,
    },
  ];

  const getStatusIcon = (status: WorkflowStageState) => {
    switch (status) {
      case 'completed':
        return <CheckCircle2 size={14} style={{ color: 'var(--status-success-text)' }} />;
      case 'pending_action':
      case 'warning':
        return <AlertCircle size={14} style={{ color: 'var(--status-warning-text)' }} />;
      case 'error':
        return <AlertCircle size={14} style={{ color: 'var(--status-error-text)' }} />;
      case 'in_progress':
        return <Circle size={14} style={{ color: 'var(--status-info-text)' }} />;
      case 'not_available':
        return <Clock size={14} style={{ color: 'var(--text-muted)', opacity: 0.5 }} />;
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
