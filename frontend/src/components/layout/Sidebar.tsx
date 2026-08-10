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
  FileCheck2,
} from 'lucide-react';
import { useProject } from '../../context/ProjectContext';
import { Badge } from '../common/Badge';
import { APP_VERSION } from '../../config/version';
import { WorkflowNavigationStatus } from '../../types';

export const Sidebar: React.FC = () => {
  const { projectId } = useParams<{ projectId?: string }>();
  const { activeProject, workflowStatus } = useProject();
  const currentId = projectId || activeProject?.id || 'lean_energy';

  const renderBadge = (stage: keyof WorkflowNavigationStatus | 'dashboard') => {
    if (!workflowStatus || stage === 'dashboard') return null;
    if (stage === 'screening') {
      return <span style={{ fontSize: '0.7rem', color: 'var(--status-success-text)' }}>Dostępne</span>;
    }
    const item = workflowStatus[stage];

    if (stage === 'deduplication') {
      const dedup = workflowStatus.deduplication;
      if (dedup.state === 'error') {
        return <span style={{ fontSize: '0.7rem', color: 'var(--status-error-text)' }}>Błąd</span>;
      }
      if (dedup.pendingGroups > 0) {
        return (
          <Badge variant="pending_action">
            {dedup.pendingGroups} do oceny
          </Badge>
        );
      }
      if (dedup.state === 'completed' || dedup.pendingGroups === 0) {
        return (
          <span style={{ fontSize: '0.7rem', color: 'var(--status-success-text)', fontWeight: 600 }}>
            Oceniono
          </span>
        );
      }
      return null;
    }

    if (item.state === 'not_available') {
      return <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>{item.label || 'Niedostępne'}</span>;
    }

    if (item.state === 'error') {
      return <span style={{ fontSize: '0.7rem', color: 'var(--status-error-text)' }}>{item.label || 'Błąd'}</span>;
    }

    if (item.label) {
      return <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>{item.label}</span>;
    }

    return null;
  };

  const navItems = [
    {
      to: `/projects/${currentId}/dashboard`,
      label: 'Dashboard',
      icon: LayoutDashboard,
      stage: 'dashboard' as const,
    },
    {
      to: `/projects/${currentId}/search`,
      label: '1. Search Strategy',
      icon: Search,
      stage: 'search' as const,
    },
    {
      to: `/projects/${currentId}/sources`,
      label: '2. Sources & Imports',
      icon: Download,
      stage: 'sources' as const,
    },
    {
      to: `/projects/${currentId}/normalize`,
      label: '3. Normalization',
      icon: Sparkles,
      stage: 'normalization' as const,
    },
    {
      to: `/projects/${currentId}/dedup`,
      label: '4. Deduplication',
      icon: GitMerge,
      stage: 'deduplication' as const,
    },
    {
      to: `/projects/${currentId}/screen/title-abstract`,
      label: '5. Screening',
      icon: Filter,
      stage: 'screening' as const,
    },
    {
      to: `/projects/${currentId}/qa`,
      label: '6. Quality Assessment',
      icon: Award,
      stage: 'qualityAssessment' as const,
    },
    {
      to: `/projects/${currentId}/extract`,
      label: '7. Data Extraction',
      icon: FileSpreadsheet,
      stage: 'dataExtraction' as const,
      disabled: true,
    },
    {
      to: `/projects/${currentId}/exports`,
      label: '8. Exports & PRISMA',
      icon: FileCheck2,
      stage: 'exports' as const,
    },
  ];

  return (
    <aside
      style={{
        width: '240px',
        backgroundColor: 'var(--bg-surface)',
        borderRight: '1px solid var(--border-subtle)',
        display: 'flex',
        flexDirection: 'column',
        padding: '16px 12px',
        gap: '4px',
        flexShrink: 0,
      }}
    >
      <div style={{ padding: '4px 12px 12px 12px', borderBottom: '1px solid var(--border-subtle)', marginBottom: '8px' }}>
        <span style={{ fontSize: '0.7rem', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-muted)', fontWeight: 600 }}>
          Kroki Procesu SLR
        </span>
      </div>

      {navItems.map((item) => {
        const Icon = item.icon;
        const badgeContent = renderBadge(item.stage);

        if (item.disabled) {
          return (
            <div
              key={item.to}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '8px 12px',
                borderRadius: 'var(--radius-md)',
                color: 'var(--text-muted)',
                fontSize: '0.85rem',
                opacity: 0.6,
                cursor: 'not-allowed',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <Icon size={16} />
                <span>{item.label}</span>
              </div>
              <span style={{ fontSize: '0.7rem', padding: '1px 6px', borderRadius: '4px', backgroundColor: 'var(--bg-surface-elevated)' }}>
                {badgeContent || 'Niedostępne'}
              </span>
            </div>
          );
        }

        return (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) => (isActive ? 'active-nav-link' : '')}
            style={({ isActive }) => ({
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '8px 12px',
              borderRadius: 'var(--radius-md)',
              color: isActive ? 'var(--text-primary)' : 'var(--text-secondary)',
              backgroundColor: isActive ? 'var(--accent-subtle)' : 'transparent',
              borderLeft: isActive ? '3px solid var(--accent-primary)' : '3px solid transparent',
              fontSize: '0.85rem',
              fontWeight: isActive ? 600 : 400,
              transition: 'all 0.15s ease',
            })}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <Icon size={16} style={{ color: 'var(--accent-primary)' }} />
              <span>{item.label}</span>
            </div>
            {badgeContent && (
              <span style={{ fontSize: '0.75rem' }}>
                {badgeContent}
              </span>
            )}
          </NavLink>
        );
      })}

      <div style={{ marginTop: 'auto', paddingTop: '16px', borderTop: '1px solid var(--border-subtle)', textAlign: 'center' }}>
        <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
          SLR Platform v{APP_VERSION}
        </span>
      </div>
    </aside>
  );
};
