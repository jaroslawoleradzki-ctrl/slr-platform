import React, { useState } from 'react';
import { Database, Plus, ChevronDown, Info } from 'lucide-react';
import { useProject } from '../../context/ProjectContext';
import { Modal } from '../common/Modal';
import { AboutModal } from '../common/AboutModal';
import { APP_VERSION } from '../../config/version';

export const Header: React.FC = () => {
  const { projects, activeProject, setActiveProjectId, createNewProject } = useProject();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isAboutOpen, setIsAboutOpen] = useState(false);
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [protocolVersion, setProtocolVersion] = useState('0.1');

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) return;
    await createNewProject(title, description, protocolVersion);
    setTitle('');
    setDescription('');
    setIsModalOpen(false);
  };

  return (
    <header
      style={{
        height: '60px',
        backgroundColor: 'var(--bg-surface)',
        borderBottom: '1px solid var(--border-subtle)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 24px',
        position: 'sticky',
        top: 0,
        zIndex: 50,
      }}
    >
      {/* Brand & Project Selector */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div
            style={{
              width: '32px',
              height: '32px',
              borderRadius: 'var(--radius-md)',
              backgroundColor: 'var(--accent-primary)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#fff',
            }}
          >
            <Database size={18} />
          </div>
          <div>
            <h1
              style={{
                fontSize: '0.95rem',
                fontWeight: 700,
                color: 'var(--text-primary)',
                letterSpacing: '-0.02em',
                lineHeight: 1.1,
              }}
            >
              SLR PLATFORM
            </h1>
            <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
              v{APP_VERSION} • Systematic Review Workbench
            </span>
          </div>
        </div>

        <div style={{ height: '24px', width: '1px', backgroundColor: 'var(--border-subtle)' }} />

        {/* Project Selector */}
        <div style={{ position: 'relative', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 500 }}>
            Projekt:
          </span>
          <select
            value={activeProject?.id || ''}
            onChange={(e) => setActiveProjectId(e.target.value)}
            style={{
              backgroundColor: 'var(--bg-primary)',
              color: 'var(--text-primary)',
              border: '1px solid var(--border-strong)',
              borderRadius: 'var(--radius-md)',
              padding: '6px 28px 6px 12px',
              fontSize: '0.85rem',
              fontWeight: 500,
              appearance: 'none',
              cursor: 'pointer',
            }}
          >
            {projects.map((proj) => (
              <option key={proj.id} value={proj.id}>
                {proj.title} (v{proj.protocolVersion})
              </option>
            ))}
          </select>
          <ChevronDown
            size={14}
            style={{
              position: 'absolute',
              right: '8px',
              pointerEvents: 'none',
              color: 'var(--text-muted)',
            }}
          />

          <button
            onClick={() => setIsModalOpen(true)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              padding: '6px 10px',
              borderRadius: 'var(--radius-md)',
              backgroundColor: 'var(--bg-surface-elevated)',
              color: 'var(--text-primary)',
              fontSize: '0.8rem',
              fontWeight: 500,
              border: '1px solid var(--border-strong)',
            }}
            title="Utwórz Nowy Projekt"
          >
            <Plus size={14} />
            <span>Nowy Projekt</span>
          </button>
        </div>
      </div>

      {/* Right Side: Runtime Status & About App */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            fontSize: '0.75rem',
            color: 'var(--status-info-text)',
            backgroundColor: 'var(--status-info-bg)',
            padding: '4px 10px',
            borderRadius: 'var(--radius-full)',
            border: '1px solid var(--status-info-border)',
          }}
        >
          <Database size={12} />
          <span>Mock API / Demo Data</span>
        </div>

        <button
          onClick={() => setIsAboutOpen(true)}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '4px',
            padding: '4px 10px',
            borderRadius: 'var(--radius-full)',
            backgroundColor: 'var(--bg-surface-elevated)',
            color: 'var(--text-secondary)',
            fontSize: '0.75rem',
            border: '1px solid var(--border-strong)',
            fontWeight: 500,
          }}
          title="Informacje o aplikacji"
        >
          <Info size={12} />
          <span>O aplikacji</span>
        </button>
      </div>

      {/* Create Project Modal */}
      <Modal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} title="Utwórz Nowy Projekt SLR">
        <form onSubmit={handleCreate} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div>
            <label style={{ display: 'block', fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '4px' }}>
              Tytuł Przeglądu Badawczego *
            </label>
            <input
              type="text"
              required
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="np. Microservices Resilience Tactics in Cloud Infrastructure"
              style={{
                width: '100%',
                padding: '8px 12px',
                borderRadius: 'var(--radius-md)',
                backgroundColor: 'var(--bg-primary)',
                border: '1px solid var(--border-strong)',
                fontSize: '0.9rem',
              }}
            />
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '4px' }}>
              Opis / Cel Badawczy
            </label>
            <textarea
              rows={3}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Cel przeglądu, pytania badawcze (RQ) oraz zakres dziedzinowy..."
              style={{
                width: '100%',
                padding: '8px 12px',
                borderRadius: 'var(--radius-md)',
                backgroundColor: 'var(--bg-primary)',
                border: '1px solid var(--border-strong)',
                fontSize: '0.9rem',
              }}
            />
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '4px' }}>
              Wersja Protokołu SLR
            </label>
            <input
              type="text"
              value={protocolVersion}
              onChange={(e) => setProtocolVersion(e.target.value)}
              style={{
                width: '140px',
                padding: '8px 12px',
                borderRadius: 'var(--radius-md)',
                backgroundColor: 'var(--bg-primary)',
                border: '1px solid var(--border-strong)',
                fontSize: '0.9rem',
              }}
            />
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '8px' }}>
            <button
              type="button"
              onClick={() => setIsModalOpen(false)}
              style={{
                padding: '8px 16px',
                borderRadius: 'var(--radius-md)',
                backgroundColor: 'var(--bg-surface-elevated)',
                color: 'var(--text-secondary)',
                fontSize: '0.85rem',
              }}
            >
              Anuluj
            </button>
            <button
              type="submit"
              style={{
                padding: '8px 16px',
                borderRadius: 'var(--radius-md)',
                backgroundColor: 'var(--accent-primary)',
                color: '#fff',
                fontWeight: 600,
                fontSize: '0.85rem',
              }}
            >
              Utwórz Projekt
            </button>
          </div>
        </form>
      </Modal>

      {/* About Application Modal */}
      <AboutModal isOpen={isAboutOpen} onClose={() => setIsAboutOpen(false)} />
    </header>
  );
};
