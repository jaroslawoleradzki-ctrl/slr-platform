import React, { useState } from 'react';
import { useParams } from 'react-router-dom';
import { Layers, Tag } from 'lucide-react';
import { useProject } from '../context/ProjectContext';
import { ClassificationWorkspace } from '../components/synthesis/ClassificationWorkspace';

export const EvidenceSynthesisPage: React.FC = () => {
  const { projectId } = useParams<{ projectId?: string }>();
  const { activeProject } = useProject();
  const currentProjectId = projectId || activeProject?.id || 'lean_energy';

  const [activeSubTab, setActiveSubTab] = useState<'classification'>('classification');

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
          <span>Terminology Classification</span>
        </button>
      </div>

      {/* Workspace Content */}
      {activeSubTab === 'classification' && (
        <ClassificationWorkspace projectId={currentProjectId} />
      )}
    </div>
  );
};
