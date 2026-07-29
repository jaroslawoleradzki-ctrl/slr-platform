import React, { useState } from 'react';
import { Layers, Check, X, RefreshCw, Loader2 } from 'lucide-react';
import { ApiDuplicateGroup, DuplicateGroupPreview, DuplicateDecisionType, DuplicateDecisionStatus } from '../../types';
import { Card } from '../common/Card';
import { projectApiService } from '../../services/api/projectApi';

interface DuplicateGroupCardPreviewProps {
  group: ApiDuplicateGroup | DuplicateGroupPreview;
  index: number;
  projectId?: string;
  onDecisionUpdated?: (groupId: string, decision: DuplicateDecisionStatus) => void;
}

export const DuplicateGroupCardPreview: React.FC<DuplicateGroupCardPreviewProps> = ({
  group,
  index,
  projectId = 'lean_energy',
  onDecisionUpdated,
}) => {
  const groupId = 'group_id' in group ? group.group_id : group.groupId;
  const reason = group.reason;
  const sharedIdentifiers = 'shared_identifiers' in group ? group.shared_identifiers : [];
  const initialStatus: DuplicateDecisionStatus = ('status' in group && group.status) ? group.status : 'PENDING';

  const [decisionStatus, setDecisionStatus] = useState<DuplicateDecisionStatus>(initialStatus);
  const [saving, setSaving] = useState<boolean>(false);
  const [saved, setSaved] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const normalizedSharedIdents = sharedIdentifiers.map((ident) =>
    typeof ident === 'string' ? ident : `${ident.identifier_type.toUpperCase()}: ${ident.value}`
  );

  const handleDecision = async (decision: DuplicateDecisionType) => {
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      const res = await projectApiService.postDuplicateGroupDecision(projectId, groupId, decision);
      setDecisionStatus(res.decision);
      setSaved(true);
      if (onDecisionUpdated) {
        onDecisionUpdated(groupId, res.decision);
      }
      setTimeout(() => setSaved(false), 2500);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Błąd podczas zapisywania decyzji.';
      setError(msg);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card
      title={
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
          <Layers size={16} style={{ color: 'var(--status-warning-text)' }} />
          <span>Candidate Duplicate Group #{index + 1} (ID: {groupId})</span>
          {decisionStatus === 'APPROVE' ? (
            <span
              style={{
                fontSize: '0.75rem',
                padding: '2px 8px',
                borderRadius: 'var(--radius-full)',
                backgroundColor: 'var(--status-success-bg)',
                color: 'var(--status-success-text)',
                border: '1px solid var(--status-success-border)',
                fontWeight: 700,
              }}
            >
              Approved
            </span>
          ) : decisionStatus === 'REJECT' ? (
            <span
              style={{
                fontSize: '0.75rem',
                padding: '2px 8px',
                borderRadius: 'var(--radius-full)',
                backgroundColor: 'var(--bg-surface-elevated)',
                color: 'var(--text-secondary)',
                border: '1px solid var(--border-strong)',
                fontWeight: 700,
              }}
            >
              Rejected
            </span>
          ) : (
            <span
              style={{
                fontSize: '0.75rem',
                padding: '2px 8px',
                borderRadius: 'var(--radius-full)',
                backgroundColor: 'var(--status-warning-bg)',
                color: 'var(--status-warning-text)',
                border: '1px solid var(--status-warning-border)',
                fontWeight: 700,
              }}
            >
              Pending
            </span>
          )}
        </div>
      }
      subtitle={
        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
          <div>Dopasowanie identyfikatora: {reason}</div>
          {normalizedSharedIdents.length > 0 && (
            <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginTop: '2px' }}>
              {normalizedSharedIdents.map((identStr) => (
                <span
                  key={identStr}
                  style={{
                    fontSize: '0.7rem',
                    padding: '1px 6px',
                    borderRadius: 'var(--radius-sm)',
                    backgroundColor: 'var(--bg-surface-elevated)',
                    border: '1px solid var(--border-subtle)',
                    color: 'var(--text-secondary)',
                    fontFamily: 'monospace',
                  }}
                >
                  {identStr}
                </span>
              ))}
            </div>
          )}
        </div>
      }
      action={
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '6px' }}>
          <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
            {saving && (
              <span
                style={{
                  fontSize: '0.75rem',
                  color: 'var(--text-muted)',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '4px',
                }}
              >
                <Loader2 size={12} style={{ animation: 'spin 1s linear infinite' }} />
                <span>Saving...</span>
              </span>
            )}
            {saved && !saving && (
              <span style={{ fontSize: '0.75rem', color: 'var(--status-success-text)', fontWeight: 600 }}>
                Saved
              </span>
            )}

            <button
              onClick={() => handleDecision('APPROVE')}
              disabled={saving}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '4px',
                padding: '6px 12px',
                borderRadius: 'var(--radius-md)',
                backgroundColor:
                  decisionStatus === 'APPROVE'
                    ? 'var(--status-success-bg)'
                    : 'var(--bg-surface-elevated)',
                color:
                  decisionStatus === 'APPROVE'
                    ? 'var(--status-success-text)'
                    : 'var(--text-primary)',
                border:
                  decisionStatus === 'APPROVE'
                    ? '2px solid var(--status-success-border)'
                    : '1px solid var(--border-strong)',
                fontSize: '0.8rem',
                fontWeight: decisionStatus === 'APPROVE' ? 700 : 600,
                cursor: saving ? 'wait' : 'pointer',
              }}
              title="Zatwierdź tę grupę duplikatów"
            >
              <Check size={14} />
              <span>Approve</span>
            </button>

            <button
              onClick={() => handleDecision('REJECT')}
              disabled={saving}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '4px',
                padding: '6px 12px',
                borderRadius: 'var(--radius-md)',
                backgroundColor:
                  decisionStatus === 'REJECT'
                    ? 'var(--bg-surface-elevated)'
                    : 'var(--bg-surface)',
                color:
                  decisionStatus === 'REJECT'
                    ? 'var(--text-primary)'
                    : 'var(--text-secondary)',
                border:
                  decisionStatus === 'REJECT'
                    ? '2px solid var(--border-strong)'
                    : '1px solid var(--border-subtle)',
                fontSize: '0.8rem',
                fontWeight: decisionStatus === 'REJECT' ? 700 : 500,
                cursor: saving ? 'wait' : 'pointer',
              }}
              title="Odrzuć tę grupę duplikatów"
            >
              <X size={14} />
              <span>Reject</span>
            </button>
          </div>

          {error && (
            <div
              style={{
                fontSize: '0.75rem',
                color: 'var(--status-error-text)',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                marginTop: '4px',
              }}
            >
              <span>Error: {error}</span>
              <button
                onClick={() => handleDecision(decisionStatus === 'REJECT' ? 'REJECT' : 'APPROVE')}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '2px',
                  fontSize: '0.7rem',
                  color: 'var(--status-error-text)',
                  textDecoration: 'underline',
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  padding: 0,
                }}
              >
                <RefreshCw size={10} />
                <span>Retry</span>
              </button>
            </div>
          )}
        </div>
      }
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
        {group.records.map((rec, recIdx) => {
          const pmid = 'pmid' in rec ? rec.pmid : undefined;
          const openalex = 'openalex_id' in rec ? rec.openalex_id : undefined;

          return (
            <div
              key={rec.id}
              style={{
                padding: '12px 14px',
                backgroundColor: 'var(--bg-primary)',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--border-subtle)',
                display: 'flex',
                alignItems: 'flex-start',
                gap: '12px',
              }}
            >
              <span
                style={{
                  fontSize: '0.7rem',
                  fontWeight: 700,
                  color: 'var(--text-muted)',
                  padding: '2px 6px',
                  borderRadius: '4px',
                  backgroundColor: 'var(--bg-surface-elevated)',
                }}
              >
                #{recIdx + 1}
              </span>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                  {rec.title}
                </div>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '2px' }}>
                  Autorzy: {rec.authors} ({rec.year || 'Brak roku'})
                </div>
                <div
                  style={{
                    fontSize: '0.75rem',
                    color: 'var(--text-muted)',
                    marginTop: '4px',
                    display: 'flex',
                    gap: '12px',
                    flexWrap: 'wrap',
                  }}
                >
                  <span>
                    Źródło: <strong>{rec.source}</strong>
                  </span>
                  {rec.doi && (
                    <span>
                      DOI: <code>{rec.doi}</code>
                    </span>
                  )}
                  {pmid && (
                    <span>
                      PMID: <code>{pmid}</code>
                    </span>
                  )}
                  {openalex && (
                    <span>
                      OpenAlex: <code>{openalex}</code>
                    </span>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </Card>
  );
};
