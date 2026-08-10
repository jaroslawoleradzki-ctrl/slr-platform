import React from 'react';
import { Edit3, Power, CheckCircle2, ShieldAlert, FileText, CheckSquare, Square } from 'lucide-react';
import { ScreeningCriterionResponse } from '../../types';
import { Button } from '../common/Button';

interface ScreeningCriterionCardProps {
  criterion: ScreeningCriterionResponse;
  onEdit: (criterion: ScreeningCriterionResponse) => void;
  onDeactivate: (criterion: ScreeningCriterionResponse) => void;
  onReactivate: (criterion: ScreeningCriterionResponse) => void;
  isActionLoading?: boolean;
}

export const ScreeningCriterionCard: React.FC<ScreeningCriterionCardProps> = ({
  criterion,
  onEdit,
  onDeactivate,
  onReactivate,
  isActionLoading = false,
}) => {
  const isTypeInclusion = criterion.criterion_type === 'inclusion';
  const stageLabelMap: Record<string, string> = {
    title_abstract: 'Title & Abstract',
    full_text: 'Full Text',
    both: 'Both',
  };

  return (
    <div
      data-testid={`criterion-card-${criterion.criterion_id}`}
      style={{
        backgroundColor: criterion.is_active
          ? 'var(--bg-surface)'
          : 'var(--bg-surface-elevated)',
        border: criterion.is_active
          ? '1px solid var(--border-subtle)'
          : '1px dashed var(--border-strong)',
        borderRadius: 'var(--radius-md)',
        padding: '16px 20px',
        display: 'flex',
        flexDirection: 'column',
        gap: '12px',
        opacity: criterion.is_active ? 1 : 0.75,
        transition: 'all 0.15s ease',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '12px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
          <span
            style={{
              fontSize: '0.75rem',
              fontWeight: 700,
              padding: '2px 8px',
              borderRadius: 'var(--radius-full)',
              backgroundColor: 'var(--bg-primary)',
              color: 'var(--text-secondary)',
              border: '1px solid var(--border-subtle)',
            }}
          >
            Kolejność: #{criterion.display_order}
          </span>

          <h3
            style={{
              fontSize: '1rem',
              fontWeight: 700,
              color: criterion.is_active ? 'var(--text-primary)' : 'var(--text-secondary)',
              margin: 0,
              textDecoration: criterion.is_active ? 'none' : 'line-through',
            }}
          >
            {criterion.name}
          </h3>
        </div>

        {/* Action Controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexShrink: 0 }}>
          <Button
            variant="outline"
            size="sm"
            onClick={() => onEdit(criterion)}
            disabled={isActionLoading}
            aria-label={`Edytuj kryterium ${criterion.name}`}
          >
            <Edit3 size={14} />
            <span>Edytuj</span>
          </Button>

          {criterion.is_active ? (
            <Button
              variant="danger"
              size="sm"
              onClick={() => onDeactivate(criterion)}
              disabled={isActionLoading}
              aria-label={`Dezaktywuj kryterium ${criterion.name}`}
            >
              <Power size={14} />
              <span>Dezaktywuj</span>
            </Button>
          ) : (
            <Button
              variant="secondary"
              size="sm"
              onClick={() => onReactivate(criterion)}
              disabled={isActionLoading}
              aria-label={`Aktywuj kryterium ${criterion.name}`}
            >
              <CheckCircle2 size={14} />
              <span>Aktywuj</span>
            </Button>
          )}
        </div>
      </div>

      {/* Description / Instructions */}
      {criterion.description && (
        <p
          style={{
            fontSize: '0.85rem',
            color: 'var(--text-secondary)',
            margin: 0,
            lineHeight: 1.5,
            whiteSpace: 'pre-wrap',
          }}
        >
          {criterion.description}
        </p>
      )}

      {/* Badges / Metadata */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap', marginTop: '4px' }}>
        {/* Inclusion vs Exclusion */}
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '4px',
            fontSize: '0.75rem',
            fontWeight: 600,
            padding: '3px 10px',
            borderRadius: 'var(--radius-full)',
            backgroundColor: isTypeInclusion ? 'var(--status-success-bg)' : 'var(--status-error-bg)',
            color: isTypeInclusion ? 'var(--status-success-text)' : 'var(--status-error-text)',
            border: `1px solid ${isTypeInclusion ? 'var(--status-success-border)' : 'var(--status-error-border)'}`,
          }}
        >
          {isTypeInclusion ? <CheckCircle2 size={12} /> : <ShieldAlert size={12} />}
          <span>{isTypeInclusion ? 'Inclusion' : 'Exclusion'}</span>
        </span>

        {/* Target Stage */}
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '4px',
            fontSize: '0.75rem',
            fontWeight: 500,
            padding: '3px 10px',
            borderRadius: 'var(--radius-full)',
            backgroundColor: 'var(--bg-primary)',
            color: 'var(--text-secondary)',
            border: '1px solid var(--border-subtle)',
          }}
        >
          <FileText size={12} />
          <span>Etap: {stageLabelMap[criterion.screening_stage] || criterion.screening_stage}</span>
        </span>

        {/* Required vs Optional */}
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '4px',
            fontSize: '0.75rem',
            fontWeight: 500,
            padding: '3px 10px',
            borderRadius: 'var(--radius-full)',
            backgroundColor: 'var(--bg-primary)',
            color: criterion.is_required ? 'var(--text-primary)' : 'var(--text-muted)',
            border: '1px solid var(--border-subtle)',
          }}
        >
          {criterion.is_required ? <CheckSquare size={12} /> : <Square size={12} />}
          <span>{criterion.is_required ? 'Required (Wymagane)' : 'Optional (Opcjonalne)'}</span>
        </span>

        {/* Active vs Inactive */}
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '4px',
            fontSize: '0.75rem',
            fontWeight: 600,
            padding: '3px 10px',
            borderRadius: 'var(--radius-full)',
            backgroundColor: criterion.is_active ? 'var(--accent-subtle)' : 'var(--bg-surface-elevated)',
            color: criterion.is_active ? 'var(--accent-primary)' : 'var(--text-muted)',
            border: `1px solid ${criterion.is_active ? 'var(--accent-primary)' : 'var(--border-subtle)'}`,
          }}
        >
          <span>{criterion.is_active ? 'Aktywne' : 'Dezaktywowane'}</span>
        </span>
      </div>
    </div>
  );
};
