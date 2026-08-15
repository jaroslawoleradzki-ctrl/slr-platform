import React, { useState } from 'react';
import { Plus, Trash2, ChevronDown, ChevronRight, Layers, AlertCircle } from 'lucide-react';
import {
  ExtractionRepeatingGroupDefinition,
  ExtractedGroupItemStateDTO,
  ExtractedValueStateDTO,
  ValueStatus,
} from '../../api/extractionApi';
import { FieldControl } from './FieldControl';

interface RelationshipManagerProps {
  groupDef: ExtractionRepeatingGroupDefinition;
  groupItems: ExtractedGroupItemStateDTO[];
  onChange: (updatedItems: ExtractedGroupItemStateDTO[]) => void;
  onOpenProvenance: (
    fieldKey: string,
    fieldName: string,
    valueState: ExtractedValueStateDTO,
    onSave: (p: Partial<ExtractedValueStateDTO>) => void,
    options: { allowSourceProvenance: boolean; allowReviewerNote: boolean },
  ) => void;
  validationErrors?: Record<string, string>;
}

export const RelationshipManager: React.FC<RelationshipManagerProps> = ({
  groupDef,
  groupItems,
  onChange,
  onOpenProvenance,
  validationErrors = {},
}) => {
  const [expandedIndices, setExpandedIndices] = useState<Record<number, boolean>>({ 0: true });

  const toggleExpand = (index: number) => {
    setExpandedIndices((prev) => ({ ...prev, [index]: !prev[index] }));
  };

  const handleAddItem = () => {
    const nextIndex = groupItems.length > 0 ? Math.max(...groupItems.map((item) => item.item_index)) + 1 : 1;
    const initialValues: ExtractedValueStateDTO[] = groupDef.field_definitions.map((field) => ({
      field_key: field.field_key,
      status: 'unassessed' as ValueStatus,
      origin: null,
    }));
    const newItem: ExtractedGroupItemStateDTO = {
      group_key: groupDef.group_key,
      item_index: nextIndex,
      values: initialValues,
    };
    const updated = [...groupItems, newItem];
    onChange(updated);
    setExpandedIndices((prev) => ({ ...prev, [groupItems.length]: true }));
  };

  const handleRemoveItem = (itemIndex: number) => {
    const updated = groupItems
      .filter((item) => item.item_index !== itemIndex)
      .map((item, idx) => ({ ...item, item_index: idx + 1 }));
    onChange(updated);
  };

  const handleFieldValueChange = (itemIdx: number, updatedValue: ExtractedValueStateDTO) => {
    const updatedItems = groupItems.map((item, idx) => {
      if (idx !== itemIdx) return item;
      const updatedValues = item.values.map((val) => (val.field_key === updatedValue.field_key ? updatedValue : val));
      if (!item.values.some((val) => val.field_key === updatedValue.field_key)) {
        updatedValues.push(updatedValue);
      }
      return { ...item, values: updatedValues };
    });
    onChange(updatedItems);
  };

  const isMinViolated = groupItems.length < groupDef.min_items;
  const isMaxViolated = groupDef.max_items !== null && groupDef.max_items !== undefined && groupItems.length > groupDef.max_items;

  return (
    <div
      style={{
        border: '1px solid var(--border-subtle)',
        borderRadius: 'var(--radius-lg)',
        backgroundColor: 'var(--bg-surface)',
        overflow: 'hidden',
        marginBottom: '24px',
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: '14px 20px',
          backgroundColor: 'var(--bg-surface-elevated)',
          borderBottom: '1px solid var(--border-subtle)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <Layers size={18} style={{ color: 'var(--accent-primary)' }} />
          <div>
            <h4 style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>
              {groupDef.name}
            </h4>
            {groupDef.description && (
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{groupDef.description}</span>
            )}
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          {/* Items Count Badge */}
          <span
            style={{
              fontSize: '0.75rem',
              fontWeight: 600,
              padding: '2px 8px',
              borderRadius: 'var(--radius-full)',
              backgroundColor: isMinViolated || isMaxViolated ? 'var(--status-error-bg)' : 'var(--bg-primary)',
              color: isMinViolated || isMaxViolated ? 'var(--status-error-text)' : 'var(--text-secondary)',
              border: '1px solid var(--border-subtle)',
            }}
          >
            Liczba elementów: {groupItems.length} (min: {groupDef.min_items}
            {groupDef.max_items ? `, max: ${groupDef.max_items}` : ''})
          </span>

          <button
            type="button"
            onClick={handleAddItem}
            disabled={groupDef.max_items !== null && groupDef.max_items !== undefined && groupItems.length >= groupDef.max_items}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              padding: '6px 12px',
              backgroundColor: 'var(--accent-subtle)',
              color: 'var(--accent-primary)',
              border: '1px solid var(--accent-primary)',
              borderRadius: 'var(--radius-md)',
              fontSize: '0.8rem',
              fontWeight: 600,
              cursor:
                groupDef.max_items !== null && groupDef.max_items !== undefined && groupItems.length >= groupDef.max_items
                  ? 'not-allowed'
                  : 'pointer',
              opacity:
                groupDef.max_items !== null && groupDef.max_items !== undefined && groupItems.length >= groupDef.max_items
                  ? 0.5
                  : 1,
            }}
          >
            <Plus size={14} /> Dodaj element
          </button>
        </div>
      </div>

      {/* Cardinality Warnings */}
      {isMinViolated && (
        <div
          style={{
            padding: '8px 20px',
            backgroundColor: 'var(--status-warning-bg)',
            color: 'var(--status-warning-text)',
            fontSize: '0.8rem',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            borderBottom: '1px solid var(--border-subtle)',
          }}
        >
          <AlertCircle size={14} /> Wymagana minimalna liczba elementów: {groupDef.min_items}. (Obecnie: {groupItems.length})
        </div>
      )}

      {isMaxViolated && (
        <div
          style={{
            padding: '8px 20px',
            backgroundColor: 'var(--status-error-bg)',
            color: 'var(--status-error-text)',
            fontSize: '0.8rem',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            borderBottom: '1px solid var(--border-subtle)',
          }}
        >
          <AlertCircle size={14} /> Przekroczono maksymalną liczbę elementów: {groupDef.max_items}.
        </div>
      )}

      {/* Items List */}
      <div style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
        {groupItems.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '24px', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
            Brak zdefiniowanych elementów w tej grupie. Kliknij <strong>„Dodaj element”</strong>, aby utworzyć wpis.
          </div>
        ) : (
          groupItems.map((item, itemIdx) => {
            const isExpanded = expandedIndices[itemIdx] ?? false;
            return (
              <div
                key={item.group_item_id || `group-item-${item.item_index}-${itemIdx}`}
                style={{
                  border: '1px solid var(--border-subtle)',
                  borderRadius: 'var(--radius-md)',
                  backgroundColor: 'var(--bg-primary)',
                  overflow: 'hidden',
                }}
              >
                {/* Item Card Header */}
                <div
                  onClick={() => toggleExpand(itemIdx)}
                  style={{
                    padding: '10px 14px',
                    backgroundColor: 'var(--bg-surface-elevated)',
                    borderBottom: isExpanded ? '1px solid var(--border-subtle)' : 'none',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    cursor: 'pointer',
                    userSelect: 'none',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    {isExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                    <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                      Element #{item.item_index}
                    </span>
                  </div>

                  <button
                    type="button"
                    aria-label={`Usuń element #${item.item_index}`}
                    onClick={(e) => {
                      e.stopPropagation();
                      handleRemoveItem(item.item_index);
                    }}
                    style={{
                      background: 'none',
                      border: 'none',
                      color: 'var(--status-error-text)',
                      cursor: 'pointer',
                      padding: '4px',
                      borderRadius: 'var(--radius-md)',
                    }}
                  >
                    <Trash2 size={15} />
                  </button>
                </div>

                {/* Item Fields */}
                {isExpanded && (
                  <div style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
                    {groupDef.field_definitions.map((fieldDef) => {
                      const valueState =
                        item.values.find((val) => val.field_key === fieldDef.field_key) || {
                          field_key: fieldDef.field_key,
                          status: 'unassessed' as ValueStatus,
                          origin: null,
                        };
                      const errorMsg = validationErrors[`${groupDef.group_key}.${item.item_index}.${fieldDef.field_key}`];

                      return (
                        <FieldControl
                          key={fieldDef.field_key}
                          fieldDef={fieldDef}
                          valueState={valueState}
                          onChange={(updated) => handleFieldValueChange(itemIdx, updated)}
                          onOpenProvenance={(val, onSave, options) => onOpenProvenance(fieldDef.field_key, fieldDef.name, val, onSave, options)}
                          errorMessage={errorMsg}
                        />
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
