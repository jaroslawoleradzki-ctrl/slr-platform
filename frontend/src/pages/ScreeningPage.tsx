import React, { useState, useEffect, useCallback } from 'react';
import { Plus, Info } from 'lucide-react';
import { useProject } from '../context/ProjectContext';
import { projectApiService } from '../services/api/projectApi';
import {
  ScreeningCriterionResponse,
  ScreeningCriterionCreatePayload,
  ScreeningCriterionUpdatePayload,
} from '../types';
import { Button } from '../components/common/Button';
import { ScreeningCriteriaList } from '../components/screening/ScreeningCriteriaList';
import { ScreeningCriterionModal } from '../components/screening/ScreeningCriterionModal';

export const ScreeningPage: React.FC = () => {
  const { activeProject } = useProject();
  const projectId = activeProject?.id;

  const [criteria, setCriteria] = useState<ScreeningCriterionResponse[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [modalMode, setModalMode] = useState<'create' | 'edit'>('create');
  const [selectedCriterion, setSelectedCriterion] = useState<ScreeningCriterionResponse | null>(null);
  const [actionLoadingId, setActionLoadingId] = useState<string | null>(null);

  const loadCriteria = useCallback(async (showFullLoading = false) => {
    if (!projectId) return;
    if (showFullLoading) setIsLoading(true);
    setError(null);
    try {
      const response = await projectApiService.listScreeningCriteria(projectId);
      setCriteria(response.items);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Nie udało się pobrać kryteriów screeningu.');
    } finally {
      setIsLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    void loadCriteria(true);
  }, [loadCriteria]);

  const handleOpenCreateModal = () => {
    setSelectedCriterion(null);
    setModalMode('create');
    setIsModalOpen(true);
  };

  const handleOpenEditModal = (criterion: ScreeningCriterionResponse) => {
    setSelectedCriterion(criterion);
    setModalMode('edit');
    setIsModalOpen(true);
  };

  const handleCloseModal = () => {
    setIsModalOpen(false);
    setSelectedCriterion(null);
  };

  const handleCreateCriterion = async (payload: ScreeningCriterionCreatePayload) => {
    if (!projectId) return;
    await projectApiService.createScreeningCriterion(projectId, payload);
    await loadCriteria();
  };

  const handleUpdateCriterion = async (
    criterionId: string,
    payload: ScreeningCriterionUpdatePayload
  ) => {
    if (!projectId) return;
    await projectApiService.updateScreeningCriterion(projectId, criterionId, payload);
    await loadCriteria();
  };

  const handleDeactivateCriterion = async (criterion: ScreeningCriterionResponse) => {
    if (!projectId) return;
    setActionLoadingId(criterion.criterion_id);
    try {
      await projectApiService.deactivateScreeningCriterion(projectId, criterion.criterion_id);
      await loadCriteria();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Nie udało się dezaktywować kryterium.');
    } finally {
      setActionLoadingId(null);
    }
  };

  const handleReactivateCriterion = async (criterion: ScreeningCriterionResponse) => {
    if (!projectId) return;
    setActionLoadingId(criterion.criterion_id);
    try {
      await projectApiService.updateScreeningCriterion(projectId, criterion.criterion_id, {
        name: criterion.name,
        description: criterion.description,
        criterion_type: criterion.criterion_type,
        screening_stage: criterion.screening_stage,
        display_order: criterion.display_order,
        is_active: true,
        is_required: criterion.is_required,
      });
      await loadCriteria();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Nie udało się aktywować kryterium.');
    } finally {
      setActionLoadingId(null);
    }
  };

  if (!activeProject) return null;

  // Calculate default display order for new criterion (max existing display_order + 1, or 0)
  const maxDisplayOrder = criteria.length > 0
    ? Math.max(...criteria.map((c) => c.display_order))
    : -1;
  const defaultNextDisplayOrder = maxDisplayOrder + 1;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Page Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '16px', flexWrap: 'wrap' }}>
        <div>
          <h2 style={{ fontSize: '1.3rem', fontWeight: 800, color: 'var(--text-primary)', margin: 0 }}>
            5. Konfiguracja Kryteriów Screeningu (Screening Criteria Configuration)
          </h2>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '4px', marginBottom: 0 }}>
            Zarządzaj konfigurowalnymi kryteriami włączenia (Inclusion) oraz wykluczenia (Exclusion) dla projektu.
          </p>
        </div>

        <Button variant="primary" onClick={handleOpenCreateModal} disabled={isLoading}>
          <Plus size={16} />
          <span>Dodaj kryterium</span>
        </Button>
      </div>

      {/* Scope banner explaining that 7.3 is configuration only */}
      <div
        style={{
          padding: '12px 16px',
          backgroundColor: 'var(--bg-surface-elevated)',
          borderRadius: 'var(--radius-md)',
          border: '1px solid var(--border-subtle)',
          fontSize: '0.85rem',
          color: 'var(--text-secondary)',
          display: 'flex',
          alignItems: 'center',
          gap: '10px',
        }}
      >
        <Info size={18} style={{ color: 'var(--accent-primary)', flexShrink: 0 }} />
        <span>
          <strong>Informacja o etapie:</strong> Ten ekran służy do konfiguracji kryteriów kwalifikacji i wykluczenia (Phase 7.3). Właściwy screening publikacji (Triage Tytułów i Abstraktów oraz Kwalifikacja Pełnotekstowa) zostanie udostępniony w kolejnych przyrostach.
        </span>
      </div>

      {/* Criteria List */}
      <ScreeningCriteriaList
        criteria={criteria}
        isLoading={isLoading}
        error={error}
        onRetry={loadCriteria}
        onOpenCreateModal={handleOpenCreateModal}
        onOpenEditModal={handleOpenEditModal}
        onDeactivate={handleDeactivateCriterion}
        onReactivate={handleReactivateCriterion}
        actionLoadingId={actionLoadingId}
      />

      {/* Create / Edit Form Modal */}
      <ScreeningCriterionModal
        isOpen={isModalOpen}
        mode={modalMode}
        criterion={selectedCriterion}
        defaultDisplayOrder={defaultNextDisplayOrder}
        onClose={handleCloseModal}
        onSubmitCreate={handleCreateCriterion}
        onSubmitUpdate={handleUpdateCriterion}
      />
    </div>
  );
};
