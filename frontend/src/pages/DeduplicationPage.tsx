import React, { useState } from 'react';
import { useProject } from '../context/ProjectContext';
import { DuplicateGroupStatus } from '../types';
import { DeduplicationSummaryCard } from '../components/deduplication/DeduplicationSummaryCard';
import { DuplicateGroupCardPreview } from '../components/deduplication/DuplicateGroupCardPreview';
import { LoadingSpinner } from '../components/common/LoadingSpinner';
import { ErrorAlert } from '../components/common/ErrorAlert';
import { EmptyState } from '../components/common/EmptyState';
import { Button } from '../components/common/Button';
import { Card } from '../components/common/Card';
import { Layers, Play, ShieldCheck } from 'lucide-react';

interface DeduplicationRunReport {
  status: 'success' | 'error';
  inputRecords: number;
  analyzedRecords: number;
  groupsFound: number;
  durationMs: number;
  completedAt: Date;
}

export const DeduplicationPage: React.FC = () => {
  const {
    activeProject,
    duplicateData,
    duplicateGroupError,
    workflowStatusLoading,
    updateGroupDecision,
    refreshWorkflowStatus,
    runDeduplication,
  } = useProject();
  const [isRunning, setIsRunning] = useState(false);
  const [runReport, setRunReport] = useState<DeduplicationRunReport | null>(null);

  const inputRecords = activeProject?.imports.reduce(
    (total, item) => item.status === 'success' || item.status === 'warning'
      ? total + item.recordsCount
      : total,
    0
  ) ?? 0;

  const handleRunDeduplication = async () => {
    const startedAt = performance.now();
    const runInputRecords = inputRecords;
    setIsRunning(true);
    setRunReport(null);
    try {
      const result = await runDeduplication();
      setRunReport({
        status: 'success',
        inputRecords: runInputRecords,
        analyzedRecords: runInputRecords,
        groupsFound: result.total_groups_count,
        durationMs: performance.now() - startedAt,
        completedAt: new Date(),
      });
    } catch {
      setRunReport({
        status: 'error',
        inputRecords: runInputRecords,
        analyzedRecords: 0,
        groupsFound: 0,
        durationMs: performance.now() - startedAt,
        completedAt: new Date(),
      });
    } finally {
      setIsRunning(false);
    }
  };

  const handleGroupDecisionUpdated = (
    groupId: string,
    decision: DuplicateGroupStatus,
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
            Dynamic Workflow Navigation Status
          </div>
        </div>
        <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
          Porównuj publikacje w grupach kandydatów obok siebie, weryfikuj zgodność pól i pochodzenie (provenance) oraz zapisuj decyzje badacza z opcjonalnym uzasadnieniem (rationale).
        </p>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginTop: '14px' }}>
          <Button
            type="button"
            onClick={() => void handleRunDeduplication()}
            isLoading={isRunning}
            loadingText="Uruchamianie deduplikacji..."
            icon={<Play size={16} />}
          >
            Uruchom deduplikację
          </Button>
        </div>
      </div>

      <Card title="Ostatnie wykonanie deduplikacji">
        {isRunning ? (
          <div role="status" style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <LoadingSpinner label={`Analizowanie ${inputRecords.toLocaleString('pl-PL')} rekordów...`} />
          </div>
        ) : runReport?.status === 'success' ? (
          <div role="status" style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            <div style={{ color: 'var(--status-success-text)', fontWeight: 700 }}>
              Deduplikacja zakończona pomyślnie
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: '14px' }}>
              <div><strong>Ostatnie wykonanie</strong><br />{runReport.completedAt.toLocaleString('pl-PL')}</div>
              <div><strong>Status</strong><br />Zakończono pomyślnie</div>
              <div><strong>Wejściowa kolekcja</strong><br />{runReport.inputRecords.toLocaleString('pl-PL')}</div>
              <div><strong>Przeanalizowano</strong><br />{runReport.analyzedRecords.toLocaleString('pl-PL')} publikacji</div>
              <div><strong>Znaleziono grup</strong><br />{runReport.groupsFound.toLocaleString('pl-PL')}</div>
              <div><strong>Czas wykonania</strong><br />{(runReport.durationMs / 1000).toFixed(1)} s</div>
            </div>
          </div>
        ) : runReport?.status === 'error' ? (
          <div role="alert" style={{ color: 'var(--status-error-text)', fontWeight: 600 }}>
            Nie udało się wykonać deduplikacji.
          </div>
        ) : (
          <div style={{ color: 'var(--text-muted)' }}>
            Nigdy nie uruchamiano deduplikacji. Wejściowa kolekcja: {inputRecords.toLocaleString('pl-PL')}.
          </div>
        )}
      </Card>

      {/* Summary Card */}
      <DeduplicationSummaryCard
        groups={duplicateData ? duplicateData.groups : []}
        summary={activeProject.deduplication}
        hasRun={runReport?.status === 'success'}
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
                onMerged={() => void refreshWorkflowStatus(activeProject.id)}
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
          <strong>Decyzje APPROVE i REJECT są trwale zapisywane w bazie SQLite.</strong> Kliknięcie <em>Approve</em> potwierdza, że rekordy reprezentują ten sam utwór, a <em>Reject</em> potwierdza, że rekordy nie są duplikatami. Zapis decyzji nie wykonuje fizycznego scalania publikacji.
        </span>
      </div>
    </div>
  );
};
