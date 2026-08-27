import React from 'react';
import {
  AlertTriangle,
  Ban,
  CheckCircle2,
  CircleDashed,
  Loader2,
  OctagonX,
} from 'lucide-react';
import {
  FetchAllProviderProgress,
  FetchAllProviderStatus,
  FetchAllStatusResult,
  ResumableSearchJobSummary,
} from '../../types';

const PROVIDER_LABELS: Record<string, string> = {
  openalex: 'OpenAlex',
  crossref: 'Crossref',
  semantic_scholar: 'Semantic Scholar',
};

const STATUS_LABELS: Record<FetchAllProviderStatus, string> = {
  pending: 'Oczekuje…',
  running: 'Pobieranie…',
  complete: 'Zakończono',
  partial: 'Zakończono częściowo',
  cancelled: 'Anulowano',
  failed: 'Błąd',
};

/** Distinct glyph per state so status never relies on colour alone. */
const statusMeta = (
  status: FetchAllProviderStatus
): { icon: React.ReactNode; color: string } => {
  switch (status) {
    case 'complete':
      return { icon: <CheckCircle2 size={13} />, color: 'var(--status-success-text)' };
    case 'running':
      return { icon: <Loader2 size={13} className="spin" />, color: 'var(--status-info-text)' };
    case 'partial':
      return { icon: <AlertTriangle size={13} />, color: 'var(--status-warning-text)' };
    case 'cancelled':
      return { icon: <Ban size={13} />, color: 'var(--text-muted)' };
    case 'failed':
      return { icon: <OctagonX size={13} />, color: 'var(--status-error-text)' };
    case 'pending':
    default:
      return { icon: <CircleDashed size={13} />, color: 'var(--text-muted)' };
  }
};

const formatNumber = (value: number): string => value.toLocaleString('pl-PL');

const gridStyle: React.CSSProperties = {
  display: 'grid',
  gridTemplateColumns: 'minmax(150px, 1.4fr) minmax(170px, 1fr) repeat(2, minmax(96px, 0.6fr))',
  columnGap: 12,
  alignItems: 'center',
};

interface Props {
  progress: FetchAllStatusResult | null;
  starting: boolean;
  resumableJobs?: ResumableSearchJobSummary[];
  onCancel?: () => void;
  onResume?: () => void;
  onResumeJob?: (jobId: string) => void;
}

