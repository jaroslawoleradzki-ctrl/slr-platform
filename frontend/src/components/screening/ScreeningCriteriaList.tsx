import React from 'react';
import { Filter, Plus, Info } from 'lucide-react';
import { ScreeningCriterionResponse } from '../../types';
import { ScreeningCriterionCard } from './ScreeningCriterionCard';
import { LoadingSpinner } from '../common/LoadingSpinner';
import { ErrorAlert } from '../common/ErrorAlert';
import { EmptyState } from '../common/EmptyState';
import { Button } from '../common/Button';

interface ScreeningCriteriaListProps {
  criteria: ScreeningCriterionResponse[];
  isLoading: boolean;
  error: string | null;
  onRetry: () => void;
  onOpenCreateModal: () => void;
  onOpenEditModal: (criterion: ScreeningCriterionResponse) => void;
  onDeactivate: (criterion: ScreeningCriterionResponse) => void;
  onReactivate: (criterion: ScreeningCriterionResponse) => void;
  actionLoadingId?: string | null;
}

export const ScreeningCriteriaList: React.FC<ScreeningCriteriaListProps> = ({
  criteria,
  isLoading,
  error,
  onRetry,
  onOpenCreateModal,
  onOpenEditModal,
  onDeactivate,
  onReactivate,
  actionLoadingId,
}) => {
  if (isLoading) {
    return (
      <div style={{ padding: '40px 0', display: 'flex', justifyContent: 'center' }}>
        <LoadingSpinner label="Ładowanie kryteriów screeningu z backendu..." />
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        <ErrorAlert message={`Nie udało się pobrać kryteriów screeningu: ${error}`} onRetry={onRetry} />
      </div>
    );
  }

  if (criteria.length === 0) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
        <EmptyState
          icon={<Filter size={24} />}
          title="Nie zdefiniowano jeszcze kryteriów screeningu."
          description="Dodaj pierwsze kryterium kwalifikacji (Inclusion) lub wykluczenia (Exclusion), aby skonfigurować proces przesiewania dla tego projektu."
          action={
            <Button variant="primary" onClick={onOpenCreateModal}>
              <Plus size={16} />
              <span>Dodaj pierwsze kryterium</span>
            </Button>
          }
        />

        {/* Information box on criteria semantics */}
        <div
          style={{
            padding: '16px',
            backgroundColor: 'var(--bg-surface-elevated)',
            borderRadius: 'var(--radius-md)',
            border: '1px solid var(--border-subtle)',
            fontSize: '0.85rem',
            color: 'var(--text-secondary)',
            display: 'flex',
            gap: '12px',
          }}
        >
          <Info size={20} style={{ color: 'var(--accent-primary)', flexShrink: 0, marginTop: '2px' }} />
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <strong style={{ color: 'var(--text-primary)' }}>Przewodnik po kryteriach screeningu:</strong>
            <ul style={{ margin: 0, paddingLeft: '20px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <li>
                <strong>Inclusion (Kwalifikacja):</strong> Kryteria, które publikacja musi spełniać, aby zostać włączoną do przeglądu.
              </li>
              <li>
                <strong>Exclusion (Wykluczenie):</strong> Kryteria, których spełnienie odrzuca publikację z dalszych etapów.
              </li>
              <li>
                <strong>Zakres etapu:</strong> Kryteria mogą dotyczyć etapu <em>Title & Abstract</em>, <em>Full Text</em> lub <em>Both</em> (obu etapów).
              </li>
              <li>
                <strong>Required / Optional:</strong> Kryteria wymagane muszą być oceniane podczas przesiewania, opcjonalne mogą być pominięte.
              </li>
            </ul>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', fontWeight: 500 }}>
          Liczba skonfigurowanych kryteriów: <strong>{criteria.length}</strong> (w tym aktywnych:{' '}
          <strong>{criteria.filter((c) => c.is_active).length}</strong>)
        </span>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
        {criteria.map((item) => (
          <ScreeningCriterionCard
            key={item.criterion_id}
            criterion={item}
            onEdit={onOpenEditModal}
            onDeactivate={onDeactivate}
            onReactivate={onReactivate}
            isActionLoading={actionLoadingId === item.criterion_id}
          />
        ))}
      </div>
    </div>
  );
};
