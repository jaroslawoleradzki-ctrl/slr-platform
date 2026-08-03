import React from 'react';
import { useProject } from '../context/ProjectContext';
import { ProviderStatusCard } from '../components/search/ProviderStatusCard';
import { FileDropzone } from '../components/imports/FileDropzone';

export const SourcesIngestionPage: React.FC = () => {
  const { activeProject, importBibliographicFile } = useProject();

  if (!activeProject) return null;


  const displayedProviders = activeProject.providers.map((provider) => {
    const providerImports = activeProject.imports
      .filter((item) => item.sourceType === 'provider' && item.provider === provider.id)
      .sort((a, b) => new Date(b.importedAt).getTime() - new Date(a.importedAt).getTime());

    const latestImport = providerImports[0];
    if (!latestImport) {
      return {
        ...provider,
        connected: false,
        status: 'idle' as const,
        resultsCount: 0,
        lastRunTimestamp: null,
      };
    }

    const isSuccess = latestImport.status === 'success';
    const recordsCount = providerImports
      .filter((item) => item.status === 'success')
      .reduce((total, item) => total + item.recordsCount, 0);
    return {
      ...provider,
      connected: isSuccess,
      status: isSuccess ? ('completed' as const) : ('failed' as const),
      resultsCount: recordsCount,
      lastRunTimestamp: latestImport.importedAt,
      errorMessage: !isSuccess ? latestImport.warnings?.[0] || 'Nieudana próba pobrania' : undefined,
    };
  });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div>
        <h2 style={{ fontSize: '1.3rem', fontWeight: 800, color: 'var(--text-primary)' }}>
          2. Źródła Wyszukiwania i Importy (Sources & Ingestion)
        </h2>
        <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
          Ręczne importy RIS i BibTeX oraz neutralny stan providerów, dla których brak zapisanych wykonań.
        </p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '16px' }}>
        {displayedProviders.map((provider) => (
          <ProviderStatusCard key={provider.id} provider={provider} />
        ))}
      </div>

      <FileDropzone
        imports={activeProject.imports}
        onFileSelect={importBibliographicFile}
      />
    </div>
  );
};
