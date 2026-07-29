import React from 'react';
import { Card } from '../components/common/Card';
import { Badge } from '../components/common/Badge';
import { FileSpreadsheet, Clock, Sparkles } from 'lucide-react';

export const DataExtractionPlaceholderPage: React.FC = () => {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div>
        <h2 style={{ fontSize: '1.3rem', fontWeight: 800, color: 'var(--text-primary)' }}>
          7. Ekstrakcja Danych i Synteza Dowodów (Data Extraction & Evidence Synthesis)
        </h2>
        <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
          Budowa macierzy syntezy, kodowanie zmiennych i meta-analiza zakwalifikowanych publikacji.
        </p>
      </div>

      <Card
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <FileSpreadsheet size={18} style={{ color: 'var(--accent-primary)' }} />
            <span>Zapowiedź Etapu: Macierz Ekstrakcji Danych (Phase 8+)</span>
          </div>
        }
        action={<Badge variant="pending" icon={<Clock size={12} />}>Future Workflow Step</Badge>}
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div
            style={{
              padding: '16px',
              borderRadius: 'var(--radius-md)',
              backgroundColor: 'var(--bg-primary)',
              border: '1px solid var(--border-subtle)',
              fontSize: '0.85rem',
              color: 'var(--text-secondary)',
              lineHeight: 1.6,
            }}
          >
            Moduł ekstrakcji danych pozwoli na definiowanie własnych pól kodowania (np. Metodologia badawcza, Wielkość próby, Badany sektor, Wyniki ilościowe, Wskaźniki efektywności energetycznej) oraz eksportowanie strukturyzowanych macierzy do syntezy jakościowej i meta-analizy.
          </div>

          <div
            style={{
              padding: '12px 16px',
              borderRadius: 'var(--radius-md)',
              backgroundColor: 'var(--status-info-bg)',
              border: '1px solid var(--status-info-border)',
              color: 'var(--status-info-text)',
              fontSize: '0.8rem',
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
            }}
          >
            <Sparkles size={16} />
            <span>Ten etap zostanie odblokowany automatycznie po zakończeniu Screeningu i Oceny Jakości.</span>
          </div>
        </div>
      </Card>
    </div>
  );
};
