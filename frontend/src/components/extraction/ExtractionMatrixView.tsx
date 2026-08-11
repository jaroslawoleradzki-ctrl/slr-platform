import React, { useState } from 'react';
import { Layers } from 'lucide-react';
import { ExtractionMatrixResponseDTO, ExtractedValueStateDTO } from '../../api/extractionApi';

interface ExtractionMatrixViewProps {
  matrix: ExtractionMatrixResponseDTO | null;
  isLoading: boolean;
}

export const ExtractionMatrixView: React.FC<ExtractionMatrixViewProps> = ({ matrix, isLoading }) => {
  const [selectedGroupKey, setSelectedGroupKey] = useState<string>('');

  if (isLoading) {
    return (
      <div
        style={{
          padding: '40px',
          textAlign: 'center',
          color: 'var(--text-muted)',
          backgroundColor: 'var(--bg-surface)',
          borderRadius: 'var(--radius-lg)',
          border: '1px solid var(--border-subtle)',
        }}
      >
        Ładowanie macierzy relacji powtarzalnych...
      </div>
    );
  }

  if (!matrix || matrix.items.length === 0) {
    return (
      <div
        style={{
          padding: '40px',
          textAlign: 'center',
          color: 'var(--text-muted)',
          backgroundColor: 'var(--bg-surface)',
          borderRadius: 'var(--radius-lg)',
          border: '1px solid var(--border-subtle)',
          fontSize: '0.9rem',
        }}
      >
        Brak wyekstrahowanych relacji (1:N repeating group items) dla tego projektu.
      </div>
    );
  }

  const groupKeys = matrix.group_keys || [];
  const activeGroupKey = selectedGroupKey || groupKeys[0] || '';

  const groupItems = matrix.items.filter((item) => !activeGroupKey || item.group_key === activeGroupKey);

  // Collect all unique field keys present across items of this group
  const fieldKeysSet = new Set<string>();
  groupItems.forEach((item) => {
    item.values.forEach((v) => fieldKeysSet.add(v.field_key));
  });
  const fieldKeys = Array.from(fieldKeysSet);

  const renderValueText = (val?: ExtractedValueStateDTO) => {
    if (!val) return '—';
    if (val.status === 'not_reported') return <span style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>[Not Reported]</span>;
    if (val.status === 'not_applicable') return <span style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>[N/A]</span>;
    if (val.status === 'unclear') return <span style={{ color: 'var(--status-warning-text)' }}>[Unclear]</span>;

    if (val.text_value !== null && val.text_value !== undefined) return val.text_value;
    if (val.float_value !== null && val.float_value !== undefined) return String(val.float_value);
    if (val.int_value !== null && val.int_value !== undefined) return String(val.int_value);
    if (val.bool_value !== null && val.bool_value !== undefined) return val.bool_value ? 'Tak' : 'Nie';
    if (val.unit_value !== null && val.unit_value !== undefined) return val.unit_value;
    if (val.json_value !== null && val.json_value !== undefined) return JSON.stringify(val.json_value);

    return '—';
  };

  return (
    <div
      style={{
        backgroundColor: 'var(--bg-surface)',
        border: '1px solid var(--border-subtle)',
        borderRadius: 'var(--radius-lg)',
        overflow: 'hidden',
      }}
    >
      {/* Header & Group Tabs */}
      <div
        style={{
          padding: '16px 20px',
          borderBottom: '1px solid var(--border-subtle)',
          backgroundColor: 'var(--bg-surface-elevated)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '12px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Layers size={18} style={{ color: 'var(--accent-primary)' }} />
          <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: 'var(--text-primary)', margin: 0 }}>
            Macierz Relacji (Cross-Study Repeating Group Matrix)
          </h3>
        </div>

        {/* Group Tabs */}
        {groupKeys.length > 1 && (
          <div style={{ display: 'flex', gap: '4px' }}>
            {groupKeys.map((gk) => (
              <button
                key={gk}
                onClick={() => setSelectedGroupKey(gk)}
                style={{
                  padding: '6px 12px',
                  borderRadius: 'var(--radius-md)',
                  border: activeGroupKey === gk ? '1px solid var(--accent-primary)' : '1px solid var(--border-subtle)',
                  backgroundColor: activeGroupKey === gk ? 'var(--bg-primary)' : 'transparent',
                  color: activeGroupKey === gk ? 'var(--accent-primary)' : 'var(--text-secondary)',
                  fontSize: '0.8rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                {gk}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Matrix Table */}
      {groupItems.length === 0 ? (
        <div style={{ padding: '30px', textAlign: 'center', color: 'var(--text-muted)' }}>
          Brak elementów dla grupy '{activeGroupKey}'.
        </div>
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.85rem' }}>
            <thead>
              <tr
                style={{
                  borderBottom: '1px solid var(--border-subtle)',
                  color: 'var(--text-muted)',
                  fontSize: '0.75rem',
                  textTransform: 'uppercase',
                  letterSpacing: '0.05em',
                }}
              >
                <th style={{ padding: '12px 16px', minWidth: '200px' }}>Publikacja (Badanie)</th>
                <th style={{ padding: '12px 16px', width: '100px' }}>Grupa / Idx</th>
                {fieldKeys.map((fk) => (
                  <th key={fk} style={{ padding: '12px 16px', minWidth: '130px' }}>
                    {fk}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {groupItems.map((item, rowIdx) => {
                const valuesMap = new Map<string, ExtractedValueStateDTO>();
                item.values.forEach((v) => valuesMap.set(v.field_key, v));

                return (
                  <tr
                    key={item.group_item_id || `${item.publication_id}_${rowIdx}`}
                    style={{
                      borderBottom: '1px solid var(--border-subtle)',
                      transition: 'background-color 0.15s ease',
                    }}
                  >
                    <td style={{ padding: '12px 16px', fontWeight: 600, color: 'var(--text-primary)' }}>
                      {item.publication_title}
                    </td>
                    <td style={{ padding: '12px 16px', color: 'var(--text-secondary)' }}>
                      <span
                        style={{
                          padding: '2px 6px',
                          borderRadius: 'var(--radius-sm)',
                          backgroundColor: 'var(--bg-surface-elevated)',
                          fontSize: '0.75rem',
                          fontWeight: 600,
                        }}
                      >
                        #{item.item_index}
                      </span>
                    </td>
                    {fieldKeys.map((fk) => {
                      const val = valuesMap.get(fk);
                      return (
                        <td key={fk} style={{ padding: '12px 16px', color: 'var(--text-primary)' }}>
                          {renderValueText(val)}
                        </td>
                      );
                    })}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
