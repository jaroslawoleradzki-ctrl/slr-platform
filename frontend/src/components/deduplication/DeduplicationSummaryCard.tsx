import React from 'react';
import { GitMerge, ShieldAlert, CheckCircle2, Info } from 'lucide-react';
import { DeduplicationSummary } from '../../types';
import { Card } from '../common/Card';
import { Badge } from '../common/Badge';

interface DeduplicationSummaryCardProps {
  summary: DeduplicationSummary;
}

export const DeduplicationSummaryCard: React.FC<DeduplicationSummaryCardProps> = ({ summary }) => {
  return (
    <Card
      title={
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <GitMerge size={18} style={{ color: 'var(--accent-primary)' }} />
          <span>Status Procesu Deduplikacji (Deduplication Pipeline Status)</span>
        </div>
      }
      action={
        summary.candidateGroupsPendingUserReview > 0 ? (
          <Badge variant="pending_action" icon={<ShieldAlert size={12} />}>
            Duplicate groups awaiting human review ({summary.candidateGroupsPendingUserReview})
          </Badge>
        ) : (
          <Badge variant="completed" icon={<CheckCircle2 size={12} />}>Zakończono</Badge>
        )
      }
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {/* Strict Constraint Warning Box */}
        <div
          style={{
            padding: '12px 16px',
            borderRadius: 'var(--radius-md)',
            backgroundColor: 'var(--status-info-bg)',
            border: '1px solid var(--status-info-border)',
            color: 'var(--status-info-text)',
            fontSize: '0.8rem',
            display: 'flex',
            alignItems: 'flex-start',
            gap: '10px',
          }}
        >
          <Info size={16} style={{ flexShrink: 0, marginTop: '2px' }} />
          <span>
            <strong>Zasada domenowa backendu:</strong> Kandydaci na duplikaty (candidate duplicate groups) wykrywani są wyłącznie na podstawie silnych identyfikatorów (<strong>DOI</strong>, <strong>PMID</strong>, <strong>OpenAlex ID</strong>). Wykryte grupy <strong>nie są scalane automatycznie</strong> przez backend i stanowią <em>duplicate groups awaiting human review</em>.
          </span>
        </div>

        {/* Metrics Grid */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px' }}>
          <div
            style={{
              padding: '14px',
              backgroundColor: 'var(--bg-primary)',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--border-subtle)',
            }}
          >
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Przed Deduplikacją</span>
            <div style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--text-primary)', marginTop: '2px' }}>
              {summary.recordsBeforeDedup.toLocaleString()}
            </div>
            <span style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>Rekordy surowe / importy</span>
          </div>

          <div
            style={{
              padding: '14px',
              backgroundColor: 'var(--bg-primary)',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--border-subtle)',
            }}
          >
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Identifier-Linked Groups</span>
            <div style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--status-success-text)', marginTop: '2px' }}>
              {summary.identifierLinkedGroupsCount.toLocaleString()}
            </div>
            <span style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>Grupy wg identyfikatorów</span>
          </div>

          <div
            style={{
              padding: '14px',
              backgroundColor: 'var(--bg-primary)',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--border-subtle)',
            }}
          >
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Po Technicznym Merge</span>
            <div style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--text-primary)', marginTop: '2px' }}>
              {summary.recordsAfterResultMerger.toLocaleString()}
            </div>
            <span style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>Wynik ResultMerger</span>
          </div>

          <div
            style={{
              padding: '14px',
              backgroundColor: 'var(--status-warning-bg)',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--status-warning-border)',
            }}
          >
            <span style={{ fontSize: '0.75rem', color: 'var(--status-warning-text)', fontWeight: 700 }}>Oczekujące na Ocenę Badacza</span>
            <div style={{ fontSize: '1.25rem', fontWeight: 800, color: 'var(--text-primary)', marginTop: '2px' }}>
              {summary.candidateGroupsPendingUserReview} grup
            </div>
            <span style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>Candidate duplicate groups</span>
          </div>
        </div>
      </div>
    </Card>
  );
};
