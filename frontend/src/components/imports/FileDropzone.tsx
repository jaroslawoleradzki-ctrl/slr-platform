import React, { useState } from 'react';
import { Upload, FileText, CheckCircle2, AlertTriangle } from 'lucide-react';
import { ImportFileRecord } from '../../types';
import { Card } from '../common/Card';
import { Badge } from '../common/Badge';

interface FileDropzoneProps {
  onFileSelect?: (filename: string, format: 'BibTeX' | 'RIS') => void;
  imports: ImportFileRecord[];
}

export const FileDropzone: React.FC<FileDropzoneProps> = ({ onFileSelect, imports }) => {
  const [dragActive, setDragActive] = useState(false);

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const file = e.dataTransfer.files[0];
      const fmt = file.name.endsWith('.bib') ? 'BibTeX' : 'RIS';
      if (onFileSelect) onFileSelect(file.name, fmt);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <Card
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Upload size={18} style={{ color: 'var(--accent-primary)' }} />
            <span>Ręczny Import Plików Bibliograficznych (BibTeX & RIS)</span>
          </div>
        }
        subtitle="Wspierane formaty: pliki .ris i .bib wyeksportowane z serwisów zewnętrznych (Google Scholar, Scopus, Web of Science, EndNote)"
      >
        <div
          onDragEnter={handleDrag}
          onDragOver={handleDrag}
          onDragLeave={handleDrag}
          onDrop={handleDrop}
          style={{
            border: `2px dashed ${dragActive ? 'var(--accent-primary)' : 'var(--border-strong)'}`,
            borderRadius: 'var(--radius-lg)',
            padding: '32px 20px',
            textAlign: 'center',
            backgroundColor: dragActive ? 'var(--accent-subtle)' : 'var(--bg-primary)',
            transition: 'all 0.15s ease',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: '12px',
          }}
        >
          <div
            style={{
              width: '48px',
              height: '48px',
              borderRadius: '50%',
              backgroundColor: 'var(--bg-surface-elevated)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--accent-primary)',
            }}
          >
            <Upload size={24} />
          </div>
          <div>
            <h4 style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--text-primary)' }}>
              Przeciągnij plik .ris lub .bib tutaj
            </h4>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '2px' }}>
              lub wybierz plik z dysku komputera
            </p>
          </div>
          <button
            onClick={() => {
              if (onFileSelect) onFileSelect('custom_import_export.ris', 'RIS');
            }}
            style={{
              padding: '8px 16px',
              borderRadius: 'var(--radius-md)',
              backgroundColor: 'var(--accent-primary)',
              color: '#fff',
              fontWeight: 600,
              fontSize: '0.85rem',
            }}
          >
            Wybierz Plik
          </button>
        </div>
      </Card>

      {/* Import History Table */}
      <Card title="Historia Zaimportowanych Plików w Projekcie">
        {imports.length === 0 ? (
          <div style={{ padding: '16px 0', textTransform: 'none', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
            Brak zaimportowanych plików w tym projekcie.
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {imports.map((item) => (
              <div
                key={item.id}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '12px 16px',
                  backgroundColor: 'var(--bg-primary)',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--border-subtle)',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <FileText size={20} style={{ color: 'var(--accent-primary)' }} />
                  <div>
                    <div style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                      {item.filename}
                    </div>
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                      Format: {item.format} • {new Date(item.importedAt).toLocaleString('pl-PL')}
                    </span>
                  </div>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                  <div style={{ textAlign: 'right' }}>
                    <div style={{ fontSize: '0.95rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                      {item.recordsCount} rekordów
                    </div>
                  </div>
                  {item.status === 'success' ? (
                    <Badge variant="completed" icon={<CheckCircle2 size={12} />}>Zaimportowano</Badge>
                  ) : (
                    <Badge variant="pending_action" icon={<AlertTriangle size={12} />}>Ostrzeżenie</Badge>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
};
