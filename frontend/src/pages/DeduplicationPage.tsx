import React, { useEffect, useState } from 'react';
import { useProject } from '../context/ProjectContext';
import { projectApiService } from '../services/api/projectApi';
import { ApiDuplicateGroupListResponse } from '../types';
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
            Review Decisions API (Phase 6.4)
          </div>
        </div>
        <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
          Przeglądaj candidate duplicate groups wykryte przez backend. Podejmuj decyzje (Approve / Reject) zapisywane w in-memory API backendu.
        </p>
      </div>

      {/* Summary Card */}
      <DeduplicationSummaryCard summary={activeProject.deduplication} />

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
          <strong>Tryb Decyzji Badacza (Phase 6.4):</strong> Kliknięcie <em>Approve</em> lub <em>Reject</em> wysyła żądanie <code>POST</code> do API backendu i zapisuje stan decyzji w pamięci runtime serwera.
        </span>
      </div>
    </div>
  );
};
