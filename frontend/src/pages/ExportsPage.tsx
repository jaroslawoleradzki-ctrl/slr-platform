import React, { useState } from 'react';
import { useProject } from '../context/ProjectContext';
import { Card } from '../components/common/Card';
import { ErrorAlert } from '../components/common/ErrorAlert';
import { LivePrismaFlowChart } from '../components/workflow/LivePrismaFlowChart';
import { extractionApi, ExtractionApiError } from '../services/api/extractionApi';
import { FileCheck2, Download, FileSpreadsheet, Code2, Share2, Layers, Loader2, Lock } from 'lucide-react';

interface ExportFormat {
  id: string;
  name: string;
  desc: string;
  icon: React.ElementType;
  available: boolean;
}

export const ExportsPage: React.FC = () => {
  const { activeProject } = useProject();
  const [exportingId, setExportingId] = useState<string | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);
  const [exportSuccess, setExportSuccess] = useState<string | null>(null);

  const exportFormats: ExportFormat[] = [
    { id: 'csv', name: 'Zestawienie Rekordów CSV', desc: 'Dane publikacji i wyników ekstrakcji w formacie CSV (metadane, DOI, status kompletności)', icon: FileSpreadsheet, available: true },
    { id: 'json', name: 'Zestawienie rekordów JSON', desc: 'Dane publikacji i wyników ekstrakcji w formacie JSON', icon: Share2, available: true },
    { id: 'bib', name: 'Eksport Bazy BibTeX (.bib)', desc: 'Format kanoniczny dla systemów LaTeX i Reference Managerów', icon: Code2, available: false },
    { id: 'ris', name: 'Eksport Bazy RIS (.ris)', desc: 'Format zgodny z EndNote, Zotero, Mendeley i RefMan', icon: Download, available: false },
    { id: 'excel', name: 'Arkusz Excel Matrix (.xlsx)', desc: 'Tabela syntezy z podziałem na etapy i statusy decyzji', icon: FileSpreadsheet, available: false },
  ];

  if (!activeProject) return null;

  const handleExport = async (format: ExportFormat) => {
    if (!format.available) return;
    setExportingId(format.id);
    setExportError(null);
    setExportSuccess(null);
    try {
      const blob = await extractionApi.exportDataset(activeProject.id, format.id as 'json' | 'csv', 'publications');
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `${activeProject.id}_publications.${format.id}`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      setTimeout(() => {
        URL.revokeObjectURL(url);
      }, 0);
      setExportSuccess(`Pobrano plik ${format.name} dla projektu ${activeProject.title}.`);
    } catch (err) {
      setExportError(err instanceof ExtractionApiError ? err.message : 'Nie udało się pobrać eksportu danych.');
    } finally {
      setExportingId(null);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div>
        <h2 style={{ fontSize: '1.3rem', fontWeight: 800, color: 'var(--text-primary)' }}>
          8. Eksporty i Generowanie Raportu PRISMA (Exports & Reporting)
        </h2>
        <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
          Eksport bazy danych w powszechnych formatach badawczych oraz generowanie oficjalnego schematu PRISMA 2020 Flow.
        </p>
      </div>

      {exportError && <ErrorAlert message={exportError} />}
      {exportSuccess && (
        <div
          role="status"
          style={{
            padding: '12px 16px',
            borderRadius: 'var(--radius-md)',
            backgroundColor: 'var(--status-success-bg)',
            border: '1px solid var(--status-success-border)',
            color: 'var(--status-success-text)',
            fontSize: '0.85rem',
            fontWeight: 600,
          }}
        >
          {exportSuccess}
        </div>
      )}

      <Card
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <FileCheck2 size={18} style={{ color: 'var(--accent-primary)' }} />
            <span>Dostępne Formaty Eksportu Danych Badawczych</span>
          </div>
        }
      >
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '16px' }}>
          {exportFormats.map((fmt) => {
            const Icon = fmt.icon;
            return (
              <div
                key={fmt.id}
                style={{
                  padding: '16px',
                  backgroundColor: 'var(--bg-primary)',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--border-subtle)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <div
                    style={{
                      width: '36px',
                      height: '36px',
                      borderRadius: 'var(--radius-md)',
                      backgroundColor: 'var(--bg-surface-elevated)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      color: fmt.available ? 'var(--accent-primary)' : 'var(--text-muted)',
                    }}
                  >
                    <Icon size={18} />
                  </div>
                  <div>
                    <h4 style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                      {fmt.name}
                    </h4>
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                      {fmt.desc}
                    </span>
                  </div>
                </div>

                {fmt.available ? (
                  <button
                    onClick={() => handleExport(fmt)}
                    disabled={exportingId !== null}
                    style={{
                      padding: '6px 12px',
                      borderRadius: 'var(--radius-md)',
                      backgroundColor: 'var(--bg-surface-elevated)',
                      border: '1px solid var(--border-strong)',
                      color: 'var(--text-primary)',
                      fontSize: '0.75rem',
                      fontWeight: 600,
                      whiteSpace: 'nowrap',
                      cursor: exportingId !== null ? 'not-allowed' : 'pointer',
                      opacity: exportingId !== null && exportingId !== fmt.id ? 0.6 : 1,
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '6px',
                    }}
                    title="Pobierz eksport"
                  >
                    {exportingId === fmt.id && <Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} />}
                    {exportingId === fmt.id ? 'Pobieranie...' : 'Pobierz'}
                  </button>
                ) : (
                  <button
                    disabled
                    style={{
                      padding: '6px 12px',
                      borderRadius: 'var(--radius-md)',
                      backgroundColor: 'var(--bg-surface-elevated)',
                      border: '1px dashed var(--border-subtle)',
                      color: 'var(--text-muted)',
                      fontSize: '0.75rem',
                      fontWeight: 600,
                      whiteSpace: 'nowrap',
                      cursor: 'not-allowed',
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '6px',
                      opacity: 0.8,
                    }}
                    title="Not yet available"
                  >
                    <Lock size={14} />
                    Not yet available
                  </button>
                )}
              </div>
            );
          })}
        </div>
      </Card>

      <Card
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Layers size={18} style={{ color: 'var(--status-info-text)' }} />
            <span>Generowanie Schematu i Raportu PRISMA 2020 Flow Diagram</span>
          </div>
        }
        subtitle="Eksportuj wygenerowany wyżej schemat PRISMA do formatów SVG, PNG lub PDF dla celów publikacyjnych."
        action={
          <button
            disabled
            style={{
              padding: '8px 16px',
              borderRadius: 'var(--radius-md)',
              backgroundColor: 'var(--bg-surface-elevated)',
              color: 'var(--text-muted)',
              fontWeight: 600,
              fontSize: '0.85rem',
              border: '1px dashed var(--border-subtle)',
              cursor: 'not-allowed',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
            }}
            title="Not yet available"
          >
            <Lock size={14} />
            Eksportuj PRISMA Flow (SVG/PDF) — Not yet available
          </button>
        }
      >
        <LivePrismaFlowChart metrics={activeProject.prismaMetrics} />
        <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', lineHeight: 1.5 }}>
          Dane do diagramu PRISMA nie są jeszcze dostępne z backendu. Diagram zostanie automatycznie uzupełniony po wdrożeniu raportowania metryk projektu.
        </div>
      </Card>
    </div>
  );
};
