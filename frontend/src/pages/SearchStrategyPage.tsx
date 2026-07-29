import React from 'react';
import { useProject } from '../context/ProjectContext';
import { ConceptGroupQueryBuilder } from '../components/search/ConceptGroupQueryBuilder';
import { SearchLimitsForm } from '../components/search/SearchLimitsForm';

export const SearchStrategyPage: React.FC = () => {
  const { activeProject } = useProject();

  if (!activeProject) return null;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div>
        <h2 style={{ fontSize: '1.3rem', fontWeight: 800, color: 'var(--text-primary)' }}>
          1. Definicja Strategii Wyszukiwania (Search Strategy & Query)
        </h2>
        <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
          Zbuduj zapytanie Boolean z wykorzystaniem grup pojęć (Concept Groups). Ustaw filtry i ograniczenia rocznikowe.
        </p>
      </div>

      <ConceptGroupQueryBuilder initialGroups={activeProject.conceptGroups} />

      <SearchLimitsForm filters={activeProject.searchFilters} />
    </div>
  );
};
