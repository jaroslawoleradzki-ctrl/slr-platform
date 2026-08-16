import React, { useState } from 'react';
import { useParams } from 'react-router-dom';
import { Camera, GitFork, Grid, Layers, SlidersHorizontal, Tag, Target } from 'lucide-react';
import { useProject } from '../context/ProjectContext';
import { ClassificationWorkspace } from '../components/synthesis/ClassificationWorkspace';
import { LeanEEMatrix } from '../components/synthesis/LeanEEMatrix';
import { MechanismWorkspace } from '../components/synthesis/MechanismWorkspace';
import { ContextWorkspace } from '../components/synthesis/ContextWorkspace';
import { ResearchGapsWorkspace } from '../components/synthesis/ResearchGapsWorkspace';
import { SnapshotsWorkspace } from '../components/synthesis/SnapshotsWorkspace';

export const EvidenceSynthesisPage: React.FC = () => {
  const { projectId } = useParams<{ projectId?: string }>();
  const { activeProject } = useProject();
  const currentProjectId = projectId || activeProject?.id || 'lean_energy';

  const [activeSubTab, setActiveSubTab] = useState<
    'classification' | 'matrix' | 'mechanisms' | 'context' | 'research-gaps' | 'snapshots'
  >('classification');

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Page Header */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          borderBottom: '1px solid var(--border-subtle)',
          paddingBottom: '16px',
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <Layers size={24} style={{ color: 'var(--accent-primary)' }} />
            <h1 style={{ fontSize: '1.5rem', fontWeight: 700, margin: 0 }}>Evidence Synthesis</h1>
          </div>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginTop: '4px', marginBottom: 0 }}>
            Phase 10: Qualitative and quantitative synthesis of empirical Lean–Energy relationships.
          </p>
        </div>
      </div>

      {/* Synthesis Section Navigation */}
      <div style={{ display: 'flex', gap: '8px', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '8px' }}>
        <button
          type="button"
          data-testid="synthesis-tab-classification"
          onClick={() => setActiveSubTab('classification')}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '8px 16px',
            borderRadius: 'var(--radius-md)',
            border: 'none',
            backgroundColor: activeSubTab === 'classification' ? 'var(--accent-subtle)' : 'transparent',
            color: activeSubTab === 'classification' ? 'var(--accent-primary)' : 'var(--text-secondary)',
            fontWeight: activeSubTab === 'classification' ? 600 : 400,
            cursor: 'pointer',
            fontSize: '0.9rem',
          }}
        >
          <Tag size={16} />
          <span>1. Terminology Classification</span>
        </button>

        <button
          type="button"
          data-testid="synthesis-tab-matrix"
          onClick={() => setActiveSubTab('matrix')}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '8px 16px',
            borderRadius: 'var(--radius-md)',
            border: 'none',
            backgroundColor: activeSubTab === 'matrix' ? 'var(--accent-subtle)' : 'transparent',
            color: activeSubTab === 'matrix' ? 'var(--accent-primary)' : 'var(--text-secondary)',
            fontWeight: activeSubTab === 'matrix' ? 600 : 400,
            cursor: 'pointer',
            fontSize: '0.9rem',
          }}
        >
          <Grid size={16} />
          <span>2. Lean–EE Analytical Matrix</span>
        </button>

        <button
          type="button"
          data-testid="synthesis-tab-mechanisms"
          onClick={() => setActiveSubTab('mechanisms')}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '8px 16px',
            borderRadius: 'var(--radius-md)',
            border: 'none',
            backgroundColor: activeSubTab === 'mechanisms' ? 'var(--accent-subtle)' : 'transparent',
            color: activeSubTab === 'mechanisms' ? 'var(--accent-primary)' : 'var(--text-secondary)',
            fontWeight: activeSubTab === 'mechanisms' ? 600 : 400,
            cursor: 'pointer',
            fontSize: '0.9rem',
          }}
        >
          <GitFork size={16} />
          <span>3. Mechanism Synthesis</span>
        </button>

        <button
          type="button"
          data-testid="synthesis-tab-context"
          onClick={() => setActiveSubTab('context')}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '8px 16px',
            borderRadius: 'var(--radius-md)',
            border: 'none',
            backgroundColor: activeSubTab === 'context' ? 'var(--accent-subtle)' : 'transparent',
            color: activeSubTab === 'context' ? 'var(--accent-primary)' : 'var(--text-secondary)',
            fontWeight: activeSubTab === 'context' ? 600 : 400,
            cursor: 'pointer',
            fontSize: '0.9rem',
          }}
        >
          <SlidersHorizontal size={16} />
          <span>4. Context Synthesis</span>
        </button>

        <button
          type="button"
          data-testid="synthesis-tab-research-gaps"
          onClick={() => setActiveSubTab('research-gaps')}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '8px 16px',
            borderRadius: 'var(--radius-md)',
            border: 'none',
            backgroundColor: activeSubTab === 'research-gaps' ? 'var(--accent-subtle)' : 'transparent',
            color: activeSubTab === 'research-gaps' ? 'var(--accent-primary)' : 'var(--text-secondary)',
            fontWeight: activeSubTab === 'research-gaps' ? 600 : 400,
            cursor: 'pointer',
            fontSize: '0.9rem',
          }}
        >
          <Target size={16} />
          <span>5. Research Gap Synthesis</span>
        </button>

        <button
          type="button"
          data-testid="synthesis-tab-snapshots"
          onClick={() => setActiveSubTab('snapshots')}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '8px 16px',
            borderRadius: 'var(--radius-md)',
            border: 'none',
            backgroundColor: activeSubTab === 'snapshots' ? 'var(--accent-subtle)' : 'transparent',
            color: activeSubTab === 'snapshots' ? 'var(--accent-primary)' : 'var(--text-secondary)',
            fontWeight: activeSubTab === 'snapshots' ? 600 : 400,
            cursor: 'pointer',
            fontSize: '0.9rem',
          }}
        >
          <Camera size={16} />
          <span>6. Synthesis Snapshots</span>
        </button>
      </div>

      {/* Workspace Content */}
      {activeSubTab === 'classification' && (
        <ClassificationWorkspace projectId={currentProjectId} />
      )}

      {activeSubTab === 'matrix' && (
        <LeanEEMatrix
          projectId={currentProjectId}
          onNavigateToClassifications={() => setActiveSubTab('classification')}
        />
      )}

      {activeSubTab === 'mechanisms' && (
        <MechanismWorkspace projectId={currentProjectId} />
      )}

      {activeSubTab === 'context' && (
        <ContextWorkspace projectId={currentProjectId} />
      )}

      {activeSubTab === 'research-gaps' && (
        <ResearchGapsWorkspace projectId={currentProjectId} />
      )}

      {activeSubTab === 'snapshots' && (
        <SnapshotsWorkspace projectId={currentProjectId} />
      )}
    </div>
  );
};
