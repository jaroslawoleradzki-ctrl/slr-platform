import React from 'react';
import { Layers, Check, X } from 'lucide-react';
import { ApiDuplicateGroup, DuplicateGroupPreview } from '../../types';
import { Card } from '../common/Card';

interface DuplicateGroupCardPreviewProps {
  group: ApiDuplicateGroup | DuplicateGroupPreview;
  index: number;
}

export const DuplicateGroupCardPreview: React.FC<DuplicateGroupCardPreviewProps> = ({ group, index }) => {
  const groupId = 'group_id' in group ? group.group_id : group.groupId;
  const reason = group.reason;
  const sharedIdentifiers = 'shared_identifiers' in group ? group.shared_identifiers : [];
  const normalizedSharedIdents = sharedIdentifiers.map((ident) =>
    typeof ident === 'string' ? ident : `${ident.identifier_type.toUpperCase()}: ${ident.value}`
  );

  return (
    <Card
      title={
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
          <Layers size={16} style={{ color: 'var(--status-warning-text)' }} />
          <span>Candidate Duplicate Group #{index + 1} (ID: {groupId})</span>
          <span
            style={{
              fontSize: '0.75rem',
              padding: '2px 6px',
              borderRadius: 'var(--radius-full)',
              backgroundColor: 'var(--status-warning-bg)',
              color: 'var(--status-warning-text)',
              fontWeight: 700,
            }}
          >
            Identifier Match (DOI / PMID / OpenAlex ID)
          </span>
        </div>
      }
      subtitle={
        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
          <div>Dopasowanie identyfikatora: {reason}</div>
          {normalizedSharedIdents.length > 0 && (
            <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginTop: '2px' }}>
              {normalizedSharedIdents.map((identStr) => (
                <span
                  key={identStr}
                  style={{
                    fontSize: '0.7rem',
                    padding: '1px 6px',
                    borderRadius: 'var(--radius-sm)',
                    backgroundColor: 'var(--bg-surface-elevated)',
                    border: '1px solid var(--border-subtle)',
                    color: 'var(--text-secondary)',
                    fontFamily: 'monospace',
                  }}
                >
                  {identStr}
                </span>
              ))}
            </div>
          )}
        </div>
      }
      action={
        <div style={{ display: 'flex', gap: '6px' }}>
          <button
            disabled
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '4px',
              padding: '6px 12px',
              borderRadius: 'var(--radius-md)',
              backgroundColor: 'var(--status-success-bg)',
              color: 'var(--status-success-text)',
              border: '1px solid var(--status-success-border)',
              fontSize: '0.8rem',
              fontWeight: 600,
              opacity: 0.65,
              cursor: 'not-allowed',
            }}
            title="Tryb podglądu — integracja zapisywania decyzji w Phase 6.4"
          >
            <Check size={14} />
            <span>Zatwierdź (Podgląd API)</span>
          </button>
          <button
            disabled
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '4px',
              padding: '6px 12px',
              borderRadius: 'var(--radius-md)',
              backgroundColor: 'var(--bg-surface-elevated)',
              color: 'var(--text-secondary)',
              border: '1px solid var(--border-strong)',
              fontSize: '0.8rem',
              opacity: 0.65,
              cursor: 'not-allowed',
            }}
            title="Tryb podglądu — integracja zapisywania decyzji w Phase 6.4"
          >
            <X size={14} />
            <span>Odrzuć (Podgląd API)</span>
          </button>
        </div>
      }
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
        {group.records.map((rec, recIdx) => {
          const pmid = 'pmid' in rec ? rec.pmid : undefined;
          const openalex = 'openalex_id' in rec ? rec.openalex_id : undefined;

          return (
            <div
              key={rec.id}
              style={{
                padding: '12px 14px',
                backgroundColor: 'var(--bg-primary)',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--border-subtle)',
                display: 'flex',
                alignItems: 'flex-start',
                gap: '12px',
              }}
            >
              <span
                style={{
                  fontSize: '0.7rem',
                  fontWeight: 700,
                  color: 'var(--text-muted)',
                  padding: '2px 6px',
                  borderRadius: '4px',
                  backgroundColor: 'var(--bg-surface-elevated)',
                }}
              >
                #{recIdx + 1}
              </span>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                  {rec.title}
                </div>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '2px' }}>
                  Autorzy: {rec.authors} ({rec.year || 'Brak roku'})
                </div>
                <div
                  style={{
                    fontSize: '0.75rem',
                    color: 'var(--text-muted)',
                    marginTop: '4px',
                    display: 'flex',
                    gap: '12px',
                    flexWrap: 'wrap',
                  }}
                >
                  <span>
                    Źródło: <strong>{rec.source}</strong>
                  </span>
                  {rec.doi && (
                    <span>
                      DOI: <code>{rec.doi}</code>
                    </span>
                  )}
                  {pmid && (
                    <span>
                      PMID: <code>{pmid}</code>
                    </span>
                  )}
                  {openalex && (
                    <span>
                      OpenAlex: <code>{openalex}</code>
                    </span>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </Card>
  );
};
