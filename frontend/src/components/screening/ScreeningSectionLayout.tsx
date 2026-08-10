import React from 'react';
import { NavLink, Outlet, useParams } from 'react-router-dom';

export const ScreeningSectionLayout: React.FC = () => {
  const { projectId } = useParams<{ projectId: string }>();
  const base = `/projects/${projectId}/screen`;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <div>
        <h2 style={{ fontSize: '1.3rem', fontWeight: 800, margin: 0 }}>5. Screening</h2>
        <p style={{ color: 'var(--text-secondary)', margin: '4px 0 0' }}>Ocena publikacji po zakończonej deduplikacji.</p>
      </div>
      <nav aria-label="Screening navigation" style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
        <NavLink to={`${base}/title-abstract`} style={({ isActive }) => ({
          padding: '8px 12px', borderRadius: 'var(--radius-md)', textDecoration: 'none',
          background: isActive ? 'var(--accent-primary)' : 'var(--bg-surface-elevated)',
          color: isActive ? '#fff' : 'var(--text-primary)', border: '1px solid var(--border-strong)', fontWeight: 600,
        })}>Title &amp; Abstract Screening</NavLink>
        <NavLink to={`${base}/criteria`} style={({ isActive }) => ({
          padding: '8px 12px', borderRadius: 'var(--radius-md)', textDecoration: 'none',
          background: isActive ? 'var(--accent-primary)' : 'var(--bg-surface-elevated)',
          color: isActive ? '#fff' : 'var(--text-primary)', border: '1px solid var(--border-strong)', fontWeight: 600,
        })}>Criteria Configuration</NavLink>
      </nav>
      <Outlet />
    </div>
  );
};
