import React from 'react';
import { Loader2 } from 'lucide-react';

export const LoadingSpinner: React.FC<{ label?: string }> = ({ label = 'Ładowanie danych...' }) => {
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '40px',
        gap: '12px',
        color: 'var(--text-secondary)',
      }}
    >
      <Loader2
        size={28}
        style={{
          animation: 'spin 1s linear infinite',
          color: 'var(--accent-primary)',
        }}
      />
      <span style={{ fontSize: '0.875rem' }}>{label}</span>
      <style>{`
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
};
