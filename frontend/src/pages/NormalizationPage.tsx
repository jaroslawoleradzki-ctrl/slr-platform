import React, { useState } from 'react';
import { useProject } from '../context/ProjectContext';
import { Card } from '../components/common/Card';
import { Badge } from '../components/common/Badge';
import { Button } from '../components/common/Button';
import { Toast } from '../components/common/Toast';
import { ErrorAlert } from '../components/common/ErrorAlert';
import { Sparkles, CheckCircle2, ShieldCheck, RotateCw } from 'lucide-react';

export const NormalizationPage: React.FC = () => {
  const { activeProject, runNormalization } = useProject();
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  if (!activeProject) return null;

  const norm = activeProject.normalization[0];
  const run = async () => {
    setRunning(true);
    setError(null);
    setToastMessage(null);
    try {
      await runNormalization();
      setToastMessage('Normalizacja została wykonana ponownie.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Nie udało się uruchomić normalizacji.');
    } finally {
      setRunning(false);
    }
  };

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

      {error && <ErrorAlert title="Błąd podczas normalizacji" message={error} />}
      {toastMessage && (
        <Toast message={toastMessage} type="success" onClose={() => setToastMessage(null)} />
      )}

      {!norm ? (
        <Card title="Normalizacja oczekuje na uruchomienie" action={<Badge variant="pending">Nie uruchamiano</Badge>}>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
            Normalizacja nie została jeszcze uruchomiona dla tego projektu.
          </p>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '16px', marginTop: '12px' }}>
            {['Przetworzone rekordy', 'Czyste rekordy canonical', 'Ostrzeżenia'].map((label) => (
              <div key={label} style={{ padding: '14px', backgroundColor: 'var(--bg-primary)', borderRadius: 'var(--radius-md)' }}>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{label}</span>
                <div style={{ fontSize: '0.95rem', color: 'var(--text-secondary)', marginTop: '4px' }}>Brak danych</div>
              </div>
            ))}
          </div>
          <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '16px' }}>
            <Button
              variant="primary"
              onClick={run}
              isLoading={running}
              loadingText="Normalizowanie..."
              icon={<RotateCw size={16} />}
            >
              Uruchom normalizację
            </Button>
          </div>
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
            action={<Badge variant={norm.status === 'warning' ? 'pending_action' : norm.status === 'error' ? 'error' : 'completed'} icon={<CheckCircle2 size={12} />}>{norm.status === 'warning' ? 'Ostrzeżenia' : norm.status === 'error' ? 'Błąd' : 'Wykonano'}</Badge>}
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
              {norm.warningsLog.length === 0 ? (
                <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>Brak wpisów audytu.</p>
              ) : norm.warningsLog.map((log, idx) => (
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
            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '16px' }}>
              <Button
                variant="primary"
                onClick={run}
                isLoading={running}
                loadingText="Normalizowanie..."
                icon={<RotateCw size={16} />}
              >
                Uruchom ponownie normalizację
              </Button>
            </div>
          </Card>
        </>
      )}
    </div>
  );
};
