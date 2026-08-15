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
import { TitleAbstractScreeningPage } from './pages/TitleAbstractScreeningPage';
import { ScreeningAuditPage } from './pages/ScreeningAuditPage';
import { ConflictResolutionPage } from './pages/ConflictResolutionPage';
import { FullTextScreeningPage } from './pages/FullTextScreeningPage';
import { ScreeningSectionLayout } from './components/screening/ScreeningSectionLayout';
import { QualityAssessmentPage } from './pages/QualityAssessmentPage';
import { DataExtractionPage } from './pages/DataExtractionPage';
import { EvidenceSynthesisPage } from './pages/EvidenceSynthesisPage';
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
            <Route path="screen" element={<ScreeningSectionLayout />}>
              <Route index element={<Navigate to="title-abstract" replace />} />
              <Route path="criteria" element={<ScreeningPage />} />
              <Route path="title-abstract" element={<TitleAbstractScreeningPage />} />
              <Route path="title-abstract/:publicationId" element={<TitleAbstractScreeningPage />} />
              <Route path="full-text" element={<FullTextScreeningPage />} />
              <Route path="full-text/:publicationId" element={<FullTextScreeningPage />} />
              <Route path="audit" element={<ScreeningAuditPage />} />
              <Route path="conflicts" element={<ConflictResolutionPage />} />
              <Route path="conflict-resolution" element={<Navigate to="../conflicts" replace />} />
            </Route>
            <Route path="quality-assessment" element={<QualityAssessmentPage />} />
            <Route path="quality-assessment/configuration" element={<QualityAssessmentPage />} />
            <Route path="quality-assessment/:publicationId" element={<QualityAssessmentPage />} />
            <Route path="qa" element={<Navigate to="../quality-assessment" replace />} />
            <Route path="extract" element={<DataExtractionPage />} />
            <Route path="extract/:publicationId" element={<DataExtractionPage />} />
            <Route path="synthesis" element={<EvidenceSynthesisPage />} />
            <Route path="synthesis/classification" element={<EvidenceSynthesisPage />} />
            <Route path="exports" element={<ExportsPage />} />
          </Route>

          <Route path="*" element={<Navigate to="/projects" replace />} />
        </Routes>
      </BrowserRouter>
    </ProjectProvider>
  );
};

export default App;
