import React, { useState } from 'react';
import { Plus, Trash2, Code2, Layers, Tag } from 'lucide-react';
import { ConceptGroup } from '../../types';
import { Card } from '../common/Card';

interface ConceptGroupQueryBuilderProps {
  initialGroups: ConceptGroup[];
  onGroupsChange?: (groups: ConceptGroup[]) => void;
}

export const ConceptGroupQueryBuilder: React.FC<ConceptGroupQueryBuilderProps> = ({
  initialGroups,
  onGroupsChange,
}) => {
  const [groups, setGroups] = useState<ConceptGroup[]>(initialGroups);
  const [newGroupName, setNewGroupName] = useState('');
  const [termInputs, setTermInputs] = useState<{ [groupId: string]: string }>({});

  const updateGroups = (updated: ConceptGroup[]) => {
    setGroups(updated);
    if (onGroupsChange) onGroupsChange(updated);
  };

  const handleAddGroup = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newGroupName.trim()) return;
    const newGroup: ConceptGroup = {
      id: `cg-${Date.now()}`,
      name: newGroupName.trim(),
      terms: [],
    };
    updateGroups([...groups, newGroup]);
    setNewGroupName('');
  };

  const handleRemoveGroup = (groupId: string) => {
    updateGroups(groups.filter((g) => g.id !== groupId));
  };

  const handleAddTerm = (groupId: string) => {
    const term = termInputs[groupId]?.trim();
    if (!term) return;
    const updated = groups.map((g) => {
      if (g.id === groupId && !g.terms.includes(term)) {
        return { ...g, terms: [...g.terms, term] };
      }
      return g;
    });
    updateGroups(updated);
    setTermInputs({ ...termInputs, [groupId]: '' });
  };

  const handleRemoveTerm = (groupId: string, termToRemove: string) => {
    const updated = groups.map((g) => {
      if (g.id === groupId) {
        return { ...g, terms: g.terms.filter((t) => t !== termToRemove) };
      }
      return g;
    });
    updateGroups(updated);
  };

  // Generate rendered Boolean Query: (Term1 OR Term2) AND (Term3 OR Term4)
  const renderedQuery = groups
    .filter((g) => g.terms.length > 0)
    .map((g) => `(${g.terms.map((t) => `"${t}"`).join(' OR ')})`)
    .join('\n  AND ');

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h3 style={{ fontSize: '1.05rem', fontWeight: 700, color: 'var(--text-primary)' }}>
            Budownik Zapytania z Grup Pojęć (Concept Groups Builder)
          </h3>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '2px' }}>
            Zdefiniuj niezależne grupy pojęciowe (OR wewnątrz grupy). Grupy są łączone operatorem AND.
          </p>
        </div>
      </div>

      {/* Add New Concept Group Bar */}
      <form
        onSubmit={handleAddGroup}
        style={{
          display: 'flex',
          gap: '8px',
          backgroundColor: 'var(--bg-surface)',
          padding: '12px',
          borderRadius: 'var(--radius-md)',
          border: '1px solid var(--border-subtle)',
        }}
      >
        <input
          type="text"
          value={newGroupName}
          onChange={(e) => setNewGroupName(e.target.value)}
          placeholder="Nazwa nowej grupy pojęć (np. Quality Management Terms)..."
          style={{
            flex: 1,
            padding: '8px 12px',
            borderRadius: 'var(--radius-md)',
            backgroundColor: 'var(--bg-primary)',
            border: '1px solid var(--border-strong)',
            fontSize: '0.875rem',
          }}
        />
        <button
          type="submit"
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '6px',
            padding: '8px 16px',
            borderRadius: 'var(--radius-md)',
            backgroundColor: 'var(--accent-primary)',
            color: '#fff',
            fontWeight: 600,
            fontSize: '0.85rem',
          }}
        >
          <Plus size={16} />
          <span>Dodaj Grupę</span>
        </button>
      </form>

      {/* Concept Groups List */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {groups.map((group, groupIdx) => (
          <React.Fragment key={group.id}>
            {groupIdx > 0 && (
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '12px',
                  margin: '4px 0',
                  color: 'var(--accent-primary)',
                  fontWeight: 700,
                  fontSize: '0.8rem',
                  letterSpacing: '0.05em',
                }}
              >
                <div style={{ flex: 1, height: '1px', backgroundColor: 'var(--border-subtle)' }} />
                <span>OPERATOR INTER-GROUP: AND</span>
                <div style={{ flex: 1, height: '1px', backgroundColor: 'var(--border-subtle)' }} />
              </div>
            )}

            <Card
              title={
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Layers size={18} style={{ color: 'var(--accent-primary)' }} />
                  <span>Grupa {groupIdx + 1}: {group.name}</span>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                    ({group.terms.length} terminów, OR)
                  </span>
                </div>
              }
              action={
                <button
                  onClick={() => handleRemoveGroup(group.id)}
                  style={{
                    color: 'var(--status-error-text)',
                    padding: '4px',
                    borderRadius: 'var(--radius-sm)',
                  }}
                  title="Usuń grupę"
                >
                  <Trash2 size={16} />
                </button>
              }
            >
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {/* Terms Badges */}
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                  {group.terms.map((term) => (
                    <span
                      key={term}
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '6px',
                        padding: '4px 10px',
                        borderRadius: 'var(--radius-md)',
                        backgroundColor: 'var(--bg-surface-elevated)',
                        border: '1px solid var(--border-strong)',
                        fontSize: '0.85rem',
                        color: 'var(--text-primary)',
                      }}
                    >
                      <Tag size={12} style={{ color: 'var(--accent-primary)' }} />
                      <span>"{term}"</span>
                      <button
                        onClick={() => handleRemoveTerm(group.id, term)}
                        style={{ color: 'var(--text-muted)', cursor: 'pointer' }}
                      >
                        ×
                      </button>
                    </span>
                  ))}
                  {group.terms.length === 0 && (
                    <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontStyle: 'italic' }}>
                      Brak terminów w tej grupie. Dodaj termin poniżej.
                    </span>
                  )}
                </div>

                {/* Add Term Input */}
                <div style={{ display: 'flex', gap: '8px' }}>
                  <input
                    type="text"
                    value={termInputs[group.id] || ''}
                    onChange={(e) =>
                      setTermInputs({ ...termInputs, [group.id]: e.target.value })
                    }
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        e.preventDefault();
                        handleAddTerm(group.id);
                      }
                    }}
                    placeholder="Wpisz słowo kluczowe/frazę i naciśnij Enter lub Dodaj..."
                    style={{
                      flex: 1,
                      padding: '6px 12px',
                      borderRadius: 'var(--radius-md)',
                      backgroundColor: 'var(--bg-primary)',
                      border: '1px solid var(--border-strong)',
                      fontSize: '0.85rem',
                    }}
                  />
                  <button
                    onClick={() => handleAddTerm(group.id)}
                    style={{
                      padding: '6px 12px',
                      borderRadius: 'var(--radius-md)',
                      backgroundColor: 'var(--bg-surface-elevated)',
                      border: '1px solid var(--border-strong)',
                      color: 'var(--text-primary)',
                      fontSize: '0.8rem',
                      fontWeight: 500,
                    }}
                  >
                    + Dodaj Termin
                  </button>
                </div>
              </div>
            </Card>
          </React.Fragment>
        ))}
      </div>

      {/* Rendered Boolean Query String Preview */}
      <Card
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Code2 size={18} style={{ color: 'var(--status-info-text)' }} />
            <span>Wyrenderowane Zapytanie Boolean (Generated Search Query)</span>
          </div>
        }
      >
        <pre
          style={{
            backgroundColor: 'var(--bg-primary)',
            padding: '14px 16px',
            borderRadius: 'var(--radius-md)',
            border: '1px solid var(--border-strong)',
            fontFamily: 'var(--font-mono)',
            fontSize: '0.85rem',
            color: 'var(--status-info-text)',
            whiteSpace: 'pre-wrap',
            lineHeight: 1.6,
          }}
        >
          {renderedQuery || '/* Zdefiniuj co najmniej jedną grupę pojęć z terminami */'}
        </pre>
      </Card>
    </div>
  );
};
