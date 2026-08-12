import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { Button } from '../components/common/Button';
import { Card } from '../components/common/Card';
import { EmptyState } from '../components/common/EmptyState';
import { ErrorAlert } from '../components/common/ErrorAlert';
import { LoadingSpinner } from '../components/common/LoadingSpinner';
import { Modal } from '../components/common/Modal';
import { AssessmentDraft, ScreeningCriteriaPanel } from '../components/screening/ScreeningCriteriaPanel';
import { ScreeningPublicationCard } from '../components/screening/ScreeningPublicationCard';
import { screeningControlStyle, screeningLabelStyle } from '../components/screening/screeningFormStyles';
import {
  ApiError, AssessmentValue, FullTextAvailabilityStatus, FullTextOverview, FullTextRecord,
  FullTextStatus, ScreeningDecision, ScreeningOutcome, screeningApi,
} from '../services/api/screeningApi';
import { useReviewerIdentity } from '../hooks/useReviewerIdentity';

const PAGE_SIZE = 50;
const filters: Array<{ value: FullTextStatus | null; label: string }> = [
  { value: 'unscreened', label: 'Nieocenione' }, { value: null, label: 'Wszystkie' },
  { value: 'included', label: 'Włączone' }, { value: 'excluded', label: 'Wykluczone' }, { value: 'uncertain', label: 'Niepewne' },
];
const outcomeLabels: Record<ScreeningOutcome, string> = { include: 'Włącz', exclude: 'Wyklucz', uncertain: 'Niepewne' };
const outcomeStatus: Record<ScreeningOutcome, FullTextStatus> = { include: 'included', exclude: 'excluded', uncertain: 'uncertain' };

const draftsFor = (record: FullTextRecord | null) => ({
  outcome: record?.latest_decision?.outcome || null,
  rationale: record?.latest_decision?.rationale || '',
  assessments: Object.fromEntries((record?.latest_decision?.criterion_assessments || []).map((item) => [item.criterion_id, { value: item.assessment_value, notes: item.notes || '' }])),
  reasons: record?.latest_decision?.exclusion_reason_criterion_ids || [],
});

