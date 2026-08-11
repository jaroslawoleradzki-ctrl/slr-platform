import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Button } from '../components/common/Button';
import { Card } from '../components/common/Card';
import { EmptyState } from '../components/common/EmptyState';
import { ErrorAlert } from '../components/common/ErrorAlert';
import { LoadingSpinner } from '../components/common/LoadingSpinner';
import { useReviewerIdentity } from '../hooks/useReviewerIdentity';
import {
  ApiError,
  ConflictResolution,
  ScreeningConflict,
  ScreeningOutcome,
  screeningApi,
} from '../services/api/screeningApi';

type Stage = 'title_abstract' | 'full_text';

const statusLabel: Record<ScreeningConflict['status'], string> = {
  incomplete: 'INCOMPLETE',
  agreement: 'AGREEMENT',
  conflict: 'CONFLICT',
  resolved: 'RESOLVED',
  stale_resolution: 'STALE',
};

export const ConflictResolutionPage: React.FC = () => {
  const { projectId = '' } = useParams<{ projectId: string }>();
  const { reviewerId } = useReviewerIdentity();
  const requestVersion = useRef(0);
  const [stage, setStage] = useState<Stage>('title_abstract');
  const [items, setItems] = useState<ScreeningConflict[]>([]);
  const [selected, setSelected] = useState<ScreeningConflict | null>(null);
  const [history, setHistory] = useState<ConflictResolution[]>([]);
  const [resolver, setResolver] = useState(reviewerId);
  const [outcome, setOutcome] = useState<ScreeningOutcome>('include');
  const [rationale, setRationale] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [concurrencyWarning, setConcurrencyWarning] = useState(false);

  const load = useCallback(async () => {
    const version = ++requestVersion.current;
    setLoading(true);
    setError(null);
    setSuccess(null);
    setItems([]);
    setSelected(null);
    setHistory([]);
    try {
      const result = await screeningApi.getConflicts(projectId, stage, null, 0, 100, reviewerId, true);
      if (version !== requestVersion.current) return;
      const next = result.items.find((item) =>
        item.status === 'conflict' || item.status === 'stale_resolution') ?? result.items[0] ?? null;
      setItems(result.items);
      setSelected(next);
      if (next) {
        const historyResult = await screeningApi.getConflictResolutionHistory(
          projectId, next.publication_id, stage,
        );
        if (version === requestVersion.current) setHistory(historyResult.resolutions);
      }
    } catch (caught) {
      if (version === requestVersion.current) {
        setError(caught instanceof Error ? caught.message : 'Nie udało się pobrać konfliktów.');
      }
    } finally {
      if (version === requestVersion.current) setLoading(false);
    }
  }, [projectId, reviewerId, stage]);

  useEffect(() => setResolver(reviewerId), [reviewerId]);
  useEffect(() => {
    setConcurrencyWarning(false);
    void load();
    return () => { requestVersion.current += 1; };
  }, [load]);

  const choose = async (item: ScreeningConflict) => {
    setSelected(item);
    setHistory([]);
    setConcurrencyWarning(false);
    setError(null);
    setSuccess(null);
    try {
      const result = await screeningApi.getConflictResolutionHistory(projectId, item.publication_id, stage);
      setHistory(result.resolutions);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Nie udało się pobrać historii resolution.');
    }
  };

  const save = async () => {
    if (!selected?.current_decision_set_key) return;
    setSaving(true);
    setError(null);
    setConcurrencyWarning(false);
    try {
      await screeningApi.saveConflictResolution(projectId, {
        publication_id: selected.publication_id,
        stage,
        resolved_outcome: outcome,
        resolver_id: resolver,
        rationale,
        expected_decision_set_key: selected.current_decision_set_key,
      });
      setRationale('');
      await load();
      setSuccess('Resolution saved.');
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 409 && caught.code === 'decision_set_changed') {
        setConcurrencyWarning(true);
      } else {
        setError(caught instanceof Error ? caught.message : 'Nie udało się zapisać resolution.');
      }
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <LoadingSpinner label="Ładowanie workspace adjudication..." />;
  if (error && !selected) return <ErrorAlert message={error} onRetry={() => void load()} />;

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'minmax(220px, 1fr) minmax(360px, 2fr)', gap: 16 }}>
      <Card title="Conflict Resolution">
        <label>Etap <select aria-label="Etap" value={stage} onChange={(event) => setStage(event.target.value as Stage)}>
          <option value="title_abstract">Title &amp; Abstract</option>
          <option value="full_text">Full Text</option>
        </select></label>
        {items.length ? items.map((item) => (
          <button type="button" key={item.publication_id} onClick={() => void choose(item)}
            style={{ display: 'block', width: '100%', textAlign: 'left', marginTop: 8 }}>
            <strong>{item.publication_title || item.publication_id}</strong><br />
            <span>{statusLabel[item.status]}</span>
          </button>
        )) : <EmptyState title="Brak konfliktów" description="Brak rekordów w kolejce adjudication." />}
      </Card>

      <Card title="Adjudication detail">
        {selected ? <>
          <h3>{selected.publication_title || selected.publication_id}</h3>
          <p>Stage: {selected.stage} · State: {statusLabel[selected.status]}</p>
          {selected.latest_decisions.map((latest) => {
            const decision = latest.decision;
            const reasonNames = decision?.criterion_assessments
              .filter((assessment) => decision.exclusion_reason_criterion_ids?.includes(assessment.criterion_id))
              .map((assessment) => assessment.criterion_name) ?? [];
            return <section key={latest.decision_id} aria-label={`Decision ${latest.reviewer_id}`}>
              <strong>{latest.reviewer_id}: {latest.outcome}</strong>
              {' · '}{new Date(latest.decided_at).toLocaleString()}
              <p>Rationale: {decision?.rationale || '—'}</p>
              <p>Assessments: {decision?.criterion_assessments.map((assessment) =>
                `${assessment.criterion_name}: ${assessment.assessment_value}`).join(', ') || '—'}</p>
              {reasonNames.length ? <p>Exclusion reasons: {reasonNames.join(', ')}</p> : null}
            </section>;
          })}
          <label>Outcome <select aria-label="Outcome" value={outcome}
            onChange={(event) => setOutcome(event.target.value as ScreeningOutcome)}>
            <option value="include">Include</option>
            <option value="exclude">Exclude</option>
            <option value="uncertain">Uncertain</option>
          </select></label>
          <label>Resolver <input aria-label="Resolver" value={resolver}
            onChange={(event) => setResolver(event.target.value)} /></label>
          <label>Rationale <textarea aria-label="Resolution rationale" required value={rationale}
            onChange={(event) => setRationale(event.target.value)} /></label>
          <Button onClick={() => void save()} isLoading={saving}
            disabled={!['conflict', 'stale_resolution'].includes(selected.status)
              || !resolver.trim() || !rationale.trim()}>
            Save Resolution
          </Button>
          {success && <p role="status">{success}</p>}
          {concurrencyWarning && <ErrorAlert
            message="Reviewer decisions changed. Reload the conflict before saving; your draft is preserved."
            onRetry={() => void load()}
          />}
          <h4>Resolution history</h4>
          {history.length ? history.map((item) => <p key={item.resolution_id}>
            {item.resolved_outcome} by {item.resolver_id} — {item.is_current ? 'current' : 'stale'}<br />
            {item.rationale}
          </p>) : <p>No resolution history.</p>}
        </> : <EmptyState title="Brak szczegółów" description="Wybierz konflikt z kolejki." />}
        {error && selected && <ErrorAlert message={error} onRetry={() => void load()} />}
      </Card>
    </div>
  );
};
