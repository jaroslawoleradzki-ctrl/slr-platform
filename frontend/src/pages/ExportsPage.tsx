import React, { useState } from 'react';
import { useProject } from '../context/ProjectContext';
import { Card } from '../components/common/Card';
import { ErrorAlert } from '../components/common/ErrorAlert';
import { LivePrismaFlowChart } from '../components/workflow/LivePrismaFlowChart';
import { extractionApi, ExtractionApiError } from '../services/api/extractionApi';
import { exportApi, ExportApiError } from '../services/api/exportApi';
import { useReviewerIdentity } from '../hooks/useReviewerIdentity';
import { triggerBlobDownload } from '../utils/downloadHelper';
import { FileCheck2, Download, FileSpreadsheet, Code2, Share2, Layers, Loader2, FileCode2 } from 'lucide-react';

interface ExportFormat {
  id: 'csv' | 'json' | 'bib' | 'ris' | 'excel';
  name: string;
  desc: string;
  icon: React.ElementType;
  available: boolean;
}

export const ExportsPage: React.FC = () => {
  const { activeProject, prismaMetricsLoading, prismaMetricsError } = useProject();
  const { reviewerId } = useReviewerIdentity();
  const [exportingId, setExportingId] = useState<string | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);
  const [exportSuccess, setExportSuccess] = useState<string | null>(null);

  const exportFormats: ExportFormat[] = [
    { id: 'csv', name: 'Zestawienie Rekordów CSV', desc: 'Dane publikacji i wyników ekstrakcji w formacie CSV (metadane, DOI, status kompletności)', icon: FileSpreadsheet, available: true },
    { id: 'json', name: 'Zestawienie rekordów JSON', desc: 'Dane publikacji i wyników ekstrakcji w formacie JSON', icon: Share2, available: true },
    { id: 'bib', name: 'Eksport Bazy BibTeX (.bib)', desc: 'Format kanoniczny dla systemów LaTeX i Reference Managerów', icon: Code2, available: true },
    { id: 'ris', name: 'Eksport Bazy RIS (.ris)', desc: 'Format zgodny z EndNote, Zotero, Mendeley i RefMan', icon: Download, available: true },
    { id: 'excel', name: 'Arkusz Excel Matrix (.xlsx)', desc: 'Tabela syntezy z podziałem na etapy i statusy decyzji', icon: FileSpreadsheet, available: true },
  ];

  if (!activeProject) return null;

  const handleExport = async (format: ExportFormat) => {
    if (!format.available || exportingId !== null) return;
    setExportingId(format.id);
    setExportError(null);
    setExportSuccess(null);
    try {
      let blob: Blob;
      let filename: string;
      const activeReviewer = reviewerId || undefined;

      switch (format.id) {
        case 'csv':
          blob = await extractionApi.exportDataset(activeProject.id, 'csv', 'publications', activeReviewer);
          filename = `${activeProject.id}_publications.csv`;
          break;
        case 'json':
          blob = await extractionApi.exportDataset(activeProject.id, 'json', 'publications', activeReviewer);
          filename = `${activeProject.id}_publications.json`;
          break;
        case 'bib':
          blob = await exportApi.exportBibtex(activeProject.id);
          filename = `${activeProject.id}_publications.bib`;
          break;
        case 'ris':
          blob = await exportApi.exportRis(activeProject.id);
          filename = `${activeProject.id}_publications.ris`;
          break;
        case 'excel':
          blob = await exportApi.exportXlsx(activeProject.id, activeReviewer);
          filename = `${activeProject.id}_publications.xlsx`;
          break;
        default:
          throw new Error(`Unsupported export format: ${format.id}`);
      }

      triggerBlobDownload(blob, filename);
      setExportSuccess(`Pobrano plik ${format.name} dla projektu ${activeProject.title}.`);
    } catch (err) {
      if (err instanceof ExtractionApiError || err instanceof ExportApiError) {
        setExportError(err.message);
      } else if (err instanceof Error) {
        setExportError(err.message);
      } else {
        setExportError('Nie udało się pobrać eksportu danych.');
      }
    } finally {
      setExportingId(null);
    }
  };

  const handlePrismaExport = async (format: 'svg' | 'pdf') => {
    const actionId = `prisma_${format}`;
    if (exportingId !== null) return;
    setExportingId(actionId);
    setExportError(null);
    setExportSuccess(null);
    try {
      let blob: Blob;
      let filename: string;
      const activeReviewer = reviewerId || undefined;

      if (format === 'svg') {
        blob = await exportApi.exportPrismaSvg(activeProject.id, activeReviewer);
        filename = `${activeProject.id}_prisma_flow.svg`;
      } else {
        blob = await exportApi.exportPrismaPdf(activeProject.id, activeReviewer);
        filename = `${activeProject.id}_prisma_flow.pdf`;
      }

      triggerBlobDownload(blob, filename);
      const label = format === 'svg' ? 'PRISMA Flow (SVG)' : 'PRISMA Flow (PDF)';
      setExportSuccess(`Pobrano plik ${label} dla projektu ${activeProject.title}.`);
    } catch (err) {
      if (err instanceof ExportApiError || err instanceof ExtractionApiError) {
        setExportError(err.message);
      } else if (err instanceof Error) {
        setExportError(err.message);
      } else {
        setExportError('Nie udało się pobrać schematu PRISMA.');
      }
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
                      color: 'var(--accent-primary)',
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
        subtitle="Eksportuj wygenerowany wyżej schemat PRISMA do formatów SVG lub PDF dla celów publikacyjnych."
        action={
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <button
              onClick={() => handlePrismaExport('svg')}
              disabled={exportingId !== null}
              style={{
                padding: '8px 14px',
                borderRadius: 'var(--radius-md)',
                backgroundColor: 'var(--bg-surface-elevated)',
                color: 'var(--text-primary)',
                fontWeight: 600,
                fontSize: '0.85rem',
                border: '1px solid var(--border-strong)',
                cursor: exportingId !== null ? 'not-allowed' : 'pointer',
                opacity: exportingId !== null && exportingId !== 'prisma_svg' ? 0.6 : 1,
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
              }}
              title="Pobierz schemat PRISMA w formacie SVG"
            >
              {exportingId === 'prisma_svg' ? (
                <Loader2 size={15} style={{ animation: 'spin 1s linear infinite' }} />
              ) : (
                <FileCode2 size={15} style={{ color: 'var(--accent-primary)' }} />
              )}
              {exportingId === 'prisma_svg' ? 'Pobieranie SVG...' : 'Pobierz SVG'}
            </button>
            <button
              onClick={() => handlePrismaExport('pdf')}
              disabled={exportingId !== null}
              style={{
                padding: '8px 14px',
                borderRadius: 'var(--radius-md)',
                backgroundColor: 'var(--bg-surface-elevated)',
                color: 'var(--text-primary)',
                fontWeight: 600,
                fontSize: '0.85rem',
                border: '1px solid var(--border-strong)',
                cursor: exportingId !== null ? 'not-allowed' : 'pointer',
                opacity: exportingId !== null && exportingId !== 'prisma_pdf' ? 0.6 : 1,
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
              }}
              title="Pobierz schemat PRISMA w formacie PDF"
            >
              {exportingId === 'prisma_pdf' ? (
                <Loader2 size={15} style={{ animation: 'spin 1s linear infinite' }} />
              ) : (
                <Download size={15} style={{ color: 'var(--accent-primary)' }} />
              )}
              {exportingId === 'prisma_pdf' ? 'Pobieranie PDF...' : 'Pobierz PDF'}
            </button>
          </div>
        }
      >
        {prismaMetricsLoading ? (
          <div
            role="status"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
              padding: '20px',
              fontSize: '0.85rem',
              color: 'var(--text-secondary)',
            }}
          >
            <Loader2 size={18} style={{ animation: 'spin 1s linear infinite', color: 'var(--accent-primary)' }} />
            Ładowanie żywych metryk PRISMA z backendu...
          </div>
        ) : prismaMetricsError ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <ErrorAlert message={prismaMetricsError} />
            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', lineHeight: 1.5 }}>
              Diagram PRISMA jest niedostępny, ponieważ nie udało się pobrać metryk z backendu. Sprawdź połączenie i odśwież dane projektu.
            </div>
          </div>
        ) : (
          <>
            <LivePrismaFlowChart metrics={activeProject.prismaMetrics} />
            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', lineHeight: 1.5 }}>
              Diagram odzwierciedla bieżący stan przebiegu procesu SLR na podstawie metryk pobranych z backendu. Po ukończeniu wszystkich etapów (deduplikacji, screeningu i oceny jakości) diagram może stanowić podstawę oficjalnego raportu PRISMA 2020.
            </div>
          </>
        )}
      </Card>
    </div>
  );
};
