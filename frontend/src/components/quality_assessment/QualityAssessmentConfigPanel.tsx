import React, { useEffect, useState } from 'react';
import { Card } from '../common/Card';
import { Button } from '../common/Button';
import { Badge } from '../common/Badge';
import { ErrorAlert } from '../common/ErrorAlert';
import { LoadingSpinner } from '../common/LoadingSpinner';
import {
  ProjectQualityAssessmentConfiguration,
  QualityAssessmentTool,
  qualityAssessmentApi,
  QualityAssessmentApiError,
} from '../../services/api/qualityAssessmentApi';
import { Check, Settings, AlertCircle, ArrowLeft } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

interface QualityAssessmentConfigPanelProps {
  projectId: string;
  onConfigurationSaved?: () => void;
}

export const QualityAssessmentConfigPanel: React.FC<QualityAssessmentConfigPanelProps> = ({
  projectId,
  onConfigurationSaved,
}) => {
  const navigate = useNavigate();
  const [tools, setTools] = useState<QualityAssessmentTool[]>([]);
  const [currentConfig, setCurrentConfig] = useState<ProjectQualityAssessmentConfiguration | null>(null);
  const [selectedToolId, setSelectedToolId] = useState<string>('');
  const [selectedTemplateId, setSelectedTemplateId] = useState<string>('');
  const [confirmChange, setConfirmChange] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(true);
  const [saving, setSaving] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);

    Promise.all([
      qualityAssessmentApi.getTools(),
      qualityAssessmentApi.getConfiguration(projectId).catch((err) => {
        if (
          err instanceof QualityAssessmentApiError &&
          (err.status === 404 || err.message.toLowerCase().includes('no active'))
        ) {
          return null;
        }
        throw err;
      }),
    ])
      .then(([toolsList, config]) => {
        if (!active) return;
        setTools(toolsList);
        setCurrentConfig(config);

        if (config) {
          setSelectedToolId(config.tool_id);
          setSelectedTemplateId(config.template_id);
        } else if (toolsList.length > 0) {
          setSelectedToolId(toolsList[0].tool_id);
          if (toolsList[0].templates.length > 0) {
            setSelectedTemplateId(toolsList[0].templates[0].template_id);
          }
        }
      })
      .catch((err) => {
        if (!active) return;
        setError(err instanceof Error ? err.message : 'Błąd podczas ładowania narzędzi QA.');
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [projectId]);

  const selectedTool = tools.find((t) => t.tool_id === selectedToolId);
  const selectedTemplate = selectedTool?.templates.find((tmpl) => tmpl.template_id === selectedTemplateId);

  const handleToolChange = (toolId: string) => {
    setSelectedToolId(toolId);
    const tool = tools.find((t) => t.tool_id === toolId);
    if (tool && tool.templates.length > 0) {
      setSelectedTemplateId(tool.templates[0].template_id);
    } else {
      setSelectedTemplateId('');
    }
  };

  const handleSaveConfig = async () => {
    if (!selectedToolId || !selectedTemplateId) return;

    setSaving(true);
    setError(null);

    try {
      const updated = await qualityAssessmentApi.updateConfiguration(
        projectId,
        selectedToolId,
        selectedTemplateId,
        confirmChange
      );
      setCurrentConfig(updated);
      setConfirmChange(false);
      if (onConfigurationSaved) {
        onConfigurationSaved();
      } else {
        navigate(`/projects/${projectId}/quality-assessment`);
      }
    } catch (err) {
      if (err instanceof QualityAssessmentApiError && err.status === 422) {
        if (err.message.includes('confirm_template_change')) {
          setConfirmChange(true);
          setError('Zmiana wersji lub szablonu wymaga potwierdzenia. Zaznacz zgodę poniżej i zapisz ponownie.');
        } else {
          setError(err.message);
        }
      } else {
        setError(err instanceof Error ? err.message : 'Wystąpił błąd podczas zapisywania konfiguracji.');
      }
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <LoadingSpinner label="Ładowanie katalogu narzędzi i konfiguracji QA..." />;
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <h2 style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--text-primary)' }}>
            Konfiguracja Szablonu Oceny Jakościowej (Quality Assessment)
          </h2>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '2px' }}>
            Wybierz aktywne narzędzie oraz wersję kwestionariusza dla projektu.
          </p>
        </div>

        <Button
          variant="secondary"
          icon={<ArrowLeft size={16} />}
          onClick={() => navigate(`/projects/${projectId}/quality-assessment`)}
        >
          Powrót do Oceny
        </Button>
      </div>

      {error && <ErrorAlert message={error} />}

      {currentConfig && (
        <Card
          title={
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Check size={18} style={{ color: 'var(--status-success-text)' }} />
              <span>Aktualnie Skonfigurowany Szablon</span>
            </div>
          }
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div>
              <div style={{ fontWeight: 600, fontSize: '1rem', color: 'var(--text-primary)' }}>
                {currentConfig.template_name} (v{currentConfig.version})
              </div>
              <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                Narzędzie: {currentConfig.tool_id} | Szablon: {currentConfig.template_key} | Skonfigurowano: {new Date(currentConfig.configured_at).toLocaleString()}
              </div>
            </div>

            <Badge variant="completed">Aktywny</Badge>
          </div>
        </Card>
      )}

      <Card
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Settings size={18} style={{ color: 'var(--accent-primary)' }} />
            <span>Wybór Narzędzia i Wersji Szablonu</span>
          </div>
        }
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {tools.length === 0 ? (
            <div style={{ padding: '16px', color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
              Brak dostępnych aktywnych narzędzi lub szablonów oceny jakości.
            </div>
          ) : (
            <>
              {/* Tool selector */}
              <div>
                <label
                  htmlFor="qa-tool-select"
                  style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '6px' }}
                >
                  1. Narzędzie Oceny Jakościowej (Tool):
                </label>
                <select
                  id="qa-tool-select"
                  value={selectedToolId}
                  onChange={(e) => handleToolChange(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '8px 12px',
                    borderRadius: 'var(--radius-md)',
                    backgroundColor: 'var(--bg-primary)',
                    color: 'var(--text-primary)',
                    border: '1px solid var(--border-subtle)',
                    fontSize: '0.9rem',
                  }}
                >
                  {tools.map((t) => (
                    <option key={t.tool_id} value={t.tool_id}>
                      {t.name} {!t.is_active ? '(Nieaktywne)' : ''}
                    </option>
                  ))}
                </select>
                {selectedTool?.description && (
                  <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '4px' }}>
                    {selectedTool.description}
                  </p>
                )}
              </div>

              {/* Template version selector */}
              {selectedTool && (
                <div>
                  <label
                    htmlFor="qa-template-select"
                    style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '6px' }}
                  >
                    2. Szablon i Wersja Kwestionariusza (Template Version):
                  </label>
                  <select
                    id="qa-template-select"
                    value={selectedTemplateId}
                    onChange={(e) => setSelectedTemplateId(e.target.value)}
                    style={{
                      width: '100%',
                      padding: '8px 12px',
                      borderRadius: 'var(--radius-md)',
                      backgroundColor: 'var(--bg-primary)',
                      color: 'var(--text-primary)',
                      border: '1px solid var(--border-subtle)',
                      fontSize: '0.9rem',
                    }}
                  >
                    {selectedTool.templates.map((tmpl) => (
                      <option key={tmpl.template_id} value={tmpl.template_id}>
                        {tmpl.name} (v{tmpl.version}) {!tmpl.is_active ? '[Wersja archiwalna/dezaktywowana]' : ''}
                      </option>
                    ))}
                  </select>
                </div>
              )}

              {/* Selected template summary */}
              {selectedTemplate && (
                <div
                  style={{
                    padding: '14px',
                    backgroundColor: 'var(--bg-primary)',
                    borderRadius: 'var(--radius-md)',
                    border: '1px solid var(--border-subtle)',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                    <span style={{ fontWeight: 600, fontSize: '0.9rem', color: 'var(--text-primary)' }}>
                      Szczegóły Szablonu: {selectedTemplate.name}
                    </span>
                    <Badge variant={selectedTemplate.is_active ? 'completed' : 'info'}>
                      {selectedTemplate.is_active ? 'Aktywny w katalogu' : 'Dezaktywowany'}
                    </Badge>
                  </div>

                  {selectedTemplate.description && (
                    <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '10px' }}>
                      {selectedTemplate.description}
                    </p>
                  )}

                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '12px', marginTop: '12px' }}>
                    <div>
                      <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Liczba Pytań / Kryteriów</span>
                      <div style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                        {selectedTemplate.criteria.length}
                      </div>
                    </div>
                    <div>
                      <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Wymagane Pytań</span>
                      <div style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--accent-primary)' }}>
                        {selectedTemplate.criteria.filter((c) => c.is_required).length}
                      </div>
                    </div>
                    <div>
                      <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Skala Odpowiedzi</span>
                      <div style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-primary)', marginTop: '2px' }}>
                        TAK | NIE | NIE MOŻNA OKREŚLIĆ
                      </div>
                    </div>
                  </div>

                  {/* Criteria list preview */}
                  <div style={{ marginTop: '16px' }}>
                    <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-secondary)' }}>
                      Lista Pytań Kryteriów:
                    </span>
                    <ol style={{ paddingLeft: '20px', marginTop: '6px', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                      {selectedTemplate.criteria.map((crit) => (
                        <li key={crit.criterion_id} style={{ marginBottom: '4px' }}>
                          <span>{crit.question}</span>
                          {crit.is_required && (
                            <span style={{ color: 'var(--status-error-text)', marginLeft: '6px', fontSize: '0.75rem' }}>
                              *wymagane
                            </span>
                          )}
                        </li>
                      ))}
                    </ol>
                  </div>
                </div>
              )}

              {/* Template change warning & checkbox */}
              {confirmChange && (
                <div
                  style={{
                    padding: '12px',
                    backgroundColor: 'var(--status-warning-bg, rgba(234, 179, 8, 0.1))',
                    border: '1px solid var(--status-warning-border, #eab308)',
                    borderRadius: 'var(--radius-md)',
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: '10px',
                  }}
                >
                  <AlertCircle size={20} style={{ color: 'var(--status-warning-text, #eab308)', flexShrink: 0, marginTop: '2px' }} />
                  <div>
                    <div style={{ fontWeight: 600, fontSize: '0.85rem', color: 'var(--text-primary)' }}>
                      Potwierdzenie Zmiany Szablonu
                    </div>
                    <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '2px' }}>
                      Projekt posiada już przypisany szablon QA. Zmiana wersji lub szablonu spowoduje, że kolejne nowe oceny będą wykonywane według nowej wersji (dotychczasowa historia pozostanie nienaruszona).
                    </p>
                    <label style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '8px', fontSize: '0.85rem', cursor: 'pointer' }}>
                      <input
                        type="checkbox"
                        checked={confirmChange}
                        onChange={(e) => setConfirmChange(e.target.checked)}
                      />
                      <span>Potwierdzam zmianę szablonu QA dla projektu</span>
                    </label>
                  </div>
                </div>
              )}
            </>
          )}

          {/* Action buttons */}
          <div style={{ display: 'flex', gap: '12px', justifyContent: 'flex-end' }}>
            <Button
              variant="secondary"
              onClick={() => navigate(`/projects/${projectId}/quality-assessment`)}
            >
              Anuluj
            </Button>
            <Button
              variant="primary"
              disabled={saving || !selectedTemplateId || !selectedToolId || tools.length === 0}
              onClick={handleSaveConfig}
            >
              {saving ? 'Zapisywanie...' : 'Zapisz Konfigurację QA'}
            </Button>
          </div>
        </div>
      </Card>
    </div>
  );
};
