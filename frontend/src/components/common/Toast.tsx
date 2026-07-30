import React from 'react';
import { CheckCircle2, X } from 'lucide-react';

interface ToastProps {
  message: string;
  type?: 'success' | 'error' | 'info';
  onClose?: () => void;
}

export const Toast: React.FC<ToastProps> = ({ message, type = 'success', onClose }) => {
  return (
    <div
      role="status"
      aria-live="polite"
      style={{
        position: 'fixed',
        bottom: '24px',
        right: '24px',
        zIndex: 1000,
        backgroundColor: type === 'success' ? 'var(--status-success-bg)' : 'var(--bg-surface-elevated)',
        border: `1px solid ${type === 'success' ? 'var(--status-success-border)' : 'var(--border-strong)'}`,
        color: type === 'success' ? 'var(--status-success-text)' : 'var(--text-primary)',
        borderRadius: 'var(--radius-md)',
        padding: '12px 18px',
        boxShadow: 'var(--shadow-lg)',
        display: 'flex',
        alignItems: 'center',
        gap: '12px',
        fontSize: '0.875rem',
        fontWeight: 600,
        animation: 'slideIn 0.2s ease-out',
      }}
    >
      <CheckCircle2 size={18} style={{ flexShrink: 0 }} />
      <span>{message}</span>
      {onClose && (
        <button
          onClick={onClose}
          aria-label="Zamknij powiadomienie"
          style={{
            color: 'inherit',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            opacity: 0.8,
            marginLeft: '8px',
            cursor: 'pointer',
          }}
        >
          <X size={16} />
        </button>
      )}
      <style>{`
        @keyframes slideIn {
          from { transform: translateY(100%); opacity: 0; }
          to { transform: translateY(0); opacity: 1; }
        }
      `}</style>
    </div>
  );
};
