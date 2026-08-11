import React from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Search, Download, Sparkles, GitMerge,
  Filter, Award, FileSpreadsheet, FileCheck2,
  CheckCircle2, AlertTriangle, AlertCircle, Clock, Loader2,
} from 'lucide-react';
import { useProject } from '../context/ProjectContext';
import { WorkflowStageState } from '../types';
import { Card } from '../components/common/Card';
import { NextActionCard } from '../components/workflow/NextActionCard';

// ─── Helpers (module-private) ─────────────────────────────────────────────────

function stageStateIcon(state: WorkflowStageState) {
  switch (state) {
    case 'completed':    return <CheckCircle2 size={15} style={{ color: 'var(--status-success-text)' }} />;
    case 'warning':
    case 'pending_action': return <AlertTriangle size={15} style={{ color: 'var(--status-warning-text)' }} />;
    case 'error':        return <AlertCircle size={15} style={{ color: 'var(--status-error-text)' }} />;
    default:             return <Clock size={15} style={{ color: 'var(--text-muted)' }} />;
  }
}

function stageBorderColor(state: WorkflowStageState): string {
  switch (state) {
    case 'completed':    return 'var(--status-success-border)';
    case 'warning':
    case 'pending_action': return 'var(--status-warning-border)';
    case 'error':        return 'var(--status-error-border)';
    default:             return 'var(--border-subtle)';
  }
}

/**
 * workflowStatus.normalization.count is errors or warnings count — NOT processed records.
 * Map state+label to a human-readable primary display string.
 */
function normPrimaryValue(state: WorkflowStageState, label: string | null): string | null {
  if (state === 'not_started') return null;        // → "Brak danych"
  if (state === 'completed')   return 'Wykonano';  // clean run
  if (label)                   return label;        // "X ostrzeżeń" / "X błędów" / "Błąd"
  return null;
}

function formatImportCount(count: number): string {
  if (count === 1) return '1 import';
  const mod10 = count % 10;
  const mod100 = count % 100;
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 10 || mod100 >= 20)) {
    return `${count} importy`;
  }
  return `${count} importów`;
}

// ─── Stage card (stages 1–4, clickable) ──────────────────────────────────────

interface StageCardProps {
  id: string;
  icon: React.ReactNode;
  label: string;
  state: WorkflowStageState;
  primary: string | null;
  secondary?: string | null;
  route: string;
}

const StageCard: React.FC<StageCardProps> = ({ id, icon, label, state, primary, secondary, route }) => {
  const navigate = useNavigate();
  return (
    <div
      id={id}
      role="region"
      aria-label={`Etap: ${label}`}
      onClick={() => navigate(route)}
      style={{
        backgroundColor: 'var(--bg-surface)',
        border: `1px solid ${stageBorderColor(state)}`,
        borderRadius: 'var(--radius-lg)',
        padding: '14px 16px',
        display: 'flex', flexDirection: 'column', gap: '8px',
        cursor: 'pointer',
        boxShadow: 'var(--shadow-sm)',
        transition: 'box-shadow 0.15s ease, transform 0.1s ease',
      }}
      onMouseEnter={(e) => {
        const el = e.currentTarget as HTMLDivElement;
        el.style.boxShadow = 'var(--shadow-md)';
        el.style.transform = 'translateY(-1px)';
      }}
      onMouseLeave={(e) => {
        const el = e.currentTarget as HTMLDivElement;
        el.style.boxShadow = 'var(--shadow-sm)';
        el.style.transform = 'translateY(0)';
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.78rem', fontWeight: 600, color: 'var(--text-secondary)' }}>
          {icon}<span>{label}</span>
        </div>
        {stageStateIcon(state)}
      </div>
      <div>
        {primary !== null
          ? <div style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--text-primary)' }}>{primary}</div>
          : <div style={{ fontSize: '0.82rem', color: 'var(--text-muted)', fontStyle: 'italic' }}>Brak danych</div>
        }
        {secondary && (
          <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', marginTop: '2px' }}>{secondary}</div>
        )}
      </div>
    </div>
  );
};

// ─── Unavailable row (stages 5–8, no navigation) ─────────────────────────────

const UnavailableRow: React.FC<{ icon: React.ReactNode; label: string }> = ({ icon, label }) => (
  <div
    aria-disabled="true"
    style={{
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      padding: '9px 12px',
      borderRadius: 'var(--radius-md)',
      border: '1px solid var(--border-subtle)',
      backgroundColor: 'var(--bg-surface)',
      opacity: 0.5,
    }}
  >
    <div style={{ display: 'flex', alignItems: 'center', gap: '7px', color: 'var(--text-muted)', fontSize: '0.8rem' }}>
      {icon}<span>{label}</span>
    </div>
    <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontWeight: 600 }}>Niedostępne</span>
  </div>
);

// ─── Page ─────────────────────────────────────────────────────────────────────

