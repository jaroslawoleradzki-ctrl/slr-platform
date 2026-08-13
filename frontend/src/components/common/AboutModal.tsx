import React from 'react';
import { Database, Info } from 'lucide-react';
import { Modal } from './Modal';
import { Badge } from './Badge';
import { APP_VERSION, RELEASE_STATUS, RUNTIME_MODE } from '../../config/version';

interface AboutModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const AboutModal: React.FC<AboutModalProps> = ({ isOpen, onClose }) => {
  return (
    <Modal isOpen={isOpen} onClose={onClose} title="O aplikacji — SLR Platform">
      <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
        {/* Header Icon & Version Badge */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div
            style={{
              width: '48px',
              height: '48px',
              borderRadius: 'var(--radius-lg)',
              backgroundColor: 'var(--accent-primary)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#fff',
              boxShadow: 'var(--shadow-md)',
            }}
          >
            <Database size={26} />
          </div>
          <div>
            <h3 style={{ fontSize: '1.2rem', fontWeight: 800, color: 'var(--text-primary)', lineHeight: 1.2 }}>
              SLR Platform
            </h3>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '4px' }}>
              <span style={{ fontSize: '0.9rem', fontWeight: 700, color: 'var(--accent-light)' }}>
                v{APP_VERSION}
              </span>
              <Badge variant="info">{RELEASE_STATUS}</Badge>
            </div>
          </div>
        </div>

        {/* Release Identity Cards */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
          <div
            style={{
              padding: '12px 14px',
              backgroundColor: 'var(--bg-primary)',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--border-subtle)',
            }}
          >
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>
              Wersja Aplikacji (App Version)
            </span>
            <div style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--text-primary)', marginTop: '2px' }}>
              {APP_VERSION}
            </div>
          </div>

          <div
            style={{
              padding: '12px 14px',
              backgroundColor: 'var(--bg-primary)',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--border-subtle)',
            }}
          >
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>
              Tryb Działania (Runtime Mode)
            </span>
            <div style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--status-info-text)', marginTop: '4px' }}>
              {RUNTIME_MODE}
            </div>
          </div>
        </div>

        {/* Description & Domain Truth */}
        <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: 1.6, display: 'flex', flexDirection: 'column', gap: '10px' }}>
          <p>
            <strong>SLR Platform</strong> jest aplikacją wspierającą pełny cykl systematycznego przeglądu literatury (Systematic Literature Review) zgodnie ze standardami naukowymi PRISMA 2020.
          </p>
          <div
            style={{
              padding: '12px',
              borderRadius: 'var(--radius-md)',
              backgroundColor: 'var(--bg-primary)',
              border: '1px solid var(--border-strong)',
              display: 'flex',
              alignItems: 'flex-start',
              gap: '10px',
              fontSize: '0.8rem',
            }}
          >
            <Info size={16} style={{ color: 'var(--accent-primary)', flexShrink: 0, marginTop: '2px' }} />
            <div>
              <strong>Backend API Connected:</strong> Wszystkie moduły interfejsu pobierają dane z backendu API i trwałej bazy SQLite. Backend pozostaje jedynym źródłem prawdy.
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', justifyContent: 'flex-end', paddingTop: '8px', borderTop: '1px solid var(--border-subtle)' }}>
          <button
            onClick={onClose}
            style={{
              padding: '8px 16px',
              borderRadius: 'var(--radius-md)',
              backgroundColor: 'var(--accent-primary)',
              color: '#fff',
              fontWeight: 600,
              fontSize: '0.85rem',
            }}
          >
            Zamknij
          </button>
        </div>
      </div>
    </Modal>
  );
};