export const FullTextScreeningPage: React.FC = () => {
  const { projectId = '', publicationId } = useParams<{ projectId: string; publicationId?: string }>();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const requested = params.get('status');
  const filter: FullTextStatus | null = requested === 'all' ? null : (['unscreened', 'included', 'excluded', 'uncertain'].includes(requested || '') ? requested as FullTextStatus : 'unscreened');
  const { reviewerId: reviewer, setReviewerId: setReviewer } = useReviewerIdentity();
  const [reviewerDraft, setReviewerDraft] = useState(reviewer);
  const [reviewerModal, setReviewerModal] = useState(!reviewer);
  const [overview, setOverview] = useState<FullTextOverview | null>(null);
  const [records, setRecords] = useState<FullTextRecord[]>([]);
  const [record, setRecord] = useState<FullTextRecord | null>(null);
  const [total, setTotal] = useState(0); const [offset, setOffset] = useState(0);
  const [outcome, setOutcome] = useState<ScreeningOutcome | null>(null);
  const [rationale, setRationale] = useState('');
  const [assessments, setAssessments] = useState<Record<string, AssessmentDraft>>({});
  const [reasons, setReasons] = useState<string[]>([]);
  const [availabilityStatus, setAvailabilityStatus] = useState<FullTextAvailabilityStatus>('unknown');
  const [externalUrl, setExternalUrl] = useState(''); const [availabilityNotes, setAvailabilityNotes] = useState('');
  const [history, setHistory] = useState<Array<ScreeningDecision & { exclusion_reason_criterion_ids: string[] }>>([]);
  const [loading, setLoading] = useState(false); const [saving, setSaving] = useState(false); const [error, setError] = useState<string | null>(null);
  const requestVersion = useRef(0); const baseline = useRef('');
  const pathFor = useCallback((id?: string) => `/projects/${projectId}/screen/full-text${id ? `/${id}` : ''}`, [projectId]);
  const query = filter ? `?status=${filter}` : '?status=all';
  const dirty = JSON.stringify({ outcome, rationale, assessments, reasons, availabilityStatus, externalUrl, availabilityNotes }) !== baseline.current;
  const setDraft = useCallback((next: FullTextRecord | null) => {
    const draft = draftsFor(next); setOutcome(draft.outcome); setRationale(draft.rationale); setAssessments(draft.assessments); setReasons(draft.reasons);
    setAvailabilityStatus(next?.availability.status || 'unknown'); setExternalUrl(next?.availability.external_url || ''); setAvailabilityNotes(next?.availability.notes || '');
    baseline.current = JSON.stringify({ ...draft, availabilityStatus: next?.availability.status || 'unknown', externalUrl: next?.availability.external_url || '', availabilityNotes: next?.availability.notes || '' });
  }, []);
  const load = useCallback(async (targetOffset = offset, preferred?: string) => {
    if (!reviewer || !projectId) return; const version = ++requestVersion.current; setLoading(true); setError(null);
    try {
      const nextOverview = await screeningApi.getFullTextOverview(projectId, reviewer); if (version !== requestVersion.current) return; setOverview(nextOverview);
      if (!nextOverview.ready) { setRecords([]); setRecord(null); return; }
      const page = await screeningApi.listFullTextRecords(projectId, reviewer, filter, targetOffset, PAGE_SIZE); if (version !== requestVersion.current) return;
      setRecords(page.items); setTotal(page.total); setOffset(targetOffset);
      let selected = page.items.find((item) => item.publication_id === preferred) || page.items.find((item) => item.publication_id === publicationId) || page.items[0] || null;
      if (publicationId && !selected) selected = await screeningApi.getFullTextRecord(projectId, publicationId, reviewer);
      if (version !== requestVersion.current) return; setRecord(selected); setDraft(selected);
      if (selected) { const loadedHistory = await screeningApi.listDecisionHistory(projectId, selected.publication_id, reviewer); if (version === requestVersion.current) setHistory(loadedHistory.items.map((item) => ({ ...item, exclusion_reason_criterion_ids: item.exclusion_reason_criterion_ids || [] }))); }
      if (selected && selected.publication_id !== publicationId) navigate(pathFor(selected.publication_id) + query, { replace: true });
    } catch (caught) { if (version === requestVersion.current) setError((caught as ApiError).message); }
    finally { if (version === requestVersion.current) setLoading(false); }
  }, [filter, navigate, offset, pathFor, projectId, publicationId, query, reviewer, setDraft]);
  useEffect(() => { void load(0); }, [projectId, reviewer, filter]); // eslint-disable-line react-hooks/exhaustive-deps
  const confirmDiscard = () => !dirty || window.confirm('Masz niezapisane zmiany. Czy chcesz je odrzucić?');
  const saveReviewer = () => { const value = reviewerDraft.trim(); if (!value) { setError('Identyfikator reviewera nie może być pusty.'); return; } setReviewer(value); setReviewerModal(false); setRecord(null); };
  const chooseFilter = (value: FullTextStatus | null) => { if (confirmDiscard()) { setOffset(0); navigate(`${pathFor()}?status=${value || 'all'}`, { replace: true }); } };
  const move = async (direction: -1 | 1) => { if (!confirmDiscard() || !record) return; const index = records.findIndex((item) => item.publication_id === record.publication_id); const target = index + direction; if (target >= 0 && target < records.length) { const next = records[target]; setRecord(next); setDraft(next); navigate(pathFor(next.publication_id) + query); return; } const nextOffset = offset + direction * PAGE_SIZE; if (nextOffset >= 0 && nextOffset < total) await load(nextOffset); };
  const requiredMissing = overview?.criteria.filter((criterion) => criterion.is_required).some((criterion) => criterion.evaluation_mode === 'metadata_rule' ? record?.automatic_assessments?.find((item) => item.criterion_id === criterion.criterion_id)?.assessment_value === 'not_assessed' : !assessments[criterion.criterion_id]?.value || assessments[criterion.criterion_id]?.value === 'not_assessed') || false;
  const validReasonIds = overview?.criteria.filter((criterion) => {
    const value = criterion.evaluation_mode === 'metadata_rule' ? record?.automatic_assessments?.find((item) => item.criterion_id === criterion.criterion_id)?.assessment_value : assessments[criterion.criterion_id]?.value;
    return criterion.criterion_type === 'inclusion' ? value === 'not_met' : value === 'met';
  }).map((criterion) => criterion.criterion_id) || [];
  const canSave = Boolean(outcome) && !requiredMissing && (outcome !== 'exclude' || reasons.length > 0);
  const saveAvailability = async () => { if (!record || saving) return; setSaving(true); setError(null); try { await screeningApi.saveFullTextAvailability(projectId, record.publication_id, { reviewer_id: reviewer, status: availabilityStatus, external_url: externalUrl.trim() || null, notes: availabilityNotes.trim() || null }); await load(offset, record.publication_id); } catch (caught) { setError((caught as ApiError).message); } finally { setSaving(false); } };
  const save = async (goNext: boolean) => { if (!record || !outcome || !canSave || saving) return; setSaving(true); setError(null); try {
    const decision = await screeningApi.saveFullTextDecision(projectId, { publication_id: record.publication_id, reviewer_id: reviewer, outcome, rationale: rationale.trim() || null, exclusion_reason_criterion_ids: outcome === 'exclude' ? reasons : [], criterion_assessments: overview?.criteria.flatMap((criterion) => criterion.evaluation_mode === 'metadata_rule' ? [] : assessments[criterion.criterion_id]?.value ? [{ criterion_id: criterion.criterion_id, assessment_value: assessments[criterion.criterion_id].value as AssessmentValue, notes: assessments[criterion.criterion_id].notes.trim() || null }] : []) || [] });
    const updated = { ...record, status: outcomeStatus[outcome], latest_decision: decision }; setRecord(updated); setDraft(updated); setHistory((current) => [{ ...decision, exclusion_reason_criterion_ids: decision.exclusion_reason_criterion_ids || [] }, ...current]); setOverview(await screeningApi.getFullTextOverview(projectId, reviewer));
    if (goNext) { const page = await screeningApi.listFullTextRecords(projectId, reviewer, filter, offset, PAGE_SIZE); setRecords(page.items); setTotal(page.total); const index = page.items.findIndex((item) => item.publication_id === record.publication_id); const next = index >= 0 ? page.items[index + 1] || page.items[index - 1] || null : page.items[0] || null; if (next) { setRecord(next); setDraft(next); navigate(pathFor(next.publication_id) + query); } }
  } catch (caught) { const value = caught as ApiError; setError(value.status === 404 ? 'Publikacja nie jest już eligible do Full Text Screening.' : value.message); if (value.status === 409) void load(offset); } finally { setSaving(false); } };
  if (!reviewer) return <Modal isOpen={reviewerModal} onClose={() => undefined} title="Reviewer"><p>Podaj lokalny identyfikator reviewera. Nie jest to konto ani login.</p>{error && <ErrorAlert message={error} />}<label style={screeningLabelStyle}>Identyfikator reviewera<input aria-label="Reviewer identifier" value={reviewerDraft} onChange={(event) => setReviewerDraft(event.target.value)} style={screeningControlStyle} autoFocus /></label><div style={{ marginTop: 12 }}><Button onClick={saveReviewer}>Rozpocznij screening</Button></div></Modal>;
  if (loading && !overview) return <LoadingSpinner label="Ładowanie Full Text Screening..." />;
  if (error && !overview) return <ErrorAlert message={error} onRetry={() => void load(0)} />;
  if (!overview) return null;
  if (!overview.ready) { const duplicate = overview.readiness_status === 'unresolved_duplicates'; const waiting = overview.readiness_status === 'waiting_for_title_abstract'; return <Card title="Full Text Screening nie jest jeszcze dostępny"><p>{duplicate ? 'Pozostały nierozstrzygnięte duplikaty.' : waiting ? 'Ten reviewer nie ma jeszcze publikacji włączonych po Title & Abstract Screening.' : overview.readiness_status === 'merge_conflict' ? 'Wystąpił konflikt podczas tworzenia canonical screening input set.' : 'Brak aktualnie eligible publikacji do Full Text Screening.'}</p>{duplicate && <Button onClick={() => navigate(`/projects/${projectId}/dedup`)}>Przejdź do Deduplication</Button>} <Button variant="outline" onClick={() => void load(0)}>Sprawdź ponownie</Button></Card>; }
  const progress = overview.progress; if (!record) return <EmptyState title={total ? 'Brak rekordów spełniających filtr' : 'Brak publikacji do Full Text Screening'} description={total ? 'Zmień filtr, aby zobaczyć inne rekordy.' : 'Włącz publikacje w Title & Abstract Screening dla tego reviewera.'} />;
  const index = records.findIndex((item) => item.publication_id === record.publication_id);
  return <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}><Card><div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}><div><strong>{progress?.completed || 0} / {progress?.total || 0} ocenionych</strong><div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Włączone: {progress?.included || 0} · Wykluczone: {progress?.excluded || 0} · Niepewne: {progress?.uncertain || 0} · Pozostałe: {progress?.unscreened || 0}</div></div><div>Reviewer: <strong>{reviewer}</strong> <Button size="sm" variant="outline" onClick={() => { if (confirmDiscard()) { setReviewerDraft(reviewer); setReviewerModal(true); } }}>Zmień</Button></div></div><div aria-label="Screening filters" style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 12 }}>{filters.map((item) => <Button key={item.label} size="sm" variant={filter === item.value ? 'primary' : 'outline'} onClick={() => chooseFilter(item.value)}>{item.label}</Button>)}</div></Card>{error && <ErrorAlert message={error} onRetry={() => void load(offset, record.publication_id)} />}<div className="full-text-workspace" style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1.4fr) minmax(320px, 1fr)', gap: 16 }}><div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}><ScreeningPublicationCard record={record} /><Card title="Dostępność pełnego tekstu" subtitle="Metadane workflow — nie ustalają automatycznie decyzji."><label style={screeningLabelStyle}>Status<select aria-label="Full text availability" value={availabilityStatus} disabled={saving} onChange={(event) => setAvailabilityStatus(event.target.value as FullTextAvailabilityStatus)} style={screeningControlStyle}><option value="unknown">Nieznany</option><option value="to_retrieve">Do pozyskania</option><option value="available">Dostępny</option><option value="unavailable">Niedostępny</option></select></label><label style={screeningLabelStyle}>Zewnętrzny link<input value={externalUrl} onChange={(event) => setExternalUrl(event.target.value)} placeholder={record.doi ? `https://doi.org/${record.doi}` : 'https://...'} style={screeningControlStyle} /></label><textarea aria-label="Full text availability notes" value={availabilityNotes} onChange={(event) => setAvailabilityNotes(event.target.value)} placeholder="Notatka o dostępności (opcjonalnie)" rows={2} style={{ ...screeningControlStyle, marginTop: 8 }} /><Button variant="outline" disabled={saving} onClick={() => void saveAvailability()}>Zapisz dostępność</Button>{record.availability.external_url && <p><a href={record.availability.external_url} target="_blank" rel="noreferrer">Otwórz wskazany pełny tekst</a></p>}</Card><Card title="Historia Full Text"><details><summary>Historia decyzji ({history.length})</summary><ul style={{ paddingLeft: 18 }}>{history.map((item) => <li key={item.decision_id}>{new Date(item.decided_at).toLocaleString()} · {outcomeLabels[item.outcome]}{item.rationale ? ` — ${item.rationale}` : ''}{item.exclusion_reason_criterion_ids.length ? ` · Powody: ${item.exclusion_reason_criterion_ids.length}` : ''}</li>)}</ul></details></Card></div><div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}><ScreeningCriteriaPanel criteria={overview.criteria} assessments={assessments} automaticAssessments={record.automatic_assessments || []} disabled={saving} onChange={(id, draft) => setAssessments((current) => ({ ...current, [id]: draft }))} /><Card title="Decyzja końcowa"><div role="group" aria-label="Decyzja końcowa" style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>{(['include', 'exclude', 'uncertain'] as ScreeningOutcome[]).map((item) => <Button key={item} variant={outcome === item ? 'primary' : 'outline'} aria-pressed={outcome === item} disabled={saving} onClick={() => { setOutcome(item); if (item !== 'exclude') setReasons([]); }}>{outcomeLabels[item]}</Button>)}</div>{outcome === 'exclude' && <section style={{ marginTop: 12 }}><strong>Powody wykluczenia</strong><p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Wybierz co najmniej jedno spełnione kryterium wykluczające lub niespełnione kryterium włączające.</p>{validReasonIds.length === 0 ? <p>Najpierw oceń kryteria, aby wskazać uzasadniony powód.</p> : overview.criteria.filter((criterion) => validReasonIds.includes(criterion.criterion_id)).map((criterion) => <label key={criterion.criterion_id} style={{ display: 'block', margin: '6px 0' }}><input type="checkbox" checked={reasons.includes(criterion.criterion_id)} onChange={() => setReasons((current) => current.includes(criterion.criterion_id) ? current.filter((id) => id !== criterion.criterion_id) : [...current, criterion.criterion_id])} /> {criterion.name}</label>)}</section>}<textarea aria-label="Decision rationale" value={rationale} disabled={saving} onChange={(event) => setRationale(event.target.value)} placeholder="Uzasadnienie decyzji (opcjonalnie)" rows={3} style={{ ...screeningControlStyle, marginTop: 12 }} /><div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 12 }}><Button variant="outline" disabled={!canSave || saving} isLoading={saving} onClick={() => void save(false)}>Zapisz</Button><Button disabled={!canSave || saving} isLoading={saving} onClick={() => void save(true)}>Zapisz i następny</Button></div></Card></div></div><div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}><Button variant="outline" disabled={(offset === 0 && index <= 0) || saving} onClick={() => void move(-1)}>Poprzedni</Button><span>Rekord {offset + Math.max(index, 0) + 1} z {total}</span><Button variant="outline" disabled={(index === records.length - 1 && offset + records.length >= total) || saving} onClick={() => void move(1)}>Następny</Button></div>{reviewerModal && <Modal isOpen onClose={() => setReviewerModal(false)} title="Zmień reviewera"><label style={screeningLabelStyle}>Identyfikator reviewera<input aria-label="Reviewer identifier" value={reviewerDraft} onChange={(event) => setReviewerDraft(event.target.value)} style={screeningControlStyle} /></label><div style={{ marginTop: 12 }}><Button onClick={saveReviewer}>Zapisz identyfikator</Button></div></Modal>}<style>{`@media (max-width: 860px) { .full-text-workspace { grid-template-columns: 1fr !important; } }`}</style></div>;
};
