import React, { useCallback, useEffect, useState } from 'react';
import {
  AlertCircle,
  Camera,
  Download,
  FileJson,
  FileSpreadsheet,
  RefreshCw,
  ShieldCheck,
  Clock,
} from 'lucide-react';
import { synthesisApi } from '../../services/api/synthesisApi';
import {
  SnapshotExport,
  SynthesisSnapshot,
  SynthesisSnapshotDetail,
} from '../../types/synthesis';

interface SnapshotsWorkspaceProps {
  projectId: string;
}

export const SnapshotsWorkspace: React.FC<SnapshotsWorkspaceProps> = ({ projectId }) => {
  const [snapshots, setSnapshots] = useState<SynthesisSnapshot[]>([]);
  const [selectedSnapshot, setSelectedSnapshot] = useState<SynthesisSnapshotDetail | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState<boolean>(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [actor, setActor] = useState<string>('lead_researcher');
  const [exportContent, setExportContent] = useState<SnapshotExport | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await synthesisApi.listSnapshots(projectId);
      setSnapshots(data);
      if (selectedSnapshot) {
        const detail = await synthesisApi.getSnapshot(projectId, selectedSnapshot.version);
        setSelectedSnapshot(detail);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to load synthesis snapshots.');
    } finally {
      setLoading(false);
    }
  }, [projectId, selectedSnapshot]);

  useEffect(() => {
    loadData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  const handleCreateSnapshot = async () => {
    setCreateError(null);
    setCreating(true);
    try {
      if (!actor.trim()) {
        setCreateError('Actor is required.');
        return;
      }
      const created = await synthesisApi.createSnapshot(projectId, { actor: actor.trim() });
      setSelectedSnapshot(created);
      const data = await synthesisApi.listSnapshots(projectId);
      setSnapshots(data);
    } catch (err: any) {
      setCreateError(err.message || 'Failed to create snapshot.');
    } finally {
      setCreating(false);
    }
  };

  const handleSelectSnapshot = async (version: number) => {
    setExportError(null);
    setExportContent(null);
    try {
      const detail = await synthesisApi.getSnapshot(projectId, version);
      setSelectedSnapshot(detail);
    } catch (err: any) {
      setError(err.message || 'Failed to load snapshot detail.');
    }
  };

  const handleExport = async (format: 'json' | 'csv') => {
    if (!selectedSnapshot) return;
    setExportError(null);
    try {
      const exported = await synthesisApi.exportSnapshot(projectId, selectedSnapshot.version, format);
      setExportContent(exported);
    } catch (err: any) {
      setExportError(err.message || 'Failed to export snapshot.');
    }
  };

  const handleDownload = () => {
    if (!exportContent) return;
    const blob = new Blob(
      exportContent.format === 'csv'
        ? [exportContent.content_csv || '']
        : [JSON.stringify(exportContent, null, 2)],
      { type: exportContent.format === 'csv' ? 'text/csv' : 'application/json' }
    );
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `snapshot-v${exportContent.version}.${exportContent.format}`;
    link.click();
    URL.revokeObjectURL(url);
  };

  if (loading && snapshots.length === 0) {
    return (
      <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>
        <RefreshCw size={24} style={{ animation: 'spin 1s linear infinite', marginBottom: '12px' }} />
        <div>Loading Synthesis Snapshots...</div>
      </div>
    );
  }

  if (error && snapshots.length === 0) {
    return (
      <div
        style={{
          padding: '24px',
          backgroundColor: 'var(--status-error-bg)',
          border: '1px solid var(--status-error-border)',
          borderRadius: 'var(--radius-lg)',
          color: 'var(--status-error-text)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontWeight: 600 }}>
          <AlertCircle size={20} />
          <span>Error loading synthesis snapshots</span>
        </div>
        <p style={{ marginTop: '8px', fontSize: '0.9rem' }}>{error}</p>
      </div>
    );
  }

  const digest = (hash: string) => (hash ? `${hash.slice(0, 10)}…` : '—');

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Workspace Header */}
      <div
        style={{
          backgroundColor: 'var(--bg-surface)',
          border: '1px solid var(--border-subtle)',
          borderRadius: 'var(--radius-lg)',
          padding: '20px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          flexWrap: 'wrap',
          gap: '16px',
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <Camera size={22} style={{ color: 'var(--accent-primary)' }} />
            <h2 style={{ fontSize: '1.25rem', fontWeight: 600, margin: 0 }}>
              Synthesis Snapshots
            </h2>
          </div>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginTop: '6px', marginBottom: 0 }}>
            Immutable, reproducible snapshots of the analytical synthesis state. Each snapshot is append-only,
            versioned per-project, and hashed against the eligible COMPLETE extraction dataset, classification rules,
            and QA configuration.
          </p>
        </div>
      </div>

      {/* Create Snapshot Panel */}
      <div
        style={{
          backgroundColor: 'var(--bg-surface)',
          border: '1px solid var(--border-subtle)',
          borderRadius: 'var(--radius-lg)',
          padding: '16px',
          display: 'flex',
          alignItems: 'flex-end',
          gap: '12px',
          flexWrap: 'wrap',
        }}
      >
        <div>
          <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 500, marginBottom: '4px' }}>
            Actor (researcher)
          </label>
          <input
            type="text"
            data-testid="snapshot-actor-input"
            value={actor}
            onChange={(e) => setActor(e.target.value)}
            placeholder="e.g. lead_researcher"
            style={{
              padding: '7px 12px',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--border-subtle)',
              backgroundColor: 'var(--bg-app)',
              color: 'var(--text-primary)',
              fontSize: '0.85rem',
              minWidth: '220px',
            }}
          />
        </div>
        <button
          type="button"
          data-testid="create-snapshot-btn"
          onClick={handleCreateSnapshot}
          disabled={creating}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            padding: '8px 16px',
            borderRadius: 'var(--radius-md)',
            border: 'none',
            backgroundColor: 'var(--accent-primary)',
            color: '#ffffff',
            cursor: creating ? 'not-allowed' : 'pointer',
            fontSize: '0.85rem',
            fontWeight: 600,
          }}
        >
          <Camera size={15} /> {creating ? 'Creating…' : 'Create Snapshot'}
        </button>
        {createError && (
          <div style={{ fontSize: '0.85rem', color: 'var(--status-error-text)' }}>{createError}</div>
        )}
      </div>

      {/* Snapshot List */}
      <div
        style={{
          backgroundColor: 'var(--bg-surface)',
          border: '1px solid var(--border-subtle)',
          borderRadius: 'var(--radius-lg)',
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            padding: '12px 16px',
            borderBottom: '1px solid var(--border-subtle)',
            fontWeight: 600,
            fontSize: '0.9rem',
            backgroundColor: 'var(--bg-app)',
          }}
        >
          Snapshot Versions ({snapshots.length})
        </div>
        {snapshots.length === 0 ? (
          <div style={{ padding: '16px', fontSize: '0.85rem', color: 'var(--text-muted)', fontStyle: 'italic' }}>
            No snapshots created yet. Snapshots are created explicitly by a researcher; they are never created
            automatically.
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            {snapshots.map((snap) => (
              <button
                type="button"
                key={snap.snapshot_id}
                data-testid={`snapshot-row-${snap.version}`}
                onClick={() => handleSelectSnapshot(snap.version)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '12px',
                  padding: '12px 16px',
                  border: 'none',
                  borderBottom: '1px solid var(--border-subtle)',
                  backgroundColor:
                    selectedSnapshot?.version === snap.version ? 'var(--accent-subtle)' : 'var(--bg-surface)',
                  color: 'var(--text-primary)',
                  cursor: 'pointer',
                  textAlign: 'left',
                  fontSize: '0.85rem',
                }}
              >
                <span
                  style={{
                    padding: '4px 10px',
                    borderRadius: 'var(--radius-sm)',
                    backgroundColor: 'var(--accent-subtle)',
                    color: 'var(--accent-primary)',
                    fontWeight: 700,
                  }}
                >
                  v{snap.version}
                </span>
                <span style={{ fontWeight: 500 }}>{snap.actor}</span>
                <span style={{ marginLeft: 'auto', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <Clock size={13} />
                  {new Date(snap.created_at).toLocaleString()}
                </span>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Snapshot Detail */}
      {selectedSnapshot && (
        <div
          data-testid="snapshot-detail-panel"
          style={{
            backgroundColor: 'var(--bg-surface)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--radius-lg)',
            padding: '20px',
            display: 'flex',
            flexDirection: 'column',
            gap: '16px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <ShieldCheck size={20} style={{ color: 'var(--accent-primary)' }} />
            <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 600 }}>
              Snapshot v{selectedSnapshot.version}
            </h3>
            <span style={{ marginLeft: 'auto', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
              {selectedSnapshot.actor} — {new Date(selectedSnapshot.created_at).toLocaleString()}
            </span>
          </div>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
              gap: '12px',
            }}
          >
            <div style={{ padding: '12px', backgroundColor: 'var(--bg-app)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)' }}>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                Extraction Dataset Hash
              </div>
              <code data-testid="dataset-hash" style={{ fontSize: '0.8rem' }}>{digest(selectedSnapshot.extraction_dataset_hash)}</code>
            </div>
            <div style={{ padding: '12px', backgroundColor: 'var(--bg-app)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)' }}>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                Classification Version
              </div>
              <code style={{ fontSize: '0.8rem' }}>{digest(selectedSnapshot.classification_version)}</code>
            </div>
            <div style={{ padding: '12px', backgroundColor: 'var(--bg-app)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)' }}>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                Content Hash
              </div>
              <code style={{ fontSize: '0.8rem' }}>{digest(selectedSnapshot.content_hash)}</code>
            </div>
          </div>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
              gap: '12px',
            }}
          >
            {[
              ['Relations', selectedSnapshot.content.relations.length],
              ['Mechanism Pathways', selectedSnapshot.content.mechanism_pathways.length],
              ['Context Assignments', selectedSnapshot.content.context_assignments.length],
              ['Research Gaps', selectedSnapshot.content.research_gaps.length],
              ['Gap Links', selectedSnapshot.content.research_gap_links.length],
              ['Term Mappings', selectedSnapshot.content.term_mappings.length],
              ['QA Profiles', selectedSnapshot.content.qa_profiles.length],
            ].map(([label, count]) => (
              <div
                key={label as string}
                data-testid={`snapshot-stat-${(label as string).toLowerCase().replace(/ /g, '-')}`}
                style={{ padding: '10px', backgroundColor: 'var(--bg-app)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)' }}
              >
                <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>{label as string}</div>
                <div style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--accent-primary)' }}>{count as number}</div>
              </div>
            ))}
          </div>

          {/* Export */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap', marginTop: '4px' }}>
            <button
              type="button"
              data-testid="export-json-btn"
              onClick={() => handleExport('json')}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '7px 12px',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--border-subtle)',
                backgroundColor: 'var(--bg-app)',
                color: 'var(--text-primary)',
                cursor: 'pointer',
                fontSize: '0.85rem',
              }}
            >
              <FileJson size={14} /> Export JSON
            </button>
            <button
              type="button"
              data-testid="export-csv-btn"
              onClick={() => handleExport('csv')}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '7px 12px',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--border-subtle)',
                backgroundColor: 'var(--bg-app)',
                color: 'var(--text-primary)',
                cursor: 'pointer',
                fontSize: '0.85rem',
              }}
            >
              <FileSpreadsheet size={14} /> Export CSV
            </button>
            {exportError && (
              <span style={{ fontSize: '0.8rem', color: 'var(--status-error-text)' }}>{exportError}</span>
            )}
          </div>

          {exportContent && (
            <div
              data-testid="export-preview"
              style={{
                padding: '12px',
                backgroundColor: 'var(--bg-app)',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--border-subtle)',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                <span style={{ fontWeight: 600, fontSize: '0.85rem', textTransform: 'uppercase' }}>
                  {exportContent.format === 'csv' ? 'CSV Relations Matrix' : 'JSON Snapshot Export'}
                </span>
                <button
                  type="button"
                  data-testid="download-export-btn"
                  onClick={handleDownload}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '5px',
                    padding: '5px 10px',
                    borderRadius: 'var(--radius-md)',
                    border: '1px solid var(--border-subtle)',
                    backgroundColor: 'var(--bg-surface)',
                    color: 'var(--accent-primary)',
                    cursor: 'pointer',
                    fontSize: '0.8rem',
                    fontWeight: 500,
                  }}
                >
                  <Download size={13} /> Download
                </button>
              </div>
              <pre
                data-testid="export-content"
                style={{
                  maxHeight: '240px',
                  overflowY: 'auto',
                  margin: 0,
                  fontSize: '0.7rem',
                  color: 'var(--text-secondary)',
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-all',
                }}
              >
                {exportContent.format === 'csv' ? exportContent.content_csv : JSON.stringify(exportContent, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
