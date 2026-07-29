import React, { useState } from 'react';
import { Filter, CheckCircle2, XCircle, HelpCircle, Clock, FileText } from 'lucide-react';
import { ScreeningStatus } from '../../types';
import { Card } from '../common/Card';

interface ScreeningPipelineOverviewProps {
  screening: ScreeningStatus;
}

export const ScreeningPipelineOverview: React.FC<ScreeningPipelineOverviewProps> = ({ screening }) => {
  const [activeTab, setActiveTab] = useState<'title_abstract' | 'full_text'>('title_abstract');

  const currentData = activeTab === 'title_abstract' ? screening.titleAbstract : screening.fullText;
  const progressPercent = currentData.total > 0
    ? Math.round(((currentData.included + currentData.excluded) / currentData.total) * 100)
    : 0;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Sub-stage Tabs */}
      <div style={{ display: 'flex', borderBottom: '1px solid var(--border-subtle)', gap: '4px' }}>
        <button
          onClick={() => setActiveTab('title_abstract')}
          style={{
            padding: '10px 18px',
            fontSize: '0.9rem',
            fontWeight: activeTab === 'title_abstract' ? 600 : 400,
            color: activeTab === 'title_abstract' ? 'var(--accent-primary)' : 'var(--text-secondary)',
            borderBottom: activeTab === 'title_abstract' ? '2px solid var(--accent-primary)' : '2px solid transparent',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
          }}
        >
          <Filter size={16} />
          <span>Pod-Etap A: Title & Abstract Screening (Triage Metadanych)</span>
        </button>

        <button
          onClick={() => setActiveTab('full_text')}
          style={{
            padding: '10px 18px',
            fontSize: '0.9rem',
            fontWeight: activeTab === 'full_text' ? 600 : 400,
            color: activeTab === 'full_text' ? 'var(--accent-primary)' : 'var(--text-secondary)',
            borderBottom: activeTab === 'full_text' ? '2px solid var(--accent-primary)' : '2px solid transparent',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
          }}
        >
          <FileText size={16} />
          <span>Pod-Etap B: Full-Text Eligibility (Kwalifikacja Pełnotekstowa)</span>
        </button>
      </div>

      {/* Rationale note */}
      <div
        style={{
          padding: '10px 14px',
          backgroundColor: 'var(--bg-surface-elevated)',
          borderRadius: 'var(--radius-md)',
          fontSize: '0.8rem',
          color: 'var(--text-secondary)',
        }}
      >
        💡 <strong>Uzasadnienie architektoniczne:</strong> Title & Abstract screening zostało zaplanowane jako dedykowany pod-etap triażu metadanych o wysokiej przepustowości. Kwalifikacja pełnotekstowa następuje dopiero dla wpisów zakwalifikowanych wstępnie i wymaga weryfikacji plików PDF.
      </div>

      {/* Progress Bar & Metrics */}
      <Card
        title={activeTab === 'title_abstract' ? 'Przesiewanie Tytułów i Abstraktów' : 'Kwalifikacja Pełnotekstowa'}
        subtitle={`Postęp etapu: ${progressPercent}% (${currentData.included + currentData.excluded} z ${currentData.total} ocenionych)`}
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {/* Progress Bar */}
          <div style={{ width: '100%', height: '8px', backgroundColor: 'var(--bg-primary)', borderRadius: '4px', overflow: 'hidden', display: 'flex' }}>
            <div style={{ width: `${(currentData.included / (currentData.total || 1)) * 100}%`, backgroundColor: 'var(--status-success-border)' }} title="Włączone" />
            <div style={{ width: `${(currentData.excluded / (currentData.total || 1)) * 100}%`, backgroundColor: 'var(--status-error-border)' }} title="Wykluczone" />
            <div style={{ width: `${(currentData.pending / (currentData.total || 1)) * 100}%`, backgroundColor: 'var(--border-strong)' }} title="Oczekujące" />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px' }}>
            <div style={{ padding: '12px', backgroundColor: 'var(--bg-primary)', borderRadius: 'var(--radius-md)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.75rem', color: 'var(--status-info-text)' }}>
                <Clock size={14} />
                <span>Oczekujące (Pending)</span>
              </div>
              <div style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--text-primary)', marginTop: '4px' }}>
                {currentData.pending}
              </div>
            </div>

            <div style={{ padding: '12px', backgroundColor: 'var(--status-success-bg)', borderRadius: 'var(--radius-md)', border: '1px solid var(--status-success-border)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.75rem', color: 'var(--status-success-text)', fontWeight: 600 }}>
                <CheckCircle2 size={14} />
                <span>Włączone (Included)</span>
              </div>
              <div style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--status-success-text)', marginTop: '4px' }}>
                {currentData.included}
              </div>
            </div>

            <div style={{ padding: '12px', backgroundColor: 'var(--status-error-bg)', borderRadius: 'var(--radius-md)', border: '1px solid var(--status-error-border)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.75rem', color: 'var(--status-error-text)', fontWeight: 600 }}>
                <XCircle size={14} />
                <span>Wykluczone (Excluded)</span>
              </div>
              <div style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--status-error-text)', marginTop: '4px' }}>
                {currentData.excluded}
              </div>
            </div>

            <div style={{ padding: '12px', backgroundColor: 'var(--bg-primary)', borderRadius: 'var(--radius-md)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.75rem', color: 'var(--status-warning-text)' }}>
                <HelpCircle size={14} />
                <span>Nierozstrzygnięte</span>
              </div>
              <div style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--text-primary)', marginTop: '4px' }}>
                {currentData.unresolved}
              </div>
            </div>
          </div>
        </div>
      </Card>
    </div>
  );
};
