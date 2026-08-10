import React, { useState, useEffect } from 'react';
import { Modal } from '../common/Modal';
import { Button } from '../common/Button';
import { ErrorAlert } from '../common/ErrorAlert';
import {
  ScreeningCriterionResponse,
  ScreeningCriterionType,
  ScreeningCriterionStage,
  ScreeningCriterionCreatePayload,
  ScreeningCriterionUpdatePayload,
  ScreeningCriterionEvaluationMode,
  MetadataRuleField,
  MetadataRuleOperator,
  MetadataRule,
} from '../../types';

interface ScreeningCriterionModalProps {
  isOpen: boolean;
  mode: 'create' | 'edit';
  criterion?: ScreeningCriterionResponse | null;
  defaultDisplayOrder?: number;
  onClose: () => void;
  onSubmitCreate: (payload: ScreeningCriterionCreatePayload) => Promise<void>;
  onSubmitUpdate: (criterionId: string, payload: ScreeningCriterionUpdatePayload) => Promise<void>;
}

export const ScreeningCriterionModal: React.FC<ScreeningCriterionModalProps> = ({
  isOpen,
  mode,
  criterion,
  defaultDisplayOrder = 0,
  onClose,
  onSubmitCreate,
  onSubmitUpdate,
}) => {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [criterionType, setCriterionType] = useState<ScreeningCriterionType>('inclusion');
  const [screeningStage, setScreeningStage] = useState<ScreeningCriterionStage>('title_abstract');
  const [displayOrder, setDisplayOrder] = useState<number>(0);
  const [isRequired, setIsRequired] = useState(true);
  const [isActive, setIsActive] = useState(true);
  const [evaluationMode, setEvaluationMode] = useState<ScreeningCriterionEvaluationMode>('manual');
  const [ruleField, setRuleField] = useState<MetadataRuleField>('publication_year');
  const [ruleOperator, setRuleOperator] = useState<MetadataRuleOperator>('greater_than');
  const [ruleValue, setRuleValue] = useState('');

  const [validationError, setValidationError] = useState<string | null>(null);
  const [apiError, setApiError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setValidationError(null);
      setApiError(null);
      setIsSubmitting(false);

      if (mode === 'edit' && criterion) {
        setName(criterion.name);
        setDescription(criterion.description || '');
        setCriterionType(criterion.criterion_type);
        setScreeningStage(criterion.screening_stage);
        setDisplayOrder(criterion.display_order);
        setIsRequired(criterion.is_required);
        setIsActive(criterion.is_active);
        setEvaluationMode(criterion.evaluation_mode || 'manual');
        setRuleField(criterion.metadata_rule?.field || 'publication_year');
        setRuleOperator(criterion.metadata_rule?.operator || 'greater_than');
        setRuleValue(criterion.metadata_rule?.value === null || criterion.metadata_rule?.value === undefined ? '' : Array.isArray(criterion.metadata_rule.value) ? criterion.metadata_rule.value.join(', ') : String(criterion.metadata_rule.value));
      } else {
        setName('');
        setDescription('');
        setCriterionType('inclusion');
        setScreeningStage('title_abstract');
        setDisplayOrder(defaultDisplayOrder);
        setIsRequired(true);
        setIsActive(true);
        setEvaluationMode('manual');
        setRuleField('publication_year');
        setRuleOperator('greater_than');
        setRuleValue('');
      }
    }
  }, [isOpen, mode, criterion, defaultDisplayOrder]);

  if (!isOpen) return null;

  const requiresValue = !['exists', 'not_exists'].includes(ruleOperator);
  const parseRule = (): MetadataRule | null => {
    if (evaluationMode === 'manual') return null;
    if (!requiresValue) return { field: ruleField, operator: ruleOperator, value: null };
    if (!ruleValue.trim()) throw new Error('Podaj wartość reguły automatycznej.');
    const entries = ruleValue.split(',').map((item) => item.trim()).filter(Boolean);
    const isList = ruleOperator === 'in' || ruleOperator === 'not_in';
    const raw = isList ? entries : entries[0];
    if (ruleField === 'publication_year') {
      const values = (Array.isArray(raw) ? raw : [raw]).map(Number);
      if (values.some((value) => !Number.isInteger(value))) throw new Error('Rok publikacji musi być liczbą całkowitą.');
      return { field: ruleField, operator: ruleOperator, value: isList ? values : values[0] };
    }
    if (ruleField === 'open_access') {
      const values = (Array.isArray(raw) ? raw : [raw]).map((value) => value.toLowerCase());
      if (values.some((value) => value !== 'true' && value !== 'false')) throw new Error('Dostęp otwarty przyjmuje wartość true lub false.');
      const booleans = values.map((value) => value === 'true');
      return { field: ruleField, operator: ruleOperator, value: isList ? booleans : booleans[0] };
    }
    return { field: ruleField, operator: ruleOperator, value: isList ? entries : entries[0] };
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setValidationError(null);
    setApiError(null);

    const trimmedName = name.trim();
    if (!trimmedName) {
      setValidationError('Nazwa kryterium nie może być pusta.');
      return;
    }

    if (displayOrder < 0 || isNaN(displayOrder)) {
      setValidationError('Kolejność wyświetlania nie może być ujemna.');
      return;
    }

    let metadataRule: MetadataRule | null;
    try { metadataRule = parseRule(); } catch (error) { setValidationError(error instanceof Error ? error.message : 'Niepoprawna reguła automatyczna.'); return; }
    setIsSubmitting(true);

    try {
      if (mode === 'create') {
        await onSubmitCreate({
          name: trimmedName,
          description: description.trim() ? description.trim() : null,
          criterion_type: criterionType,
          screening_stage: screeningStage,
          display_order: Number(displayOrder),
          is_active: true, // Always active on creation
          is_required: isRequired,
          ...(evaluationMode === 'metadata_rule' ? { evaluation_mode: evaluationMode, metadata_rule: metadataRule } : {}),
        });
      } else if (mode === 'edit' && criterion) {
        await onSubmitUpdate(criterion.criterion_id, {
          name: trimmedName,
          description: description.trim() ? description.trim() : null,
          criterion_type: criterionType,
          screening_stage: screeningStage,
          display_order: Number(displayOrder),
          is_active: isActive,
          is_required: isRequired,
          ...(evaluationMode === 'metadata_rule' ? { evaluation_mode: evaluationMode, metadata_rule: metadataRule } : {}),
        });
      }
      onClose();
    } catch (err: unknown) {
      setApiError(err instanceof Error ? err.message : 'Wystąpił błąd podczas zapisywania kryterium.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={mode === 'create' ? 'Dodaj nowe kryterium screeningu' : 'Edytuj kryterium screeningu'}
    >
      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {validationError && <ErrorAlert message={validationError} />}
        {apiError && <ErrorAlert message={apiError} />}

        {/* Name */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
          <label
            htmlFor="criterion-name"
            style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-primary)' }}
          >
            Nazwa kryterium <span style={{ color: 'var(--status-error-text)' }}>*</span>
          </label>
          <input
            id="criterion-name"
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="np. Prace opublikowane po 2018 roku"
            disabled={isSubmitting}
            style={{
              padding: '8px 12px',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--border-subtle)',
              backgroundColor: 'var(--bg-primary)',
              color: 'var(--text-primary)',
              fontSize: '0.9rem',
            }}
          />
        </div>

        {/* Description / Instructions */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
          <label
            htmlFor="criterion-description"
            style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-primary)' }}
          >
            Opis / Instrukcje dla oceniaszającego (opcjonalnie)
          </label>
          <textarea
            id="criterion-description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Szczegółowe wyjaśnienie lub zasady stosowania tego kryterium..."
            rows={3}
            disabled={isSubmitting}
            style={{
              padding: '8px 12px',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--border-subtle)',
              backgroundColor: 'var(--bg-primary)',
              color: 'var(--text-primary)',
              fontSize: '0.85rem',
              resize: 'vertical',
            }}
          />
        </div>

        {/* Type & Stage (2 columns) */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
          {/* Type */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <label
              htmlFor="criterion-type"
              style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-primary)' }}
            >
              Typ kryterium <span style={{ color: 'var(--status-error-text)' }}>*</span>
            </label>
            <select
              id="criterion-type"
              value={criterionType}
              onChange={(e) => setCriterionType(e.target.value as ScreeningCriterionType)}
              disabled={isSubmitting}
              style={{
                padding: '8px 12px',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--border-subtle)',
                backgroundColor: 'var(--bg-primary)',
                color: 'var(--text-primary)',
                fontSize: '0.9rem',
              }}
            >
              <option value="inclusion">Inclusion (Kwalifikacja)</option>
              <option value="exclusion">Exclusion (Wykluczenie)</option>
            </select>
          </div>

          {/* Stage */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <label
              htmlFor="criterion-stage"
              style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-primary)' }}
            >
              Zakres etapu <span style={{ color: 'var(--status-error-text)' }}>*</span>
            </label>
            <select
              id="criterion-stage"
              value={screeningStage}
              onChange={(e) => setScreeningStage(e.target.value as ScreeningCriterionStage)}
              disabled={isSubmitting}
              style={{
                padding: '8px 12px',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--border-subtle)',
                backgroundColor: 'var(--bg-primary)',
                color: 'var(--text-primary)',
                fontSize: '0.9rem',
              }}
            >
              <option value="title_abstract">Title & Abstract</option>
              <option value="full_text">Full Text</option>
              <option value="both">Both (Oba etapy)</option>
            </select>
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', padding: '12px', border: '1px solid var(--border-strong)', borderRadius: 'var(--radius-md)', background: 'var(--bg-surface-elevated)' }}>
          <label style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-primary)' }}>Sposób oceny</label>
          <div role="group" aria-label="Sposób oceny" style={{ display: 'flex', gap: '8px' }}>
            {[['manual', 'Ręczna'], ['metadata_rule', 'Automatyczna na podstawie metadanych']].map(([value, label]) => <button key={value} type="button" aria-pressed={evaluationMode === value} disabled={isSubmitting} onClick={() => setEvaluationMode(value as ScreeningCriterionEvaluationMode)} style={{ padding: '7px 10px', borderRadius: 'var(--radius-md)', border: `1px solid ${evaluationMode === value ? 'var(--accent-primary)' : 'var(--border-strong)'}`, background: evaluationMode === value ? 'var(--accent-primary)' : 'var(--bg-primary)', color: 'var(--text-primary)', cursor: 'pointer' }}>{label}</button>)}
          </div>
          {evaluationMode === 'metadata_rule' && <>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: '12px' }}>
              <label style={{ fontSize: '0.85rem', color: 'var(--text-primary)' }}>Pole
                <select aria-label="Pole reguły" value={ruleField} disabled={isSubmitting} onChange={(event) => { const field = event.target.value as MetadataRuleField; setRuleField(field); if (field === 'doi' || field === 'abstract') setRuleOperator('exists'); }} style={{ width: '100%', marginTop: '4px', padding: '8px', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-strong)', background: 'var(--bg-primary)', color: 'var(--text-primary)' }}>
                  <option value="publication_year">Rok publikacji</option><option value="language">Język</option><option value="document_type">Typ dokumentu</option><option value="open_access">Otwarty dostęp</option><option value="doi">DOI</option><option value="abstract">Abstrakt</option>
                </select>
              </label>
              <label style={{ fontSize: '0.85rem', color: 'var(--text-primary)' }}>Operator
                <select aria-label="Operator reguły" value={ruleOperator} disabled={isSubmitting} onChange={(event) => setRuleOperator(event.target.value as MetadataRuleOperator)} style={{ width: '100%', marginTop: '4px', padding: '8px', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-strong)', background: 'var(--bg-primary)', color: 'var(--text-primary)' }}>
                  {(ruleField === 'doi' || ruleField === 'abstract') ? <><option value="exists">Istnieje</option><option value="not_exists">Nie istnieje</option></> : <><option value="equals">Równe</option><option value="not_equals">Różne od</option><option value="in">Należy do listy</option><option value="not_in">Nie należy do listy</option>{ruleField === 'publication_year' && <><option value="greater_than">Większy niż</option><option value="greater_than_or_equal">Większy lub równy</option><option value="less_than">Mniejszy niż</option><option value="less_than_or_equal">Mniejszy lub równy</option></>}<option value="exists">Istnieje</option><option value="not_exists">Nie istnieje</option></>}
                </select>
              </label>
            </div>
            {requiresValue && <label style={{ fontSize: '0.85rem', color: 'var(--text-primary)' }}>Wartość{ruleOperator === 'in' || ruleOperator === 'not_in' ? ' (oddziel przecinkami)' : ''}
              <input aria-label="Wartość reguły" value={ruleValue} disabled={isSubmitting} onChange={(event) => setRuleValue(event.target.value)} placeholder={ruleField === 'publication_year' ? 'np. 2021' : ruleField === 'open_access' ? 'true lub false' : 'np. en'} style={{ width: '100%', marginTop: '4px', boxSizing: 'border-box', padding: '8px', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-strong)', background: 'var(--bg-primary)', color: 'var(--text-primary)' }} />
            </label>}
          </>}
        </div>

        {/* Display Order */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
          <label
            htmlFor="criterion-display-order"
            style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-primary)' }}
          >
            Kolejność wyświetlania (Display Order)
          </label>
          <input
            id="criterion-display-order"
            type="number"
            min={0}
            value={displayOrder}
            onChange={(e) => setDisplayOrder(e.target.value === '' ? -1 : Number(e.target.value))}
            disabled={isSubmitting}
            style={{
              padding: '8px 12px',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--border-subtle)',
              backgroundColor: 'var(--bg-primary)',
              color: 'var(--text-primary)',
              fontSize: '0.9rem',
            }}
          />
        </div>

        {/* Checkboxes: Required & Active */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginTop: '4px' }}>
          {/* Required */}
          <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', fontSize: '0.85rem', color: 'var(--text-primary)' }}>
            <input
              type="checkbox"
              checked={isRequired}
              onChange={(e) => setIsRequired(e.target.checked)}
              disabled={isSubmitting}
            />
            <span>Kryterium wymagane (Required — ocena jest obowiazkowa podczas screeningu)</span>
          </label>

          {/* Active (Only shown in Edit mode per prompt rule 2) */}
          {mode === 'edit' && (
            <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', fontSize: '0.85rem', color: 'var(--text-primary)' }}>
              <input
                type="checkbox"
                checked={isActive}
                onChange={(e) => setIsActive(e.target.checked)}
                disabled={isSubmitting}
              />
              <span>Kryterium aktywne (Active)</span>
            </label>
          )}
        </div>

        {/* Modal Actions */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', marginTop: '16px' }}>
          <Button variant="outline" type="button" onClick={onClose} disabled={isSubmitting}>
            Anuluj
          </Button>
          <Button variant="primary" type="submit" isLoading={isSubmitting} disabled={isSubmitting}>
            {isSubmitting ? 'Zapisywanie...' : mode === 'create' ? 'Utwórz kryterium' : 'Zapisz zmiany'}
          </Button>
        </div>
      </form>
    </Modal>
  );
};
