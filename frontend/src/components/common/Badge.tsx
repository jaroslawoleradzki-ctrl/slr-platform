import React from 'react';
import { StageStatus } from '../../types';

interface BadgeProps {
  variant?: StageStatus | 'info' | 'default';
  children: React.ReactNode;
  icon?: React.ReactNode;
}

export const Badge: React.FC<BadgeProps> = ({ variant = 'default', children, icon }) => {
  const getStyles = (): React.CSSProperties => {
    switch (variant) {
      case 'completed':
        return {
          backgroundColor: 'var(--status-success-bg)',
          color: 'var(--status-success-text)',
          borderColor: 'var(--status-success-border)',
        };
      case 'in_progress':
      case 'info':
        return {
          backgroundColor: 'var(--status-info-bg)',
          color: 'var(--status-info-text)',
          borderColor: 'var(--status-info-border)',
        };
      case 'pending_action':
        return {
          backgroundColor: 'var(--status-warning-bg)',
          color: 'var(--status-warning-text)',
          borderColor: 'var(--status-warning-border)',
        };
      case 'error':
        return {
          backgroundColor: 'var(--status-error-bg)',
          color: 'var(--status-error-text)',
          borderColor: 'var(--status-error-border)',
        };
      case 'pending':
      default:
        return {
          backgroundColor: 'var(--status-pending-bg)',
          color: 'var(--status-pending-text)',
          borderColor: 'var(--status-pending-border)',
        };
    }
  };

  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '4px',
        padding: '2px 8px',
        borderRadius: 'var(--radius-full)',
        fontSize: '0.75rem',
        fontWeight: 600,
        border: '1px solid',
        lineHeight: 1.4,
        whiteSpace: 'nowrap',
        ...getStyles(),
      }}
    >
      {icon && <span style={{ display: 'inline-flex', alignItems: 'center' }}>{icon}</span>}
      {children}
    </span>
  );
};
