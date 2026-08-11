import React, { useState } from 'react';
import { Card } from '../common/Card';
import { Badge } from '../common/Badge';
import { History, ChevronDown, ChevronUp, User, Calendar, CheckCircle2, XCircle, HelpCircle } from 'lucide-react';
import { QualityAssessment, QualityAssessmentResponseValue } from '../../services/api/qualityAssessmentApi';

interface QualityAssessmentHistoryPanelProps {
  history: QualityAssessment[];
  currentTemplateVersion?: number | null;
}

const valueLabels: Record<QualityAssessmentResponseValue, { label: string; icon: React.ReactNode; color: string }> = {
  YES: { label: 'TAK', icon: <CheckCircle2 size={14} />, color: 'var(--status-success-text)' },
  NO: { label: 'NIE', icon: <XCircle size={14} />, color: 'var(--status-error-text)' },
  CANNOT_DETERMINE: { label: 'NIE MOŻNA OKREŚLIĆ', icon: <HelpCircle size={14} />, color: 'var(--status-warning-text)' },
};

export const QualityAssessmentHistoryPanel: React.FC<QualityAssessmentHistoryPanelProps> = ({
  history,
}) => {
  const [expanded, setExpanded] = useState<boolean>(false);

  if (history.length === 0) return null;

  return (
    <Card
      title={
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            width: '100%',
            cursor: 'pointer',
          }}
          onClick={() => setExpanded(!expanded)}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <History size={18} style={{ color: 'var(--accent-primary)' }} />
            <span>Historia Ocen Publikacji ({history.length})</span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Badge variant="info">{history.length === 1 ? '1 ocena' : `${history.length} ocen`}</Badge>
            {expanded ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
          </div>
        </div>
      }
    >
      {expanded && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', marginTop: '12px' }}>
          <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            System przechowuje pełny ślad audytowy wszystkich zacommitowanych ocen tej publikacji. Nowe zapisy nie zastępują historycznych prób.
          </p>

          {history.map((assessment, index) => (
            <div
              key={assessment.assessment_id}
              style={{
                padding: '14px',
                backgroundColor: 'var(--bg-primary)',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--border-subtle)',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px', fontSize: '0.85rem' }}>
                  <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                    Ocena #{history.length - index} {index === 0 ? '(Najnowsza)' : ''}
                  </span>
                  <span style={{ display: 'flex', alignItems: 'center', gap: '4px', color: 'var(--text-muted)' }}>
                    <User size={14} /> {assessment.reviewer_id}
                  </span>
                  <span style={{ display: 'flex', alignItems: 'center', gap: '4px', color: 'var(--text-muted)' }}>
                    <Calendar size={14} /> {new Date(assessment.assessed_at).toLocaleString()}
                  </span>
                </div>

                <Badge variant="default">
                  Szablon ID: {assessment.template_id.substring(0, 8)}...
                </Badge>
              </div>

              {/* Criteria responses */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginTop: '8px' }}>
                {assessment.responses.map((resp) => {
                  const valInfo = valueLabels[resp.response_value] || {
                    label: resp.response_value,
                    icon: null,
                    color: 'var(--text-primary)',
                  };

                  return (
                    <div
                      key={resp.response_id}
                      style={{
                        padding: '10px 12px',
                        backgroundColor: 'var(--bg-surface)',
                        borderRadius: 'var(--radius-sm)',
                        borderLeft: `3px solid ${valInfo.color}`,
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                        <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                          {resp.question_snapshot}
                        </span>

                        <span
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '4px',
                            fontSize: '0.8rem',
                            fontWeight: 700,
                            color: valInfo.color,
                          }}
                        >
                          {valInfo.icon}
                          <span>{valInfo.label}</span>
                        </span>
                      </div>

                      {resp.justification && (
                        <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '4px', fontStyle: 'italic' }}>
                          Uzasadnienie: &quot;{resp.justification}&quot;
                        </p>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
};
