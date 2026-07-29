import React from 'react';
import { useProject } from '../context/ProjectContext';
import { Card } from '../components/common/Card';
import { Badge } from '../components/common/Badge';
import { Sparkles, CheckCircle2, ShieldCheck } from 'lucide-react';

export const NormalizationPage: React.FC = () => {
  const { activeProject } = useProject();

  if (!activeProject) return null;

  const norm = activeProject.normalization[0];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div>
        <h2 style={{ fontSize: '1.3rem', fontWeight: 800, color: 'var(--text-primary)' }}>
          3. Normalizacja i Jakość Danych Canonical (Data Normalization)
        </h2>
        <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
          Czyszczenie i sprowadzanie metadanych (DOI, autorzy, ORCID, ISSN) do postaci canonical.
        </p>
      </div>

      {!norm ? (
        <Card title="Normalizacja oczekuje na uruchomienie">
          <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
            Uruchom wyszukiwanie lub zaimportuj pliki, aby wykonać automatyczną normalizację kanoniczną.
          </p>
        </Card>
      ) : (
        <>
          <Card
            title={
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Sparkles size={18} style={{ color: 'var(--status-success-text)' }} />
                <span>Status Normalizacji Kanonicznej</span>
              </div>
            }
            action={<Badge variant="completed" icon={<CheckCircle2 size={12} />}>Wykonano</Badge>}
          >
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '16px' }}>
              <div style={{ padding: '14px', backgroundColor: 'var(--bg-primary)', borderRadius: 'var(--radius-md)' }}>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Przetworzone Rekordy</span>
                <div style={{ fontSize: '1.3rem', fontWeight: 700, color: 'var(--text-primary)', marginTop: '2px' }}>
                  {norm.totalRecordsProcessed.toLocaleString()}
                </div>
              </div>

              <div style={{ padding: '14px', backgroundColor: 'var(--status-success-bg)', borderRadius: 'var(--radius-md)', border: '1px solid var(--status-success-border)' }}>
                <span style={{ fontSize: '0.75rem', color: 'var(--status-success-text)', fontWeight: 600 }}>Czyste Rekordy Canonical</span>
                <div style={{ fontSize: '1.3rem', fontWeight: 700, color: 'var(--status-success-text)', marginTop: '2px' }}>
                  {norm.cleanRecordsCount.toLocaleString()}
                </div>
              </div>

              <div style={{ padding: '14px', backgroundColor: 'var(--bg-primary)', borderRadius: 'var(--radius-md)' }}>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Ostrzeżenia Formatowania</span>
                <div style={{ fontSize: '1.3rem', fontWeight: 700, color: 'var(--status-warning-text)', marginTop: '2px' }}>
                  {norm.warningsCount}
                </div>
              </div>
            </div>
          </Card>

          <Card title="Dziennik Wykonanych Reguł Normalizacyjnych (Normalization Audit Trail)">
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {norm.warningsLog.map((log, idx) => (
                <div
                  key={idx}
                  style={{
                    padding: '10px 14px',
                    backgroundColor: 'var(--bg-primary)',
                    borderRadius: 'var(--radius-md)',
                    border: '1px solid var(--border-subtle)',
                    fontSize: '0.85rem',
                    color: 'var(--text-secondary)',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '10px',
                  }}
                >
                  <ShieldCheck size={16} style={{ color: 'var(--status-success-text)' }} />
                  <span>{log}</span>
                </div>
              ))}
            </div>
          </Card>
        </>
      )}
    </div>
  );
};
