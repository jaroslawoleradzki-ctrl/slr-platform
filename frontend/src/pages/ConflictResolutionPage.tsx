import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Button } from '../components/common/Button';
import { Card } from '../components/common/Card';
import { EmptyState } from '../components/common/EmptyState';
import { ErrorAlert } from '../components/common/ErrorAlert';
import { LoadingSpinner } from '../components/common/LoadingSpinner';
import { useReviewerIdentity } from '../hooks/useReviewerIdentity';
import { screeningControlStyle, screeningLabelStyle } from '../components/screening/screeningFormStyles';
import {
  ApiError,
  ConflictResolution,
  ScreeningConflict,
  ScreeningOutcome,
  screeningApi,
} from '../services/api/screeningApi';

type Stage = 'title_abstract' | 'full_text';
type ConflictFilter = '' | 'incomplete' | 'agreement' | 'conflict' | 'resolved' | 'stale_resolution';

const statusLabel: Record<ScreeningConflict['status'], string> = {
  incomplete: 'Niepełne',
  agreement: 'Zgodne',
  conflict: 'Konflikt',
  resolved: 'Rozstrzygnięte',
  stale_resolution: 'Nieaktualne rozstrzygnięcie',
};

const filterLabel: Record<ConflictFilter, string> = {
  '': 'Wszystkie statusy',
  incomplete: 'Niepełne',
  agreement: 'Zgodne',
  conflict: 'Konflikty',
  resolved: 'Rozstrzygnięte',
  stale_resolution: 'Nieaktualne rozstrzygnięcia',
};

