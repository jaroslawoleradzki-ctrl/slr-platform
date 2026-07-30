import React from 'react';
import { Database, CheckCircle2, Clock, AlertTriangle, RefreshCw } from 'lucide-react';
import { SearchProviderStatus } from '../../types';
import { Badge } from '../common/Badge';

interface ProviderStatusCardProps {
  provider: SearchProviderStatus;
  onRunSearch?: (id: string) => void;
}

export const ProviderStatusCard: React.FC<ProviderStatusCardProps> = ({ provider, onRunSearch }) => {
  const getStatusBadge = () => {
    switch (provider.status) {
      case 'completed':
        return <Badge variant="completed" icon={<CheckCircle2 size={12} />}>Zaimportowano</Badge>;
      case 'running':
        return <Badge variant="in_progress" icon={<RefreshCw size={12} />}>Uruchomiono...</Badge>;
      case 'failed':
        return <Badge variant="error" icon={<AlertTriangle size={12} />}>Błąd Providera</Badge>;
      default:
        return <Badge variant="pending" icon={<Clock size={12} />}>Nie uruchamiano</Badge>;
    }
  };

  return (
    <div
      style={{
        backgroundColor: 'var(--bg-surface)',
        borderRadius: 'var(--radius-lg)',
        border: '1px solid var(--border-subtle)',
        padding: '18px 20px',
        display: 'flex',
        flexDirection: 'column',
        gap: '14px',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div
            style={{
              width: '36px',
              height: '36px',
              borderRadius: 'var(--radius-md)',
              backgroundColor: 'var(--bg-surface-elevated)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--accent-primary)',
            }}
          >
            <Database size={18} />
          </div>
          <div>
            <h4 style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--text-primary)' }}>
              {provider.name}
            </h4>
            <span style={{ fontSize: '0.75rem', color: provider.connected ? 'var(--status-success-text)' : 'var(--status-error-text)' }}>
              {provider.connected ? '● Połączenie OK' : '○ Brak danych'}
            </span>
          </div>
        </div>
        {getStatusBadge()}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', paddingTop: '4px', borderTop: '1px solid var(--border-subtle)' }}>
        <div>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Pobrane Rekordy</span>
          <div style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--text-primary)' }}>
            {provider.resultsCount > 0 ? provider.resultsCount.toLocaleString() : 'Brak danych'}
          </div>
        </div>
        <div>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Ostatnie Wykonanie</span>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '2px' }}>
            {provider.lastRunTimestamp
              ? new Date(provider.lastRunTimestamp).toLocaleString('pl-PL', { dateStyle: 'short', timeStyle: 'short' })
              : 'Nie uruchamiano'}
          </div>
        </div>
      </div>

      {provider.errorMessage && (
        <div style={{ fontSize: '0.75rem', color: 'var(--status-error-text)', backgroundColor: 'var(--status-error-bg)', padding: '6px 10px', borderRadius: 'var(--radius-sm)' }}>
          {provider.errorMessage}
        </div>
      )}

      {onRunSearch && (
        <button
          onClick={() => onRunSearch(provider.id)}
          style={{
            marginTop: '4px',
            padding: '6px 12px',
            borderRadius: 'var(--radius-md)',
            backgroundColor: 'var(--bg-surface-elevated)',
            border: '1px solid var(--border-strong)',
            color: 'var(--text-primary)',
            fontSize: '0.8rem',
            fontWeight: 500,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '6px',
          }}
        >
          <RefreshCw size={12} />
          <span>Uruchom Wyszukiwanie</span>
        </button>
      )}
    </div>
  );
};
