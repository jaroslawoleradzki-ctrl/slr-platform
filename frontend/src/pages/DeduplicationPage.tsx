import React, { useEffect, useState } from 'react';
import { useProject } from '../context/ProjectContext';
import { projectApiService } from '../services/api/projectApi';
import { ApiDuplicateGroupListResponse, DuplicateDecisionStatus } from '../types';
import { DeduplicationSummaryCard } from '../components/deduplication/DeduplicationSummaryCard';
import { DuplicateGroupCardPreview } from '../components/deduplication/DuplicateGroupCardPreview';
import { LoadingSpinner } from '../components/common/LoadingSpinner';
import { ErrorAlert } from '../components/common/ErrorAlert';
import { EmptyState } from '../components/common/EmptyState';
import { Layers, ShieldCheck } from 'lucide-react';

export const DeduplicationPage: React.FC = () => {
  const { activeProject } = useProject();
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [duplicateData, setDuplicateData] = useState<ApiDuplicateGroupListResponse | null>(null);

  const fetchDuplicateGroups = async (projectId: string) => {
    setLoading(true);
    setError(null);
    try {
      const result = await projectApiService.getDuplicateGroups(projectId);
      setDuplicateData(result);
    } catch (err: unknown) {
      const errorMessage =
        err instanceof Error
          ? err.message
          : 'Nie udało się połączyć z API backendu deduplikacji.';
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (activeProject) {
      fetchDuplicateGroups(activeProject.id);
    }
  }, [activeProject?.id]);

  const handleGroupDecisionUpdated = (
    groupId: string,
    decision: DuplicateDecisionStatus,
    rationale?: string | null
  ) => {
    setDuplicateData((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        groups: prev.groups.map((g) =>
          g.group_id === groupId
            ? { ...g, status: decision, rationale: rationale ?? g.rationale }
            : g
        ),
      };
    });
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
            Durable Duplicate Review Integration (v0.2.1)
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
      {loading ? (
        <div style={{ padding: '40px 0' }}>
          <LoadingSpinner label="Pobieranie grup kandydatów z API backendu..." />
        </div>
      ) : error ? (
        <ErrorAlert
          title="Błąd połączenia z API Deduplikacji"
          message={error}
          onRetry={() => activeProject && fetchDuplicateGroups(activeProject.id)}
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
          <strong>Trwała rejestracja decyzji w SQLite (v0.2.1):</strong> Kliknięcie <em>Approve</em> potwierdza, że rekordy reprezentują ten sam utwór, a <em>Reject</em> potwierdza, że rekordy nie są duplikatami. Decyzja i uzasadnienie są zapisywane trwale w bazie SQLite. W wersji 0.2.1 zatwierdzenie nie wykonuje jeszcze fizycznego scalenia (merge) publikacji w zbiorze roboczym.
        </span>
      </div>
    </div>
  );
};
