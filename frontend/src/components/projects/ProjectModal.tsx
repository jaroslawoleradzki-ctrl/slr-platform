import React, { useState, useEffect } from 'react';
import { Modal } from '../common/Modal';
import { Button } from '../common/Button';
import { ErrorAlert } from '../common/ErrorAlert';
import { SLRProject } from '../../types';
import { FileText, Tag, AlignLeft } from 'lucide-react';

interface ProjectModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (title: string, description: string, protocolVersion: string) => Promise<void>;
  projectToEdit?: SLRProject | null;
}

export const ProjectModal: React.FC<ProjectModalProps> = ({
  isOpen,
  onClose,
  onSubmit,
  projectToEdit,
}) => {
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [protocolVersion, setProtocolVersion] = useState('1.0');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isEditMode = Boolean(projectToEdit);

  useEffect(() => {
    if (projectToEdit) {
      setTitle(projectToEdit.title);
      setDescription(projectToEdit.description || '');
      setProtocolVersion(projectToEdit.protocolVersion || '1.0');
    } else {
      setTitle('');
      setDescription('');
      setProtocolVersion('1.0');
    }
    setError(null);
  }, [projectToEdit, isOpen]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const cleanTitle = title.trim();
    if (!cleanTitle) {
      setError('Tytuł projektu jest wymagany i nie może być pusty.');
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      await onSubmit(cleanTitle, description.trim(), protocolVersion.trim() || '1.0');
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Wystąpił błąd podczas zapisu projektu.');
    } finally {
      setSubmitting(false);
    }
  };

  const inputStyle: React.CSSProperties = {
    width: '100%',
    backgroundColor: 'var(--bg-primary)',
    border: '1px solid var(--border-strong)',
    borderRadius: 'var(--radius-md)',
    padding: '10px 14px',
    color: 'var(--text-primary)',
    fontSize: '0.9rem',
    transition: 'border-color 0.15s ease, box-shadow 0.15s ease',
  };

  const labelStyle: React.CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    fontSize: '0.85rem',
    fontWeight: 600,
    color: 'var(--text-secondary)',
    marginBottom: '6px',
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={isEditMode ? 'Edycja Metadanych Projektu' : 'Utwórz Nowy Projekt SLR'}
    >
      {error && (
        <div style={{ marginBottom: '16px' }}>
          <ErrorAlert title="Niepoprawny formularz" message={error} />
        </div>
      )}

      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
        <div>
          <label style={labelStyle}>
            <FileText size={15} style={{ color: 'var(--accent-primary)' }} />
            <span>Tytuł / Nazwa Projektu</span>
            <span style={{ color: 'var(--status-error-text)' }}>*</span>
          </label>
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="np. Lean Management in Industrial Manufacturing"
            disabled={submitting}
            style={inputStyle}
            autoFocus
          />
        </div>

        <div>
          <label style={labelStyle}>
            <AlignLeft size={15} style={{ color: 'var(--accent-primary)' }} />
            <span>Opis Zakresu / Cel Badawczy</span>
          </label>
          <textarea
            rows={3}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Opisz zakres merytoryczny, cele lub specyfikę tego przeglądu literatury..."
            disabled={submitting}
            style={{
              ...inputStyle,
              resize: 'vertical',
              minHeight: '80px',
            }}
          />
        </div>

        <div>
          <label style={labelStyle}>
            <Tag size={15} style={{ color: 'var(--accent-primary)' }} />
            <span>Wersja Protokołu Badawczego</span>
          </label>
          <input
            type="text"
            value={protocolVersion}
            onChange={(e) => setProtocolVersion(e.target.value)}
            placeholder="np. 1.0"
            disabled={submitting}
            style={{
              ...inputStyle,
              fontFamily: 'var(--font-mono)',
              width: '180px',
            }}
          />
        </div>

        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'flex-end',
            gap: '12px',
            marginTop: '8px',
            paddingTop: '16px',
            borderTop: '1px solid var(--border-subtle)',
          }}
        >
          <Button
            type="button"
            variant="secondary"
            onClick={onClose}
            disabled={submitting}
          >
            Anuluj
          </Button>
          <Button
            type="submit"
            variant="primary"
            isLoading={submitting}
            loadingText={isEditMode ? 'Zapisywanie...' : 'Tworzenie...'}
          >
            {isEditMode ? 'Zapisz Zmiany' : 'Utwórz Projekt'}
          </Button>
        </div>
      </form>
    </Modal>
  );
};
