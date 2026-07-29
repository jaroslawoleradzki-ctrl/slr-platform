import React from 'react';
import { useProject } from '../context/ProjectContext';
import { ProviderStatusCard } from '../components/search/ProviderStatusCard';
import { FileDropzone } from '../components/imports/FileDropzone';

export const SourcesIngestionPage: React.FC = () => {
  const { activeProject } = useProject();

  if (!activeProject) return null;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div>
        <h2 style={{ fontSize: '1.3rem', fontWeight: 800, color: 'var(--text-primary)' }}>
          2. Źródła Wyszukiwania i Importy (Sources & Ingestion)
        </h2>
        <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
          Status połączeń z live API (OpenAlex, Crossref, Semantic Scholar) oraz ręczne importy plików Ris i BibTeX.
        </p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '16px' }}>
        {activeProject.providers.map((provider) => (
          <ProviderStatusCard key={provider.id} provider={provider} />
        ))}
      </div>

      <FileDropzone imports={activeProject.imports} />
    </div>
  );
};
