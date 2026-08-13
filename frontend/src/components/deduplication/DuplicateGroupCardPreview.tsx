import React, { useEffect, useState } from 'react';
import {
  Layers,
  Check,
  X,
  RefreshCw,
  Loader2,
  ChevronDown,
  ChevronUp,
  AlertTriangle,
  HelpCircle,
  Minus,
  FileText,
  Building2,
  Calendar,
  User,
  Database,
  ShieldCheck,
} from 'lucide-react';
import {
  ApiDuplicateGroup,
  DuplicateGroupPreview,
  DuplicateDecisionType,
  DuplicateDecisionStatus,
  ApiDuplicateRecordPreview,
} from '../../types';
import { Card } from '../common/Card';
import { projectApiService } from '../../services/api/projectApi';

interface DuplicateGroupCardPreviewProps {
  group: ApiDuplicateGroup | DuplicateGroupPreview;
  index: number;
  projectId?: string;
  onDecisionUpdated?: (groupId: string, decision: DuplicateDecisionStatus, rationale?: string | null) => void;
}

type ComparisonFieldState = 'MATCH' | 'DIFFERENT' | 'PARTIAL' | 'UNAVAILABLE';

function getFieldState(values: (string | number | null | undefined)[]): ComparisonFieldState {
  const normalized = values.map((v) =>
    v !== null && v !== undefined && String(v).trim() !== '' ? String(v).trim() : null
  );
  const nonNulls = normalized.filter((v): v is string => v !== null);

  if (nonNulls.length === 0) return 'UNAVAILABLE';
  if (nonNulls.length < normalized.length) {
    const unique = new Set(nonNulls.map((v) => v.toLowerCase()));
    return unique.size === 1 ? 'PARTIAL' : 'DIFFERENT';
  }
  const unique = new Set(nonNulls.map((v) => v.toLowerCase()));
  return unique.size === 1 ? 'MATCH' : 'DIFFERENT';
}

function renderFieldBadge(state: ComparisonFieldState) {
  switch (state) {
    case 'MATCH':
      return (
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '4px',
            fontSize: '0.7rem',
            fontWeight: 700,
            padding: '2px 8px',
            borderRadius: 'var(--radius-full)',
            backgroundColor: 'var(--status-success-bg)',
            color: 'var(--status-success-text)',
            border: '1px solid var(--status-success-border)',
          }}
        >
          <Check size={12} />
          <span>Zgodne (Identical)</span>
        </span>
      );
    case 'DIFFERENT':
      return (
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '4px',
            fontSize: '0.7rem',
            fontWeight: 700,
            padding: '2px 8px',
            borderRadius: 'var(--radius-full)',
            backgroundColor: 'rgba(239, 68, 68, 0.1)',
            color: 'var(--status-error-text)',
            border: '1px solid rgba(239, 68, 68, 0.3)',
          }}
        >
          <AlertTriangle size={12} />
          <span>Różne (Different)</span>
        </span>
      );
    case 'PARTIAL':
      return (
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '4px',
            fontSize: '0.7rem',
            fontWeight: 700,
            padding: '2px 8px',
            borderRadius: 'var(--radius-full)',
            backgroundColor: 'var(--status-warning-bg)',
            color: 'var(--status-warning-text)',
            border: '1px solid var(--status-warning-border)',
          }}
        >
          <HelpCircle size={12} />
          <span>Częściowe (Partial)</span>
        </span>
      );
    case 'UNAVAILABLE':
    default:
      return (
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '4px',
            fontSize: '0.7rem',
            fontWeight: 600,
            padding: '2px 8px',
            borderRadius: 'var(--radius-full)',
            backgroundColor: 'var(--bg-surface-elevated)',
            color: 'var(--text-muted)',
            border: '1px solid var(--border-subtle)',
          }}
        >
          <Minus size={12} />
          <span>Brak danych (Missing)</span>
        </span>
      );
  }
}

