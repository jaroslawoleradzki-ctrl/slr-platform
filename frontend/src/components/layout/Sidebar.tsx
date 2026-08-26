import React from 'react';
import { NavLink, useParams } from 'react-router-dom';
import {
  LayoutDashboard,
  Search,
  Download,
  Sparkles,
  GitMerge,
  Filter,
  Award,
  FileSpreadsheet,
  Layers,
  FileCheck2,
} from 'lucide-react';
import { useProject } from '../../context/ProjectContext';
import { Badge } from '../common/Badge';
import { APP_VERSION } from '../../config/version';
import { WorkflowNavigationStatus } from '../../types';
import { WORKFLOW_STAGES, buildStagePath } from '../../config/workflowStages';
import { getStageStatusPresentation } from '../workflow/stageStatusPresentation';

const STAGE_ICONS: Record<string, React.ComponentType<{ size?: number | string; style?: React.CSSProperties }>> = {
  search: Search,
  sources: Download,
  normalize: Sparkles,
  dedup: GitMerge,
  screening: Filter,
  'quality-assessment': Award,
  extract: FileSpreadsheet,
  synthesis: Layers,
  exports: FileCheck2,
};

export const Sidebar: React.FC = () => {
  const { projectId } = useParams<{ projectId?: string }>();
  const { activeProject, workflowStatus } = useProject();
  const currentId = projectId || activeProject?.id || '';

  /** Detailed right-hand status for one stage; keeps the exact labels users already know. */
  const renderStageStatus = (
    stageKey: keyof WorkflowNavigationStatus,
    stageId: string
  ): React.ReactNode => {
    if (!workflowStatus) return null;
    const item = workflowStatus[stageKey];

    if (stageId === 'dedup') {
      const dedup = workflowStatus.deduplication;
      if (dedup.state === 'error') {
        return (
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 3, fontSize: '0.72rem', color: 'var(--status-error-text)' }}>
            Błąd
          </span>
        );
      }
      if (dedup.pendingGroups > 0) {
        return <Badge variant="pending_action">{dedup.pendingGroups} do oceny</Badge>;
      }
      if (dedup.state === 'completed') {
        return (
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 3, fontSize: '0.72rem', color: 'var(--status-success-text)', fontWeight: 600 }}>
            Oceniono
          </span>
        );
      }
      return null;
    }

    if (item.state === 'pending_action') {
      return <Badge variant="pending_action">{item.label}</Badge>;
    }

    if (item.state === 'in_progress' || item.state === 'warning' || item.state === 'error' || item.state === 'completed') {
      const p = getStageStatusPresentation(item.state, 12);
      return (
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 4,
            fontSize: '0.72rem',
            color: p.color,
            fontWeight: item.state === 'completed' ? 600 : 500,
          }}
        >
          {p.icon}
          {item.label}
        </span>
      );
    }

    // not_started / not_available — quiet muted hint
    return (
      <span
        style={{
          fontSize: '0.72rem',
          color: 'var(--text-muted)',
          opacity: item.state === 'not_available' ? 0.7 : 1,
        }}
      >
        {item.label}
      </span>
    );
  };

  return (
    <aside
      style={{
        width: '240px',
        backgroundColor: 'var(--bg-surface)',
        borderRight: '1px solid var(--border-subtle)',
        display: 'flex',
        flexDirection: 'column',
        padding: '16px 10px',
        gap: '2px',
        flexShrink: 0,
        overflowY: 'auto',
      }}
    >
      <div style={{ padding: '4px 10px 10px 10px', borderBottom: '1px solid var(--border-subtle)', marginBottom: '8px' }}>
        <span style={{ fontSize: '0.68rem', textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-muted)', fontWeight: 700 }}>
          Kroki Procesu SLR
        </span>
      </div>

      <nav style={{ display: 'flex', flexDirection: 'column', gap: 2 }} aria-label="Kroki procesu SLR">
        <NavLink
          to={buildPath('dashboard')}
          style={({ isActive }) => stageRowStyle(isActive)}
        >
          {({ isActive }) => (
            <>
              <span style={stageNumberStyle(false, isActive)} aria-hidden="true">
                <LayoutDashboard size={12} />
              </span>
              <span style={{ flex: 1 }}>Dashboard</span>
            </>
          )}
        </NavLink>

        {WORKFLOW_STAGES.map((stage) => {
          const Icon = STAGE_ICONS[stage.id] ?? Layers;
          const statusContent = stage.statusKey ? renderStageStatus(stage.statusKey, stage.id) : null;

          return (
            <NavLink
              key={stage.id}
              to={buildStagePath(currentId || undefined, stage.pathSuffix)}
              style={({ isActive }) => stageRowStyle(isActive)}
            >
              {({ isActive }) => (
                <>
                  <span style={stageNumberStyle(true, isActive)} aria-hidden="true">
                    {stage.number}
                  </span>
                  <span style={{ flex: 1, minWidth: 0 }}>{stage.fullLabel}</span>
                  {statusContent && (
                    <span style={{ display: 'inline-flex', alignItems: 'center', maxWidth: '45%' }}>
                      {statusContent}
                    </span>
                  )}
                  {!statusContent && (
                    <span style={{ color: isActive ? 'var(--accent-light)' : 'var(--text-muted)' }}>
                      <Icon size={14} />
                    </span>
                  )}
                </>
              )}
            </NavLink>
          );
        })}
      </nav>

      <div style={{ marginTop: 'auto', paddingTop: '16px', borderTop: '1px solid var(--border-subtle)', textAlign: 'center' }}>
        <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
          SLR Platform v{APP_VERSION}
        </span>
      </div>
    </aside>
  );

  function buildPath(suffix: string): string {
    return currentId ? `/projects/${currentId}/${suffix}` : '/projects';
  }
};

const stageRowStyle = (isActive: boolean): React.CSSProperties => ({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  gap: 8,
  padding: '7px 9px',
  borderRadius: 'var(--radius-md)',
  color: isActive ? 'var(--text-primary)' : 'var(--text-secondary)',
  backgroundColor: isActive ? 'var(--accent-subtle)' : 'transparent',
  borderLeft: isActive ? '3px solid var(--accent-primary)' : '3px solid transparent',
  paddingLeft: isActive ? 6 : 9,
  fontSize: '0.84rem',
  lineHeight: 1.25,
  fontWeight: isActive ? 600 : 400,
  transition: 'background-color 0.15s ease',
});

const stageNumberStyle = (_numbered: boolean, isActive: boolean): React.CSSProperties => ({
  width: 20,
  height: 20,
  flexShrink: 0,
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  borderRadius: 'var(--radius-full)',
  fontSize: '0.68rem',
  fontFamily: 'var(--font-mono)',
  fontWeight: 700,
  color: isActive ? '#fff' : 'var(--text-secondary)',
  backgroundColor: isActive ? 'var(--accent-primary)' : 'var(--bg-surface-elevated)',
});
