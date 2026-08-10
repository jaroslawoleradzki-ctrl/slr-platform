import React, { useState, useEffect } from 'react';
import { Modal } from '../common/Modal';
import { Button } from '../common/Button';
import { AlertOctagon } from 'lucide-react';
import { SLRProject } from '../../types';

interface ConfirmDeleteModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: (id: string) => Promise<void>;
  project: SLRProject | null;
}

export const ConfirmDeleteModal: React.FC<ConfirmDeleteModalProps> = ({
  isOpen,
  onClose,
  onConfirm,
  project,
}) => {
  const [typedTitle, setTypedTitle] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setTypedTitle('');
    setError(null);
    setSubmitting(false);
  }, [isOpen, project]);

  if (!isOpen || !project) return null;

  const isConfirmed = typedTitle.trim() === project.title.trim();

  const handleConfirm = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isConfirmed) return;

    setSubmitting(true);
    setError(null);
    try {
      await onConfirm(project.id);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Wystąpił błąd podczas usuwania projektu.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Usuń Projekt Trwale"
    >
      <form onSubmit={handleConfirm} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        <div
          style={{
            display: 'flex',
            alignItems: 'flex-start',
            gap: '14px',
            padding: '16px',
            backgroundColor: 'var(--status-error-bg)',
            border: '1px solid var(--status-error-border)',
            borderRadius: 'var(--radius-md)',
            color: 'var(--status-error-text)',
          }}
        >
          <AlertOctagon size={24} style={{ flexShrink: 0, marginTop: '2px' }} />
          <div>
            <h4 style={{ fontSize: '0.95rem', fontWeight: 700, marginBottom: '4px' }}>
              Uwaga! Operacja destrukcyjna i nieodwracalna.
            </h4>
            <p style={{ fontSize: '0.85rem', opacity: 0.9, lineHeight: 1.45 }}>
              To trwale usunie projekt <strong>„{project.title}”</strong> oraz wszystkie powiązane dane:
              publikacje, strategie wyszukiwania, historię importów, kryteria i decyzje screeningu.
              Tej operacji nie można cofnąć.
            </p>
          </div>
        </div>

        {error && (
          <div
            style={{
              padding: '10px 14px',
              backgroundColor: 'var(--status-error-bg)',
              border: '1px solid var(--status-error-border)',
              borderRadius: 'var(--radius-md)',
              color: 'var(--status-error-text)',
              fontSize: '0.85rem',
            }}
          >
            {error}
          </div>
        )}

        <div>
          <label
            style={{
              display: 'block',
              fontSize: '0.85rem',
              fontWeight: 600,
              color: 'var(--text-secondary)',
              marginBottom: '6px',
            }}
          >
            Wpisz dokładną nazwę projektu <code>{project.title}</code>, aby potwierdzić usuwanie:
          </label>
          <input
            type="text"
            value={typedTitle}
            onChange={(e) => setTypedTitle(e.target.value)}
            placeholder={project.title}
            disabled={submitting}
            style={{
              width: '100%',
              backgroundColor: 'var(--bg-primary)',
              border: '1px solid var(--border-strong)',
              borderRadius: 'var(--radius-md)',
              padding: '10px 14px',
              color: 'var(--text-primary)',
              fontSize: '0.9rem',
            }}
            autoFocus
          />
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
          <Button variant="secondary" onClick={onClose} disabled={submitting} type="button">
            Anuluj
          </Button>
          <Button
            variant="danger"
            type="submit"
            disabled={!isConfirmed || submitting}
            isLoading={submitting}
            loadingText="Usuwanie..."
          >
            Usuń trwale
          </Button>
        </div>
      </form>
    </Modal>
  );
};
