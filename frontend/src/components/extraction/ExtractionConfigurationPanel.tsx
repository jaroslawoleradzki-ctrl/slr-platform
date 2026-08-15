import React, { useEffect, useMemo, useState } from 'react';
import { AlertCircle, CheckCircle2, Settings, X } from 'lucide-react';
import {
  ExtractionApiError,
  ExtractionTemplateVersion,
  extractionApi,
} from '../../api/extractionApi';

interface ExtractionConfigurationPanelProps {
  projectId: string;
  currentTemplate: ExtractionTemplateVersion | null;
  hasStartedExtraction: boolean;
  onConfigured: () => void;
}

const templateKey = (template: ExtractionTemplateVersion) =>
  `${template.template_id}::${template.version}`;

export const ExtractionConfigurationPanel: React.FC<ExtractionConfigurationPanelProps> = ({
  projectId,
  currentTemplate,
  hasStartedExtraction,
  onConfigured,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [templates, setTemplates] = useState<ExtractionTemplateVersion[]>([]);
  const [selectedKey, setSelectedKey] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen) return;
    let isMounted = true;
    setIsLoading(true);
    setError(null);
    extractionApi
      .listExtractionTemplates()
      .then((availableTemplates) => {
        if (!isMounted) return;
        setTemplates(availableTemplates);
        const currentKey = currentTemplate ? templateKey(currentTemplate) : '';
        setSelectedKey(
          availableTemplates.some((item) => templateKey(item) === currentKey) ? currentKey : '',
        );
      })
      .catch((caughtError) => {
        if (!isMounted) return;
        setError(
          caughtError instanceof ExtractionApiError
            ? caughtError.message
            : 'Nie udało się pobrać katalogu szablonów ekstrakcji.',
        );
      })
      .finally(() => {
        if (isMounted) setIsLoading(false);
      });
    return () => {
      isMounted = false;
    };
  }, [isOpen, currentTemplate]);

  const selectedTemplate = useMemo(
    () => templates.find((template) => templateKey(template) === selectedKey) ?? null,
    [selectedKey, templates],
  );

  const handleSave = async () => {
    if (!selectedTemplate) return;
    setIsSaving(true);
    setError(null);
    try {
      await extractionApi.setProjectConfiguration(
        projectId,
        selectedTemplate.template_id,
        selectedTemplate.version,
      );
      setIsOpen(false);
      onConfigured();
    } catch (caughtError) {
      if (caughtError instanceof ExtractionApiError && caughtError.statusCode === 409) {
        setError(
          'Nie można zmienić szablonu, ponieważ dla projektu istnieją już rekordy ekstrakcji. '
          + 'Dotychczasowa wersja pozostaje niezmieniona.',
        );
      } else {
        setError(
          caughtError instanceof ExtractionApiError
            ? caughtError.message
            : 'Nie udało się zapisać konfiguracji ekstrakcji.',
        );
      }
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <section
      aria-label="Konfiguracja ekstrakcji danych"
      style={{
        padding: '16px',
        marginBottom: '20px',
        border: '1px solid var(--border-subtle)',
        borderRadius: 'var(--radius-lg)',
        backgroundColor: 'var(--bg-surface)',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '16px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontWeight: 700 }}>
            <Settings size={18} /> Szablon ekstrakcji danych
          </div>
          {currentTemplate ? (
            <>
              <p style={{ margin: '8px 0 4px', color: 'var(--text-primary)' }}>
                <strong>{currentTemplate.name}</strong> — wersja {currentTemplate.version}
              </p>
              {currentTemplate.description && (
                <p style={{ margin: 0, color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
                  {currentTemplate.description}
                </p>
              )}
            </>
          ) : (
            <p style={{ margin: '8px 0 0', color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
              Szablon określa, jakie informacje badacz będzie zbierać z każdej zakwalifikowanej
              publikacji. Wybierz opublikowaną wersję i sprawdź jej pola przed zapisaniem.
            </p>
          )}
        </div>
        <button
          type="button"
          onClick={() => setIsOpen((open) => !open)}
          disabled={Boolean(currentTemplate && hasStartedExtraction)}
          title={
            currentTemplate && hasStartedExtraction
              ? 'Konfiguracja jest zablokowana po rozpoczęciu ekstrakcji.'
              : undefined
          }
          style={{ whiteSpace: 'nowrap' }}
        >
          {isOpen ? <X size={16} aria-hidden="true" /> : <Settings size={16} aria-hidden="true" />}
          {' '}
          {isOpen
            ? 'Zamknij konfigurację'
            : currentTemplate
              ? 'Zmień szablon'
              : 'Skonfiguruj ekstrakcję danych'}
        </button>
      </div>

      {currentTemplate && hasStartedExtraction && (
        <p style={{ margin: '10px 0 0', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
          Konfiguracja jest zablokowana, ponieważ rozpoczęto już ekstrakcję. Istniejące rekordy
          pozostają powiązane z wersją {currentTemplate.version}.
        </p>
      )}

      {isOpen && (
        <div style={{ marginTop: '18px', borderTop: '1px solid var(--border-subtle)', paddingTop: '16px' }}>
          <h3 style={{ margin: '0 0 6px', fontSize: '1rem' }}>Dostępne opublikowane szablony</h3>
          <p style={{ margin: '0 0 14px', color: 'var(--text-secondary)', fontSize: '0.88rem' }}>
            Wybór dotyczy całego projektu. Po utworzeniu pierwszego rekordu ekstrakcji nie można
            przełączyć projektu na inną wersję szablonu.
          </p>

          {isLoading && <p>Ładowanie katalogu szablonów…</p>}
          {!isLoading && templates.length === 0 && !error && (
            <div role="status" style={{ padding: '12px', backgroundColor: 'var(--bg-surface-elevated)' }}>
              Brak aktywnych, opublikowanych szablonów ekstrakcji. Administrator musi najpierw
              dodać szablon do katalogu.
            </div>
          )}

          {!isLoading && templates.map((template) => {
            const isSelected = templateKey(template) === selectedKey;
            return (
              <label
                key={templateKey(template)}
                style={{
                  display: 'block',
                  marginBottom: '10px',
                  padding: '12px',
                  border: isSelected
                    ? '2px solid var(--accent-primary)'
                    : '1px solid var(--border-subtle)',
                  borderRadius: 'var(--radius-md)',
                  cursor: 'pointer',
                }}
              >
                <span style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <input
                    type="radio"
                    name="extraction-template-version"
                    value={templateKey(template)}
                    checked={isSelected}
                    onChange={() => setSelectedKey(templateKey(template))}
                  />
                  <strong>{template.name}</strong>
                  <span style={{ color: 'var(--text-muted)' }}>wersja {template.version}</span>
                </span>
                {template.description && (
                  <span style={{ display: 'block', margin: '6px 0 0 24px', color: 'var(--text-secondary)' }}>
                    {template.description}
                  </span>
                )}
              </label>
            );
          })}

          {selectedTemplate && (
            <div style={{ padding: '14px', backgroundColor: 'var(--bg-surface-elevated)', borderRadius: 'var(--radius-md)' }}>
              <h4 style={{ margin: '0 0 8px' }}>Pola zbierane dla publikacji</h4>
              {selectedTemplate.publication_fields.length > 0 ? (
                <ul style={{ margin: '0 0 12px', paddingLeft: '20px' }}>
                  {selectedTemplate.publication_fields.map((field) => (
                    <li key={field.field_key}>
                      {field.name}{field.is_required ? ' (wymagane)' : ''}
                    </li>
                  ))}
                </ul>
              ) : (
                <p>Brak pól na poziomie publikacji.</p>
              )}
              {selectedTemplate.repeating_groups.map((group) => (
                <div key={group.group_key}>
                  <h4 style={{ margin: '10px 0 6px' }}>{group.name} (grupa powtarzalna)</h4>
                  {group.description && <p style={{ margin: '0 0 6px' }}>{group.description}</p>}
                  <ul style={{ margin: 0, paddingLeft: '20px' }}>
                    {group.field_definitions.map((field) => (
                      <li key={field.field_key}>
                        {field.name}{field.is_required ? ' (wymagane)' : ''}
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          )}

          {error && (
            <div role="alert" style={{ display: 'flex', gap: '8px', marginTop: '12px', color: 'var(--status-error-text)' }}>
              <AlertCircle size={18} /> {error}
            </div>
          )}

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '14px' }}>
            <button type="button" onClick={() => setIsOpen(false)}>Anuluj</button>
            <button
              type="button"
              onClick={handleSave}
              disabled={!selectedTemplate || isLoading || isSaving}
            >
              <CheckCircle2 size={16} aria-hidden="true" />{' '}
              {isSaving ? 'Zapisywanie…' : 'Zapisz konfigurację'}
            </button>
          </div>
        </div>
      )}
    </section>
  );
};
