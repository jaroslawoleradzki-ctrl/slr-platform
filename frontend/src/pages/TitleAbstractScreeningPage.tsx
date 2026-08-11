import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { Button } from '../components/common/Button';
import { Card } from '../components/common/Card';
import { EmptyState } from '../components/common/EmptyState';
import { ErrorAlert } from '../components/common/ErrorAlert';
import { LoadingSpinner } from '../components/common/LoadingSpinner';
import { Modal } from '../components/common/Modal';
import { ScreeningCriteriaPanel, AssessmentDraft } from '../components/screening/ScreeningCriteriaPanel';
import { ScreeningDecisionPanel } from '../components/screening/ScreeningDecisionPanel';
import { ScreeningPublicationCard } from '../components/screening/ScreeningPublicationCard';
import { screeningControlStyle, screeningLabelStyle } from '../components/screening/screeningFormStyles';
import {
  ApiError, AssessmentValue, ScreeningOutcome, TitleAbstractOverview, TitleAbstractRecord,
  TitleAbstractStatus, screeningApi,
} from '../services/api/screeningApi';
import { useReviewerIdentity } from '../hooks/useReviewerIdentity';

const PAGE_SIZE = 50;
const filters: Array<{ value: TitleAbstractStatus | null; label: string }> = [
  { value: 'unscreened', label: 'Nieocenione' }, { value: null, label: 'Wszystkie' },
  { value: 'included', label: 'Włączone' }, { value: 'excluded', label: 'Wykluczone' }, { value: 'uncertain', label: 'Niepewne' },
];

const outcomeStatus: Record<ScreeningOutcome, TitleAbstractStatus> = {
  include: 'included', exclude: 'excluded', uncertain: 'uncertain',
};

const draftsFor = (record: TitleAbstractRecord | null): { outcome: ScreeningOutcome | null; rationale: string; assessments: Record<string, AssessmentDraft> } => ({
  outcome: record?.latest_decision?.outcome || null,
  rationale: record?.latest_decision?.rationale || '',
  assessments: Object.fromEntries((record?.latest_decision?.criterion_assessments || []).map((item) => [
    item.criterion_id, { value: item.assessment_value, notes: item.notes || '' },
  ])),
});

