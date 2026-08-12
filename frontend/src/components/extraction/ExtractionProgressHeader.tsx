import React from 'react';
import { CheckCircle2, Clock, FileSpreadsheet, AlertCircle, FileX } from 'lucide-react';
import { ExtractionProgressResponseDTO } from '../../api/extractionApi';

interface ExtractionProgressHeaderProps {
  progress: ExtractionProgressResponseDTO | null;
}

export const ExtractionProgressHeader: React.FC<ExtractionProgressHeaderProps> = ({ progress }) => {
  if (!progress) return null;

  const {
    total_eligible_publications,
    not_started_count,
    in_progress_count,
    complete_count,
    needs_review_count,
    completion_percentage,
  } = progress;

  return (
    <div
      style={{
        backgroundColor: 'var(--bg-surface)',
        border: '1px solid var(--border-subtle)',
        borderRadius: 'var(--radius-lg)',
        padding: '20px',
        marginBottom: '24px',
        display: 'flex',
        flexDirection: 'column',
        gap: '16px',
      }}
    >
      {/* Progress Bar Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <h3 style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--text-primary)', margin: 0 }}>
            Postęp Ekstrakcji Danych (Data Extraction Progress)
          </h3>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            Autorytatywny stan zwalidowanych wpisów dla publikacji zakwalifikowanych.
          </span>
        </div>
        <div style={{ fontSize: '1.25rem', fontWeight: 800, color: 'var(--accent-primary)' }}>
          {completion_percentage}%
        </div>
      </div>

      {/* Progress Bar Visual Track */}
      <div
        style={{
          width: '100%',
          height: '10px',
          backgroundColor: 'var(--bg-surface-elevated)',
          borderRadius: 'var(--radius-full)',
          overflow: 'hidden',
          border: '1px solid var(--border-subtle)',
        }}
        role="progressbar"
        aria-valuenow={completion_percentage}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label="Postęp ekstrakcji danych"
      >
        <div
          style={{
            width: `${Math.min(100, Math.max(0, completion_percentage))}%`,
            height: '100%',
            backgroundColor: 'var(--status-success-text)',
            transition: 'width 0.4s ease-in-out',
          }}
        />
      </div>

      {/* Summary Stat Cards Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '12px' }}>
        {/* Total Eligible */}
        <div
          style={{
            padding: '12px 16px',
            backgroundColor: 'var(--bg-primary)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--radius-md)',
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
          }}
        >
          <FileSpreadsheet size={20} style={{ color: 'var(--accent-primary)' }} />
          <div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 600 }}>Kwalifikowalne</div>
            <div style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--text-primary)' }}>
              {total_eligible_publications}
            </div>
          </div>
        </div>

        {/* Not Started */}
        <div
          style={{
            padding: '12px 16px',
            backgroundColor: 'var(--bg-primary)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--radius-md)',
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
          }}
        >
          <FileX size={20} style={{ color: 'var(--text-muted)' }} />
          <div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 600 }}>Nie rozpoczęto</div>
            <div style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--text-primary)' }}>
              {not_started_count}
            </div>
          </div>
        </div>

        {/* In Progress */}
        <div
          style={{
            padding: '12px 16px',
            backgroundColor: 'var(--bg-primary)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--radius-md)',
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
          }}
        >
          <Clock size={20} style={{ color: 'var(--accent-primary)' }} />
          <div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 600 }}>W trakcie (Draft)</div>
            <div style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--accent-primary)' }}>
              {in_progress_count}
            </div>
          </div>
        </div>

        {/* Complete */}
        <div
          style={{
            padding: '12px 16px',
            backgroundColor: 'var(--bg-primary)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--radius-md)',
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
          }}
        >
          <CheckCircle2 size={20} style={{ color: 'var(--status-success-text)' }} />
          <div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 600 }}>Zakończone</div>
            <div style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--status-success-text)' }}>
              {complete_count}
            </div>
          </div>
        </div>

        {/* Needs Review */}
        <div
          style={{
            padding: '12px 16px',
            backgroundColor: 'var(--bg-primary)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--radius-md)',
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
          }}
        >
          <AlertCircle size={20} style={{ color: 'var(--status-warning-text)' }} />
          <div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 600 }}>Do weryfikacji</div>
            <div style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--status-warning-text)' }}>
              {needs_review_count}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
