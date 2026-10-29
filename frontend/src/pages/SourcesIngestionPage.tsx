import React, { useEffect, useState, useCallback } from 'react';
import { useProject } from '../context/ProjectContext';
import { ProviderStatusCard } from '../components/search/ProviderStatusCard';
import { FileDropzone } from '../components/imports/FileDropzone';
import { projectApiService } from '../services/api/projectApi';
import {
  SourcesSummaryResponse,
  ImportFileRecord,
  ImportReviewDecisionResponse,
} from '../types';

export const SourcesIngestionPage: React.FC = () => {
  const { activeProject, importBibliographicFile } = useProject();
  const [sourcesSummary, setSourcesSummary] = useState<SourcesSummaryResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const activeProjectId = activeProject?.id;

  const fetchSummary = useCallback(async () => {
    if (!activeProjectId) return;
    setLoading(true);
    setError(null);
    try {
      const summary = await projectApiService.getSourcesSummary(activeProjectId);
      setSourcesSummary(summary);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Nie udało się pobrać podsumowania źródeł');
    } finally {
      setLoading(false);
    }
  }, [activeProjectId]);

  useEffect(() => {
    void fetchSummary();
  }, [fetchSummary]);

  const handleDecisionApplied = useCallback((result: ImportReviewDecisionResponse) => {
    setSourcesSummary((current) => {
      if (!current) return current;
      return {
        ...current,
        import_history: current.import_history.map((item) => (
          item.import_id === result.import_id
            ? {
                ...item,
                effective_status: result.effective_status,
                review_status: result.review_status,
                reviewer_id: result.decision.reviewer_id,
                reviewed_at: result.decision.decided_at,
                can_accept: false,
                can_reject: false,
              }
            : item
        )),
      };
    });
  }, []);

  if (!activeProject) return null;

  const handleFileSelect = async (file: File) => {
    const res = await importBibliographicFile(file);
    await fetchSummary();
    return res;
  };

  const displayedProviders = activeProject.providers.map((provider) => {
    const summaryItem = sourcesSummary?.source_summaries.find(
      (s) => s.source_kind === 'provider' && s.source === provider.id.toLowerCase()
    );

    if (!summaryItem) {
      return {
        ...provider,
        connected: false,
        status: 'idle' as const,
        resultsCount: 0,
        lastRunTimestamp: null,
      };
    }

    const isSuccess = summaryItem.last_import_status === 'success' || summaryItem.last_import_status === 'warning';
    return {
      ...provider,
      connected: isSuccess,
      status: isSuccess ? ('completed' as const) : ('failed' as const),
      resultsCount: summaryItem.records_added_count,
      lastRunTimestamp: summaryItem.last_import_at,
      errorMessage: summaryItem.last_import_status === 'failed' ? 'Nieudana próba pobrania' : undefined,
    };
  });

  const importFileRecords: ImportFileRecord[] = (sourcesSummary?.import_history || []).map((item) => ({
    id: item.import_id,
    sourceType: item.source_type,
    filename: item.filename,
    format: item.format as 'BibTeX' | 'RIS' | null,
    provider: item.provider,
    query: item.query,
    recordsCount: item.records_count,
    importedAt: item.created_at,
    status: item.status,
    warnings: item.warnings,
    sourceRecordCount: item.source_record_count,
    canonicalPublicationCount: item.canonical_publication_count,
    exactDoiMatchCount: item.exact_doi_match_count,
    repeatedSourceCount: item.repeated_source_count,
    titleCandidateCount: item.title_candidate_count,
    similarTitleCandidateCount: item.similar_title_candidate_count,
    skippedCanonicalCount: item.skipped_canonical_count,
    invalidDoiCount: item.invalid_doi_count,
    validationErrorCount: item.validation_error_count,
    skipAuditAvailable: item.skip_audit_available,
    auditAvailable: item.audit_available,
    recoveryStatus: item.recovery_status,
    reviewStatus: item.review_status,
    effectiveStatus: item.effective_status,
    reviewerId: item.reviewer_id,
    reviewedAt: item.reviewed_at,
    canAccept: item.can_accept,
    canReject: item.can_reject,
  }));

  if (loading && !sourcesSummary) {
    return <div style={{ padding: '24px', color: 'var(--text-muted)' }}>Ładowanie podsumowania źródeł…</div>;
  }

  if (error && !sourcesSummary) {
    return (
      <div role="alert" style={{ padding: '24px', color: 'var(--status-error-text)' }}>
        {error}
        <div style={{ marginTop: '12px' }}>
          <button type="button" onClick={() => void fetchSummary()}>Ponów</button>
        </div>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div>
        <h2 style={{ fontSize: '1.3rem', fontWeight: 800, color: 'var(--text-primary)' }}>
          2. Źródła Wyszukiwania i Importy (Sources & Ingestion)
        </h2>
        <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
          Łącznie publikacji w kolekcji roboczej (Working Collection): {sourcesSummary?.working_collection.total_records ?? 0}
        </p>
      </div>

      {error && (
        <div
          role="alert"
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '12px',
            padding: '12px 14px',
            borderRadius: 'var(--radius-md)',
            border: '1px solid var(--status-error-border)',
            backgroundColor: 'var(--status-error-bg)',
            color: 'var(--status-error-text)',
            fontSize: '0.85rem',
          }}
        >
          <span>
            {error} Wyświetlane liczniki mogą być nieaktualne.
          </span>
          <button type="button" onClick={() => void fetchSummary()}>Ponów</button>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '16px' }}>
        {displayedProviders.map((provider) => (
          <ProviderStatusCard key={provider.id} provider={provider} />
        ))}
      </div>

      <FileDropzone
        imports={importFileRecords}
        onFileSelect={handleFileSelect}
        projectId={activeProject.id}
        onRefresh={fetchSummary}
        onDecisionApplied={handleDecisionApplied}
      />
    </div>
  );
};
