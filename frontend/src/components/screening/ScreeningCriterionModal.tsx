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
      } else {
        setName('');
        setDescription('');
        setCriterionType('inclusion');
        setScreeningStage('title_abstract');
        setDisplayOrder(defaultDisplayOrder);
        setIsRequired(true);
        setIsActive(true);
      }
    }
  }, [isOpen, mode, criterion, defaultDisplayOrder]);

  if (!isOpen) return null;

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
