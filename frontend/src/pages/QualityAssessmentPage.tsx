import React from 'react';
import { useProject } from '../context/ProjectContext';
import { Card } from '../components/common/Card';
import { Badge } from '../components/common/Badge';
import { Award, Clock } from 'lucide-react';

export const QualityAssessmentPage: React.FC = () => {
  const { activeProject } = useProject();

  if (!activeProject) return null;

  const qa = activeProject.qualityAssessment;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div>
        <h2 style={{ fontSize: '1.3rem', fontWeight: 800, color: 'var(--text-primary)' }}>
          6. Ocena Jakości i Ryzyka Błędu Systematycznego (Quality Assessment)
        </h2>
        <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
          Ocena metodologiczna publikacji wg list kontrolnych (CASP, MMAT, RoB-2) oraz zarządzanie konfliktami recenzentów.
        </p>
      </div>

      <Card
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Award size={18} style={{ color: 'var(--accent-primary)' }} />
            <span>Podsumowanie Postępu Oceny Jakościowej</span>
          </div>
        }
        action={<Badge variant="pending" icon={<Clock size={12} />}>Zaplanowane na Fazę 7</Badge>}
      >
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '16px' }}>
          <div style={{ padding: '14px', backgroundColor: 'var(--bg-primary)', borderRadius: 'var(--radius-md)' }}>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Wymagające Oceny</span>
            <div style={{ fontSize: '1.3rem', fontWeight: 700, color: 'var(--text-primary)', marginTop: '2px' }}>
              {qa.totalToAssess} publikacji
            </div>
          </div>

          <div style={{ padding: '14px', backgroundColor: 'var(--bg-primary)', borderRadius: 'var(--radius-md)' }}>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Ukończone Oceny</span>
            <div style={{ fontSize: '1.3rem', fontWeight: 700, color: 'var(--status-success-text)', marginTop: '2px' }}>
              {qa.completedAssessments}
            </div>
          </div>

          <div style={{ padding: '14px', backgroundColor: 'var(--bg-primary)', borderRadius: 'var(--radius-md)' }}>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Konflikty Recenzentów</span>
            <div style={{ fontSize: '1.3rem', fontWeight: 700, color: 'var(--status-warning-text)', marginTop: '2px' }}>
              {qa.reviewerConflictsCount}
            </div>
          </div>
        </div>
      </Card>

      <Card title="Kwestionariusz Oceny Metodologicznej (Coming in Phase 7)">
        <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
          W kolejnej fazie system umożliwi definiowanie szablonów kryteriów oceny (np. Jasność celu badawczego, Rygor dobóru próby, Replikowalność wyników) oraz przypisywanie 2 niezależnych recenzentów do każdej pracy.
        </p>
      </Card>
    </div>
  );
};
