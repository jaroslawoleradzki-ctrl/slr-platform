import React from 'react';
import { FolderOpen } from 'lucide-react';

interface EmptyStateProps {
  title?: string;
  description?: string;
  action?: React.ReactNode;
  icon?: React.ReactNode;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  title = 'Brak danych do wyświetlenia',
  description = 'Dla wybranego etapu nie znaleziono jeszcze zarejestrowanych danych.',
  action,
  icon,
}) => {
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '48px 24px',
        textAlign: 'center',
        backgroundColor: 'var(--bg-surface)',
        borderRadius: 'var(--radius-lg)',
        border: '1px dashed var(--border-strong)',
        gap: '12px',
      }}
    >
      <div
        style={{
          width: '48px',
          height: '48px',
          borderRadius: '50%',
          backgroundColor: 'var(--bg-surface-elevated)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: 'var(--text-secondary)',
        }}
      >
        {icon || <FolderOpen size={24} />}
      </div>
      <h4 style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--text-primary)' }}>{title}</h4>
      <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', maxWidth: '420px' }}>
        {description}
      </p>
      {action && <div style={{ marginTop: '8px' }}>{action}</div>}
    </div>
  );
};
