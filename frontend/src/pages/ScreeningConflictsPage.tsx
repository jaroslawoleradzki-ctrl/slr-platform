import React, { useCallback, useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Button } from '../components/common/Button';
import { Card } from '../components/common/Card';
import { EmptyState } from '../components/common/EmptyState';
import { ErrorAlert } from '../components/common/ErrorAlert';
import { LoadingSpinner } from '../components/common/LoadingSpinner';
import { ScreeningConflict, screeningApi } from '../services/api/screeningApi';
import { useReviewerIdentity } from '../hooks/useReviewerIdentity';

const PAGE_SIZE = 25;

type Stage = 'title_abstract' | 'full_text';
type ConflictFilter = '' | 'incomplete' | 'agreement' | 'conflict';

const statusLabel: Record<string, string> = {
  incomplete: 'Niepełne',
  agreement: 'Zgodne',
  conflict: 'Konflikt',
};

export const ScreeningConflictsPage: React.FC = () => {
  const { projectId = '' } = useParams<{ projectId: string }>();
  const [stage, setStage] = useState<Stage>('title_abstract');
  const [filter, setFilter] = useState<ConflictFilter>('');
  const [reviewers, setReviewers] = useState('');
  const [items, setItems] = useState<ScreeningConflict[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [metrics, setMetrics] = useState<{ incomplete: number; agreement: number; conflict: number; agreement_rate: number | null } | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { reviewerId } = useReviewerIdentity();

  const load = useCallback(async (nextOffset = 0) => {
    setLoading(true);
    setError(null);
    try {
      const [roster, conflicts, nextMetrics] = await Promise.all([
        screeningApi.getReviewerRoster(projectId, stage),
        screeningApi.getConflicts(projectId, stage, filter || null, nextOffset, PAGE_SIZE, reviewerId),
        screeningApi.getConflictMetrics(projectId, stage),
      ]);
      setReviewers(roster.filter((item) => item.is_active).map((item) => item.reviewer_id).join(', '));
      setItems(conflicts.items);
      setTotal(conflicts.total);
      setMetrics(nextMetrics);
      setOffset(nextOffset);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Nie udało się pobrać stanu multi-reviewer.');
    } finally {
      setLoading(false);
    }
  }, [filter, projectId, reviewerId, stage]);

  useEffect(() => {
    void load(0);
  }, [load]);

  const saveRoster = async () => {
    setSaving(true);
    setError(null);
    try {
      await screeningApi.saveReviewerRoster(
        projectId,
        stage,
        reviewers.split(',').map((value) => value.trim()).filter(Boolean),
      );
      await load(0);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Nie udało się zapisać zespołu reviewerów.');
    } finally {
      setSaving(false);
    }
  };

  const updateStage = (value: Stage) => {
    setStage(value);
    setOffset(0);
  };

  const updateFilter = (value: ConflictFilter) => {
    setFilter(value);
    setOffset(0);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <Card title="Multi-reviewer screening" subtitle="Zespół reviewerów jest wspólny dla projektu i etapu; usunięci reviewerzy pozostają w historii decyzji.">
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
          <label>Etap <select value={stage} onChange={(event) => updateStage(event.target.value as Stage)}>
            <option value="title_abstract">Title &amp; Abstract</option>
            <option value="full_text">Full Text</option>
          </select></label>
          <label style={{ flex: '1 1 280px' }}>Reviewerzy (oddzieleni przecinkiem)
            <input value={reviewers} onChange={(event) => setReviewers(event.target.value)} />
          </label>
          <Button onClick={() => void saveRoster()} isLoading={saving}>Zapisz zespół reviewerów</Button>
        </div>
      </Card>

      {metrics && <Card title="Zgodność decyzji">
        <p>Niepełne: {metrics.incomplete} · Zgodne: {metrics.agreement} · Konflikty: {metrics.conflict}</p>
        <p>Agreement rate: {metrics.agreement_rate === null ? 'brak ukończonych porównań' : `${Math.round(metrics.agreement_rate * 100)}%`}</p>
      </Card>}

      <Card title="Kolejka zgodności">
        <label>Filtr <select value={filter} onChange={(event) => updateFilter(event.target.value as ConflictFilter)}>
          <option value="">Wszystkie statusy</option>
          <option value="incomplete">Niepełne</option>
          <option value="agreement">Zgodne</option>
          <option value="conflict">Konflikty</option>
        </select></label>
        {loading ? <LoadingSpinner label="Ładowanie kolejki..." /> : items.length ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginTop: 12 }}>
            {items.map((item) => <ConflictCard key={item.publication_id} item={item} />)}
          </div>
        ) : <EmptyState title="Brak rekordów" description="Skonfiguruj aktywny zespół reviewerów lub zmień filtr." />}
        {total > PAGE_SIZE && <div style={{ display: 'flex', gap: 8, marginTop: 16 }}>
          <Button variant="outline" disabled={offset === 0 || loading} onClick={() => void load(Math.max(0, offset - PAGE_SIZE))}>Poprzednia</Button>
          <Button variant="outline" disabled={offset + PAGE_SIZE >= total || loading} onClick={() => void load(offset + PAGE_SIZE)}>Następna</Button>
        </div>}
      </Card>
      {error && <ErrorAlert message={error} onRetry={() => void load(offset)} />}
    </div>
  );
};

const ConflictCard: React.FC<{ item: ScreeningConflict }> = ({ item }) => (
  <div style={{ border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-md)', padding: 12 }}>
    <strong>{item.publication_title || item.publication_id}</strong>
    <div>Status: {statusLabel[item.status] || item.status}</div>
    <div>Oczekują: {item.pending_reviewers.join(', ') || 'brak'}</div>
    <div>
      {item.latest_decisions.length
        ? item.latest_decisions.map((decision) => `${decision.reviewer_id}: ${decision.outcome}`).join(' · ')
        : 'Outcomes innych reviewerów są ukryte do czasu zapisania własnej decyzji.'}
    </div>
  </div>
);
