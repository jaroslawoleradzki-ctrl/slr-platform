import React from 'react';
import { ArrowRight, AlertTriangle, CheckCircle2 } from 'lucide-react';
import { useNavigate, useParams } from 'react-router-dom';
import { useProject } from '../../context/ProjectContext';
import { deriveNextAction } from '../../selectors/workflowNextAction';

/**
 * Displays the next recommended workflow action derived from WorkflowNavigationStatus.
 *
 * Derivation logic lives exclusively in `selectors/workflowNextAction.ts`.
 * This component only handles rendering and navigation.
 */
export const NextActionCard: React.FC = () => {
  const { activeProject, workflowStatus, workflowStatusLoading } = useProject();
  const navigate = useNavigate();
  const { projectId } = useParams<{ projectId?: string }>();
  const currentId = projectId || activeProject?.id || '';

  if (!activeProject || workflowStatusLoading || !workflowStatus) return null;

  const nextAction = deriveNextAction(workflowStatus);
  if (!nextAction) return null;

  const isUrgent = nextAction.severity === 'urgent';

  return (
    <div
      style={{
        backgroundColor: isUrgent ? 'var(--status-warning-bg)' : 'var(--accent-subtle)',
        border: `1px solid ${isUrgent ? 'var(--status-warning-border)' : 'var(--accent-primary)'}`,
        borderRadius: 'var(--radius-lg)',
        padding: '20px 24px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: '20px',
        boxShadow: 'var(--shadow-md)',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: '16px' }}>
        <div
          style={{
            width: '40px',
            height: '40px',
            borderRadius: '50%',
            backgroundColor: isUrgent ? 'var(--status-warning-border)' : 'var(--accent-primary)',
            color: '#fff',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0,
          }}
        >
          {isUrgent ? <AlertTriangle size={20} /> : <CheckCircle2 size={20} />}
        </div>

        <div>
          <span
            style={{
              fontSize: '0.7rem',
              textTransform: 'uppercase',
              fontWeight: 700,
              letterSpacing: '0.05em',
              color: isUrgent ? 'var(--status-warning-text)' : 'var(--accent-primary)',
            }}
          >
            Kolejny Krok Procesu
          </span>

          <h3
            style={{
              fontSize: '1.1rem',
              fontWeight: 700,
              color: 'var(--text-primary)',
              marginTop: '2px',
            }}
          >
            {nextAction.title}
          </h3>

          <p
            style={{
              fontSize: '0.875rem',
              color: 'var(--text-secondary)',
              marginTop: '4px',
              maxWidth: '720px',
            }}
          >
            {nextAction.description}
          </p>
        </div>
      </div>

      <button
        onClick={() => navigate(`/projects/${currentId}/${nextAction.targetStageId}`)}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '8px',
          padding: '10px 18px',
          borderRadius: 'var(--radius-md)',
          backgroundColor: isUrgent ? 'var(--status-warning-border)' : 'var(--accent-primary)',
          color: '#fff',
          fontWeight: 600,
          fontSize: '0.875rem',
          whiteSpace: 'nowrap',
          boxShadow: 'var(--shadow-sm)',
          transition: 'all 0.15s ease',
        }}
      >
        <span>{nextAction.actionLabel}</span>
        <ArrowRight size={16} />
      </button>
    </div>
  );
};
