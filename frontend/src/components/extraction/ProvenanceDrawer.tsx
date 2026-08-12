import React, { useState, useEffect } from 'react';
import { X, Check, FileText } from 'lucide-react';
import { ExtractedValueStateDTO } from '../../api/extractionApi';

interface ProvenanceDrawerProps {
  isOpen: boolean;
  fieldKey: string;
  fieldName: string;
  valueState: ExtractedValueStateDTO;
  onSave: (updatedProvenance: Partial<ExtractedValueStateDTO>) => void;
  onClose: () => void;
}

export const ProvenanceDrawer: React.FC<ProvenanceDrawerProps> = ({
  isOpen,
  fieldKey,
  fieldName,
  valueState,
  onSave,
  onClose,
}) => {
  const [sourcePage, setSourcePage] = useState(valueState.source_page || '');
  const [sourceSection, setSourceSection] = useState(valueState.source_section || '');
  const [sourceLocator, setSourceLocator] = useState(valueState.source_locator || '');
  const [sourceQuote, setSourceQuote] = useState(valueState.source_quote || '');
  const [reviewerNote, setReviewerNote] = useState(valueState.reviewer_note || '');

  useEffect(() => {
    setSourcePage(valueState.source_page || '');
    setSourceSection(valueState.source_section || '');
    setSourceLocator(valueState.source_locator || '');
    setSourceQuote(valueState.source_quote || '');
    setReviewerNote(valueState.reviewer_note || '');
  }, [valueState, isOpen]);

  if (!isOpen) return null;

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    onSave({
      source_page: sourcePage.trim() || null,
      source_section: sourceSection.trim() || null,
      source_locator: sourceLocator.trim() || null,
      source_quote: sourceQuote.trim() || null,
      reviewer_note: reviewerNote.trim() || null,
    });
    onClose();
  };

  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        right: 0,
        bottom: 0,
        width: '420px',
        backgroundColor: 'var(--bg-surface)',
        borderLeft: '1px solid var(--border-strong)',
        boxShadow: '-4px 0 20px rgba(0, 0, 0, 0.25)',
        zIndex: 100,
        display: 'flex',
        flexDirection: 'column',
        animation: 'slideIn 0.2s ease-out',
      }}
      role="dialog"
      aria-label={`Provenance metadata for ${fieldName}`}
    >
      {/* Header */}
      <div
        style={{
          padding: '16px 20px',
          borderBottom: '1px solid var(--border-subtle)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          backgroundColor: 'var(--bg-surface-elevated)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <FileText size={18} style={{ color: 'var(--accent-primary)' }} />
          <div>
            <h3 style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>
              Proweniencja pola
            </h3>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              {fieldName} ({fieldKey})
            </span>
          </div>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Zamknij"
          style={{
            background: 'none',
            border: 'none',
            color: 'var(--text-muted)',
            cursor: 'pointer',
            padding: '4px',
            borderRadius: 'var(--radius-md)',
          }}
        >
          <X size={18} />
        </button>
      </div>

      {/* Form Content */}
      <form onSubmit={handleSave} style={{ flex: 1, padding: '20px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '16px' }}>
        <div>
          <label htmlFor="provenance-source-page" style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '4px' }}>
            Strona w publikacji (source_page)
          </label>
          <input
            id="provenance-source-page"
            type="text"
            value={sourcePage}
            onChange={(e) => setSourcePage(e.target.value)}
            placeholder="np. Str. 14, p. 12"
            style={{
              width: '100%',
              padding: '8px 12px',
              backgroundColor: 'var(--bg-primary)',
              border: '1px solid var(--border-strong)',
              borderRadius: 'var(--radius-md)',
              color: 'var(--text-primary)',
              fontSize: '0.85rem',
            }}
          />
        </div>

        <div>
          <label htmlFor="provenance-source-section" style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '4px' }}>
            Sekcja / Rozdział (source_section)
          </label>
          <input
            id="provenance-source-section"
            type="text"
            value={sourceSection}
            onChange={(e) => setSourceSection(e.target.value)}
            placeholder="np. Methods 2.1, Results"
            style={{
              width: '100%',
              padding: '8px 12px',
              backgroundColor: 'var(--bg-primary)',
              border: '1px solid var(--border-strong)',
              borderRadius: 'var(--radius-md)',
              color: 'var(--text-primary)',
              fontSize: '0.85rem',
            }}
          />
        </div>

        <div>
          <label htmlFor="provenance-source-locator" style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '4px' }}>
            Lokalizator elementu (source_locator)
          </label>
          <input
            id="provenance-source-locator"
            type="text"
            value={sourceLocator}
            onChange={(e) => setSourceLocator(e.target.value)}
            placeholder="np. Tabela 2 row 4, Rysunek 1"
            style={{
              width: '100%',
              padding: '8px 12px',
              backgroundColor: 'var(--bg-primary)',
              border: '1px solid var(--border-strong)',
              borderRadius: 'var(--radius-md)',
              color: 'var(--text-primary)',
              fontSize: '0.85rem',
            }}
          />
        </div>

        <div>
          <label htmlFor="provenance-source-quote" style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '4px' }}>
            Cytat z tekstu źródłowego (source_quote, max 500 znaków)
          </label>
          <textarea
            id="provenance-source-quote"
            rows={4}
            maxLength={500}
            value={sourceQuote}
            onChange={(e) => setSourceQuote(e.target.value)}
            placeholder="Krótki dosłowny cytat uzasadniający wydobycie (opcjonalny)..."
            style={{
              width: '100%',
              padding: '8px 12px',
              backgroundColor: 'var(--bg-primary)',
              border: '1px solid var(--border-strong)',
              borderRadius: 'var(--radius-md)',
              color: 'var(--text-primary)',
              fontSize: '0.85rem',
              resize: 'vertical',
            }}
          />
          <div style={{ textAlign: 'right', fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '2px' }}>
            {sourceQuote.length} / 500
          </div>
        </div>

        <div>
          <label htmlFor="provenance-reviewer-note" style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '4px' }}>
            Notatka recenzenta (reviewer_note)
          </label>
          <textarea
            id="provenance-reviewer-note"
            rows={3}
            value={reviewerNote}
            onChange={(e) => setReviewerNote(e.target.value)}
            placeholder="Komentarz własny recenzenta dot. tego pola..."
            style={{
              width: '100%',
              padding: '8px 12px',
              backgroundColor: 'var(--bg-primary)',
              border: '1px solid var(--border-strong)',
              borderRadius: 'var(--radius-md)',
              color: 'var(--text-primary)',
              fontSize: '0.85rem',
              resize: 'vertical',
            }}
          />
        </div>

        {/* Action Buttons */}
        <div style={{ marginTop: 'auto', paddingTop: '16px', borderTop: '1px solid var(--border-subtle)', display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
          <button
            type="button"
            onClick={onClose}
            style={{
              padding: '8px 16px',
              backgroundColor: 'transparent',
              border: '1px solid var(--border-strong)',
              borderRadius: 'var(--radius-md)',
              color: 'var(--text-secondary)',
              fontSize: '0.85rem',
              cursor: 'pointer',
            }}
          >
            Anuluj
          </button>
          <button
            type="submit"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '8px 16px',
              backgroundColor: 'var(--accent-primary)',
              color: '#fff',
              border: 'none',
              borderRadius: 'var(--radius-md)',
              fontSize: '0.85rem',
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            <Check size={16} /> Zapisz proweniencję
          </button>
        </div>
      </form>
    </div>
  );
};