export const ConflictResolutionPage: React.FC = () => {
  const { projectId = '' } = useParams<{ projectId: string }>();
  const { reviewerId } = useReviewerIdentity();
  const requestVersion = useRef(0);
  const [stage, setStage] = useState<Stage>('title_abstract');
  const [filter, setFilter] = useState<ConflictFilter>('');
  const [reviewers, setReviewers] = useState('');
  const [metrics, setMetrics] = useState<{ incomplete: number; agreement: number; conflict: number; agreement_rate: number | null } | null>(null);
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
      const [result, nextMetrics, roster] = await Promise.all([
        screeningApi.getConflicts(projectId, stage, filter || null, 0, 100, reviewerId, true),
        screeningApi.getConflictMetrics(projectId, stage),
        screeningApi.getReviewerRoster(projectId, stage),
      ]);
      if (version !== requestVersion.current) return;
      const next = result.items.find((item) =>
        item.status === 'conflict' || item.status === 'stale_resolution') ?? result.items[0] ?? null;
      setItems(result.items);
      setMetrics(nextMetrics);
      setReviewers(roster.filter((item) => item.is_active).map((item) => item.reviewer_id).join(', '));
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
  }, [filter, projectId, reviewerId, stage]);

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
      setError(caught instanceof Error ? caught.message : 'Nie udało się pobrać historii rozstrzygnięć.');
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
      setSuccess('Rozstrzygnięcie zapisane.');
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 409 && caught.code === 'decision_set_changed') {
        setConcurrencyWarning(true);
      } else {
        setError(caught instanceof Error ? caught.message : 'Nie udało się zapisać rozstrzygnięcia.');
      }
    } finally {
      setSaving(false);
    }
  };

  const saveReviewerTeam = async () => {
    setSaving(true);
    setError(null);
    try {
      await screeningApi.saveReviewerRoster(projectId, stage, reviewers.split(',').map((value) => value.trim()).filter(Boolean));
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Nie udało się zapisać zespołu reviewerów.');
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <LoadingSpinner label="Ładowanie konfliktów i rozstrzygnięć..." />;
  if (error && !selected) return <ErrorAlert message={error} onRetry={() => void load()} />;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div>
        <h2 style={{ margin: 0 }}>Konflikty i rozstrzygnięcia</h2>
        <p style={{ color: 'var(--text-secondary)', margin: '4px 0 0' }}>Analiza rozbieżnych decyzji reviewerów i zapisanie ostatecznego rozstrzygnięcia.</p>
      </div>
      <Card title="Zespół reviewerów" subtitle="Reviewerzy przypisani do tego etapu screeningu.">
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'end' }}>
          <label style={screeningLabelStyle}>Etap<select aria-label="Etap" value={stage} onChange={(event) => setStage(event.target.value as Stage)} style={screeningControlStyle}>
          <option value="title_abstract">Title &amp; Abstract</option>
          <option value="full_text">Full Text</option>
          </select></label>
          <label style={{ ...screeningLabelStyle, flex: '1 1 280px' }}>Reviewerzy (oddzieleni przecinkiem)
            <input value={reviewers} onChange={(event) => setReviewers(event.target.value)} style={screeningControlStyle} />
          </label>
          <Button onClick={() => void saveReviewerTeam()} isLoading={saving}>Zapisz zespół reviewerów</Button>
        </div>
      </Card>
      {metrics && <Card title="Statystyki decyzji">
        <p>Niepełne: {metrics.incomplete} · Zgodne: {metrics.agreement} · Konflikty: {metrics.conflict}</p>
        <p>Agreement rate: {metrics.agreement_rate === null ? 'brak ukończonych porównań' : `${Math.round(metrics.agreement_rate * 100)}%`}</p>
      </Card>}
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(220px, 1fr) minmax(360px, 2fr)', gap: 16 }}>
      <Card title="Konflikty i rozstrzygnięcia" subtitle="Wybierz publikację, aby przejść od analizy decyzji do rozstrzygnięcia.">
        <label style={screeningLabelStyle}>Filtr statusu<select aria-label="Filtr statusu" value={filter} onChange={(event) => setFilter(event.target.value as ConflictFilter)} style={screeningControlStyle}>
          {(Object.keys(filterLabel) as ConflictFilter[]).map((value) => <option key={value} value={value}>{filterLabel[value]}</option>)}
        </select></label>
        {items.length ? items.map((item) => (
          <button type="button" key={item.publication_id} onClick={() => void choose(item)}
            style={{ display: 'block', width: '100%', textAlign: 'left', marginTop: 8, padding: 10, borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)', background: selected?.publication_id === item.publication_id ? 'var(--accent-subtle)' : 'var(--bg-surface-elevated)', color: 'var(--text-primary)' }}>
            <strong>{item.publication_title || item.publication_id}</strong><br />
            <span>{statusLabel[item.status]}</span>
          </button>
        )) : <EmptyState title="Brak konfliktów wymagających rozstrzygnięcia" description="Konflikt pojawi się tutaj, gdy reviewerzy podejmą różne decyzje dla tej samej publikacji." />}
      </Card>

      <Card title="Analiza i rozstrzygnięcie">
        {selected ? <>
          <h3>{selected.publication_title || selected.publication_id}</h3>
          <p>Etap: {selected.stage} · Status: {statusLabel[selected.status]}</p>
          {selected.latest_decisions.map((latest) => {
            const decision = latest.decision;
            const reasonNames = decision?.criterion_assessments
              .filter((assessment) => decision.exclusion_reason_criterion_ids?.includes(assessment.criterion_id))
              .map((assessment) => assessment.criterion_name) ?? [];
            return <section key={latest.decision_id} aria-label={`Decision ${latest.reviewer_id}`}>
              <strong>{latest.reviewer_id}: {latest.outcome}</strong>
              {' · '}{new Date(latest.decided_at).toLocaleString()}
              <p>Uzasadnienie: {decision?.rationale || '—'}</p>
              <p>Kryteria: {decision?.criterion_assessments.map((assessment) =>
                `${assessment.criterion_name}: ${assessment.assessment_value}`).join(', ') || '—'}</p>
              {reasonNames.length ? <p>Powody wykluczenia: {reasonNames.join(', ')}</p> : null}
            </section>;
          })}
          <label style={screeningLabelStyle}>Rozstrzygnięcie<select aria-label="Rozstrzygnięcie" value={outcome} style={screeningControlStyle}
            onChange={(event) => setOutcome(event.target.value as ScreeningOutcome)}>
            <option value="include">Include</option>
            <option value="exclude">Exclude</option>
            <option value="uncertain">Uncertain</option>
          </select></label>
          <label style={screeningLabelStyle}>Osoba rozstrzygająca <input aria-label="Osoba rozstrzygająca" value={resolver}
            style={screeningControlStyle}
            onChange={(event) => setResolver(event.target.value)} /></label>
          <label style={screeningLabelStyle}>Uzasadnienie rozstrzygnięcia <textarea aria-label="Uzasadnienie rozstrzygnięcia" required value={rationale}
            style={{ ...screeningControlStyle, resize: 'vertical' }}
            onChange={(event) => setRationale(event.target.value)} /></label>
          <Button onClick={() => void save()} isLoading={saving}
            disabled={!['conflict', 'stale_resolution'].includes(selected.status)
              || !resolver.trim() || !rationale.trim()}>
            Zapisz rozstrzygnięcie
          </Button>
          {success && <p role="status">{success}</p>}
          {concurrencyWarning && <ErrorAlert
            message="Decyzje reviewerów zmieniły się. Wczytaj konflikt ponownie przed zapisem; szkic został zachowany."
            onRetry={() => void load()}
          />}
          <h4>Historia rozstrzygnięć</h4>
          {history.length ? history.map((item) => <p key={item.resolution_id}>
            {item.resolved_outcome} · {item.resolver_id} — {item.is_current ? 'aktualne' : 'nieaktualne'}<br />
            {item.rationale}
          </p>) : <p>Brak historii rozstrzygnięć.</p>}
        </> : <EmptyState title="Brak szczegółów" description="Wybierz konflikt z kolejki." />}
        {error && selected && <ErrorAlert message={error} onRetry={() => void load()} />}
      </Card>
      </div>
    </div>
  );
};
