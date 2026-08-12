import React from 'react';
import { Card } from '../common/Card';
import { Button } from '../common/Button';
import { Badge } from '../common/Badge';
import {
  QualityAssessmentRecordDetail,
  QualityAssessmentResponseValue,
} from '../../services/api/qualityAssessmentApi';
import { QualityAssessmentHistoryPanel } from './QualityAssessmentHistoryPanel';
import {
  CheckCircle2,
  XCircle,
  HelpCircle,
  Save,
  ChevronRight,
  ChevronLeft,
  ExternalLink,
  BookOpen,
  FileText,
  AlertCircle,
  Settings,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';

interface QualityAssessmentExecutionPanelProps {
  projectId: string;
  detail: QualityAssessmentRecordDetail;
  draftResponses: Record<string, { value: QualityAssessmentResponseValue | null; justification: string }>;
  onResponseChange: (criterionId: string, value: QualityAssessmentResponseValue) => void;
  onJustificationChange: (criterionId: string, justification: string) => void;
  onSave: (goNext: boolean) => void;
  saving: boolean;
  dirty: boolean;
  hasPreviousPage: boolean;
  hasNextPage: boolean;
  onPrevious: () => void;
  onNext: () => void;
  recordIndex: number;
  totalRecords: number;
}

const responseOptions: Array<{
  value: QualityAssessmentResponseValue;
  label: string;
  icon: React.ReactNode;
  activeBg: string;
  activeColor: string;
  activeBorder: string;
}> = [
  {
    value: 'YES',
    label: 'TAK',
    icon: <CheckCircle2 size={16} />,
    activeBg: 'var(--status-success-bg, rgba(34, 197, 94, 0.15))',
    activeColor: 'var(--status-success-text, #22c55e)',
    activeBorder: 'var(--status-success-border, #22c55e)',
  },
  {
    value: 'NO',
    label: 'NIE',
    icon: <XCircle size={16} />,
    activeBg: 'var(--status-error-bg, rgba(239, 68, 68, 0.15))',
    activeColor: 'var(--status-error-text, #ef4444)',
    activeBorder: 'var(--status-error-border, #ef4444)',
  },
  {
    value: 'CANNOT_DETERMINE',
    label: 'NIE MOŻNA OKREŚLIĆ',
    icon: <HelpCircle size={16} />,
    activeBg: 'var(--status-warning-bg, rgba(234, 179, 8, 0.15))',
    activeColor: 'var(--status-warning-text, #eab308)',
    activeBorder: 'var(--status-warning-border, #eab308)',
  },
];

export const QualityAssessmentExecutionPanel: React.FC<QualityAssessmentExecutionPanelProps> = ({
  projectId,
  detail,
  draftResponses,
  onResponseChange,
  onJustificationChange,
  onSave,
  saving,
  dirty,
  hasPreviousPage,
  hasNextPage,
  onPrevious,
  onNext,
  recordIndex,
  totalRecords,
}) => {
  const navigate = useNavigate();
  const pub = detail.publication;
  const template = detail.template;

  // Validation: Check if all required criteria are answered with non-blank justification
  const missingRequired = template.criteria.some((crit) => {
    const draft = draftResponses[crit.criterion_id];
    if (crit.is_required && !draft?.value) return true;
    if (draft?.value && (!draft.justification || !draft.justification.trim())) return true;
    return false;
  });

  const canSave = !missingRequired && !saving;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Top Banner: Tool / Template Context + Config Link */}
      <div
        style={{
          padding: '12px 16px',
          backgroundColor: 'var(--bg-surface-elevated)',
          borderRadius: 'var(--radius-md)',
          border: '1px solid var(--border-subtle)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <BookOpen size={18} style={{ color: 'var(--accent-primary)' }} />
          <div>
            <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-primary)' }}>
              Aktywne Narzędzie Oceny: {template.name} (v{template.version})
            </span>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              Narzędzie: {template.tool_id} | Szablon Key: {template.template_key} | Liczba kryteriów: {template.criteria.length}
            </div>
          </div>
        </div>

        <Button
          variant="secondary"
          size="sm"
          icon={<Settings size={14} />}
          onClick={() => navigate(`/projects/${projectId}/quality-assessment/configuration`)}
        >
          Zmień Szablon QA
        </Button>
      </div>

      {/* Notice if publication already has a previous assessment */}
      {detail.latest_assessment && (
        <div
          style={{
            padding: '10px 14px',
            backgroundColor: 'var(--accent-subtle)',
            borderRadius: 'var(--radius-md)',
            border: '1px solid var(--accent-border, rgba(59, 130, 246, 0.3))',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            fontSize: '0.85rem',
            color: 'var(--text-primary)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <FileText size={16} style={{ color: 'var(--accent-primary)' }} />
            <span>
              Ta publikacja posiada już ocenę z dnia {new Date(detail.latest_assessment.assessed_at).toLocaleString()}.
              Ponowny zapis utworzy nową wersję oceny (append-only).
            </span>
          </div>
          <Badge variant="completed">Oceniono</Badge>
        </div>
      )}

      {/* Publication Details Card */}
      <Card
        title={
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
            <span style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--text-primary)' }}>
              {pub.title}
            </span>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
              Rekord {recordIndex + 1} z {totalRecords}
            </span>
          </div>
        }
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {/* Metadata chips */}
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '12px', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
            {pub.authors.length > 0 && (
              <div>
                <strong>Autorzy:</strong> {pub.authors.map((a) => a.display_name).join(', ')}
              </div>
            )}
            {pub.publication_year && (
              <div>
                <strong>Rok:</strong> {pub.publication_year}
              </div>
            )}
            {pub.venue?.name && (
              <div>
                <strong>Źródło / Czasopismo:</strong> {pub.venue.name}
              </div>
            )}
            {pub.doi && (
              <div>
                <strong>DOI:</strong>{' '}
                <a
                  href={`https://doi.org/${pub.doi}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{ color: 'var(--accent-primary)', textDecoration: 'none' }}
                >
                  {pub.doi}
                </a>
              </div>
            )}
          </div>

          {/* External Full-Text Reference Link */}
          {pub.urls && pub.urls.length > 0 && (
            <div style={{ fontSize: '0.8rem', marginTop: '2px' }}>
              <strong>Odnośnik do Pełnego Tekstu:</strong>{' '}
              {pub.urls.map((url, idx) => (
                <a
                  key={url + idx}
                  href={url}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '4px',
                    color: 'var(--accent-primary)',
                    marginRight: '12px',
                    textDecoration: 'none',
                  }}
                >
                  {url} <ExternalLink size={12} />
                </a>
              ))}
            </div>
          )}

          {/* Abstract */}
          {pub.abstract && (
            <div
              style={{
                marginTop: '6px',
                padding: '12px',
                backgroundColor: 'var(--bg-primary)',
                borderRadius: 'var(--radius-md)',
                fontSize: '0.85rem',
                color: 'var(--text-secondary)',
                lineHeight: 1.5,
                maxHeight: '200px',
                overflowY: 'auto',
              }}
            >
              <strong style={{ display: 'block', marginBottom: '4px', color: 'var(--text-primary)' }}>Abstrakt:</strong>
              {pub.abstract}
            </div>
          )}
        </div>
      </Card>

      {/* Quality Assessment Form Card */}
      <Card
        title={
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--text-primary)' }}>
              Kwestionariusz Oceny Jakościowej ({template.name})
            </span>
            {dirty && (
              <span style={{ fontSize: '0.75rem', color: 'var(--status-warning-text)', fontWeight: 600 }}>
                • Niezapisane zmiany
              </span>
            )}
          </div>
        }
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {template.criteria.map((crit, idx) => {
            const draft = draftResponses[crit.criterion_id] || { value: null, justification: '' };
            const selectedVal = draft.value;

            return (
              <div
                key={crit.criterion_id}
                style={{
                  padding: '16px',
                  backgroundColor: 'var(--bg-primary)',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--border-subtle)',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '12px',
                }}
              >
                {/* Question Header */}
                <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '12px' }}>
                  <div>
                    <div style={{ fontWeight: 600, fontSize: '0.95rem', color: 'var(--text-primary)' }}>
                      {idx + 1}. {crit.question}
                    </div>
                    {crit.guidance && (
                      <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '4px', lineHeight: 1.4 }}>
                        Wytyczne: {crit.guidance}
                      </p>
                    )}
                  </div>

                  <Badge variant={crit.is_required ? 'error' : 'default'}>
                    {crit.is_required ? 'Wymagane' : 'Opcjonalne'}
                  </Badge>
                </div>

                {/* Segmented Response Choice Buttons (No raw radio buttons) */}
                <div>
                  <div style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '6px' }}>
                    Odpowiedź:
                  </div>

                  <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                    {responseOptions.map((opt) => {
                      const isSelected = selectedVal === opt.value;

                      return (
                        <button
                          key={opt.value}
                          type="button"
                          onClick={() => onResponseChange(crit.criterion_id, opt.value)}
                          style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '6px',
                            padding: '8px 16px',
                            borderRadius: 'var(--radius-md)',
                            fontSize: '0.85rem',
                            fontWeight: isSelected ? 700 : 500,
                            cursor: 'pointer',
                            transition: 'all 0.15s ease',
                            border: `2px solid ${isSelected ? opt.activeBorder : 'var(--border-subtle)'}`,
                            backgroundColor: isSelected ? opt.activeBg : 'var(--bg-surface)',
                            color: isSelected ? opt.activeColor : 'var(--text-secondary)',
                            outline: 'none',
                          }}
                        >
                          {opt.icon}
                          <span>{opt.label}</span>
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* Criterion Justification Textarea */}
                <div>
                  <label
                    htmlFor={`justification-${crit.criterion_id}`}
                    style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '4px' }}
                  >
                    Uzasadnienie (wymagane w przypadku wyboru odpowiedzi):
                  </label>

                  <textarea
                    id={`justification-${crit.criterion_id}`}
                    rows={2}
                    value={draft.justification}
                    onChange={(e) => onJustificationChange(crit.criterion_id, e.target.value)}
                    placeholder="Wprowadź uzasadnienie oceny dla tego kryterium..."
                    style={{
                      width: '100%',
                      padding: '8px 12px',
                      borderRadius: 'var(--radius-md)',
                      backgroundColor: 'var(--bg-surface)',
                      color: 'var(--text-primary)',
                      border: '1px solid var(--border-subtle)',
                      fontSize: '0.85rem',
                      fontFamily: 'inherit',
                      resize: 'vertical',
                    }}
                  />
                  {selectedVal && (!draft.justification || !draft.justification.trim()) && (
                    <span style={{ fontSize: '0.75rem', color: 'var(--status-error-text)', marginTop: '2px', display: 'block' }}>
                      Wymagane jest wprowadzenie niepustego uzasadnienia.
                    </span>
                  )}
                </div>
              </div>
            );
          })}

          {/* Missing required validation warning */}
          {missingRequired && (
            <div
              style={{
                padding: '10px 14px',
                backgroundColor: 'var(--status-error-bg, rgba(239, 68, 68, 0.1))',
                border: '1px solid var(--status-error-border, #ef4444)',
                borderRadius: 'var(--radius-md)',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                fontSize: '0.85rem',
                color: 'var(--status-error-text)',
              }}
            >
              <AlertCircle size={16} />
              <span>
                Aby zapisać ocenę, musisz odpowiedzieć na wszystkie wymagane pytania oraz podać niepuste uzasadnienie dla każdego z nich.
              </span>
            </div>
          )}

          {/* Action Buttons: Save & Save Next, Navigation */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              paddingTop: '12px',
              borderTop: '1px solid var(--border-subtle)',
            }}
          >
            {/* Pagination Prev/Next */}
            <div style={{ display: 'flex', gap: '8px' }}>
              <Button
                variant="secondary"
                disabled={!hasPreviousPage || saving}
                icon={<ChevronLeft size={16} />}
                onClick={onPrevious}
              >
                Poprzedni
              </Button>
              <Button
                variant="secondary"
                disabled={!hasNextPage || saving}
                icon={<ChevronRight size={16} />}
                onClick={onNext}
              >
                Następny
              </Button>
            </div>

            {/* Save Actions */}
            <div style={{ display: 'flex', gap: '12px' }}>
              <Button
                variant="secondary"
                disabled={!canSave}
                icon={<Save size={16} />}
                onClick={() => onSave(false)}
              >
                {saving ? 'Zapisywanie...' : 'Zapisz'}
              </Button>

              <Button
                variant="primary"
                disabled={!canSave}
                icon={<ChevronRight size={16} />}
                onClick={() => onSave(true)}
              >
                {saving ? 'Zapisywanie...' : 'Zapisz i następny'}
              </Button>
            </div>
          </div>
        </div>
      </Card>

      {/* Historical Audit Trail */}
      {detail.history && detail.history.length > 0 && (
        <QualityAssessmentHistoryPanel
          history={detail.history}
          currentTemplateVersion={template.version}
        />
      )}
    </div>
  );
};
