import React from 'react';
import { ArrowDown, Database, FileSpreadsheet, GitMerge, Filter, Award, CheckCircle2, FileText, FolderKanban, Globe, BookOpen, Database as DatabaseIcon } from 'lucide-react';
import { PrismaFunnelMetrics, ManualSourceDatabase, MANUAL_SOURCE_DATABASE_LABELS } from '../../types';

interface LivePrismaFlowChartProps {
  metrics: PrismaFunnelMetrics;
}

export const LivePrismaFlowChart: React.FC<LivePrismaFlowChartProps> = ({ metrics }) => {
  const getSourceIcon = (source: string): React.ReactNode => {
    switch (source) {
      case 'google_scholar_pop':
        return <Globe size={14} />;
      case 'scopus':
        return <DatabaseIcon size={14} />;
      case 'web_of_science':
        return <Globe size={14} />;
      case 'pubmed':
        return <BookOpen size={14} />;
      case 'ebsco':
        return <DatabaseIcon size={14} />;
      case 'proquest':
        return <Globe size={14} />;
      case 'other':
        return <FolderKanban size={14} />;
      default:
        return <FileText size={14} />;
    }
  };

  const getSourceLabel = (source: string): string => {
    return MANUAL_SOURCE_DATABASE_LABELS[source as ManualSourceDatabase] ?? source;
  };

  const manualBreakdown = metrics.manualSourceBreakdown ?? {};

  return (
    <div
      style={{
        backgroundColor: 'var(--bg-surface)',
        borderRadius: 'var(--radius-lg)',
        border: '1px solid var(--border-subtle)',
        padding: '24px',
        display: 'flex',
        flexDirection: 'column',
        gap: '20px',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h3 style={{ fontSize: '1.05rem', fontWeight: 700, color: 'var(--text-primary)' }}>
            Dynamic PRISMA 2020 Flow Diagram
          </h3>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '2px' }}>
            Żywy schemat przepływu rekordów zaktualizowany na żywo z wyników backendu.
          </p>
        </div>
        <span
          style={{
            fontSize: '0.75rem',
            padding: '4px 8px',
            borderRadius: 'var(--radius-full)',
            backgroundColor: 'var(--status-info-bg)',
            color: 'var(--status-info-text)',
            border: '1px solid var(--status-info-border)',
            fontWeight: 600,
          }}
        >
          PRISMA 2020 Compliant
        </span>
      </div>

      {/* PRISMA 2020 Flow Stages Diagram */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', alignItems: 'center' }}>
        {/* Stage 1: Identification */}
        <div style={{ width: '100%', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
          <div
            style={{
              padding: '14px 18px',
              backgroundColor: 'var(--bg-primary)',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--border-strong)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-muted)', fontSize: '0.75rem', fontWeight: 600 }}>
              <Database size={14} />
              <span>LIVE API PROVIDERS</span>
            </div>
            <div style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--text-primary)', marginTop: '4px' }}>
              {metrics.recordsIdentifiedProviders.toLocaleString()} rekordów
            </div>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>OpenAlex, Crossref, Semantic Scholar</span>
          </div>

          <div
            style={{
              padding: '14px 18px',
              backgroundColor: 'var(--bg-primary)',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--border-strong)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-muted)', fontSize: '0.75rem', fontWeight: 600 }}>
              <FileSpreadsheet size={14} />
              <span>MANUAL FILE IMPORTS</span>
            </div>
            <div style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--text-primary)', marginTop: '4px' }}>
              {metrics.recordsIdentifiedImports.toLocaleString()} rekordów
            </div>
            {Object.keys(manualBreakdown).length > 0 && (
              <div style={{ marginTop: '12px', display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                {Object.entries(manualBreakdown).map(([source, count]) => (
                  <span
                    key={source}
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '4px',
                      fontSize: '0.7rem',
                      color: 'var(--text-secondary)',
                      backgroundColor: 'var(--bg-surface-elevated)',
                      padding: '4px 8px',
                      borderRadius: 'var(--radius-sm)',
                      border: '1px solid var(--border-subtle)',
                    }}
                  >
                    {getSourceIcon(source)}
                    <span>{getSourceLabel(source)}: {count.toLocaleString()}</span>
                  </span>
                ))}
              </div>
            )}
            {Object.keys(manualBreakdown).length === 0 && (
              <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Pliki BibTeX, RIS (np. wyeksportowane z Google Scholar, Scopus)</span>
            )}
          </div>
        </div>

        <ArrowDown size={18} style={{ color: 'var(--accent-primary)' }} />

        {/* Total Identified */}
        <div
          style={{
            width: '100%',
            padding: '12px 20px',
            backgroundColor: 'var(--bg-surface-elevated)',
            borderRadius: 'var(--radius-md)',
            border: '1px solid var(--accent-primary)',
            textAlign: 'center',
          }}
        >
          <span style={{ fontSize: '0.75rem', color: 'var(--accent-light)', textTransform: 'uppercase', fontWeight: 600 }}>
            Łącznie Zidentyfikowano Rekordów (Total Identified Records)
          </span>
          <div style={{ fontSize: '1.4rem', fontWeight: 800, color: 'var(--text-primary)' }}>
            {metrics.totalIdentified.toLocaleString()}
          </div>
        </div>

        <ArrowDown size={18} style={{ color: 'var(--accent-primary)' }} />

        {/* Deduplication Stage */}
        <div
          style={{
            width: '100%',
            display: 'grid',
            gridTemplateColumns: '2fr 1fr',
            gap: '16px',
            padding: '16px',
            backgroundColor: 'var(--bg-primary)',
            borderRadius: 'var(--radius-md)',
            border: '1px solid var(--border-strong)',
          }}
        >
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--status-info-text)', fontSize: '0.8rem', fontWeight: 600 }}>
              <GitMerge size={16} />
              <span>Techniczny Merge DOI (ResultMerger)</span>
            </div>
            <div style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--text-primary)', marginTop: '4px' }}>
              {metrics.recordsAfterTechnicalMerger.toLocaleString()} unikalnych rekordów
            </div>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
              Usunięto rekordy z identycznym canonical DOI
            </span>
          </div>

          <div
            style={{
              padding: '10px 14px',
              backgroundColor: 'var(--status-warning-bg)',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--status-warning-border)',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'center',
            }}
          >
            <span style={{ fontSize: '0.7rem', color: 'var(--status-warning-text)', fontWeight: 700, textTransform: 'uppercase' }}>
              Weryfikacja Badacza
            </span>
            <div style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--text-primary)' }}>
              {metrics.duplicateGroupsPendingReview} grup
            </div>
            <span style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>
              Fuzzy duplikaty do oceny
            </span>
          </div>
        </div>

        <ArrowDown size={18} style={{ color: 'var(--accent-primary)' }} />

        {/* Screening Stage */}
        <div style={{ width: '100%', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
          <div
            style={{
              padding: '14px 18px',
              backgroundColor: 'var(--bg-primary)',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--border-strong)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--status-info-text)', fontSize: '0.8rem', fontWeight: 600 }}>
              <Filter size={16} />
              <span>Triage Tytuł / Abstrakt</span>
            </div>
            <div style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--text-primary)', marginTop: '4px' }}>
              {metrics.recordsScreenedTitleAbstract.toLocaleString()} ocenionych
            </div>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
              Włączono do kolejnego etapu
            </span>
          </div>

          <div
            style={{
              padding: '14px 18px',
              backgroundColor: 'var(--bg-primary)',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--border-strong)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-muted)', fontSize: '0.8rem', fontWeight: 600 }}>
              <Award size={16} />
              <span>Full-Text & Quality Assessment</span>
            </div>
            <div style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--text-primary)', marginTop: '4px' }}>
              {metrics.recordsScreenedFullText.toLocaleString()} ukończonych
            </div>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
              Pełny tekst i kryteria jakościowe
            </span>
          </div>
        </div>

        <ArrowDown size={18} style={{ color: 'var(--accent-primary)' }} />

        {/* Final Included */}
        <div
          style={{
            width: '100%',
            padding: '14px 20px',
            backgroundColor: 'var(--status-success-bg)',
            borderRadius: 'var(--radius-md)',
            border: '1px solid var(--status-success-border)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <CheckCircle2 size={20} style={{ color: 'var(--status-success-text)' }} />
            <div>
              <div style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--status-success-text)', textTransform: 'uppercase' }}>
                Studia Zakwalifikowane do Ekstrakcji (Included in Synthesis)
              </div>
              <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                Finalna próba publikacji zakwalifikowana do analizy jakościowej i ilościowej
              </span>
            </div>
          </div>
          <div style={{ fontSize: '1.5rem', fontWeight: 800, color: 'var(--status-success-text)' }}>
            {metrics.studiesIncludedSynthesis.toLocaleString()}
          </div>
        </div>
      </div>
    </div>
  );
};
