import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useLocation, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { Card } from '../components/common/Card';
import { Button } from '../components/common/Button';
import { Badge } from '../components/common/Badge';
import { Modal } from '../components/common/Modal';
import { ErrorAlert } from '../components/common/ErrorAlert';
import { LoadingSpinner } from '../components/common/LoadingSpinner';
import {
  qualityAssessmentApi,
  QualityAssessmentOverview,
  QualityAssessmentRecordDetail,
  QualityAssessmentStatusFilter,
  QualityAssessmentResponseValue,
  EligiblePublicationRecord,
  QualityAssessmentApiError,
} from '../services/api/qualityAssessmentApi';
import { QualityAssessmentReadinessAlert } from '../components/quality_assessment/QualityAssessmentReadinessAlert';
import { QualityAssessmentConfigPanel } from '../components/quality_assessment/QualityAssessmentConfigPanel';
import { QualityAssessmentExecutionPanel } from '../components/quality_assessment/QualityAssessmentExecutionPanel';
import { Award, Filter, RefreshCw, User, Settings } from 'lucide-react';
import { screeningControlStyle, screeningLabelStyle } from '../components/screening/screeningFormStyles';
import { useReviewerIdentity } from '../hooks/useReviewerIdentity';

const PAGE_SIZE = 20;

const filterOptions: Array<{ value: QualityAssessmentStatusFilter; label: string }> = [
  { value: 'unassessed', label: 'Nieocenione' },
  { value: 'all', label: 'Wszystkie' },
  { value: 'assessed', label: 'Ocenione' },
];

