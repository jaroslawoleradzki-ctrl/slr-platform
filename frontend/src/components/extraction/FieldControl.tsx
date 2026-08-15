import React, { useEffect } from 'react';
import { FileText, HelpCircle } from 'lucide-react';
import {
  ExtractionFieldDefinition,
  ExtractedValueStateDTO,
  ValueStatus,
  ValueOrigin,
} from '../../api/extractionApi';

interface FieldControlProps {
  fieldDef: ExtractionFieldDefinition;
  valueState: ExtractedValueStateDTO;
  onChange: (updated: ExtractedValueStateDTO) => void;
  onOpenProvenance: (
    valueState: ExtractedValueStateDTO,
    onSave: (p: Partial<ExtractedValueStateDTO>) => void,
    options: { allowSourceProvenance: boolean; allowReviewerNote: boolean },
  ) => void;
  errorMessage?: string;
}

export const FieldControl: React.FC<FieldControlProps> = ({
  fieldDef,
  valueState,
  onChange,
  onOpenProvenance,
  errorMessage,
}) => {
  const hasTentativeValue = hasValueForField(valueState, fieldDef.data_type);
  const isValueDisabled = ['unassessed', 'not_reported', 'not_applicable'].includes(valueState.status);
  const originAllowed = valueState.status === 'present' || (valueState.status === 'unclear' && hasTentativeValue);
  const sourceProvenanceAllowed = originAllowed;
  const reviewerNoteAllowed = valueState.status !== 'unassessed';
  const selectableStatuses = [
    'unassessed' as ValueStatus,
    ...(fieldDef.allowed_statuses || ['present' as ValueStatus]).filter(
      (status) => status !== 'unassessed',
    ),
  ];

  useEffect(() => {
    const hasSourceProvenance = Boolean(
      valueState.source_page || valueState.source_section || valueState.source_locator || valueState.source_quote,
    );
    const hasAnyValue = Boolean(
      valueState.text_value != null ||
      valueState.int_value != null ||
      valueState.float_value != null ||
      valueState.bool_value != null ||
      valueState.unit_value != null ||
      valueState.json_value != null,
    );

    if (
      ['unassessed', 'not_reported', 'not_applicable'].includes(valueState.status) &&
      (hasAnyValue || valueState.origin || hasSourceProvenance ||
        (valueState.status === 'unassessed' && valueState.reviewer_note))
    ) {
      onChange({
        ...valueState,
        text_value: null,
        int_value: null,
        float_value: null,
        bool_value: null,
        unit_value: null,
        json_value: null,
        origin: null,
        source_page: null,
        source_section: null,
        source_locator: null,
        source_quote: null,
        reviewer_note: valueState.status === 'unassessed' ? null : valueState.reviewer_note,
      });
    } else if (valueState.status === 'unclear' && !hasTentativeValue && (valueState.origin || hasSourceProvenance)) {
      onChange({
        ...valueState,
        origin: null,
        source_page: null,
        source_section: null,
        source_locator: null,
        source_quote: null,
      });
    }
  }, [hasTentativeValue, onChange, valueState]);

  const handleStatusChange = (newStatus: ValueStatus) => {
    if (['unassessed', 'not_reported', 'not_applicable'].includes(newStatus)) {
      onChange({
        ...valueState,
        status: newStatus,
        origin: null,
        text_value: null,
        int_value: null,
        float_value: null,
        bool_value: null,
        unit_value: null,
        json_value: null,
        source_page: null, source_section: null, source_locator: null, source_quote: null,
      });
    } else {
      onChange({
        ...valueState,
        status: newStatus,
      });
    }
  };

  const handleOriginChange = (newOrigin: ValueOrigin | null) => {
    onChange({ ...valueState, origin: newOrigin });
  };

  const hasProvenance =
    Boolean(valueState.source_page) ||
    Boolean(valueState.source_section) ||
    Boolean(valueState.source_locator) ||
    Boolean(valueState.source_quote) ||
    Boolean(valueState.reviewer_note);

  const renderTypedControl = () => {
    switch (fieldDef.data_type) {
      case 'long_text':
        return (
          <textarea
            aria-label={fieldDef.name}
            disabled={isValueDisabled}
            rows={3}
            value={valueState.text_value || ''}
            onChange={(e) => onChange({ ...valueState, text_value: e.target.value })}
            placeholder={isValueDisabled ? `Brak wartości (${valueState.status.toUpperCase()})` : 'Wprowadź tekst...'}
            style={inputStyle(isValueDisabled, Boolean(errorMessage))}
          />
        );

      case 'integer':
        return (
          <input
            aria-label={fieldDef.name}
            type="number"
            step="1"
            disabled={isValueDisabled}
            value={valueState.int_value !== null && valueState.int_value !== undefined ? valueState.int_value : ''}
            onChange={(e) =>
              onChange({
                ...valueState,
                int_value: e.target.value !== '' ? parseInt(e.target.value, 10) : null,
              })
            }
            placeholder={isValueDisabled ? `Brak wartości` : 'np. 42'}
            style={inputStyle(isValueDisabled, Boolean(errorMessage))}
          />
        );

      case 'decimal':
        return (
          <input
            aria-label={fieldDef.name}
            type="number"
            step="any"
            disabled={isValueDisabled}
            value={valueState.float_value !== null && valueState.float_value !== undefined ? valueState.float_value : ''}
            onChange={(e) =>
              onChange({
                ...valueState,
                float_value: e.target.value !== '' ? parseFloat(e.target.value) : null,
              })
            }
            placeholder={isValueDisabled ? `Brak wartości` : 'np. 12.5'}
            style={inputStyle(isValueDisabled, Boolean(errorMessage))}
          />
        );

      case 'boolean':
        return (
          <div style={{ display: 'flex', gap: '16px', alignItems: 'center', height: '36px' }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: '6px', cursor: isValueDisabled ? 'not-allowed' : 'pointer', fontSize: '0.85rem' }}>
              <input
                type="radio"
                name={`bool-${fieldDef.field_key}`}
                disabled={isValueDisabled}
                checked={valueState.bool_value === true}
                onChange={() => onChange({ ...valueState, bool_value: true })}
              />
              Tak (True)
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: '6px', cursor: isValueDisabled ? 'not-allowed' : 'pointer', fontSize: '0.85rem' }}>
              <input
                type="radio"
                name={`bool-${fieldDef.field_key}`}
                disabled={isValueDisabled}
                checked={valueState.bool_value === false}
                onChange={() => onChange({ ...valueState, bool_value: false })}
              />
              Nie (False)
            </label>
          </div>
        );

      case 'date':
        return (
          <input
            aria-label={fieldDef.name}
            type="date"
            disabled={isValueDisabled}
            value={valueState.text_value || ''}
            onChange={(e) => onChange({ ...valueState, text_value: e.target.value })}
            style={inputStyle(isValueDisabled, Boolean(errorMessage))}
          />
        );

      case 'enum':
        return (
          <select
            aria-label={fieldDef.name}
            disabled={isValueDisabled}
            value={valueState.text_value || ''}
            onChange={(e) => onChange({ ...valueState, text_value: e.target.value || null })}
            style={inputStyle(isValueDisabled, Boolean(errorMessage))}
          >
            <option value="">-- Wybierz opcję --</option>
            {(fieldDef.allowed_values || []).map((val) => (
              <option key={val} value={val}>
                {val}
              </option>
            ))}
          </select>
        );

      case 'multi_enum':
        const selectedList = valueState.json_value || [];
        return (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            {(fieldDef.allowed_values || []).map((val) => {
              const isChecked = selectedList.includes(val);
              return (
                <label key={val} style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.85rem', cursor: isValueDisabled ? 'not-allowed' : 'pointer' }}>
                  <input
                    type="checkbox"
                    disabled={isValueDisabled}
                    checked={isChecked}
                    onChange={(e) => {
                      const newList = e.target.checked
                        ? [...selectedList, val]
                        : selectedList.filter((item) => item !== val);
                      onChange({ ...valueState, json_value: newList.length > 0 ? newList : null });
                    }}
                  />
                  {val}
                </label>
              );
            })}
          </div>
        );

      case 'number_with_unit':
        return (
          <div style={{ display: 'flex', gap: '8px' }}>
            <input
              aria-label={`${fieldDef.name} wartość`}
              type="number"
              step="any"
              disabled={isValueDisabled}
              value={valueState.float_value !== null && valueState.float_value !== undefined ? valueState.float_value : ''}
              onChange={(e) =>
                onChange({
                  ...valueState,
                  float_value: e.target.value !== '' ? parseFloat(e.target.value) : null,
                })
              }
              placeholder="Wartość"
              style={{ ...inputStyle(isValueDisabled, Boolean(errorMessage)), flex: 1 }}
            />
            <select
              aria-label={`${fieldDef.name} jednostka`}
              disabled={isValueDisabled}
              value={valueState.unit_value || ''}
              onChange={(e) => onChange({ ...valueState, unit_value: e.target.value || null })}
              style={{ ...inputStyle(isValueDisabled, Boolean(errorMessage)), width: '120px' }}
            >
              <option value="">Jednostka</option>
              {(fieldDef.allowed_units || []).map((unit) => (
                <option key={unit} value={unit}>
                  {unit}
                </option>
              ))}
            </select>
          </div>
        );

      case 'text':
      case 'identifier':
      default:
        return (
          <input
            aria-label={fieldDef.name}
            type="text"
            disabled={isValueDisabled}
            value={valueState.text_value || ''}
            onChange={(e) => onChange({ ...valueState, text_value: e.target.value })}
            placeholder={isValueDisabled ? `Brak wartości (${valueState.status.toUpperCase()})` : 'Wprowadź wartość...'}
            style={inputStyle(isValueDisabled, Boolean(errorMessage))}
          />
        );
    }
  };

  return (
    <div
      style={{
        padding: '14px 16px',
        backgroundColor: 'var(--bg-surface)',
        border: errorMessage ? '1px solid var(--status-error-text)' : '1px solid var(--border-subtle)',
        borderRadius: 'var(--radius-md)',
        display: 'flex',
        flexDirection: 'column',
        gap: '10px',
      }}
    >
      {/* Label Row */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--text-primary)' }}>
            {fieldDef.name}
          </span>
          {fieldDef.is_required && (
            <span style={{ fontSize: '0.7rem', color: 'var(--status-error-text)', fontWeight: 700 }}>
              *wymagane
            </span>
          )}
          {fieldDef.description && (
            <span title={fieldDef.description} style={{ color: 'var(--text-muted)', cursor: 'help' }}>
              <HelpCircle size={14} />
            </span>
          )}
        </div>

        {/* Provenance Button Trigger */}
        <button
          type="button"
          disabled={!sourceProvenanceAllowed && !reviewerNoteAllowed}
          onClick={() =>
            onOpenProvenance(
              valueState,
              (updated) => onChange({ ...valueState, ...updated }),
              { allowSourceProvenance: sourceProvenanceAllowed, allowReviewerNote: reviewerNoteAllowed },
            )
          }
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '4px',
            padding: '3px 8px',
            backgroundColor: hasProvenance ? 'var(--accent-subtle)' : 'transparent',
            color: hasProvenance ? 'var(--accent-primary)' : 'var(--text-muted)',
            border: hasProvenance ? '1px solid var(--accent-primary)' : '1px solid var(--border-subtle)',
            borderRadius: 'var(--radius-md)',
            fontSize: '0.75rem',
            cursor: !sourceProvenanceAllowed && !reviewerNoteAllowed ? 'not-allowed' : 'pointer',
            opacity: !sourceProvenanceAllowed && !reviewerNoteAllowed ? 0.55 : 1,
          }}
        >
          <FileText size={13} />
          {hasProvenance ? 'Proweniencja ✓' : '+ Proweniencja'}
        </button>
      </div>

      {/* Control Controls Bar: Status & Origin */}
      <div style={{ display: 'flex', gap: '16px', alignItems: 'center', flexWrap: 'wrap', fontSize: '0.8rem' }}>
        {/* Value Status Selector */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span style={{ color: 'var(--text-muted)', fontWeight: 500 }}>Status:</span>
          <select
            value={valueState.status}
            onChange={(e) => handleStatusChange(e.target.value as ValueStatus)}
            style={{
              padding: '2px 8px',
              fontSize: '0.75rem',
              backgroundColor: 'var(--bg-primary)',
              color: 'var(--text-primary)',
              border: '1px solid var(--border-strong)',
              borderRadius: 'var(--radius-sm)',
            }}
          >
            {selectableStatuses.map((status) => (
              <option key={status} value={status}>
                {status === 'unassessed' && 'UNASSESSED (Nie oceniono)'}
                {status === 'present' && 'PRESENT (Obecna)'}
                {status === 'not_reported' && 'NOT_REPORTED (Brak raportowania)'}
                {status === 'not_applicable' && 'NOT_APPLICABLE (Nie dotyczy)'}
                {status === 'unclear' && 'UNCLEAR (Niejasna)'}
              </option>
            ))}
          </select>
        </div>

        {/* Value Origin Selector */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span style={{ color: 'var(--text-muted)', fontWeight: 500 }}>Źródło:</span>
          <select
            disabled={!originAllowed}
            value={valueState.origin || ''}
            onChange={(e) => handleOriginChange(e.target.value === '' ? null : e.target.value as ValueOrigin)}
            style={{
              padding: '2px 8px',
              fontSize: '0.75rem',
              backgroundColor: 'var(--bg-primary)',
              color: 'var(--text-primary)',
              border: '1px solid var(--border-strong)',
              borderRadius: 'var(--radius-sm)',
            }}
          >
            <option value="">-- wybierz pochodzenie --</option>
            <option value="reported">REPORTED (Wprost z artykułu)</option>
            <option value="reviewer_coded">REVIEWER_CODED (Interpretacja recenzenta)</option>
          </select>
        </div>
      </div>

      {/* Main Typed Input Widget */}
      <div>{renderTypedControl()}</div>

      {/* Error Message Display */}
      {errorMessage && (
        <span style={{ fontSize: '0.75rem', color: 'var(--status-error-text)', fontWeight: 500 }}>
          {errorMessage}
        </span>
      )}
    </div>
  );
};

function inputStyle(disabled: boolean, hasError: boolean): React.CSSProperties {
  return {
    width: '100%',
    padding: '8px 12px',
    backgroundColor: disabled ? 'var(--bg-surface-elevated)' : 'var(--bg-primary)',
    color: disabled ? 'var(--text-muted)' : 'var(--text-primary)',
    border: hasError ? '1px solid var(--status-error-text)' : '1px solid var(--border-strong)',
    borderRadius: 'var(--radius-md)',
    fontSize: '0.85rem',
    cursor: disabled ? 'not-allowed' : 'text',
  };
}

function hasValueForField(value: ExtractedValueStateDTO, dataType: ExtractionFieldDefinition['data_type']): boolean {
  if (dataType === 'number_with_unit') {
    return value.int_value != null || value.float_value != null;
  }
  return (
    (value.text_value != null && value.text_value !== '') ||
    value.int_value != null ||
    value.float_value != null ||
    value.bool_value != null ||
    (value.json_value != null && value.json_value.length > 0)
  );
}
