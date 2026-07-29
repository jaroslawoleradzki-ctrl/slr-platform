import React from 'react';
import { AlertTriangle } from 'lucide-react';

interface ErrorAlertProps {
  title?: string;
  message: string;
  onRetry?: () => void;
}

export const ErrorAlert: React.FC<ErrorAlertProps> = ({
  title = 'Wystąpił błąd',
  message,
  onRetry,
}) => {
  return (
    <div
      style={{
        padding: '16px',
        borderRadius: 'var(--radius-md)',
        backgroundColor: 'var(--status-error-bg)',
        border: '1px solid var(--status-error-border)',
        color: 'var(--status-error-text)',
        display: 'flex',
        alignItems: 'flex-start',
        gap: '12px',
      }}
    >
      <AlertTriangle size={20} style={{ flexShrink: 0, marginTop: '2px' }} />
      <div style={{ flex: 1 }}>
        <h5 style={{ fontWeight: 600, fontSize: '0.9rem' }}>{title}</h5>
        <p style={{ fontSize: '0.85rem', marginTop: '2px', opacity: 0.9 }}>{message}</p>
        {onRetry && (
          <button
            onClick={onRetry}
            style={{
              marginTop: '8px',
              fontSize: '0.8rem',
              fontWeight: 600,
              textDecoration: 'underline',
              color: 'var(--status-error-text)',
            }}
          >
            Spróbuj ponownie
          </button>
        )}
      </div>
    </div>
  );
};
