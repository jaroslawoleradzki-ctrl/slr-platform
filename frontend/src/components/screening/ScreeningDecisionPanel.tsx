import React from 'react';
import { Button } from '../common/Button';
import { Card } from '../common/Card';
import { ScreeningDecision, ScreeningOutcome } from '../../services/api/screeningApi';
import { screeningControlStyle } from './screeningFormStyles';

const outcomeLabels: Record<ScreeningOutcome, string> = {
  include: 'Włącz', exclude: 'Wyklucz', uncertain: 'Niepewne',
};

const outcomeStyle = (outcome: ScreeningOutcome, selected: boolean): React.CSSProperties => ({
  borderColor: selected ? (outcome === 'exclude' ? 'var(--status-error-border)' : 'var(--accent-primary)') : 'var(--border-strong)',
  backgroundColor: selected ? (outcome === 'exclude' ? 'var(--status-error-bg)' : 'var(--accent-primary)') : 'var(--bg-surface-elevated)',
  color: outcome === 'exclude' && selected ? 'var(--status-error-text)' : 'var(--text-primary)',
  boxShadow: selected ? '0 0 0 2px var(--accent-subtle)' : 'none',
});

export const ScreeningDecisionPanel: React.FC<{
  outcome: ScreeningOutcome | null;
  rationale: string;
  latestDecision: ScreeningDecision | null;
  onOutcome: (value: ScreeningOutcome) => void;
  onRationale: (value: string) => void;
  onSave: (next: boolean) => void;
  canSave: boolean;
  saving: boolean;
}> = ({ outcome, rationale, latestDecision, onOutcome, onRationale, onSave, canSave, saving }) => (
  <Card title="Decyzja końcowa">
    {latestDecision && <div style={{ padding: '10px', background: 'var(--bg-surface-elevated)', marginBottom: '12px', fontSize: '0.85rem' }}>
      Najnowsza decyzja: <strong>{outcomeLabels[latestDecision.outcome]}</strong> · {new Date(latestDecision.decided_at).toLocaleString()}<br />
      {latestDecision.rationale || 'Brak uzasadnienia.'}
      {latestDecision.criterion_assessments.length > 0 && <details style={{ marginTop: '6px' }}>
        <summary>Najnowsze oceny kryteriów</summary>
        <ul style={{ margin: '6px 0 0', paddingLeft: '18px' }}>
          {latestDecision.criterion_assessments.map((assessment) => <li key={assessment.criterion_id}>
            {assessment.criterion_name}: {assessment.assessment_value}{assessment.notes ? ` — ${assessment.notes}` : ''}
          </li>)}
        </ul>
      </details>}
    </div>}
    <div role="group" aria-label="Decyzja końcowa" style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
      {(['include', 'exclude', 'uncertain'] as ScreeningOutcome[]).map((value) => (
        <Button key={value} type="button" aria-pressed={outcome === value} variant="outline" style={outcomeStyle(value, outcome === value)} disabled={saving} onClick={() => onOutcome(value)}>
          {outcomeLabels[value]}
        </Button>
      ))}
    </div>
    <textarea aria-label="Decision rationale" value={rationale} disabled={saving} onChange={(event) => onRationale(event.target.value)}
      placeholder="Uzasadnienie decyzji (opcjonalnie)" rows={3} style={{ ...screeningControlStyle, marginTop: '12px', resize: 'vertical' }} />
    <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '12px', flexWrap: 'wrap' }}>
      <Button type="button" variant="outline" disabled={!canSave} isLoading={saving} onClick={() => onSave(false)}>Zapisz</Button>
      <Button type="button" disabled={!canSave} isLoading={saving} onClick={() => onSave(true)}>Zapisz i następny</Button>
    </div>
  </Card>
);
