import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Card } from '../common/Card';
import { Button } from '../common/Button';
import { AlertTriangle, Settings, FileSearch } from 'lucide-react';
import { QualityAssessmentReadiness } from '../../services/api/qualityAssessmentApi';

interface ReadinessAlertProps {
  projectId: string;
  readiness: QualityAssessmentReadiness;
  onOpenConfig?: () => void;
}

export const QualityAssessmentReadinessAlert: React.FC<ReadinessAlertProps> = ({
  projectId,
  readiness,
  onOpenConfig,
}) => {
  const navigate = useNavigate();

  if (readiness === 'ready') return null;

  if (readiness === 'no_quality_assessment_configuration') {
    return (
      <Card
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--status-warning-text)' }}>
            <AlertTriangle size={20} />
            <span>Brak skonfigurowanego kwestionariusza oceny jakości (Quality Assessment)</span>
          </div>
        }
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
            Projekt nie posiada jeszcze wybranego narzędzia i szablonu oceny metodologicznej (np. CASP).
            Wybierz szablon kryteriów jakościowych, aby odblokować proces oceny publikacji zakwalifikowanych w etapie Full-Text.
          </p>

          <div>
            <Button
              variant="primary"
              icon={<Settings size={16} />}
              onClick={() => {
                if (onOpenConfig) {
                  onOpenConfig();
                } else {
                  navigate(`/projects/${projectId}/quality-assessment/configuration`);
                }
              }}
            >
              Skonfiguruj Szablon Quality Assessment
            </Button>
          </div>
        </div>
      </Card>
    );
  }

  if (readiness === 'no_eligible_publications') {
    return (
      <Card
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-secondary)' }}>
            <FileSearch size={20} />
            <span>Brak zakwalifikowanych publikacji do Oceny Jakości</span>
          </div>
        }
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
            Żadna publikacja nie została jeszcze zakwalifikowana (decyzja <strong>WŁĄCZ / INCLUDE</strong>) przez aktualnego recenzenta w etapie <strong>Full-Text Screening</strong>.
          </p>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
            Wróć do etapu Full-Text Screening, dokończ ocenę pełnych tekstów, a następnie przejdź do oceny jakościowej wyłonionych prac.
          </p>

          <div>
            <Button
              variant="secondary"
              icon={<FileSearch size={16} />}
              onClick={() => navigate(`/projects/${projectId}/screen/full-text`)}
            >
              Przejdź do Full-Text Screening
            </Button>
          </div>
        </div>
      </Card>
    );
  }

  return null;
};
