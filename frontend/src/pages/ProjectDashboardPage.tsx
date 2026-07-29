import React from 'react';
import { useProject } from '../context/ProjectContext';
import { NextActionCard } from '../components/workflow/NextActionCard';
import { LivePrismaFlowChart } from '../components/workflow/LivePrismaFlowChart';
import { Card } from '../components/common/Card';
import { Badge } from '../components/common/Badge';
import { Database, Filter, GitMerge, FileCheck2 } from 'lucide-react';

export const ProjectDashboardPage: React.FC = () => {
  const { activeProject } = useProject();

  if (!activeProject) return null;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Header Info */}
      <div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <h2 style={{ fontSize: '1.4rem', fontWeight: 800, color: 'var(--text-primary)' }}>
            {activeProject.title}
          </h2>
          <Badge variant="info">Protokoły v{activeProject.protocolVersion}</Badge>
        </div>
        <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
          {activeProject.description}
        </p>
      </div>

      {/* 1. Next Action Block */}
      <NextActionCard />

      {/* 2. Key Stage Health Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px' }}>
        <Card
          title={
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.85rem' }}>
              <Database size={16} style={{ color: 'var(--accent-primary)' }} />
              <span>1. Live Providers</span>
            </div>
          }
        >
          <div style={{ fontSize: '1.4rem', fontWeight: 800, color: 'var(--text-primary)' }}>
            {activeProject.prismaMetrics.recordsIdentifiedProviders.toLocaleString()}
          </div>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
            OpenAlex, Crossref, S2
          </span>
        </Card>

        <Card
          title={
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.85rem' }}>
              <GitMerge size={16} style={{ color: 'var(--status-info-text)' }} />
              <span>2. Deduplikacja</span>
            </div>
          }
        >
          <div style={{ fontSize: '1.4rem', fontWeight: 800, color: 'var(--text-primary)' }}>
            {activeProject.prismaMetrics.recordsAfterTechnicalMerger.toLocaleString()}
          </div>
          <span style={{ fontSize: '0.75rem', color: 'var(--status-warning-text)', fontWeight: 600 }}>
            {activeProject.deduplication.candidateGroupsPendingUserReview} grup do oceny
          </span>
        </Card>

        <Card
          title={
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.85rem' }}>
              <Filter size={16} style={{ color: 'var(--status-success-text)' }} />
              <span>3. Triage Tytułów</span>
            </div>
          }
        >
          <div style={{ fontSize: '1.4rem', fontWeight: 800, color: 'var(--text-primary)' }}>
            {activeProject.screening.titleAbstract.included} / {activeProject.screening.titleAbstract.total}
          </div>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
            Włączone do screeningu
          </span>
        </Card>

        <Card
          title={
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.85rem' }}>
              <FileCheck2 size={16} style={{ color: 'var(--accent-light)' }} />
              <span>4. Finalna Synteza</span>
            </div>
          }
        >
          <div style={{ fontSize: '1.4rem', fontWeight: 800, color: 'var(--text-primary)' }}>
            {activeProject.prismaMetrics.studiesIncludedSynthesis}
          </div>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
            Zakwalifikowane studia
          </span>
        </Card>
      </div>

      {/* 3. Dynamic PRISMA 2020 Flow Diagram */}
      <LivePrismaFlowChart metrics={activeProject.prismaMetrics} />
    </div>
  );
};
