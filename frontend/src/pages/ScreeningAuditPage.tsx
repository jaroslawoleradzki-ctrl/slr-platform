import React, { useCallback, useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Button } from '../components/common/Button';
import { Card } from '../components/common/Card';
import { EmptyState } from '../components/common/EmptyState';
import { ErrorAlert } from '../components/common/ErrorAlert';
import { LoadingSpinner } from '../components/common/LoadingSpinner';
import {
  ScreeningAuditPage as AuditPage,
  ScreeningReport,
  ScreeningStageProgress,
  screeningApi,
} from '../services/api/screeningApi';
import { useReviewerIdentity } from '../hooks/useReviewerIdentity';

const PAGE_SIZE = 25;

const stageLabel: Record<string, string> = {
  title_abstract: 'Title & Abstract',
  full_text: 'Full Text',
};

const outcomeLabel: Record<string, string> = {
  include: 'Włącz',
  exclude: 'Wyklucz',
  uncertain: 'Niepewne',
};

const StageCard: React.FC<{
  label: string;
  progress: ScreeningStageProgress | null;
}> = ({ label, progress }) => (
  <Card title={label}>
    <strong>{progress?.screened ?? 0} / {progress?.total_eligible ?? 0} ocenionych</strong>
    <p>
      Włączone: {progress?.included ?? 0} · Wykluczone: {progress?.excluded ?? 0}
      {' · '}Niepewne: {progress?.uncertain ?? 0}
      {' · '}Pozostałe: {progress?.remaining ?? 0}
    </p>
  </Card>
);