export const TitleAbstractScreeningPage: React.FC = () => {
  const { projectId = '', publicationId } = useParams<{ projectId: string; publicationId?: string }>();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const requestedStatus = searchParams.get('status');
  const selectedFilter: TitleAbstractStatus | null = requestedStatus === 'all'
    ? null
    : (['unscreened', 'included', 'excluded', 'uncertain'].includes(requestedStatus || '')
      ? requestedStatus as TitleAbstractStatus
      : 'unscreened');
  const { reviewerId: reviewer, setReviewerId: setReviewer } = useReviewerIdentity();
  const [reviewerDraft, setReviewerDraft] = useState(reviewer);
  const [reviewerModal, setReviewerModal] = useState(!reviewer);
  const [overview, setOverview] = useState<TitleAbstractOverview | null>(null);
  const [records, setRecords] = useState<TitleAbstractRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [record, setRecord] = useState<TitleAbstractRecord | null>(null);
  const [outcome, setOutcome] = useState<ScreeningOutcome | null>(null);
  const [rationale, setRationale] = useState('');
  const [assessments, setAssessments] = useState<Record<string, AssessmentDraft>>({});
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const requestVersion = useRef(0);
  const baseline = useRef('');

  const dirty = JSON.stringify({ outcome, rationale, assessments }) !== baseline.current;
  const setDraft = useCallback((next: TitleAbstractRecord | null) => {
    const draft = draftsFor(next);
    setOutcome(draft.outcome); setRationale(draft.rationale); setAssessments(draft.assessments);
    baseline.current = JSON.stringify(draft);
  }, []);
  const pathFor = useCallback((id?: string) => `/projects/${projectId}/screen/title-abstract${id ? `/${id}` : ''}`, [projectId]);
  const filterQuery = selectedFilter ? `?status=${selectedFilter}` : '?status=all';

  const load = useCallback(async (targetOffset = offset, preferredId?: string) => {
    if (!reviewer || !projectId) return;
    const version = ++requestVersion.current;
    setLoading(true); setError(null);
    try {
      const nextOverview = await screeningApi.getOverview(projectId, reviewer);
      if (version !== requestVersion.current) return;
      setOverview(nextOverview);
      if (!nextOverview.ready) { setRecords([]); setRecord(null); return; }
      const page = await screeningApi.listRecords(projectId, reviewer, selectedFilter, targetOffset, PAGE_SIZE);
      if (version !== requestVersion.current) return;
      setRecords(page.items); setTotal(page.total); setOffset(targetOffset);
      let next = page.items.find((item) => item.publication_id === preferredId) || page.items.find((item) => item.publication_id === publicationId) || page.items[0] || null;
      if (publicationId && !next) next = await screeningApi.getRecord(projectId, publicationId, reviewer);
      if (version !== requestVersion.current) return;
      setRecord(next); setDraft(next);
      if (next && next.publication_id !== publicationId) navigate(pathFor(next.publication_id) + filterQuery, { replace: true });
    } catch (caught) {
      if (version !== requestVersion.current) return;
      const apiError = caught as ApiError;
      if (apiError.status === 409) {
        try { setOverview(await screeningApi.getOverview(projectId, reviewer)); } catch { /* retain typed error */ }
      }
      setError(apiError.message);
    } finally { if (version === requestVersion.current) setLoading(false); }
  }, [filterQuery, offset, pathFor, projectId, publicationId, reviewer, selectedFilter, setDraft, navigate]);

  useEffect(() => { void load(0); }, [projectId, reviewer, selectedFilter]); // eslint-disable-line react-hooks/exhaustive-deps

  const confirmDiscard = () => !dirty || window.confirm('Masz niezapisane zmiany. Czy chcesz je odrzucić?');
  const changeReviewer = () => { if (confirmDiscard()) { setReviewerDraft(reviewer); setReviewerModal(true); } };
  const submitReviewer = () => {
    const value = reviewerDraft.trim();
    if (!value) { setError('Identyfikator reviewera nie może być pusty.'); return; }
    setReviewer(value); setReviewerModal(false); setError(null); setRecord(null); setDraft(null);
  };
  const chooseFilter = (value: TitleAbstractStatus | null) => {
    if (!confirmDiscard()) return;
    setOffset(0); navigate(`${pathFor()}?status=${value || 'all'}`, { replace: true });
  };
  const move = async (direction: -1 | 1) => {
    if (!confirmDiscard() || !record) return;
    const index = records.findIndex((item) => item.publication_id === record.publication_id);
    const nextIndex = index + direction;
    if (nextIndex >= 0 && nextIndex < records.length) {
      const next = records[nextIndex]; setRecord(next); setDraft(next); navigate(pathFor(next.publication_id) + filterQuery); return;
    }
    const nextOffset = offset + direction * PAGE_SIZE;
    if (nextOffset >= 0 && nextOffset < total) await load(nextOffset);
  };
  const missingRequired = overview?.criteria.filter((criterion) => criterion.is_required).some((criterion) => {
    if (criterion.evaluation_mode === 'metadata_rule') {
      const automatic = record?.automatic_assessments?.find((item) => item.criterion_id === criterion.criterion_id);
      return !automatic || automatic.assessment_value === 'not_assessed';
    }
    const value = assessments[criterion.criterion_id]?.value;
    return !value || value === 'not_assessed';
  }) || false;
  const save = async (goNext: boolean) => {
    if (!record || !outcome || missingRequired || saving) return;
    setSaving(true); setError(null);
    try {
      const decision = await screeningApi.saveDecision(projectId, {
        publication_id: record.publication_id, reviewer_id: reviewer, outcome, rationale: rationale.trim() || null,
        criterion_assessments: overview?.criteria.flatMap((criterion) => {
          if (criterion.evaluation_mode === 'metadata_rule') return [];
          const draft = assessments[criterion.criterion_id];
          return draft?.value ? [{ criterion_id: criterion.criterion_id, assessment_value: draft.value as AssessmentValue, notes: draft.notes.trim() || null }] : [];
        }) || [],
      });
      const updated = { ...record, status: outcomeStatus[outcome], latest_decision: decision };
      setRecord(updated); setDraft(updated);
      const freshOverview = await screeningApi.getOverview(projectId, reviewer); setOverview(freshOverview);
      if (!goNext) return;
      // An UNSCREENED record disappears after saving. Keep the current offset: [A,B,C] -> [B,C].
      const nextOffset = offset;
      const page = await screeningApi.listRecords(projectId, reviewer, selectedFilter, nextOffset, PAGE_SIZE);
      setRecords(page.items); setTotal(page.total); setOffset(nextOffset);
      let next: TitleAbstractRecord | null = null;
      if (selectedFilter === 'unscreened') next = page.items[0] || null;
      else {
        const oldIndex = page.items.findIndex((item) => item.publication_id === record.publication_id);
        next = oldIndex >= 0 ? page.items[oldIndex + 1] || null : page.items[0] || null;
      }
      if (next) { setRecord(next); setDraft(next); navigate(pathFor(next.publication_id) + filterQuery); }
    } catch (caught) {
      const apiError = caught as ApiError;
      setError(apiError.status === 404
        ? 'Ta publikacja nie należy już do aktualnego Screening Input Set.'
        : apiError.message);
      if (apiError.status === 409) void load(offset, record.publication_id);
    }
    finally { setSaving(false); }
  };

  if (!reviewer) return <Modal isOpen={reviewerModal} onClose={() => undefined} title="Reviewer">
    <p>Podaj lokalny identyfikator reviewera. Nie jest to konto ani login.</p>
    {error && <ErrorAlert message={error} />}
    <label style={screeningLabelStyle}>Identyfikator reviewera<input aria-label="Reviewer identifier" value={reviewerDraft} onChange={(event) => setReviewerDraft(event.target.value)} style={screeningControlStyle} autoFocus /></label>
    <div style={{ marginTop: '12px' }}><Button onClick={submitReviewer}>Rozpocznij screening</Button></div>
  </Modal>;
  if (loading && !overview) return <LoadingSpinner label="Ładowanie screeningu tytułów i abstraktów..." />;
  if (error && !overview) return <ErrorAlert message={error} onRetry={() => void load(0)} />;
  if (!overview) return null;
  if (!overview.ready) {
    const unresolved = overview.readiness_status === 'unresolved_duplicates';
    return <Card title="Screening nie może się rozpocząć"><p>{unresolved ? 'Pozostały nierozstrzygnięte duplikaty.' : 'Wystąpił konflikt metadanych podczas tworzenia canonical screening input set.'}</p>
      {unresolved && <p>Grupy do rozstrzygnięcia: {overview.unresolved_duplicate_groups}</p>}
      <Button onClick={() => navigate(`/projects/${projectId}/dedup`)}>Przejdź do Deduplication</Button>{' '}
      <Button variant="outline" onClick={() => void load(0)}>Sprawdź ponownie</Button></Card>;
  }
  const progress = overview.progress;
  if (!record) return <>{error && <ErrorAlert message={error} onRetry={() => void load(offset)} />}<EmptyState title={total === 0 ? 'Brak publikacji do screeningu' : 'Brak rekordów spełniających filtr'} description={total === 0 ? 'Canonical Screening Input Set jest pusty.' : 'Zmień filtr, aby zobaczyć inne rekordy.'} action={total > 0 ? <Button onClick={() => chooseFilter(null)}>Pokaż wszystkie</Button> : undefined} /></>;
  const currentIndex = records.findIndex((item) => item.publication_id === record.publication_id);
  return <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
    <Card><div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', flexWrap: 'wrap' }}>
      <div><strong>{progress?.completed || 0} / {progress?.total || 0} ocenionych</strong><div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Włączone: {progress?.included || 0} · Wykluczone: {progress?.excluded || 0} · Niepewne: {progress?.uncertain || 0} · Pozostałe: {progress?.unscreened || 0}</div></div>
      <div>Reviewer: <strong>{reviewer}</strong> <Button size="sm" variant="outline" onClick={changeReviewer}>Zmień</Button></div>
    </div><div aria-label="Screening filters" style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginTop: '12px' }}>{filters.map((filter) => <Button key={filter.label} size="sm" variant={selectedFilter === filter.value ? 'primary' : 'outline'} onClick={() => chooseFilter(filter.value)}>{filter.label}</Button>)}</div></Card>
    {error && <ErrorAlert message={error} onRetry={() => void load(offset, record.publication_id)} />}
    <div className="title-abstract-screening-workspace" style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1.4fr) minmax(320px, 1fr)', gap: '16px' }}>
      <ScreeningPublicationCard record={record} />
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        <ScreeningCriteriaPanel criteria={overview.criteria} assessments={assessments} automaticAssessments={record.automatic_assessments || []} disabled={saving} onChange={(id, draft) => setAssessments((current) => ({ ...current, [id]: draft }))} />
        <ScreeningDecisionPanel outcome={outcome} rationale={rationale} latestDecision={record.latest_decision} onOutcome={setOutcome} onRationale={setRationale} onSave={save} saving={saving} canSave={Boolean(outcome) && !missingRequired} />
      </div>
    </div>
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '12px' }}><Button variant="outline" disabled={offset === 0 && currentIndex <= 0 || saving} onClick={() => void move(-1)}>Poprzedni</Button><span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Rekord {offset + Math.max(currentIndex, 0) + 1} z {total}</span><Button variant="outline" disabled={(currentIndex === records.length - 1 && offset + records.length >= total) || saving} onClick={() => void move(1)}>Następny</Button></div>
    {reviewerModal && <Modal isOpen onClose={() => setReviewerModal(false)} title="Zmień reviewera"><label style={screeningLabelStyle}>Identyfikator reviewera<input aria-label="Reviewer identifier" value={reviewerDraft} onChange={(event) => setReviewerDraft(event.target.value)} style={screeningControlStyle} /></label><div style={{ marginTop: '12px' }}><Button onClick={submitReviewer}>Zapisz identyfikator</Button></div></Modal>}
    <style>{`@media (max-width: 860px) { .title-abstract-screening-workspace { grid-template-columns: 1fr !important; } }`}</style>
  </div>;
};
