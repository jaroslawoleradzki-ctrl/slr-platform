import React from 'react';
import { AlertTriangle, CheckCircle2, Loader2 } from 'lucide-react';
import { FetchAllProviderProgress, FetchAllStatusResult } from '../../types';

const PROVIDER_LABELS: Record<string, string> = {
  openalex: 'OpenAlex',
  crossref: 'Crossref',
  semantic_scholar: 'Semantic Scholar',
};

const STATUS_LABELS: Record<FetchAllProviderProgress['status'], string> = {
  pending: 'Oczekuje…',
  running: 'Pobieranie…',
  complete: 'Zakończono',
  partial: 'Zakończono częściowo',
  cancelled: 'Anulowano',
  failed: 'Błąd',
};

const formatNumber = (value: number): string => value.toLocaleString('pl-PL');

interface Props {
  progress: FetchAllStatusResult | null;
  starting: boolean;
  onCancel?: () => void;
}

export const FetchAllProgressPanel: React.FC<Props> = ({
  progress,
  starting,
  onCancel,
}) => {
  if (!progress) {
    if (!starting) return null;
    return (
      <div
        role="status"
        style={{
          marginBottom: 12,
          padding: '10px 14px',
          borderRadius: 'var(--radius-md)',
          border: '1px dashed var(--border-strong)',
          backgroundColor: 'var(--bg-surface-elevated)',
          display: 'flex',
          alignItems: 'center',
          gap: 8,
        }}
      >
        <Loader2 size={16} className="spin" />
        <span>Rozpoczynanie pobierania wszystkich dostępnych wyników…</span>
      </div>
    );
  }

  const running = progress.status === 'running';
  const incompleteProviders = progress.providers.filter(
    (p) => p.status === 'partial' || p.status === 'failed'
  );

  return (
    <div
      data-testid="fetch-all-progress"
      role={running ? 'status' : undefined}
      style={{
        marginBottom: 12,
        padding: '10px 14px',
        borderRadius: 'var(--radius-md)',
        border: `1px ${running ? 'dashed' : 'solid'} var(--border-strong)`,
        backgroundColor: 'var(--bg-surface-elevated)',
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 12,
        }}
      >
        <strong style={{ fontSize: '0.88rem' }}>
          {running
            ? 'Pobieranie wszystkich dostępnych wyników…'
            : progress.status === 'cancelled'
              ? 'Pobieranie anulowane — zachowano dotychczasowe wyniki.'
              : progress.status === 'failed'
                ? 'Pobieranie zakończyło się błędem.'
                : 'Pobieranie wszystkich dostępnych wyników zakończone.'}
        </strong>
        {onCancel && running && (
          <button type="button" onClick={onCancel} className="btn-secondary">
            Anuluj pobieranie
          </button>
        )}
      </div>

      <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 4 }}>
        {progress.providers.map((provider) => (
          <div key={provider.provider} style={{ fontSize: '0.82rem' }}>
            <span style={{ fontWeight: 700 }}>
              {PROVIDER_LABELS[provider.provider] ?? provider.provider}
            </span>{' '}
            —{' '}
            <span>
              {formatNumber(provider.fetched_count)} pobranych
              {provider.total_reported !== null && (
                <>
                  {' '}z ~{formatNumber(provider.total_reported)} zgłoszonych przez
                  providera
                </>
              )}
            </span>
            <span>
              {' '}· canonical: {formatNumber(provider.canonical_accepted_count ?? 0)} zaakceptowanych,
              {' '}{formatNumber(provider.canonical_rejected_count ?? 0)} odrzuconych
              {' '}· nieokreślone: {formatNumber(provider.canonical_indeterminate_count ?? 0)}
              {' '}· duplikaty: {formatNumber(provider.deduplicated_count ?? 0)}
            </span>
            {provider.limit_reached && (
              <span style={{ color: 'var(--status-warning-text)' }}>
                {' '}· osiągnięto limit możliwy do pobrania z API
              </span>
            )}{' '}
            — <em>{STATUS_LABELS[provider.status]}</em>
          </div>
        ))}
      </div>

      <div style={{ marginTop: 8, fontSize: '0.85rem', fontWeight: 600 }}>
        Pobrano: {formatNumber(progress.fetched_total)} · Canonical accepted:{' '}
        {formatNumber(progress.canonical_accepted_total ?? 0)} · Canonical rejected:{' '}
        {formatNumber(progress.canonical_rejected_total ?? 0)} · Nieokreślone:{' '}
        {formatNumber(progress.canonical_indeterminate_total ?? 0)} · Po deduplikacji:{' '}
        {formatNumber(
          (progress.canonical_accepted_total ?? 0) +
          (progress.canonical_indeterminate_total ?? 0) -
          (progress.deduplicated_total ?? 0)
        )} ·
        Zapisano po ograniczeniach metadanych: {formatNumber(progress.kept_total)}
      </div>

      {!running && incompleteProviders.length > 0 && (
        <div
          role="alert"
          style={{
            marginTop: 8,
            padding: 10,
            borderRadius: 'var(--radius-md)',
            border: '1px solid var(--status-warning-border)',
            backgroundColor: 'var(--status-warning-bg)',
            color: 'var(--status-warning-text)',
            fontSize: '0.82rem',
            display: 'flex',
            gap: 8,
          }}
        >
          <AlertTriangle size={16} />
          <span>
            Niekompletne dane:{' '}
            {incompleteProviders
              .map((p) => {
                const label = PROVIDER_LABELS[p.provider] ?? p.provider;
                return `${label} — ${
                  p.status === 'failed' ? 'błąd' : 'częściowo'
                }${p.message ? ` (${p.message})` : ''}`;
              })
              .join('; ')}
          </span>
        </div>
      )}

      {!running &&
        progress.status === 'completed' &&
        incompleteProviders.length === 0 && (
          <div
            role="status"
            style={{
              marginTop: 8,
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              color: 'var(--status-success-text, var(--text-secondary))',
              fontSize: '0.82rem',
            }}
          >
            <CheckCircle2 size={15} />
            <span>Wszyscy wybrani providerzy przekazali pełen zakres wyników.</span>
          </div>
        )}
    </div>
  );
};
