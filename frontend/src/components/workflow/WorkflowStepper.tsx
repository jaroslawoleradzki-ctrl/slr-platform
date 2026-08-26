import React from 'react';
import { NavLink, useParams } from 'react-router-dom';
import { useProject } from '../../context/ProjectContext';
import {
  WORKFLOW_STAGES,
  buildStagePath,
  getWorkflowStageState,
} from '../../config/workflowStages';
import {
  getStageStatusPresentation,
  getStageStatusTitle,
} from './stageStatusPresentation';

/**
 * Compact process overview (top bar).
 * Shows one small chip per stage: state icon + short label (+ pending count).
 * Full names and detailed statuses live in the sidebar; hover reveals a tooltip.
 */
export const WorkflowStepper: React.FC = () => {
  const { projectId } = useParams<{ projectId?: string }>();
  const { activeProject, workflowStatus, workflowStatusLoading } = useProject();
  const currentId = projectId || activeProject?.id;

  if (!currentId) return null;

  return (
    <div
      data-testid="workflow-stepper"
      style={{
        backgroundColor: 'var(--bg-surface)',
        borderBottom: '1px solid var(--border-subtle)',
        padding: '6px 20px',
        overflowX: 'auto',
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          minWidth: 'max-content',
        }}
      >
        {WORKFLOW_STAGES.map((stage, idx) => {
          const state = getWorkflowStageState(workflowStatus, stage);
          const presentation = getStageStatusPresentation(state, 13);
          const detailLabel =
            stage.statusKey && workflowStatus
              ? workflowStatus[stage.statusKey].label
              : null;
          const alertCount =
            stage.id === 'dedup' &&
            workflowStatus?.deduplication &&
            workflowStatus.deduplication.pendingGroups > 0
              ? workflowStatus.deduplication.pendingGroups
              : null;

          return (
            <React.Fragment key={stage.id}>
              {idx > 0 && (
                <div
                  aria-hidden="true"
                  style={{
                    width: '12px',
                    height: '1px',
                    flexShrink: 0,
                    backgroundColor: 'var(--border-subtle)',
                  }}
                />
              )}
              <NavLink
                to={buildStagePath(currentId, stage.pathSuffix)}
                title={getStageStatusTitle(stage.number, stage.fullLabel, detailLabel, presentation)}
                style={({ isActive }) => ({
                  display: 'flex',
                  alignItems: 'center',
                  gap: '5px',
                  padding: '3px 9px',
                  borderRadius: 'var(--radius-full)',
                  fontSize: '0.74rem',
                  fontWeight: isActive ? 700 : 500,
                  whiteSpace: 'nowrap',
                  color: isActive ? 'var(--text-primary)' : 'var(--text-secondary)',
                  backgroundColor: isActive ? 'var(--accent-subtle)' : 'transparent',
                  border: isActive
                    ? '1px solid var(--accent-primary)'
                    : '1px solid transparent',
                  opacity: state === 'not_available' ? 0.55 : 1,
                })}
              >
                {presentation.icon}
                <span>
                  {stage.number}. {stage.shortLabel}
                </span>
                {alertCount !== null && (
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
                    {alertCount}
                  </span>
                )}
              </NavLink>
            </React.Fragment>
          );
        })}
        {workflowStatusLoading && (
          <span
            role="status"
            aria-label="Ładowanie statusów etapów"
            style={{ fontSize: '0.7rem', color: 'var(--text-muted)', paddingLeft: 4 }}
          >
            …
          </span>
        )}
      </div>
    </div>
  );
};