export const FetchAllProgressPanel: React.FC<Props> = ({
  progress,
  starting,
  resumableJobs = [],
  onCancel,
  onResume,
  onResumeJob,
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
  const canResume = !running && Boolean(progress.resumable || incompleteProviders.some(p => p.resumable));

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
        <div style={{ display: 'flex', gap: 8 }}>
          {onCancel && running && (
            <button type="button" onClick={onCancel} style={{ ...ghostButtonStyle }}>
              Anuluj pobieranie
            </button>
          )}
          {onResume && canResume && (
            <button type="button" onClick={onResume} className="btn-primary" data-testid="resume-fetch-all-btn">
              Wznów pobieranie (Resume)
            </button>
          )}
        </div>
      </div>

      {progress.providers.length > 0 && (
        <div style={{ marginTop: 10, overflowX: 'auto' }}>
          <div style={{ minWidth: 520 }}>
            {/* Header row */}
            <div
              style={{
                ...gridStyle,
                padding: '4px 10px',
                fontSize: '0.68rem',
                textTransform: 'uppercase',
                letterSpacing: '0.05em',
                fontWeight: 700,
                color: 'var(--text-muted)',
              }}
            >
              <span>Provider</span>
              <span>Status</span>
              <span style={{ textAlign: 'right' }}>Pobrano</span>
              <span style={{ textAlign: 'right' }}>Zgłoszono</span>
            </div>

            {progress.providers.map((provider) => (
              <ProviderRow key={provider.provider} provider={provider} running={running} />
            ))}
          </div>
        </div>
      )}

      <div style={{ marginTop: 8, fontSize: '0.85rem', fontWeight: 600 }}>
        Łącznie pobrano: {formatNumber(progress.fetched_total)} · Po lokalnych
        filtrach: {formatNumber(progress.kept_total)}
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
            data-testid="fetch-all-complete-note"
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

      {/* ── Historical Resumable Jobs Section ──────────────────────────────── */}
      {!running && resumableJobs.length > 0 && (
        <div
          data-testid="historical-resumable-jobs-section"
          style={{
            marginTop: 12,
            paddingTop: 10,
            borderTop: '1px solid var(--border-subtle)',
          }}
        >
          <div
            style={{
              fontSize: '0.75rem',
              fontWeight: 700,
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
              color: 'var(--text-muted)',
              marginBottom: 6,
            }}
          >
            Wznawialne zadania historyczne ({resumableJobs.length})
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {resumableJobs.map((rj) => {
              const rjProviders = rj.providers && rj.providers.length > 0
                ? rj.providers.map((p) => PROVIDER_LABELS[p] ?? p).join(', ')
                : PROVIDER_LABELS[rj.provider] ?? rj.provider;
              const dateStr = new Date(rj.updated_at).toLocaleString('pl-PL');
              const isCurrent = progress.job_id === rj.job_id;

              return (
                <div
                  key={rj.job_id}
                  data-testid={`resumable-job-row-${rj.job_id}`}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    gap: 8,
                    padding: '6px 10px',
                    borderRadius: 'var(--radius-sm)',
                    backgroundColor: isCurrent ? 'var(--bg-surface)' : 'transparent',
                    border: '1px solid var(--border-subtle)',
                    fontSize: '0.8rem',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                    <strong style={{ color: 'var(--text-primary)' }}>{rjProviders}</strong>
                    <span style={{ color: 'var(--text-muted)' }}>({dateStr})</span>
                    <span style={{ color: 'var(--text-secondary)' }}>
                      Pobrano: {formatNumber(rj.fetched_count)} · Zaakceptowano: {formatNumber(rj.canonical_accepted_count)}
                    </span>
                    {rj.message && (
                      <span style={{ color: 'var(--status-warning-text)', fontSize: '0.75rem' }}>
                        [{rj.message}]
                      </span>
                    )}
                  </div>
                  <div style={{ display: 'flex', gap: 6 }}>
                    <button
                      type="button"
                      data-testid={`resume-job-btn-${rj.job_id}`}
                      onClick={() => {
                        if (onResumeJob) {
                          onResumeJob(rj.job_id);
                        } else if (onResume) {
                          onResume();
                        }
                      }}
                      style={{ ...ghostButtonStyle, padding: '3px 8px', fontSize: '0.75rem' }}
                    >
                      Wznów to zadanie
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};

const ProviderRow: React.FC<{ provider: FetchAllProviderProgress; running: boolean }> = ({
  provider,
  running,
}) => {
  const meta = statusMeta(provider.status);
  const name = PROVIDER_LABELS[provider.provider] ?? provider.provider;

  return (
    <div
      data-testid={`fetch-all-provider-row-${provider.provider}`}
      style={{
        ...gridStyle,
        padding: '7px 10px',
        borderTop: '1px solid var(--border-subtle)',
        fontSize: '0.82rem',
        opacity: provider.status === 'pending' && running ? 0.65 : 1,
      }}
    >
      <span style={{ fontWeight: 700 }} title={provider.message ?? undefined}>
        {name}
        {provider.limit_reached && (
          <span
            style={{
              display: 'block',
              fontWeight: 400,
              fontSize: '0.72rem',
              color: 'var(--status-warning-text)',
            }}
          >
            osiągnięto limit możliwy do pobrania z API
          </span>
        )}
      </span>
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, color: meta.color }}>
        {meta.icon}
        {STATUS_LABELS[provider.status]}
      </span>
      <span style={{ textAlign: 'right', fontFamily: 'var(--font-mono)', fontSize: '0.8rem' }}>
        {formatNumber(provider.fetched_count)}
      </span>
      <span
        style={{
          textAlign: 'right',
          fontFamily: 'var(--font-mono)',
          fontSize: '0.8rem',
          color: 'var(--text-secondary)',
        }}
      >
        {provider.total_reported !== null ? `~${formatNumber(provider.total_reported)}` : '–'}
      </span>
    </div>
  );
};

export const ghostButtonStyle: React.CSSProperties = {
  padding: '6px 12px',
  borderRadius: 'var(--radius-md)',
  border: '1px solid var(--border-strong)',
  backgroundColor: 'transparent',
  color: 'var(--text-primary)',
  fontWeight: 600,
  fontSize: '0.78rem',
  cursor: 'pointer',
};
