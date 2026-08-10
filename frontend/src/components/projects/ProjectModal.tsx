import React, { useState, useEffect } from 'react';
import { SLRProject } from '../../types';

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

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const cleanTitle = title.trim();
    if (!cleanTitle) {
      setError('Nazwa projektu nie może być pusta.');
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

  return (
    <div
      tabIndex={-1}
      aria-modal="true"
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-4 backdrop-blur-sm"
    >
      <div className="w-full max-w-lg rounded-xl border border-slate-700 bg-slate-800 p-6 shadow-2xl">
        <div className="mb-4 flex items-center justify-between border-b border-slate-700 pb-3">
          <h2 className="text-xl font-semibold text-slate-100">
            {isEditMode ? 'Edycja Projektu' : 'Utwórz Nowy Projekt SLR'}
          </h2>
          <button
            onClick={onClose}
            disabled={submitting}
            className="text-slate-400 hover:text-slate-200"
          >
            ✕
          </button>
        </div>

        {error && (
          <div className="mb-4 rounded-lg bg-rose-500/10 p-3 text-sm text-rose-400 border border-rose-500/20">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">
              Tytuł / Nazwa Projektu <span className="text-rose-400">*</span>
            </label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="np. Lean Management in Industrial Manufacturing"
              className="w-full rounded-lg border border-slate-600 bg-slate-900 px-3 py-2 text-slate-100 focus:border-indigo-500 focus:outline-none"
              disabled={submitting}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">
              Opis Zakresu / Cel Badawczy
            </label>
            <textarea
              rows={3}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="np. Systematyczny przegląd literatury dotyczący wdrożeń Kaizen..."
              className="w-full rounded-lg border border-slate-600 bg-slate-900 px-3 py-2 text-slate-100 focus:border-indigo-500 focus:outline-none"
              disabled={submitting}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">
              Wersja Protokołu Przeglądu
            </label>
            <input
              type="text"
              value={protocolVersion}
              onChange={(e) => setProtocolVersion(e.target.value)}
              placeholder="1.0"
              className="w-full rounded-lg border border-slate-600 bg-slate-900 px-3 py-2 text-slate-100 focus:border-indigo-500 focus:outline-none"
              disabled={submitting}
            />
          </div>

          <div className="mt-6 flex items-center justify-end gap-3 pt-3 border-t border-slate-700">
            <button
              type="button"
              onClick={onClose}
              disabled={submitting}
              className="rounded-lg border border-slate-600 px-4 py-2 text-sm font-medium text-slate-300 hover:bg-slate-700"
            >
              Anuluj
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
            >
              {submitting ? 'Zapisywanie...' : isEditMode ? 'Zapisz Zmiany' : 'Utwórz Projekt'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
