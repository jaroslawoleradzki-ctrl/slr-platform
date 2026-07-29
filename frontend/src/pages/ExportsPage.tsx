import React from 'react';
import { useProject } from '../context/ProjectContext';
import { Card } from '../components/common/Card';
import { FileCheck2, Download, FileSpreadsheet, Code2, Share2, Layers } from 'lucide-react';

export const ExportsPage: React.FC = () => {
  const { activeProject } = useProject();

  if (!activeProject) return null;

  const exportFormats = [
    { id: 'csv', name: 'Zestawienie Rekordów CSV', desc: 'Pełna tabela z metadanymi, DOI, abstrakty i tagi', icon: FileSpreadsheet },
    { id: 'bib', name: 'Eksport Bazy BibTeX (.bib)', desc: 'Format kanoniczny dla systemów LaTeX i Reference Managerów', icon: Code2 },
    { id: 'ris', name: 'Eksport Bazy RIS (.ris)', desc: 'Format zgodny z EndNote, Zotero, Mendeley i RefMan', icon: Download },
    { id: 'json', name: 'Struktura JSON Project Dump', desc: 'Pełny dump stanu projektu SLR ze statystykami i audit trailem', icon: Share2 },
    { id: 'excel', name: 'Arkusz Excel Matrix (.xlsx)', desc: 'Tabela syntezy z podziałem na etapy i statusy decyzji', icon: FileSpreadsheet },
  ];

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
                  style={{
                    padding: '6px 12px',
                    borderRadius: 'var(--radius-md)',
                    backgroundColor: 'var(--bg-surface-elevated)',
                    border: '1px solid var(--border-strong)',
                    color: 'var(--text-primary)',
                    fontSize: '0.75rem',
                    fontWeight: 600,
                    whiteSpace: 'nowrap',
                  }}
                  title="Pobierz eksport"
                >
                  Pobierz
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
        subtitle="Eksportuj wygenerowany wyżej schemat PRISMA do formatów SVG, PNG lub PDF dla celów publikacyjnych."
        action={
          <button
            style={{
              padding: '8px 16px',
              borderRadius: 'var(--radius-md)',
              backgroundColor: 'var(--accent-primary)',
              color: '#fff',
              fontWeight: 600,
              fontSize: '0.85rem',
            }}
          >
            Eksportuj PRISMA Flow (SVG/PDF)
          </button>
        }
      >
        <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
          Generowany raport zawiera dokładne zliczenia rekordów na każdym etapie (Live Providers, Manual Imports, Exact DOI Merges, Deduplication Decisions, Screening Triage, Full-Text Eligibility oraz Included Studies) w pełnej zgodności ze standardem PRISMA 2020 Statement.
        </div>
      </Card>
    </div>
  );
};
