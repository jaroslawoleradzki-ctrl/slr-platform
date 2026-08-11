import React from 'react';
import { Card } from '../common/Card';
import { AssessmentValue, FullTextRecord, ScreeningCriterion, TitleAbstractRecord } from '../../services/api/screeningApi';
import { screeningControlStyle } from './screeningFormStyles';

export interface AssessmentDraft { value: AssessmentValue | ''; notes: string; }

const values: Array<{ value: AssessmentValue; label: string }> = [
  { value: 'met', label: 'Spełnione' },
  { value: 'not_met', label: 'Niespełnione' },
  { value: 'uncertain', label: 'Niepewne' },
];

export const ScreeningCriteriaPanel: React.FC<{
  criteria: ScreeningCriterion[];
  assessments: Record<string, AssessmentDraft>;
  onChange: (criterionId: string, draft: AssessmentDraft) => void;
  disabled: boolean;
  automaticAssessments: NonNullable<TitleAbstractRecord['automatic_assessments'] | FullTextRecord['automatic_assessments']>;
}> = ({ criteria, assessments, onChange, disabled, automaticAssessments }) => (
  <Card title="Ocena kryteriów" subtitle="Oceń wszystkie wymagane kryteria przed zapisaniem decyzji.">
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      {criteria.map((criterion) => {
        const draft = assessments[criterion.criterion_id] || { value: '', notes: '' };
        const automatic = automaticAssessments.find((item) => item.criterion_id === criterion.criterion_id);
        const rule = criterion.metadata_rule;
        const fieldLabel: Record<string, string> = { publication_year: 'Rok publikacji', language: 'Język', document_type: 'Typ dokumentu', open_access: 'Otwarty dostęp', doi: 'DOI', abstract: 'Abstrakt' };
        const operatorLabel: Record<string, string> = { equals: 'równe', not_equals: 'różne od', in: 'należy do', not_in: 'nie należy do', greater_than: 'większe niż', greater_than_or_equal: 'większe lub równe', less_than: 'mniejsze niż', less_than_or_equal: 'mniejsze lub równe', exists: 'istnieje', not_exists: 'nie istnieje' };
        return <section key={criterion.criterion_id} style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: '14px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: '8px' }}>
            <strong>{criterion.name}</strong>
            <span style={{ fontSize: '0.75rem', color: criterion.is_required ? 'var(--status-error-text)' : 'var(--text-muted)' }}>
              {criterion.is_required ? 'Wymagane' : 'Opcjonalne'} · {criterion.criterion_type === 'inclusion' ? 'włączenie' : 'wykluczenie'}
            </span>
          </div>
          {criterion.description && <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', margin: '5px 0' }}>{criterion.description}</p>}
          {criterion.evaluation_mode === 'metadata_rule' && rule && automatic ? <div data-testid={`automatic-assessment-${criterion.criterion_id}`} style={{ marginTop: '10px', padding: '10px', borderRadius: 'var(--radius-md)', background: 'var(--bg-surface-elevated)', border: '1px solid var(--border-strong)' }}>
            <strong style={{ fontSize: '0.8rem' }}>Automatyczne</strong>
            <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '4px' }}>Warunek: {fieldLabel[rule.field]} {operatorLabel[rule.operator]} {rule.value === null ? '' : Array.isArray(rule.value) ? rule.value.join(', ') : String(rule.value)}</div>
            <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '3px' }}>Wartość publikacji: {automatic.evaluated_metadata_value === null ? 'brak w zapisanych metadanych' : Array.isArray(automatic.evaluated_metadata_value) ? automatic.evaluated_metadata_value.join(', ') : String(automatic.evaluated_metadata_value)}</div>
            <div style={{ fontWeight: 700, marginTop: '6px', color: automatic.assessment_value === 'met' ? 'var(--status-success-text)' : automatic.assessment_value === 'not_met' ? 'var(--status-error-text)' : 'var(--status-warning-text)' }}>Wynik: {automatic.assessment_value === 'met' ? 'Spełnione' : automatic.assessment_value === 'not_met' ? 'Niespełnione' : 'Nie oceniono — brakuje metadanych'}</div>
          </div> : <>
          <div role="group" aria-label={criterion.name} style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginTop: '10px' }}>
            {values.concat(criterion.is_required ? [] : [{ value: 'not_assessed', label: 'Nie oceniono' }]).map((option) => {
              const selected = draft.value === option.value;
              return <button key={option.value} type="button" aria-pressed={selected} disabled={disabled}
                onClick={() => onChange(criterion.criterion_id, { ...draft, value: option.value })}
                style={{ padding: '7px 10px', borderRadius: 'var(--radius-md)', border: `1px solid ${selected ? 'var(--accent-primary)' : 'var(--border-strong)'}`,
                  background: selected ? 'var(--accent-primary)' : 'var(--bg-surface-elevated)', color: 'var(--text-primary)', fontWeight: selected ? 700 : 500,
                  opacity: disabled ? 0.55 : 1, cursor: disabled ? 'not-allowed' : 'pointer' }}>
                {option.label}
              </button>;
            })}
          </div>
          <textarea aria-label={`Notes for ${criterion.name}`} disabled={disabled} value={draft.notes}
            onChange={(event) => onChange(criterion.criterion_id, { ...draft, notes: event.target.value })}
            placeholder="Notatka do kryterium (opcjonalnie)" rows={2} style={{ ...screeningControlStyle, marginTop: '10px', resize: 'vertical' }} />
          </>}
        </section>;
      })}
    </div>
  </Card>
);