export const QualityAssessmentPage: React.FC = () => {
  const { projectId = '', publicationId } = useParams<{ projectId: string; publicationId?: string }>();
  const location = useLocation();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const isConfigRoute = location.pathname.endsWith('/configuration');

  const requestedStatus = searchParams.get('status');
  const selectedFilter: QualityAssessmentStatusFilter =
    requestedStatus === 'all' || requestedStatus === 'assessed'
      ? requestedStatus
      : 'unassessed';

  const { reviewerId: reviewer, setReviewerId: setReviewer } = useReviewerIdentity();
  const [reviewerDraft, setReviewerDraft] = useState<string>(reviewer);
  const [reviewerModal, setReviewerModal] = useState<boolean>(!reviewer);

  const [overview, setOverview] = useState<QualityAssessmentOverview | null>(null);
  const [records, setRecords] = useState<EligiblePublicationRecord[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [offset, setOffset] = useState<number>(0);
  const [currentDetail, setCurrentDetail] = useState<QualityAssessmentRecordDetail | null>(null);

  const [draftResponses, setDraftResponses] = useState<
    Record<string, { value: QualityAssessmentResponseValue | null; justification: string }>
  >({});
  const [loading, setLoading] = useState<boolean>(false);
  const [saving, setSaving] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const requestVersion = useRef<number>(0);
  const baselineDraft = useRef<string>('');

  const isDirty = JSON.stringify(draftResponses) !== baselineDraft.current;

  const initDraftForDetail = useCallback((detail: QualityAssessmentRecordDetail | null) => {
    if (!detail) {
      setDraftResponses({});
      baselineDraft.current = JSON.stringify({});
      return;
    }

    const templateCriteria = detail.template.criteria;
    const latestRespMap = new Map(
      (detail.latest_assessment?.responses || []).map((r) => [r.criterion_id, r])
    );

    const initialDrafts: Record<string, { value: QualityAssessmentResponseValue | null; justification: string }> = {};

    for (const crit of templateCriteria) {
      const existing = latestRespMap.get(crit.criterion_id);
      if (existing) {
        initialDrafts[crit.criterion_id] = {
          value: existing.response_value,
          justification: existing.justification || '',
        };
      } else {
        initialDrafts[crit.criterion_id] = {
          value: null,
          justification: '',
        };
      }
    }

    setDraftResponses(initialDrafts);
    baselineDraft.current = JSON.stringify(initialDrafts);
  }, []);

  const pathFor = useCallback(
    (pubId?: string) => `/projects/${projectId}/quality-assessment${pubId ? `/${pubId}` : ''}`,
    [projectId]
  );

  const filterQuery = `?status=${selectedFilter}`;

  const loadData = useCallback(
    async (targetOffset = offset, preferredPubId?: string) => {
      if (!reviewer || !projectId || isConfigRoute) return;

      const version = ++requestVersion.current;
      setLoading(true);
      setError(null);

      try {
        const nextOverview = await qualityAssessmentApi.getOverview(projectId, reviewer);
        if (version !== requestVersion.current) return;
        setOverview(nextOverview);

        if (nextOverview.readiness !== 'ready') {
          setRecords([]);
          setCurrentDetail(null);
          return;
        }

        const page = Math.floor(targetOffset / PAGE_SIZE) + 1;
        const recordList = await qualityAssessmentApi.listRecords(
          projectId,
          reviewer,
          selectedFilter,
          page,
          PAGE_SIZE
        );
        if (version !== requestVersion.current) return;

        setRecords(recordList.items);
        setTotal(recordList.total);
        setOffset(targetOffset);

        if (recordList.items.length === 0) {
          setCurrentDetail(null);
          initDraftForDetail(null);
          return;
        }

        let targetId = preferredPubId || publicationId;
        if (!targetId || !recordList.items.some((item) => item.publication.record_id === targetId)) {
          targetId = recordList.items[0].publication.record_id;
        }

        const detail = await qualityAssessmentApi.getRecordDetail(projectId, targetId, reviewer);
        if (version !== requestVersion.current) return;

        setCurrentDetail(detail);
        initDraftForDetail(detail);

        if (targetId !== publicationId) {
          navigate(pathFor(targetId) + filterQuery, { replace: true });
        }
      } catch (caught) {
        if (version !== requestVersion.current) return;
        const apiErr = caught as QualityAssessmentApiError;
        setError(apiErr.message || 'Wystąpił błąd podczas ładowania danych oceny jakościowej.');
      } finally {
        if (version === requestVersion.current) {
          setLoading(false);
        }
      }
    },
    [filterQuery, initDraftForDetail, isConfigRoute, navigate, offset, pathFor, projectId, publicationId, reviewer, selectedFilter]
  );

  useEffect(() => {
    void loadData(0);
  }, [projectId, reviewer, selectedFilter, isConfigRoute]); // eslint-disable-line react-hooks/exhaustive-deps

  const confirmDiscard = (): boolean => {
    if (!isDirty) return true;
    return window.confirm('Masz niezapisane zmiany w formularzu oceny. Czy chcesz je odrzucić?');
  };

  const submitReviewer = () => {
    const value = reviewerDraft.trim();
    if (!value) {
      setError('Identyfikator recenzenta nie może być pusty.');
      return;
    }
    setReviewer(value);
    setReviewerModal(false);
    setError(null);
    setCurrentDetail(null);
    initDraftForDetail(null);
  };

  const chooseFilter = (filterVal: QualityAssessmentStatusFilter) => {
    if (!confirmDiscard()) return;
    setOffset(0);
    navigate(`/projects/${projectId}/quality-assessment?status=${filterVal}`, { replace: true });
  };

  const handleResponseChange = (criterionId: string, value: QualityAssessmentResponseValue) => {
    setDraftResponses((prev) => ({
      ...prev,
      [criterionId]: {
        value,
        justification: prev[criterionId]?.justification || '',
      },
    }));
  };

  const handleJustificationChange = (criterionId: string, justification: string) => {
    setDraftResponses((prev) => ({
      ...prev,
      [criterionId]: {
        value: prev[criterionId]?.value || null,
        justification,
      },
    }));
  };

  const navigateToRecordIndex = async (index: number) => {
    if (!confirmDiscard() || index < 0 || index >= records.length) return;
    const targetPubId = records[index].publication.record_id;

    setLoading(true);
    try {
      const detail = await qualityAssessmentApi.getRecordDetail(projectId, targetPubId, reviewer);
      setCurrentDetail(detail);
      initDraftForDetail(detail);
      navigate(pathFor(targetPubId) + filterQuery);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Nie udało się załadować publikacji.');
    } finally {
      setLoading(false);
    }
  };

  const handleSaveAssessment = async (goNext: boolean) => {
    if (!currentDetail || saving) return;

    const payloadResponses = currentDetail.template.criteria.flatMap((crit) => {
      const draft = draftResponses[crit.criterion_id];
      if (!draft || !draft.value) return [];
      return [
        {
          criterion_id: crit.criterion_id,
          response_value: draft.value,
          justification: draft.justification.trim(),
        },
      ];
    });

    setSaving(true);
    setError(null);

    try {
      await qualityAssessmentApi.saveAssessment(projectId, {
        reviewer_id: reviewer,
        publication_id: currentDetail.publication.record_id,
        responses: payloadResponses,
      });

      // Reload fresh overview & detail
      const freshOverview = await qualityAssessmentApi.getOverview(projectId, reviewer);
      setOverview(freshOverview);

      const updatedDetail = await qualityAssessmentApi.getRecordDetail(
        projectId,
        currentDetail.publication.record_id,
        reviewer
      );
      setCurrentDetail(updatedDetail);
      initDraftForDetail(updatedDetail);

      if (!goNext) return;

      // Save & Next logic for UNASSESSED filter invariant:
      // When saving an UNASSESSED record, it disappears from the UNASSESSED list.
      // Keeping current offset re-fetches records, so index 0 is the NEXT unassessed item.
      const currentPage = Math.floor(offset / PAGE_SIZE) + 1;
      const recordList = await qualityAssessmentApi.listRecords(
        projectId,
        reviewer,
        selectedFilter,
        currentPage,
        PAGE_SIZE
      );

      setRecords(recordList.items);
      setTotal(recordList.total);

      if (recordList.items.length > 0) {
        let nextPubId = recordList.items[0].publication.record_id;

        if (selectedFilter !== 'unassessed') {
          const currentIndex = recordList.items.findIndex(
            (item) => item.publication.record_id === currentDetail.publication.record_id
          );
          if (currentIndex >= 0 && currentIndex + 1 < recordList.items.length) {
            nextPubId = recordList.items[currentIndex + 1].publication.record_id;
          }
        }

        const nextDetail = await qualityAssessmentApi.getRecordDetail(projectId, nextPubId, reviewer);
        setCurrentDetail(nextDetail);
        initDraftForDetail(nextDetail);
        navigate(pathFor(nextPubId) + filterQuery);
      } else {
        setCurrentDetail(null);
        initDraftForDetail(null);
      }
    } catch (caught) {
      const apiErr = caught as QualityAssessmentApiError;
      setError(
        apiErr.status === 422
          ? `Błąd walidacji zapisu oceny: ${apiErr.message}`
          : apiErr.message || 'Nie udało się zapisać oceny jakościowej.'
      );
    } finally {
      setSaving(false);
    }
  };

  // Reviewer prompt modal
  if (!reviewer) {
    return (
      <Modal isOpen={reviewerModal} onClose={() => undefined} title="Identyfikator Recenzenta">
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
            Podaj lokalny identyfikator recenzenta dla sesji (np. <code>analyst_1</code>). Postęp i historia ocen są przypisywane do Twojego identyfikatora.
          </p>

          {error && <ErrorAlert message={error} />}

          <label style={screeningLabelStyle}>
            Identyfikator recenzenta
            <input
              aria-label="Reviewer identifier"
              value={reviewerDraft}
              onChange={(e) => setReviewerDraft(e.target.value)}
              style={screeningControlStyle}
              autoFocus
            />
          </label>

          <div>
            <Button variant="primary" onClick={submitReviewer}>
              Rozpocznij Ocenę Jakości
            </Button>
          </div>
        </div>
      </Modal>
    );
  }

  // Render Configuration subview if route is /configuration
  if (isConfigRoute) {
    return (
      <QualityAssessmentConfigPanel
        projectId={projectId}
        onConfigurationSaved={() => navigate(`/projects/${projectId}/quality-assessment`)}
      />
    );
  }

  const currentRecordIndex = currentDetail
    ? records.findIndex((r) => r.publication.record_id === currentDetail.publication.record_id)
    : -1;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <h2 style={{ fontSize: '1.3rem', fontWeight: 800, color: 'var(--text-primary)' }}>
            6. Ocena Jakości i Ryzyka Błędu Systematycznego (Quality Assessment)
          </h2>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
            Metodologiczna ocena publikacji zakwalifikowanych w etapie Full-Text wg szablonów kryteriów.
          </p>
        </div>

        {/* Reviewer identity & Configuration action */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <Button
            variant="secondary"
            size="sm"
            icon={<User size={14} />}
            onClick={() => {
              if (confirmDiscard()) {
                setReviewerDraft(reviewer);
                setReviewerModal(true);
              }
            }}
          >
            Recenzent: {reviewer}
          </Button>

          <Button
            variant="secondary"
            size="sm"
            icon={<Settings size={14} />}
            onClick={() => {
              if (confirmDiscard()) {
                navigate(`/projects/${projectId}/quality-assessment/configuration`);
              }
            }}
          >
            Konfiguracja QA
          </Button>
        </div>
      </div>

      {error && <ErrorAlert message={error} />}

      {/* Progress & Overview Card */}
      {overview && (
        <Card
          title={
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Award size={18} style={{ color: 'var(--accent-primary)' }} />
                <span>Postęp Oceny Jakościowej Recenzenta</span>
              </div>

              {overview.readiness === 'ready' && (
                <Badge variant="completed">Etap Gotowy</Badge>
              )}
            </div>
          }
        >
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '16px' }}>
            <div style={{ padding: '14px', backgroundColor: 'var(--bg-primary)', borderRadius: 'var(--radius-md)' }}>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Kwalifikujące się (Full-Text INCLUDE)</span>
              <div style={{ fontSize: '1.3rem', fontWeight: 700, color: 'var(--text-primary)', marginTop: '2px' }}>
                {overview.total_eligible} publikacji
              </div>
            </div>

            <div style={{ padding: '14px', backgroundColor: 'var(--bg-primary)', borderRadius: 'var(--radius-md)' }}>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Ocenione Publikacje</span>
              <div style={{ fontSize: '1.3rem', fontWeight: 700, color: 'var(--status-success-text)', marginTop: '2px' }}>
                {overview.total_assessed}
              </div>
            </div>

            <div style={{ padding: '14px', backgroundColor: 'var(--bg-primary)', borderRadius: 'var(--radius-md)' }}>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Pozostałe do Oceny</span>
              <div style={{ fontSize: '1.3rem', fontWeight: 700, color: 'var(--accent-primary)', marginTop: '2px' }}>
                {overview.total_remaining}
              </div>
            </div>
          </div>
        </Card>
      )}

      {/* Readiness Alerts (Blocking states for missing config / no eligible records) */}
      {overview && overview.readiness !== 'ready' && (
        <QualityAssessmentReadinessAlert
          projectId={projectId}
          readiness={overview.readiness}
          onOpenConfig={() => navigate(`/projects/${projectId}/quality-assessment/configuration`)}
        />
      )}

      {/* Execution Workspace (When READY) */}
      {overview?.readiness === 'ready' && (
        <>
          {/* Status Filters Bar */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Filter size={16} style={{ color: 'var(--text-muted)' }} />
              <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary)' }}>Filtruj:</span>
              <div style={{ display: 'flex', gap: '6px' }}>
                {filterOptions.map((opt) => (
                  <Button
                    key={opt.value}
                    variant={selectedFilter === opt.value ? 'primary' : 'secondary'}
                    size="sm"
                    onClick={() => chooseFilter(opt.value)}
                  >
                    {opt.label}
                  </Button>
                ))}
              </div>
            </div>

            <Button
              variant="secondary"
              size="sm"
              icon={<RefreshCw size={14} />}
              onClick={() => void loadData(offset)}
            >
              Odśwież
            </Button>
          </div>

          {/* Main Execution View or Empty Filter State */}
          {loading && !currentDetail ? (
            <LoadingSpinner label="Ładowanie kwestionariusza oceny jakościowej..." />
          ) : currentDetail ? (
            <QualityAssessmentExecutionPanel
              projectId={projectId}
              detail={currentDetail}
              draftResponses={draftResponses}
              onResponseChange={handleResponseChange}
              onJustificationChange={handleJustificationChange}
              onSave={handleSaveAssessment}
              saving={saving}
              dirty={isDirty}
              hasPreviousPage={currentRecordIndex > 0}
              hasNextPage={currentRecordIndex < records.length - 1}
              onPrevious={() => void navigateToRecordIndex(currentRecordIndex - 1)}
              onNext={() => void navigateToRecordIndex(currentRecordIndex + 1)}
              recordIndex={currentRecordIndex}
              totalRecords={total}
            />
          ) : (
            <Card title="Brak publikacji w wybranym filtrze">
              <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                Nie znaleziono żadnych publikacji odpowiadających kryteriom filtra <strong>{selectedFilter}</strong>.
              </p>
            </Card>
          )}
        </>
      )}

      {/* Reviewer Modal when changing reviewer */}
      <Modal isOpen={reviewerModal} onClose={() => setReviewerModal(false)} title="Zmień Reviewera">
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
            Wprowadź nowy identyfikator reviewera. Odświeży to postęp i listę ocen dopasowaną do nowej tożsamości.
          </p>

          {error && <ErrorAlert message={error} />}

          <label style={screeningLabelStyle}>
            Identyfikator recenzenta
            <input
              aria-label="Reviewer identifier"
              value={reviewerDraft}
              onChange={(e) => setReviewerDraft(e.target.value)}
              style={screeningControlStyle}
              autoFocus
            />
          </label>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
            <Button variant="secondary" onClick={() => setReviewerModal(false)}>
              Anuluj
            </Button>
            <Button variant="primary" onClick={submitReviewer}>
              Zapisz i Przełącz
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
};
