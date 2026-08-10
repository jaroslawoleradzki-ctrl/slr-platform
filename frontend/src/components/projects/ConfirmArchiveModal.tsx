import React, { useState } from 'react';
import { Modal } from '../common/Modal';
import { Button } from '../common/Button';
import { AlertTriangle } from 'lucide-react';
import { SLRProject } from '../../types';

interface ConfirmArchiveModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: (id: string) => Promise<void>;
  project: SLRProject | null;
}

export const ConfirmArchiveModal: React.FC<ConfirmArchiveModalProps> = ({
  isOpen,
  onClose,
  onConfirm,
  project,
}) => {
  const [submitting, setSubmitting] = useState(false);

  if (!isOpen || !project) return null;

  const handleConfirm = async () => {
    setSubmitting(true);
    try {
      await onConfirm(project.id);
      onClose();
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Zarchiwizuj Projekt"
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        <div
          style={{
            display: 'flex',
            alignItems: 'flex-start',
            gap: '14px',
            padding: '16px',
            backgroundColor: 'var(--status-warning-bg)',
            border: '1px solid var(--status-warning-border)',
            borderRadius: 'var(--radius-md)',
            color: 'var(--status-warning-text)',
          }}
        >
          <AlertTriangle size={24} style={{ flexShrink: 0, marginTop: '2px' }} />
          <div>
            <h4 style={{ fontSize: '0.95rem', fontWeight: 600, marginBottom: '4px' }}>
              Czy na pewno chcesz zarchiwizować ten projekt?
            </h4>
            <p style={{ fontSize: '0.85rem', opacity: 0.9, lineHeight: 1.4 }}>
              Projekt <strong>„{project.title}”</strong> zostanie przeniesiony do zakładki zarchiwizowanych.
              Wszystkie dane, badania i decyzje screeningowe pozostaną w bazie danych. W dowolnym momencie możesz przywrócić projekt.
            </p>
          </div>
        </div>

        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'flex-end',
            gap: '12px',
            paddingTop: '12px',
            borderTop: '1px solid var(--border-subtle)',
          }}
        >
          <Button variant="secondary" onClick={onClose} disabled={submitting}>
            Anuluj
          </Button>
          <Button
            variant="danger"
            onClick={handleConfirm}
            isLoading={submitting}
            loadingText="Archiwizowanie..."
          >
            Zarchiwizuj Projekt
          </Button>
        </div>
      </div>
    </Modal>
  );
};