export const ScreeningAuditPage: React.FC = () => {
  const { projectId = '' } = useParams<{ projectId: string }>();
  const { reviewerId: reviewer, setReviewerId: setReviewer } = useReviewerIdentity();
  const [reviewerDraft, setReviewerDraft] = useState(reviewer);
  const [editingReviewer, setEditingReviewer] = useState(!reviewer);
  const [report, setReport] = useState<ScreeningReport | null>(null);
  const [audit, setAudit] = useState<AuditPage | null>(null);
  const [offset, setOffset] = useState(0);
  const [stage, setStage] = useState<string | null>(null);
  const [outcome, setOutcome] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (nextOffset: number) => {
    if (!reviewer) return;
    setError(null);
    try {
      const [nextReport, nextAudit] = await Promise.all([
        screeningApi.getReport(projectId, reviewer),
        screeningApi.getAudit(projectId, reviewer, nextOffset, PAGE_SIZE, stage, outcome),
      ]);
      setReport(nextReport);
      setAudit(nextAudit);
      setOffset(nextOffset);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Nie udało się pobrać audytu.');
    }
  }, [outcome, projectId, reviewer, stage]);

  useEffect(() => {
    void load(0);
  }, [load]);

  const saveReviewer = () => {
    const value = reviewerDraft.trim();
    if (!value) return;
    setReviewer(value);
    setEditingReviewer(false);
    setOffset(0);
  };

  if (!reviewer || editingReviewer) {
    return (
      <Card title="Podsumowanie i historia">
        <p>Podaj identyfikator reviewera, aby zobaczyć jego postęp i historię.</p>
        <label htmlFor="audit-reviewer">Identyfikator reviewera</label>
        <input
          id="audit-reviewer"
          value={reviewerDraft}
          onChange={(event) => setReviewerDraft(event.target.value)}
        />
        <Button onClick={saveReviewer} disabled={!reviewerDraft.trim()}>Zapisz</Button>
      </Card>
    );
  }

  if (!report || !audit) {
    return error
      ? <ErrorAlert message={error} onRetry={() => void load(0)} />
      : <LoadingSpinner label="Ładowanie audytu screeningu..." />;
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <Card title="Podsumowanie i historia" subtitle={`Reviewer: ${reviewer}`}>
        <p>Canonical input: {report.canonical_records_count} · Working Collection: {report.working_collection_count}</p>
        <Button variant="outline" onClick={() => setEditingReviewer(true)}>Zmień reviewera</Button>
      </Card>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 12 }}>
        <StageCard label="Title & Abstract" progress={report.title_abstract} />
        <StageCard label="Full Text" progress={report.full_text} />
      </div>

      <Card title="Przejścia w pipeline">
        <p>
          Canonical input: {report.transitions?.canonical_input ?? 0} · po Title & Abstract:
          {' '}{report.transitions?.title_abstract_included ?? 0} · w Full Text:
          {' '}{report.transitions?.full_text_eligible ?? 0} · włączone po Full Text:
          {' '}{report.transitions?.full_text_included ?? 0}
        </p>
      </Card>

      <Card title="Zgodność multi-reviewer">
        <p>Title &amp; Abstract: {formatMultiReviewer(report.title_abstract_multi_reviewer)}</p>
        <p>Full Text: {formatMultiReviewer(report.full_text_multi_reviewer)}</p>
      </Card>

      <Card title="Powody wykluczenia Full Text">
        {report.full_text_exclusion_reasons.length ? (
          <ul>
            {report.full_text_exclusion_reasons.map((item) => (
              <li key={item.criterion_snapshot_key}>
                {item.criterion_assessment.criterion_name}: {item.count}
                {!item.snapshot_complete && ' (historyczny snapshot v1)'}
              </li>
            ))}
          </ul>
        ) : <p>Brak aktualnych powodów wykluczenia.</p>}
      </Card>

      <Card title="Historia decyzji">
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 12 }}>
          <label>Etap <select value={stage ?? ''} onChange={(event) => setStage(event.target.value || null)}>
            <option value="">Wszystkie</option>
            <option value="title_abstract">Title &amp; Abstract</option>
            <option value="full_text">Full Text</option>
          </select></label>
          <label>Wynik <select value={outcome ?? ''} onChange={(event) => setOutcome(event.target.value || null)}>
            <option value="">Wszystkie</option>
            <option value="include">Włącz</option>
            <option value="exclude">Wyklucz</option>
            <option value="uncertain">Niepewne</option>
          </select></label>
        </div>
        {audit.items.length ? <ul>{audit.items.map((item) => item.event_type === 'RESOLUTION' ? (
          <li key={item.resolution_id} style={{ marginBottom: 12 }}>
            <strong>{item.publication_title || item.publication_id}</strong>
            {' · '}{stageLabel[item.stage]} · Resolution: {outcomeLabel[item.resolved_outcome]}
            {' · '}{new Date(item.resolved_at).toLocaleString()}
            <div>Resolver: {item.resolver_id} · {item.status === 'CURRENT' ? 'current' : 'stale'}</div>
            <div>Uzasadnienie resolution: {item.rationale}</div>
            <div>Reviewer outcomes: {item.reviewer_outcomes.map((value) => `${value.reviewer_id}: ${value.outcome}`).join(', ')}</div>
          </li>
        ) : (
          <li key={item.decision.decision_id} style={{ marginBottom: 12 }}>
            <strong>{item.publication_title || item.decision.publication_id}</strong>
            {' · '}{stageLabel[item.decision.stage]} · {outcomeLabel[item.decision.outcome]}
            {' · '}{new Date(item.decision.decided_at).toLocaleString()}
            {item.previous_outcome && ` (${outcomeLabel[item.previous_outcome]} →)`}
            {item.decision.criterion_snapshot_schema_version === 1 && ' · historyczny snapshot v1'}
            {item.decision.rationale && <div>Uzasadnienie: {item.decision.rationale}</div>}
            <div>Kryteria: {item.decision.criterion_assessments.map((assessment) => `${assessment.criterion_name}: ${assessment.assessment_value}`).join(', ') || 'brak'}</div>
            {item.decision.exclusion_reason_criterion_ids?.length ? <div>Powody wykluczenia: {item.decision.exclusion_reason_criterion_ids.length}</div> : null}
          </li>
        ))}</ul> : <EmptyState title="Brak historii" description="Brak decyzji spełniających filtr." />}
        {audit.total > PAGE_SIZE && <div style={{ display: 'flex', gap: 8 }}>
          <Button variant="outline" disabled={offset === 0} onClick={() => void load(Math.max(0, offset - PAGE_SIZE))}>Poprzednia</Button>
          <Button variant="outline" disabled={offset + PAGE_SIZE >= audit.total} onClick={() => void load(offset + PAGE_SIZE)}>Następna</Button>
        </div>}
      </Card>
      {error && <ErrorAlert message={error} onRetry={() => void load(offset)} />}
    </div>
  );
};

function formatMultiReviewer(metrics: ScreeningReport['title_abstract_multi_reviewer']): string {
  if (!metrics) return 'Brak aktywnego rosteru.';
  const rate = metrics.agreement_rate === null ? 'brak danych' : `${Math.round(metrics.agreement_rate * 100)}%`;
  return `zgodne: ${metrics.agreement}, konflikty: ${metrics.conflict}, niepełne: ${metrics.incomplete}, agreement rate: ${rate}`;
}
