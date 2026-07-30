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

export const Sidebar: React.FC = () => {
  const { projectId } = useParams<{ projectId?: string }>();
  const { activeProject } = useProject();
  const currentId = projectId || activeProject?.id || 'lean_energy';
  const completedProviderCount = activeProject?.providers.filter(
    (provider) => provider.status === 'completed'
  ).length ?? 0;

  const navItems = [
    {
      to: `/projects/${currentId}/dashboard`,
      label: 'Dashboard',
      icon: LayoutDashboard,
      badge: null,
    },
    {
      to: `/projects/${currentId}/search`,
      label: '1. Search Strategy',
      icon: Search,
      badge: activeProject?.conceptGroups?.length ? `${activeProject.conceptGroups.length} grup` : null,
    },
    {
      to: `/projects/${currentId}/sources`,
      label: '2. Sources & Imports',
      icon: Download,
      badge: activeProject?.providers
        ? completedProviderCount > 0
          ? `${completedProviderCount}/${activeProject.providers.length}`
          : 'Brak danych'
        : null,
    },
    {
      to: `/projects/${currentId}/normalize`,
      label: '3. Normalization',
      icon: Sparkles,
      badge: activeProject?.normalization?.[0]?.completed ? 'OK' : 'Pending',
    },
    {
      to: `/projects/${currentId}/dedup`,
      label: '4. Deduplication',
      icon: GitMerge,
      badge: activeProject?.deduplication?.candidateGroupsPendingUserReview ? (
        <Badge variant="pending_action">
          {activeProject.deduplication.candidateGroupsPendingUserReview} do oceny
        </Badge>
      ) : null,
    },
    {
      to: `/projects/${currentId}/screen`,
      label: '5. Screening',
      icon: Filter,
      badge: activeProject?.screening?.titleAbstract?.pending ? `${activeProject.screening.titleAbstract.pending} pending` : null,
    },
    {
      to: `/projects/${currentId}/qa`,
      label: '6. Quality Assessment',
      icon: Award,
      badge: 'Faza 7',
    },
    {
      to: `/projects/${currentId}/extract`,
      label: '7. Data Extraction',
      icon: FileSpreadsheet,
      badge: 'Faza 8',
      disabled: true,
    },
    {
      to: `/projects/${currentId}/exports`,
      label: '8. Exports & PRISMA',
      icon: FileCheck2,
      badge: 'Flow',
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
                {typeof item.badge === 'string' ? item.badge : 'Coming'}
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
            {item.badge && (
              <span style={{ fontSize: '0.75rem' }}>
                {typeof item.badge === 'string' ? (
                  <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>{item.badge}</span>
                ) : (
                  item.badge
                )}
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