export const DuplicateGroupCardPreview: React.FC<DuplicateGroupCardPreviewProps> = ({
  group,
  index,
  projectId = '',
  onDecisionUpdated,
}) => {
  const groupId = 'group_id' in group ? group.group_id : group.groupId;
  const reason = group.reason;
  const sharedIdentifiers = 'shared_identifiers' in group ? group.shared_identifiers : [];
  const initialStatus: DuplicateDecisionStatus = ('status' in group && group.status) ? group.status : 'PENDING';
  const initialRationale: string = ('rationale' in group && group.rationale) ? group.rationale : '';

  const decisionStatus = initialStatus;
  const [rationale, setRationale] = useState<string>(initialRationale);
  const [isExpanded, setIsExpanded] = useState<boolean>(true);
  const [saving, setSaving] = useState<boolean>(false);
  const [saved, setSaved] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setRationale(('rationale' in group && group.rationale) ? group.rationale : '');
  }, [group]);

  const normalizedSharedIdents = sharedIdentifiers.map((ident) =>
    typeof ident === 'string' ? ident : `${ident.identifier_type.toUpperCase()}: ${ident.value}`
  );

  const records: ApiDuplicateRecordPreview[] = group.records.map((r) => ({
    id: r.id,
    title: r.title,
    authors: r.authors,
    year: r.year,
    source: r.source,
    venue: 'venue' in r ? r.venue : undefined,
    doi: 'doi' in r ? r.doi : undefined,
    pmid: 'pmid' in r ? r.pmid : undefined,
    openalex_id: 'openalex_id' in r ? r.openalex_id : undefined,
    provenance: 'provenance' in r && Array.isArray(r.provenance) ? r.provenance : undefined,
  }));

  const handleDecision = async (decision: DuplicateDecisionType) => {
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      const res = await projectApiService.postDuplicateGroupDecision(
        projectId,
        groupId,
        decision,
        rationale
      );
      setRationale(res.rationale || '');
      setSaved(true);
      if (onDecisionUpdated) {
        onDecisionUpdated(groupId, res.decision, res.rationale);
      }
      setTimeout(() => setSaved(false), 2500);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Błąd podczas zapisywania decyzji.';
      setError(msg);
    } finally {
      setSaving(false);
    }
  };

  // Field Comparison States
  const titleState = getFieldState(records.map((r) => r.title));
  const authorsState = getFieldState(records.map((r) => r.authors));
  const yearState = getFieldState(records.map((r) => r.year));
  const venueState = getFieldState(records.map((r) => r.venue));
  const doiState = getFieldState(records.map((r) => r.doi));
  const pmidState = getFieldState(records.map((r) => r.pmid));
  const openalexState = getFieldState(records.map((r) => r.openalex_id));

  return (
    <Card
      title={
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
          <Layers size={18} style={{ color: 'var(--status-warning-text)' }} />
          <span style={{ fontWeight: 700 }}>Candidate Duplicate Group #{index + 1}</span>
          <code
            style={{
              fontSize: '0.75rem',
              color: 'var(--text-secondary)',
              backgroundColor: 'var(--bg-surface-elevated)',
              padding: '2px 6px',
              borderRadius: 'var(--radius-sm)',
            }}
          >
            {groupId}
          </code>

          {decisionStatus === 'APPROVE' ? (
            <span
              style={{
                fontSize: '0.75rem',
                padding: '2px 10px',
                borderRadius: 'var(--radius-full)',
                backgroundColor: 'var(--status-success-bg)',
                color: 'var(--status-success-text)',
                border: '1px solid var(--status-success-border)',
                fontWeight: 700,
                display: 'inline-flex',
                alignItems: 'center',
                gap: '4px',
              }}
            >
              <Check size={12} />
              Approved
            </span>
          ) : decisionStatus === 'REJECT' ? (
            <span
              style={{
                fontSize: '0.75rem',
                padding: '2px 10px',
                borderRadius: 'var(--radius-full)',
                backgroundColor: 'var(--bg-surface-elevated)',
                color: 'var(--text-secondary)',
                border: '1px solid var(--border-strong)',
                fontWeight: 700,
                display: 'inline-flex',
                alignItems: 'center',
                gap: '4px',
              }}
            >
              <X size={12} />
              Rejected
            </span>
          ) : (
            <span
              style={{
                fontSize: '0.75rem',
                padding: '2px 10px',
                borderRadius: 'var(--radius-full)',
                backgroundColor: 'var(--status-warning-bg)',
                color: 'var(--status-warning-text)',
                border: '1px solid var(--status-warning-border)',
                fontWeight: 700,
                display: 'inline-flex',
                alignItems: 'center',
                gap: '4px',
              }}
            >
              <HelpCircle size={12} />
              Pending Review
            </span>
          )}
        </div>
      }
      subtitle={
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
          <div>Powód wykrycia: {reason}</div>
          {normalizedSharedIdents.length > 0 && (
            <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginTop: '2px' }}>
              {normalizedSharedIdents.map((identStr) => (
                <span
                  key={identStr}
                  style={{
                    fontSize: '0.7rem',
                    padding: '2px 8px',
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
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          aria-expanded={isExpanded}
          aria-label={isExpanded ? 'Zwiń porównanie szczegółowe' : 'Rozwiń porównanie szczegółowe'}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '6px',
            padding: '6px 12px',
            borderRadius: 'var(--radius-md)',
            backgroundColor: 'var(--bg-surface-elevated)',
            color: 'var(--text-primary)',
            border: '1px solid var(--border-strong)',
            fontSize: '0.8rem',
            fontWeight: 600,
            cursor: 'pointer',
          }}
        >
          {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          <span>{isExpanded ? 'Zwiń Szczegóły Grupy' : 'Porównaj Publikacje'}</span>
        </button>
      }
    >
      {isExpanded && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {/* Section Header */}
          <div
            style={{
              padding: '10px 14px',
              borderRadius: 'var(--radius-md)',
              backgroundColor: 'var(--bg-surface-elevated)',
              border: '1px solid var(--border-subtle)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              flexWrap: 'wrap',
              gap: '10px',
            }}
          >
            <span style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--text-primary)' }}>
              Porównanie Publikacji Obok Siebie ({records.length} Rekordy)
            </span>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              Deterministyczne porównanie pól i identyfikatorów
            </span>
          </div>

          {/* Side-by-Side Comparison Grid */}
          <div
            style={{
              overflowX: 'auto',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--border-subtle)',
            }}
          >
            <table
              style={{
                width: '100%',
                borderCollapse: 'collapse',
                fontSize: '0.85rem',
                textAlign: 'left',
              }}
            >
              <thead>
                <tr style={{ backgroundColor: 'var(--bg-surface-elevated)', borderBottom: '1px solid var(--border-subtle)' }}>
                  <th style={{ padding: '10px 14px', width: '180px', color: 'var(--text-secondary)', fontWeight: 700 }}>
                    Pole Porównawcze
                  </th>
                  <th style={{ padding: '10px 14px', width: '150px', color: 'var(--text-secondary)', fontWeight: 700 }}>
                    Stan Zgodności
                  </th>
                  {records.map((rec, rIdx) => (
                    <th
                      key={rec.id}
                      style={{
                        padding: '10px 14px',
                        color: 'var(--text-primary)',
                        fontWeight: 700,
                        borderLeft: '1px solid var(--border-subtle)',
                      }}
                    >
                      Rekord #{rIdx + 1} ({rec.source})
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {/* Title */}
                <tr style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                  <td style={{ padding: '10px 14px', fontWeight: 600, color: 'var(--text-primary)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <FileText size={14} style={{ color: 'var(--text-muted)' }} />
                      <span>Tytuł (Title)</span>
                    </div>
                  </td>
                  <td style={{ padding: '10px 14px' }}>{renderFieldBadge(titleState)}</td>
                  {records.map((rec) => (
                    <td key={rec.id} style={{ padding: '10px 14px', borderLeft: '1px solid var(--border-subtle)', fontWeight: 600 }}>
                      {rec.title}
                    </td>
                  ))}
                </tr>

                {/* Authors */}
                <tr style={{ borderBottom: '1px solid var(--border-subtle)', backgroundColor: 'var(--bg-surface-elevated)' }}>
                  <td style={{ padding: '10px 14px', fontWeight: 600, color: 'var(--text-primary)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <User size={14} style={{ color: 'var(--text-muted)' }} />
                      <span>Autorzy (Authors)</span>
                    </div>
                  </td>
                  <td style={{ padding: '10px 14px' }}>{renderFieldBadge(authorsState)}</td>
                  {records.map((rec) => (
                    <td key={rec.id} style={{ padding: '10px 14px', borderLeft: '1px solid var(--border-subtle)', color: 'var(--text-secondary)' }}>
                      {rec.authors || <span style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>Brak</span>}
                    </td>
                  ))}
                </tr>

                {/* Year */}
                <tr style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                  <td style={{ padding: '10px 14px', fontWeight: 600, color: 'var(--text-primary)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <Calendar size={14} style={{ color: 'var(--text-muted)' }} />
                      <span>Rok Wydania (Year)</span>
                    </div>
                  </td>
                  <td style={{ padding: '10px 14px' }}>{renderFieldBadge(yearState)}</td>
                  {records.map((rec) => (
                    <td key={rec.id} style={{ padding: '10px 14px', borderLeft: '1px solid var(--border-subtle)' }}>
                      {rec.year ? String(rec.year) : <span style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>Brak roku</span>}
                    </td>
                  ))}
                </tr>

                {/* Venue */}
                <tr style={{ borderBottom: '1px solid var(--border-subtle)', backgroundColor: 'var(--bg-surface-elevated)' }}>
                  <td style={{ padding: '10px 14px', fontWeight: 600, color: 'var(--text-primary)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <Building2 size={14} style={{ color: 'var(--text-muted)' }} />
                      <span>Czasopismo / Venue</span>
                    </div>
                  </td>
                  <td style={{ padding: '10px 14px' }}>{renderFieldBadge(venueState)}</td>
                  {records.map((rec) => (
                    <td key={rec.id} style={{ padding: '10px 14px', borderLeft: '1px solid var(--border-subtle)' }}>
                      {rec.venue || <span style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>Brak czasopisma</span>}
                    </td>
                  ))}
                </tr>

                {/* DOI */}
                <tr style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                  <td style={{ padding: '10px 14px', fontWeight: 600, color: 'var(--text-primary)' }}>
                    <span>DOI Identifier</span>
                  </td>
                  <td style={{ padding: '10px 14px' }}>{renderFieldBadge(doiState)}</td>
                  {records.map((rec) => (
                    <td key={rec.id} style={{ padding: '10px 14px', borderLeft: '1px solid var(--border-subtle)' }}>
                      {rec.doi ? <code style={{ color: 'var(--text-primary)' }}>{rec.doi}</code> : <span style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>Brak</span>}
                    </td>
                  ))}
                </tr>

                {/* PMID */}
                <tr style={{ borderBottom: '1px solid var(--border-subtle)', backgroundColor: 'var(--bg-surface-elevated)' }}>
                  <td style={{ padding: '10px 14px', fontWeight: 600, color: 'var(--text-primary)' }}>
                    <span>PMID Identifier</span>
                  </td>
                  <td style={{ padding: '10px 14px' }}>{renderFieldBadge(pmidState)}</td>
                  {records.map((rec) => (
                    <td key={rec.id} style={{ padding: '10px 14px', borderLeft: '1px solid var(--border-subtle)' }}>
                      {rec.pmid ? <code style={{ color: 'var(--text-primary)' }}>{rec.pmid}</code> : <span style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>Brak</span>}
                    </td>
                  ))}
                </tr>

                {/* OpenAlex ID */}
                <tr style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                  <td style={{ padding: '10px 14px', fontWeight: 600, color: 'var(--text-primary)' }}>
                    <span>OpenAlex ID</span>
                  </td>
                  <td style={{ padding: '10px 14px' }}>{renderFieldBadge(openalexState)}</td>
                  {records.map((rec) => (
                    <td key={rec.id} style={{ padding: '10px 14px', borderLeft: '1px solid var(--border-subtle)' }}>
                      {rec.openalex_id ? <code style={{ color: 'var(--text-primary)' }}>{rec.openalex_id}</code> : <span style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>Brak</span>}
                    </td>
                  ))}
                </tr>

                {/* Provenance */}
                <tr style={{ backgroundColor: 'var(--bg-surface-elevated)' }}>
                  <td style={{ padding: '10px 14px', fontWeight: 600, color: 'var(--text-primary)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <Database size={14} style={{ color: 'var(--text-muted)' }} />
                      <span>Pochodzenie (Provenance)</span>
                    </div>
                  </td>
                  <td style={{ padding: '10px 14px' }}>
                    <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Źródła danych</span>
                  </td>
                  {records.map((rec) => (
                    <td key={rec.id} style={{ padding: '10px 14px', borderLeft: '1px solid var(--border-subtle)' }}>
                      {rec.provenance && rec.provenance.length > 0 ? (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                          {rec.provenance.map((p, pIdx) => (
                            <div key={pIdx} style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                              <strong>{p.source}</strong> (ID: <code>{p.source_record_id}</code>)
                              {p.retrieved_at && (
                                <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                                  Pobrano: {new Date(p.retrieved_at).toLocaleDateString()}
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      ) : (
                        <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                          Źródło: <strong>{rec.source}</strong>
                        </span>
                      )}
                    </td>
                  ))}
                </tr>
              </tbody>
            </table>
          </div>

          {/* Decision & Optional Rationale Form */}
          <div
            style={{
              padding: '16px',
              borderRadius: 'var(--radius-md)',
              backgroundColor: 'var(--bg-surface-elevated)',
              border: '1px solid var(--border-strong)',
              display: 'flex',
              flexDirection: 'column',
              gap: '12px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <label
                htmlFor={`rationale-input-${groupId}`}
                style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '6px' }}
              >
                <ShieldCheck size={16} style={{ color: 'var(--status-info-text)' }} />
                <span>Uzasadnienie Decyzji Badacza (Rationale - Opcjonalne)</span>
              </label>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                {rationale.length} / 1000 znaków
              </span>
            </div>

            <textarea
              id={`rationale-input-${groupId}`}
              value={rationale}
              onChange={(e) => setRationale(e.target.value)}
              disabled={saving}
              placeholder="Wprowadź opcjonalne uzasadnienie decyzji (np. Potwierdzono spójność publikacji na podstawie pełnego tekstu)..."
              maxLength={1000}
              rows={3}
              style={{
                width: '100%',
                padding: '10px 12px',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--border-subtle)',
                backgroundColor: 'var(--bg-primary)',
                color: 'var(--text-primary)',
                fontSize: '0.85rem',
                fontFamily: 'inherit',
                resize: 'vertical',
              }}
            />

            {/* Action Buttons & Status Indicators */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                {saving && (
                  <span
                    style={{
                      fontSize: '0.8rem',
                      color: 'var(--text-muted)',
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '4px',
                    }}
                  >
                    <Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} />
                    <span>Zapisywanie w API...</span>
                  </span>
                )}
                {saved && !saving && (
                  <span style={{ fontSize: '0.8rem', color: 'var(--status-success-text)', fontWeight: 700 }}>
                    Decyzja Zapisana!
                  </span>
                )}
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <button
                  onClick={() => handleDecision('APPROVE')}
                  disabled={saving}
                  aria-label="Zatwierdź tę grupę jako potwierdzony duplikat"
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '6px',
                    padding: '8px 16px',
                    borderRadius: 'var(--radius-md)',
                    backgroundColor:
                      decisionStatus === 'APPROVE'
                        ? 'var(--status-success-bg)'
                        : 'var(--bg-surface)',
                    color:
                      decisionStatus === 'APPROVE'
                        ? 'var(--status-success-text)'
                        : 'var(--text-primary)',
                    border:
                      decisionStatus === 'APPROVE'
                        ? '2px solid var(--status-success-border)'
                        : '1px solid var(--border-strong)',
                    fontSize: '0.85rem',
                    fontWeight: decisionStatus === 'APPROVE' ? 700 : 600,
                    cursor: saving ? 'wait' : 'pointer',
                  }}
                >
                  <Check size={16} />
                  <span>Approve (Duplikat)</span>
                </button>

                <button
                  onClick={() => handleDecision('REJECT')}
                  disabled={saving}
                  aria-label="Odrzuć tę grupę jako niebędącą duplikatem"
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '6px',
                    padding: '8px 16px',
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
                    fontSize: '0.85rem',
                    fontWeight: decisionStatus === 'REJECT' ? 700 : 500,
                    cursor: saving ? 'wait' : 'pointer',
                  }}
                >
                  <X size={16} />
                  <span>Reject (Odrzuć)</span>
                </button>
              </div>
            </div>

            {error && (
              <div
                style={{
                  fontSize: '0.8rem',
                  color: 'var(--status-error-text)',
                  backgroundColor: 'rgba(239, 68, 68, 0.08)',
                  padding: '8px 12px',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid rgba(239, 68, 68, 0.2)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  marginTop: '4px',
                }}
              >
                <span>Błąd zapisu: {error}</span>
                <button
                  onClick={() => handleDecision(decisionStatus === 'REJECT' ? 'REJECT' : 'APPROVE')}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '4px',
                    fontSize: '0.75rem',
                    color: 'var(--status-error-text)',
                    fontWeight: 700,
                    background: 'none',
                    border: 'none',
                    cursor: 'pointer',
                    textDecoration: 'underline',
                  }}
                >
                  <RefreshCw size={12} />
                  <span>Ponów Próbę (Retry)</span>
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </Card>
  );
};