export const ProjectDashboardPage: React.FC = () => {
  const { activeProject, workflowStatus, workflowStatusLoading } = useProject();
  const { projectId } = useParams<{ projectId?: string }>();
  const pid = projectId || activeProject?.id || '';

  if (!activeProject) return null;

  const s = workflowStatus;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>

      {/* Project header */}
      <div>
        <h2 style={{ fontSize: '1.4rem', fontWeight: 800, color: 'var(--text-primary)' }}>
          {activeProject.title}
        </h2>
        <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
          {activeProject.description}
        </p>
      </div>

      {/* Next Action — rendered by NextActionCard using deriveNextAction from shared selector */}
      <NextActionCard />

      {/* Loading skeleton */}
      {workflowStatusLoading && (
        <div
          aria-label="Ładowanie statusu projektu"
          style={{
            display: 'flex', alignItems: 'center', gap: '10px',
            padding: '16px 20px',
            backgroundColor: 'var(--bg-surface)',
            borderRadius: 'var(--radius-lg)',
            border: '1px solid var(--border-subtle)',
            color: 'var(--text-secondary)',
            fontSize: '0.875rem',
          }}
        >
          <Loader2 size={18} style={{ animation: 'spin 1s linear infinite', color: 'var(--accent-primary)' }} />
          <span>Ładowanie statusu projektu...</span>
        </div>
      )}

      {/* Stage status cards 1–4 (render when workflowStatus available) */}
      {s && (
        <div>
          <h3 style={{ fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-muted)', fontWeight: 600, marginBottom: '10px' }}>
            Stan Etapów Procesu
          </h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '10px' }}>

            <StageCard
              id="stage-card-search"
              icon={<Search size={13} style={{ color: 'var(--accent-primary)' }} />}
              label="1. Search Strategy"
              state={s.search.state}
              primary={s.search.state === 'not_started' ? null
                : s.search.count !== null ? `${s.search.count} ${s.search.count === 1 ? 'grupa' : 'grup'}` : null}
              secondary={s.search.label}
              route={`/projects/${pid}/search`}
            />

            <StageCard
              id="stage-card-sources"
              icon={<Download size={13} style={{ color: 'var(--status-info-text)' }} />}
              label="2. Sources & Imports"
              state={s.sources.state}
              primary={s.sources.state === 'not_started' ? null
                : s.sources.count !== null ? formatImportCount(s.sources.count) : null}
              secondary={s.sources.label}
              route={`/projects/${pid}/sources`}
            />

            <StageCard
              id="stage-card-normalization"
              icon={<Sparkles size={13} style={{ color: 'var(--status-success-text)' }} />}
              label="3. Normalizacja"
              state={s.normalization.state}
              primary={normPrimaryValue(s.normalization.state, s.normalization.label)}
              secondary={s.normalization.state === 'completed' ? s.normalization.label : null}
              route={`/projects/${pid}/normalize`}
            />

            <StageCard
              id="stage-card-deduplication"
              icon={<GitMerge size={13} style={{ color: 'var(--status-warning-text)' }} />}
              label="4. Deduplikacja"
              state={s.deduplication.state}
              primary={
                s.deduplication.state === 'not_started' || s.deduplication.state === 'error' ? null
                  : s.deduplication.totalGroups > 0 ? `${s.deduplication.totalGroups} grup`
                  : 'Brak duplikatów'
              }
              secondary={
                s.deduplication.state === 'not_started' || s.deduplication.state === 'error'
                  ? s.deduplication.label
                  : s.deduplication.pendingGroups > 0
                    ? `${s.deduplication.pendingGroups} oczekuje`
                    : (s.deduplication.approvedGroups > 0 || s.deduplication.rejectedGroups > 0)
                      ? `${s.deduplication.approvedGroups} APPROVE · ${s.deduplication.rejectedGroups} REJECT`
                      : s.deduplication.label
              }
              route={`/projects/${pid}/dedup`}
            />

            <StageCard
              id="stage-card-screening"
              icon={<Filter size={13} style={{ color: 'var(--accent-primary)' }} />}
              label="5. Title & Abstract Screening"
              state={s.screening.state}
              primary={
                s.screening.state === 'not_started' ? 'Dostępne'
                  : s.screening.total !== null && s.screening.total > 0
                    ? `${s.screening.count ?? 0}/${s.screening.total} oceniono`
                    : 'Dostępne'
              }
              secondary={s.screening.label}
              route={`/projects/${pid}/screen/title-abstract`}
            />
          </div>
        </div>
      )}

      {/* Future stages: unavailable, no navigation */}
      <Card
        title={
          <span style={{ fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-muted)', fontWeight: 600 }}>
            Etapy Przyszłe
          </span>
        }
        style={{ gap: '6px' }}
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: '5px' }}>
          <UnavailableRow icon={<Filter size={13} />}        label="5b. Full-Text Screening (Phase 7.6)" />
          <UnavailableRow icon={<Award size={13} />}         label="6. Quality Assessment" />
          <UnavailableRow icon={<FileSpreadsheet size={13} />} label="7. Data Extraction" />
          <UnavailableRow icon={<FileCheck2 size={13} />}    label="8. Exports & PRISMA" />
        </div>
      </Card>
    </div>
  );
};
