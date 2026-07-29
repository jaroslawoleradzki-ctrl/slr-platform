import React from 'react';
import { useProject } from '../context/ProjectContext';
import { DeduplicationSummaryCard } from '../components/deduplication/DeduplicationSummaryCard';
import { DuplicateGroupCardPreview } from '../components/deduplication/DuplicateGroupCardPreview';

export const DeduplicationPage: React.FC = () => {
  const { activeProject } = useProject();

  if (!activeProject) return null;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div>
        <h2 style={{ fontSize: '1.3rem', fontWeight: 800, color: 'var(--text-primary)' }}>
          4. Wykrywanie i Przegląd Duplikatów (Deduplication)
        </h2>
        <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
          Backend wykrywa candidate duplicate groups na podstawie silnych identyfikatorów (DOI, PMID, OpenAlex ID). Grupy powiązane identyfikatorami stanowią duplicate groups awaiting human review.
        </p>
      </div>

      <DeduplicationSummaryCard summary={activeProject.deduplication} />

      <div>
        <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '12px' }}>
          Duplicate Groups Awaiting Human Review ({activeProject.duplicateGroups.length})
        </h3>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {activeProject.duplicateGroups.map((group, idx) => (
            <DuplicateGroupCardPreview key={group.groupId} group={group} index={idx} />
          ))}
        </div>
      </div>
    </div>
  );
};
