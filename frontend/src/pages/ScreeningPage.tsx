import React from 'react';
import { useProject } from '../context/ProjectContext';
import { ScreeningPipelineOverview } from '../components/screening/ScreeningPipelineOverview';

export const ScreeningPage: React.FC = () => {
  const { activeProject } = useProject();

  if (!activeProject) return null;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div>
        <h2 style={{ fontSize: '1.3rem', fontWeight: 800, color: 'var(--text-primary)' }}>
          5. Seleksja i Screening Publikacji (Study Screening)
        </h2>
        <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
          Dwuetapowy proces przesiewania: Triage Tytułów i Abstraktów oraz Kwalifikacja Pełnotekstowa.
        </p>
      </div>

      <ScreeningPipelineOverview screening={activeProject.screening} />
    </div>
  );
};
