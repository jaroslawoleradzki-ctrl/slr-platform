import React, { useRef, useState } from 'react';
import { Code2, Edit3, Layers, Plus, Tag, Trash2 } from 'lucide-react';
import { SearchStrategyConceptGroup } from '../../types';
import { Card } from '../common/Card';

interface Props {
  groups: SearchStrategyConceptGroup[];
  groupOperator: 'and' | 'or';
  onGroupsChange: (groups: SearchStrategyConceptGroup[]) => void;
  onGroupOperatorChange: (operator: 'and' | 'or') => void;
  disabled?: boolean;
}

interface EditedTerm {
  groupId: string;
  termIndex: number;
  originalValue: string;
}

const inputStyle: React.CSSProperties = {
  padding: '7px 12px',
  borderRadius: 'var(--radius-md)',
  backgroundColor: 'var(--bg-primary)',
  border: '1px solid var(--border-strong)',
  fontSize: '0.85rem',
  color: 'var(--text-primary)',
};

export const ConceptGroupQueryBuilder: React.FC<Props> = ({
  groups,
  groupOperator,
  onGroupsChange,
  onGroupOperatorChange,
  disabled = false,
}) => {
  const [newGroupName, setNewGroupName] = useState('');
  const [termInputs, setTermInputs] = useState<Record<string, string>>({});
  const [editedTerm, setEditedTerm] = useState<EditedTerm | null>(null);
  const [termDraft, setTermDraft] = useState('');
  const groupSequence = useRef(0);

  const updateGroup = (groupId: string, patch: Partial<SearchStrategyConceptGroup>) => {
    onGroupsChange(
      groups.map((group) => (group.group_id === groupId ? { ...group, ...patch } : group)),
    );
  };

  const addGroup = (event: React.FormEvent) => {
    event.preventDefault();
    const name = newGroupName.trim();
    if (!name) return;
    groupSequence.current += 1;
    const newId = `cg-${Date.now()}-${groupSequence.current}`;
    onGroupsChange([
      ...groups,
      {
        group_id: newId,
        name,
        terms: [],
        operator: 'or',
      },
    ]);
    setNewGroupName('');
  };

  const addTerm = (group: SearchStrategyConceptGroup) => {
    const term = termInputs[group.group_id]?.trim();
    if (!term || group.terms.includes(term)) return;
    updateGroup(group.group_id, { terms: [...group.terms, term] });
    setTermInputs((current) => ({ ...current, [group.group_id]: '' }));
  };

  const beginTermEdit = (groupId: string, termIndex: number, value: string) => {
    setEditedTerm({ groupId, termIndex, originalValue: value });
    setTermDraft(value);
  };

  const finishTermEdit = () => {
    if (!editedTerm) return;
    const value = termDraft.trim();
    if (value) {
      const group = groups.find((item) => item.group_id === editedTerm.groupId);
      if (group) {
        const terms = [...group.terms];
        terms[editedTerm.termIndex] = value;
        updateGroup(group.group_id, { terms });
      }
    }
    setEditedTerm(null);
    setTermDraft('');
  };

  const cancelTermEdit = () => {
    setEditedTerm(null);
    setTermDraft('');
  };

  const renderedQuery = groups
    .filter((group) => group.terms.length > 0)
    .map(
      (group) =>
        `(${group.terms.map((term) => `"${term}"`).join(` ${group.operator.toUpperCase()} `)})`,
    )
    .join(`\n${groupOperator.toUpperCase()}\n`);

  return (
    <div data-testid="concept-groups-builder" style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div>
        <h3 style={{ fontSize: '1.05rem', fontWeight: 700, color: 'var(--text-primary)' }}>
          Budownik Zapytania z Grup Pojęć (Concept Groups Builder)
        </h3>
        <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: 2 }}>
          Zdefiniuj niezależne grupy pojęciowe (OR wewnątrz grupy). Grupy są łączone operatorem AND.
        </p>
      </div>

      <fieldset disabled={disabled} style={{ border: 0, padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: 20 }}>
        <form
          onSubmit={addGroup}
          style={{
            display: 'flex',
            gap: 8,
            backgroundColor: 'var(--bg-surface)',
            padding: 12,
            borderRadius: 'var(--radius-md)',
            border: '1px solid var(--border-subtle)',
          }}
        >
          <input
            aria-label="Nazwa nowej grupy"
            value={newGroupName}
            onChange={(event) => setNewGroupName(event.target.value)}
            placeholder="Nazwa nowej grupy pojęć (np. Quality Management Terms)..."
            style={{ ...inputStyle, flex: 1 }}
          />
          <button
            type="submit"
            aria-label="Dodaj grupę"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
              padding: '7px 14px',
              borderRadius: 'var(--radius-md)',
              backgroundColor: 'var(--accent-primary)',
              color: '#fff',
              fontWeight: 600,
              fontSize: '0.85rem',
            }}
          >
            <Plus size={16} /> Dodaj grupę
          </button>
        </form>

        {groups.length > 1 && (
          <div
            data-testid="group-operator-separator"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 12,
              margin: '4px 0',
              color: 'var(--accent-primary)',
              fontWeight: 700,
              fontSize: '0.8rem',
              letterSpacing: '0.05em',
            }}
          >
            <div style={{ flex: 1, height: 1, backgroundColor: 'var(--border-subtle)' }} />
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span>OPERATOR INTER-GROUP:</span>
              <select
                aria-label="Operator łączący grupy"
                value={groupOperator}
                onChange={(e) => onGroupOperatorChange(e.target.value as 'and' | 'or')}
                style={{
                  ...inputStyle,
                  padding: '2px 8px',
                  fontWeight: 700,
                  color: 'var(--accent-primary)',
                }}
              >
                <option value="and">AND</option>
                <option value="or">OR</option>
              </select>
            </div>
            <div style={{ flex: 1, height: 1, backgroundColor: 'var(--border-subtle)' }} />
          </div>
        )}

        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {groups.map((group, groupIndex) => (
            <React.Fragment key={group.group_id}>
              {groupIndex > 0 && groups.length <= 1 && (
                <div
                  data-testid="group-operator-separator"
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 12,
                    margin: '4px 0',
                    color: 'var(--accent-primary)',
                    fontWeight: 700,
                    fontSize: '0.8rem',
                    letterSpacing: '0.05em',
                  }}
                >
                  <div style={{ flex: 1, height: 1, backgroundColor: 'var(--border-subtle)' }} />
                  <span>OPERATOR INTER-GROUP: {groupOperator.toUpperCase()}</span>
                  <div style={{ flex: 1, height: 1, backgroundColor: 'var(--border-subtle)' }} />
                </div>
              )}
              <Card
                title={
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                    <Layers size={18} style={{ color: 'var(--accent-primary)' }} />
                    <span>Grupa {groupIndex + 1}:</span>
                    <input
                      aria-label={`Nazwa grupy ${groupIndex + 1}`}
                      value={group.name}
                      onChange={(event) => updateGroup(group.group_id, { name: event.target.value })}
                      style={{ ...inputStyle, fontWeight: 600, minWidth: 220 }}
                    />
                    <select
                      aria-label={`Operator terminów grupy ${groupIndex + 1}`}
                      value={group.operator}
                      onChange={(e) => updateGroup(group.group_id, { operator: e.target.value as 'and' | 'or' })}
                      style={{ ...inputStyle, padding: '2px 6px', fontSize: '0.75rem' }}
                    >
                      <option value="or">OR</option>
                      <option value="and">AND</option>
                    </select>
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                      ({group.terms.length} terminów)
                    </span>
                  </div>
                }
                action={
                  <button
                    type="button"
                    aria-label={`Usuń grupę ${groupIndex + 1}`}
                    onClick={() => onGroupsChange(groups.filter((item) => item.group_id !== group.group_id))}
                    style={{ color: 'var(--status-error-text)', padding: 4, borderRadius: 'var(--radius-sm)' }}
                  >
                    <Trash2 size={16} />
                  </button>
                }
              >
                <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                    {group.terms.map((term, termIndex) => {
                      const isEditing =
                        editedTerm?.groupId === group.group_id && editedTerm.termIndex === termIndex;
                      return (
                        <span
                          key={`${group.group_id}-term-${termIndex}`}
                          data-testid="concept-term-tag"
                          style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: 6,
                            padding: '4px 10px',
                            borderRadius: 'var(--radius-md)',
                            backgroundColor: 'var(--bg-surface-elevated)',
                            border: '1px solid var(--border-strong)',
                            fontSize: '0.85rem',
                            color: 'var(--text-primary)',
                          }}
                        >
                          <Tag size={12} style={{ color: 'var(--accent-primary)' }} />
                          {isEditing ? (
                            <input
                              autoFocus
                              aria-label={`Edytuj termin ${termIndex + 1} grupy ${groupIndex + 1}`}
                              value={termDraft}
                              onChange={(event) => setTermDraft(event.target.value)}
                              onBlur={finishTermEdit}
                              onKeyDown={(event) => {
                                if (event.key === 'Enter') {
                                  event.preventDefault();
                                  finishTermEdit();
                                } else if (event.key === 'Escape') {
                                  event.preventDefault();
                                  cancelTermEdit();
                                }
                              }}
                              style={{ ...inputStyle, padding: '2px 6px' }}
                            />
                          ) : (
                            <>
                              <span>"{term}"</span>
                              <button
                                type="button"
                                aria-label={`Edytuj termin ${termIndex + 1} grupy ${groupIndex + 1}`}
                                onClick={() => beginTermEdit(group.group_id, termIndex, term)}
                                style={{ color: 'var(--text-secondary)', display: 'inline-flex' }}
                              >
                                <Edit3 size={12} />
                              </button>
                            </>
                          )}
                          <button
                            type="button"
                            aria-label={`Usuń termin ${termIndex + 1} grupy ${groupIndex + 1}`}
                            onClick={() =>
                              updateGroup(group.group_id, {
                                terms: group.terms.filter((_, index) => index !== termIndex),
                              })
                            }
                            style={{ color: 'var(--text-muted)', cursor: 'pointer' }}
                          >
                            ×
                          </button>
                        </span>
                      );
                    })}
                    {group.terms.length === 0 && (
                      <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontStyle: 'italic' }}>
                        Brak terminów w tej grupie. Dodaj termin poniżej.
                      </span>
                    )}
                  </div>
                  <div style={{ display: 'flex', gap: 8 }}>
                    <input
                      aria-label={`Nowy termin grupy ${groupIndex + 1}`}
                      value={termInputs[group.group_id] ?? ''}
                      onChange={(event) =>
                        setTermInputs((current) => ({
                          ...current,
                          [group.group_id]: event.target.value,
                        }))
                      }
                      onKeyDown={(event) => {
                        if (event.key === 'Enter') {
                          event.preventDefault();
                          addTerm(group);
                        }
                      }}
                      placeholder="Wpisz słowo kluczowe/frazę i naciśnij Enter lub Dodaj..."
                      style={{ ...inputStyle, flex: 1 }}
                    />
                    <button
                      type="button"
                      aria-label={`Dodaj termin do grupy ${groupIndex + 1}`}
                      onClick={() => addTerm(group)}
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

        <Card
          title={
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Code2 size={18} style={{ color: 'var(--status-info-text)' }} />
              <span>Roboczy podgląd zapytania Boolean</span>
            </div>
          }
          subtitle="Podgląd bieżącego formularza. Backend zwraca autorytatywne rendered_query po użyciu Wykonaj."
        >
          <pre
            data-testid="boolean-query-preview"
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
            {renderedQuery || '/* Dodaj grupy i terminy, aby zobaczyć podgląd */'}
          </pre>
        </Card>
      </fieldset>
    </div>
  );
};
