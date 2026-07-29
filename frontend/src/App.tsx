import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ProjectProvider } from './context/ProjectContext';
import { AppShell } from './components/layout/AppShell';

import { ProjectsListPage } from './pages/ProjectsListPage';
import { ProjectDashboardPage } from './pages/ProjectDashboardPage';
import { SearchStrategyPage } from './pages/SearchStrategyPage';
import { SourcesIngestionPage } from './pages/SourcesIngestionPage';
import { NormalizationPage } from './pages/NormalizationPage';
import { DeduplicationPage } from './pages/DeduplicationPage';
import { ScreeningPage } from './pages/ScreeningPage';
import { QualityAssessmentPage } from './pages/QualityAssessmentPage';
import { DataExtractionPlaceholderPage } from './pages/DataExtractionPlaceholderPage';
import { ExportsPage } from './pages/ExportsPage';

export const App: React.FC = () => {
  return (
    <ProjectProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Navigate to="/projects" replace />} />
          <Route path="/projects" element={<ProjectsListPage />} />
          
          <Route path="/projects/:projectId" element={<AppShell />}>
            <Route index element={<Navigate to="dashboard" replace />} />
            <Route path="dashboard" element={<ProjectDashboardPage />} />
            <Route path="overview" element={<Navigate to="../dashboard" replace />} />
            <Route path="search" element={<SearchStrategyPage />} />
            <Route path="sources" element={<SourcesIngestionPage />} />
            <Route path="normalize" element={<NormalizationPage />} />
            <Route path="dedup" element={<DeduplicationPage />} />
            <Route path="screen" element={<ScreeningPage />} />
            <Route path="qa" element={<QualityAssessmentPage />} />
            <Route path="extract" element={<DataExtractionPlaceholderPage />} />
            <Route path="exports" element={<ExportsPage />} />
          </Route>

          <Route path="*" element={<Navigate to="/projects" replace />} />
        </Routes>
      </BrowserRouter>
    </ProjectProvider>
  );
};

export default App;
