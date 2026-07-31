import React from 'react';
import { useProject } from '../context/ProjectContext';
import { DuplicateDecisionStatus } from '../types';
import { DeduplicationSummaryCard } from '../components/deduplication/DeduplicationSummaryCard';
import { DuplicateGroupCardPreview } from '../components/deduplication/DuplicateGroupCardPreview';
import { LoadingSpinner } from '../components/common/LoadingSpinner';
import { ErrorAlert } from '../components/common/ErrorAlert';
import { EmptyState } from '../components/common/EmptyState';
import { Layers, ShieldCheck } from 'lucide-react';

export const DeduplicationPage: React.FC = () => {
  const {
    activeProject,
    duplicateData,
    duplicateGroupError,
    workflowStatusLoading,
    updateGroupDecision,
    refreshWorkflowStatus,
  } = useProject();

  const handleGroupDecisionUpdated = (
    groupId: string,
    decision: DuplicateDecisionStatus,
    rationale?: string | null
  ) => {
    updateGroupDecision(groupId, decision, rationale);
  };

  if (!activeProject) return null;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Header & Section Title */}
      <div>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <h2 style={{ fontSize: '1.3rem', fontWeight: 800, color: 'var(--text-primary)' }}>
            4. Wykrywanie i Przegląd Duplikatów (Deduplication)
          </h2>
          <div
            style={{
              fontSize: '0.75rem',
              color: 'var(--status-info-text)',
              backgroundColor: 'var(--status-info-bg)',
              padding: '4px 10px',
              borderRadius: 'var(--radius-full)',
              border: '1px solid var(--status-info-border)',
              fontWeight: 600,
            }}
          >
            Dynamic Workflow Navigation Status (v0.2.2)
          </div>
        </div>
        <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
          Porównuj publikacje w grupach kandydatów obok siebie, weryfikuj zgodność pól i pochodzenie (provenance) oraz zapisuj decyzje badacza z opcjonalnym uzasadnieniem (rationale).
        </p>
      </div>

      {/* Summary Card */}
      <DeduplicationSummaryCard
        groups={duplicateData ? duplicateData.groups : []}
        summary={activeProject.deduplication}
      />

      {/* Main Content Area Handling Loading, Error, Empty & Success States */}
      {workflowStatusLoading && !duplicateData && !duplicateGroupError ? (
        <div style={{ padding: '40px 0' }}>
          <LoadingSpinner label="Pobieranie grup kandydatów z API backendu..." />
        </div>
      ) : duplicateGroupError ? (
        <ErrorAlert
          title="Błąd połączenia z API Deduplikacji"
          message={duplicateGroupError}
          onRetry={() => activeProject && void refreshWorkflowStatus(activeProject.id)}
        />
      ) : duplicateData && duplicateData.total_groups_count === 0 ? (
        <EmptyState
          icon={<Layers size={36} />}
          title="Brak grup kandydatów na duplikaty"
          description="Nie znaleziono żadnych dodatkowych grup powiązanych silnymi identyfikatorami (DOI, PMID, OpenAlex ID) w tym projekcie."
        />
      ) : duplicateData ? (
        <div>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
            <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--text-primary)' }}>
              Duplicate Groups Awaiting Human Review ({duplicateData.total_groups_count})
            </h3>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              Pobrano {duplicateData.total_groups_count} grup z API backendu
            </span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {duplicateData.groups.map((group, idx) => (
              <DuplicateGroupCardPreview
                key={group.group_id}
                group={group}
                index={idx}
                projectId={activeProject.id}
                onDecisionUpdated={handleGroupDecisionUpdated}
              />
            ))}
          </div>
        </div>
      ) : null}

      {/* Decision Recording Notice */}
      <div
        style={{
          padding: '12px 16px',
          borderRadius: 'var(--radius-md)',
          backgroundColor: 'var(--bg-surface-elevated)',
          border: '1px solid var(--border-subtle)',
          fontSize: '0.8rem',
          color: 'var(--text-secondary)',
          display: 'flex',
          alignItems: 'center',
          gap: '10px',
        }}
      >
        <ShieldCheck size={16} style={{ color: 'var(--status-success-text)', flexShrink: 0 }} />
        <span>
          <strong>Trwała rejestracja decyzji w SQLite (v0.2.2):</strong> Kliknięcie <em>Approve</em> potwierdza, że rekordy reprezentują ten sam utwór, a <em>Reject</em> potwierdza, że rekordy nie są duplikatami. Decyzja i uzasadnienie są zapisywane trwale w bazie SQLite. W wersji 0.2.2 stan nawigacji workflow odświeża się natychmiast po zapisaniu decyzji.
        </span>
      </div>
    </div>
  );
};
