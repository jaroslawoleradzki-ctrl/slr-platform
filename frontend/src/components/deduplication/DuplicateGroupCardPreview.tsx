import React from 'react';
import { Layers, Check, X } from 'lucide-react';
import { DuplicateGroupPreview } from '../../types';
import { Card } from '../common/Card';

interface DuplicateGroupCardPreviewProps {
  group: DuplicateGroupPreview;
  index: number;
}

export const DuplicateGroupCardPreview: React.FC<DuplicateGroupCardPreviewProps> = ({ group, index }) => {
  return (
    <Card
      title={
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Layers size={16} style={{ color: 'var(--status-warning-text)' }} />
          <span>Candidate Duplicate Group #{index + 1} (ID: {group.groupId})</span>
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
      subtitle={`Dopasowanie identyfikatora: ${group.reason}`}
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
            title="Tryb podglądu — integracja decyzji z API w Phase 6.2"
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
            title="Tryb podglądu — integracja decyzji z API w Phase 6.2"
          >
            <X size={14} />
            <span>Odrzuć (Podgląd API)</span>
          </button>
        </div>
      }
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
        {group.records.map((rec, recIdx) => (
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
                Autorzy: {rec.authors} ({rec.year})
              </div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '4px', display: 'flex', gap: '12px' }}>
                <span>Źródło: <strong>{rec.source}</strong></span>
                {rec.doi && <span>DOI: <code>{rec.doi}</code></span>}
              </div>
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
};
