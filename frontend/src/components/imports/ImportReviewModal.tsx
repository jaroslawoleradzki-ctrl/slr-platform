import React, { useCallback, useEffect, useRef, useState } from 'react';
import { AlertTriangle, CheckCircle2, ShieldAlert } from 'lucide-react';
import { Button } from '../common/Button';
import { Modal } from '../common/Modal';
import { useReviewerIdentity } from '../../hooks/useReviewerIdentity';
import { projectApiService } from '../../services/api/projectApi';
import {
  ImportFileRecord,
  ImportReviewBlocker,
  ImportReviewDecisionResponse,
  ImportReviewDetail,
} from '../../types';

interface ImportReviewModalProps {
  importRecord: ImportFileRecord;
  projectId: string;
  onClose: () => void;
  onChanged: () => Promise<void> | void;
  onDecisionApplied?: (result: ImportReviewDecisionResponse) => void;
}

type PendingAction = 'accept' | 'reject' | null;

const blockerLabel = (blocker: ImportReviewBlocker): string => {
  const publicationLabel = blocker.count === 1 ? 'publikacja' : 'publikacji';
  return `${blocker.message} (${blocker.count} ${publicationLabel})`;
};

export const ImportReviewModal: React.FC<ImportReviewModalProps> = ({
  importRecord,
  projectId,
  onClose,
  onChanged,
  onDecisionApplied,
}) => {
  const { reviewerId } = useReviewerIdentity();
  const reviewer = reviewerId || 'default_reviewer';
  const [detail, setDetail] = useState<ImportReviewDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [pendingAction, setPendingAction] = useState<PendingAction>(null);
  const pendingActionRef = useRef<PendingAction>(null);
  const [error, setError] = useState<string | null>(null);
  const [blockers, setBlockers] = useState<ImportReviewBlocker[]>([]);
  const [confirmReject, setConfirmReject] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setDetail(await projectApiService.getImportReview(projectId, importRecord.id));
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : 'Nie udało się pobrać szczegółów importu.',
      );
    } finally {
      setLoading(false);
    }
  }, [importRecord.id, projectId]);

  useEffect(() => {
    void load();
  }, [load]);

  const applyDecision = (result: ImportReviewDecisionResponse) => {
    setDetail((current) => current ? {
      ...current,
      effective_status: result.effective_status,
      review_status: result.review_status,
      can_accept: false,
      can_reject: false,
      decision: result.decision,
    } : current);
  };

  const submitDecision = async (
    action: Exclude<PendingAction, null>,
    payload: Parameters<typeof projectApiService.postImportReview>[2],
    fallbackError: string,
  ) => {
    if (pendingActionRef.current !== null) return;
    pendingActionRef.current = action;
    setPendingAction(action);
    setError(null);
    setBlockers([]);
    try {
      const result = await projectApiService.postImportReview(
        projectId,
        importRecord.id,
        payload,
      );
      applyDecision(result);
      try {
        onDecisionApplied?.(result);
      } catch {
        // A parent callback failure must not turn a committed decision into a failed one.
      }
      setConfirmReject(false);
      onClose();
      try {
        // The refresh is intentionally not awaited: the decision is already terminal.
        void Promise.resolve(onChanged()).catch(() => undefined);
      } catch {
        // A synchronous refresh failure is reported by the Sources view, not here.
      }
    } catch (caught) {
      const typed = caught as Error & { blockers?: ImportReviewBlocker[] };
      setError(typed.message || fallbackError);
      setBlockers(typed.blockers || []);
    } finally {
      pendingActionRef.current = null;
      setPendingAction(null);
    }
  };

  const accept = () => submitDecision(
    'accept',
    { decision: 'accept', reviewer_id: reviewer },
    'Nie udało się zaakceptować importu.',
  );

  const reject = () => submitDecision(
    'reject',
    { decision: 'reject', reviewer_id: reviewer, confirm_rejection: true },
    'Nie udało się odrzucić importu.',
  );

  const title = `Szczegóły importu: ${importRecord.filename ?? importRecord.provider ?? 'Import'}`;

  return (
    <>
      <Modal
        isOpen
        onClose={() => {
          if (pendingAction === null) onClose();
        }}
        title={title}
        maxWidth="720px"
      >
        {loading ? (
          <p role="status" style={{ color: 'var(--text-secondary)' }}>Ładowanie szczegółów importu…</p>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: '8px', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
              <div>Plik: <strong>{detail?.filename ?? importRecord.filename ?? 'brak'}</strong></div>
              <div>Status: <strong>{detail?.effective_status ?? importRecord.effectiveStatus ?? importRecord.status}</strong></div>
              <div>Rekordy źródłowe: <strong>{detail?.source_record_count ?? importRecord.sourceRecordCount ?? 'brak danych'}</strong></div>
              <div>Publikacje kanoniczne: <strong>{detail?.canonical_publication_count ?? importRecord.canonicalPublicationCount ?? 'brak danych'}</strong></div>
              <div>Dokładne duplikaty DOI: <strong>{detail?.exact_doi_match_count ?? importRecord.exactDoiMatchCount ?? 0}</strong></div>
              <div>Powtórzone wystąpienia: <strong>{detail?.repeated_source_count ?? importRecord.repeatedSourceCount ?? 0}</strong></div>
              <div>Kandydaci tytułowi: <strong>{detail?.title_candidate_count ?? importRecord.titleCandidateCount ?? 0}</strong></div>
              <div>Kandydaci podobni: <strong>{detail?.similar_title_candidate_count ?? importRecord.similarTitleCandidateCount ?? 0}</strong></div>
              <div>Pominięte wstawienia: <strong>{detail?.skipped_canonical_count ?? importRecord.skippedCanonicalCount ?? 0}</strong></div>
              <div>Audyt dostępny: <strong>{(detail?.audit_available ?? importRecord.auditAvailable ?? importRecord.skipAuditAvailable) ? 'tak' : 'nie'}</strong></div>
              <div>Status odzyskiwania: <strong>{importRecord.recoveryStatus ?? 'brak danych'}</strong></div>
              <div>Niepoprawne DOI: <strong>{detail?.invalid_doi_count ?? importRecord.invalidDoiCount ?? 0}</strong></div>
              <div>Błędy walidacji: <strong>{detail?.validation_error_count ?? importRecord.validationErrorCount ?? 0}</strong></div>
            </div>

            {detail?.warning_categories && detail.warning_categories.length > 0 && (
              <div>
                <strong style={{ display: 'block', marginBottom: '6px' }}>Kategorie ostrzeżeń</strong>
                <ul style={{ margin: 0, paddingLeft: '20px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  {detail.warning_categories.map((category) => (
                    <li key={category.code} style={{ fontSize: '0.85rem' }}>
                      {category.label}: <strong>{category.count}</strong>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {(detail?.warnings ?? importRecord.warnings ?? []).length > 0 ? (
              <div>
                <strong style={{ display: 'block', marginBottom: '6px' }}>Zapisane ostrzeżenia</strong>
                <ul style={{ margin: 0, paddingLeft: '20px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {(detail?.warnings ?? importRecord.warnings ?? []).map((warning, index) => (
                    <li key={index} style={{ fontSize: '0.85rem', color: 'var(--text-primary)' }}>{warning}</li>
                  ))}
                </ul>
              </div>
            ) : (
              <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                Brak szczegółowych informacji diagnostycznych dla tego importu historycznego.
              </p>
            )}

            {detail?.decision && (
              <div style={{ padding: '10px 12px', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-md)', fontSize: '0.85rem' }}>
                Decyzja: <strong>{detail.decision.decision === 'accepted' ? 'Akceptacja' : 'Odrzucenie'}</strong>
                {' · '}Reviewer: <strong>{detail.decision.reviewer_id}</strong>
                {' · '}{new Date(detail.decision.decided_at).toLocaleString('pl-PL')}
              </div>
            )}

            {detail && !detail.can_reject && detail.blockers.length > 0 && (
              <div role="alert" style={{ padding: '12px 14px', borderRadius: 'var(--radius-md)', backgroundColor: 'var(--status-warning-bg)', border: '1px solid var(--status-warning-border)', color: 'var(--status-warning-text)', fontSize: '0.85rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontWeight: 700 }}>
                  <ShieldAlert size={16} /> Odrzucenie jest zablokowane
                </div>
                <p style={{ margin: '6px 0 4px' }}>Ten import nie może zostać odrzucony, ponieważ jego publikacje są używane w istniejących decyzjach badawczych.</p>
                <ul style={{ margin: 0, paddingLeft: '18px' }}>
                  {detail.blockers.map((blocker) => <li key={blocker.code}>{blockerLabel(blocker)}</li>)}
                </ul>
              </div>
            )}

            {error && (
              <div role="alert" style={{ color: 'var(--status-error-text)', fontSize: '0.85rem' }}>
                {error}
                {blockers.length > 0 && (
                  <ul style={{ margin: '6px 0 0', paddingLeft: '18px' }}>
                    {blockers.map((blocker) => <li key={blocker.code}>{blockerLabel(blocker)}</li>)}
                  </ul>
                )}
              </div>
            )}

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', flexWrap: 'wrap', borderTop: '1px solid var(--border-subtle)', paddingTop: '14px' }}>
              {detail?.can_accept && (
                <>
                  <Button
                    variant="outline"
                    disabled={pendingAction !== null || !detail.can_reject}
                    onClick={() => setConfirmReject(true)}
                    title={!detail.can_reject ? 'Odrzucenie jest zablokowane przez zależne decyzje badawcze.' : undefined}
                  >
                    Odrzucam
                  </Button>
                  <Button
                    isLoading={pendingAction === 'accept'}
                    disabled={pendingAction !== null}
                    onClick={() => void accept()}
                    icon={pendingAction === 'accept' ? undefined : <CheckCircle2 size={15} />}
                  >
                    Akceptuję
                  </Button>
                </>
              )}
              <Button
                variant="outline"
                onClick={onClose}
                disabled={pendingAction !== null}
              >
                Zamknij
              </Button>
            </div>
          </div>
        )}
      </Modal>

      {confirmReject && (
        <Modal
          isOpen
          onClose={() => {
            if (pendingAction === null) setConfirmReject(false);
          }}
          title="Odrzucić import?"
          maxWidth="520px"
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div style={{ display: 'flex', gap: '10px', alignItems: 'flex-start', color: 'var(--status-warning-text)' }}>
              <AlertTriangle size={20} style={{ flexShrink: 0, marginTop: '2px' }} />
              <p style={{ margin: 0, fontSize: '0.9rem', color: 'var(--text-primary)' }}>
                „Czy na pewno chcesz odrzucić ten import? Operacja usunie dane należące do wybranego importu. Nie wpłynie na pozostałe importy.”
              </p>
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
              <Button
                variant="outline"
                onClick={() => setConfirmReject(false)}
                disabled={pendingAction !== null}
              >
                Anuluj
              </Button>
              <Button
                isLoading={pendingAction === 'reject'}
                disabled={pendingAction !== null}
                onClick={() => void reject()}
              >
                Potwierdź odrzucenie
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </>
  );
};
