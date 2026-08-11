import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  FileSpreadsheet,
  Save,
  CheckCircle,
  History,
  AlertCircle,
  BookOpen,
  Check,
  Table,
  Layers,
  ArrowLeft,
  Download,
} from 'lucide-react';
import { useProject } from '../context/ProjectContext';
import {
  extractionApi,
  ExtractionRecordResponseDTO,
  ExtractionRevisionHistoryResponseDTO,
  ExtractionTemplateVersion,
  ExtractedValueStateDTO,
  ExtractedGroupItemStateDTO,
  ExtractionEligibilityResult,
  ExtractionProgressResponseDTO,
  ExtractionRecordSummaryDTO,
  ExtractionMatrixResponseDTO,
  ExtractionApiError,
  ValueStatus,
  ValueOrigin,
} from '../api/extractionApi';
import { ExtractionFormView } from '../components/extraction/ExtractionFormView';
import { ProvenanceDrawer } from '../components/extraction/ProvenanceDrawer';
import { RevisionHistoryDrawer } from '../components/extraction/RevisionHistoryDrawer';
import { ExtractionProgressHeader } from '../components/extraction/ExtractionProgressHeader';
import { ExtractionTableView } from '../components/extraction/ExtractionTableView';
import { ExtractionMatrixView } from '../components/extraction/ExtractionMatrixView';

// Standard fallback extraction template definition (domain-agnostic)
const DEFAULT_TEMPLATE: ExtractionTemplateVersion = {
  template_id: 'default_extraction_template',
  version: '1.0.0',
  name: 'Standard Data Extraction Template',
  description: 'Uniwersalny formularz ekstrakcji danych z publikacji i grup badanych.',
  is_published: true,
  is_active: true,
  created_at: new Date().toISOString(),
  publication_fields: [
    {
      field_key: 'study_design',
      name: 'Typ badania (Study Design)',
      data_type: 'enum',
      description: 'Metodologia przeprowadzonego badania',
      allowed_values: ['RCT', 'Cohort', 'Case-Control', 'Cross-Sectional', 'Systematic Review', 'Other'],
      is_required: true,
    },
    {
      field_key: 'sample_size',
      name: 'Wielkość próby (N total)',
      data_type: 'integer',
      description: 'Całkowita liczba uczestników włączonych do analizy',
      is_required: false,
      min_value: 1,
    },
    {
      field_key: 'key_finding',
      name: 'Główny wniosek / Wynik (Key Finding)',
      data_type: 'long_text',
      description: 'Podsumowanie najważniejszych wyników wyciągniętych z tekstu',
      is_required: false,
    },
  ],
  repeating_groups: [
    {
      group_key: 'study_arms',
      name: 'Ramiona Badania / Grupy Uczestników (1:N Study Arms)',
      description: 'Charakterystyka poszczególnych podgrup (np. Grupa Eksperymentalna vs Kontrolna)',
      min_items: 1,
      max_items: 10,
      field_definitions: [
        {
          field_key: 'arm_name',
          name: 'Nazwa grupy / ramienia',
          data_type: 'text',
          description: 'np. Grupa A (Interwencja Lean) lub Grupa B (Kontrola)',
          is_required: true,
        },
        {
          field_key: 'group_size',
          name: 'Liczebność n w grupie',
          data_type: 'integer',
          description: 'Liczba badanych w tym konkretnym ramieniu',
          is_required: false,
          min_value: 1,
        },
        {
          field_key: 'age_mean',
          name: 'Średni wiek badanych (Mean Age)',
          data_type: 'decimal',
          description: 'Średnia arytmetyczna wieku w grupie',
          is_required: false,
          min_value: 0,
        },
        {
          field_key: 'primary_outcome_metric',
          name: 'Główny wskaźnik wyniku (Primary Metric)',
          data_type: 'number_with_unit',
          description: 'Wartość i jednostka dla głównego punktu końcowego',
          is_required: false,
        },
      ],
    },
  ],
};

export const DataExtractionPage: React.FC = () => {
  const { projectId: routeProjectId, publicationId: routePubId } = useParams<{
    projectId?: string;
    publicationId?: string;
  }>();
  const navigate = useNavigate();
  const { activeProject } = useProject();
  const projectId = routeProjectId || activeProject?.id || 'lean_energy';

  // View Mode: 'table' vs 'form'
  const [viewMode, setViewMode] = useState<'table' | 'form'>(routePubId ? 'form' : 'table');
  const [tableTab, setTableTab] = useState<'summary' | 'matrix'>('summary');

  // State
  const [progress, setProgress] = useState<ExtractionProgressResponseDTO | null>(null);
  const [recordsSummary, setRecordsSummary] = useState<ExtractionRecordSummaryDTO[]>([]);
  const [matrix, setMatrix] = useState<ExtractionMatrixResponseDTO | null>(null);

  const [eligibilityList, setEligibilityList] = useState<ExtractionEligibilityResult[]>([]);
  const [selectedPubId, setSelectedPubId] = useState<string>(routePubId || '');
  const [, setRecord] = useState<ExtractionRecordResponseDTO | null>(null);
  const [history, setHistory] = useState<ExtractionRevisionHistoryResponseDTO | null>(null);
  const [templateVersion] = useState<ExtractionTemplateVersion>(DEFAULT_TEMPLATE);

  const [publicationValues, setPublicationValues] = useState<ExtractedValueStateDTO[]>([]);
  const [groupItems, setGroupItems] = useState<ExtractedGroupItemStateDTO[]>([]);

  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isSaving, setIsSaving] = useState<boolean>(false);
  const [errorBanner, setErrorBanner] = useState<string | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);
  const [isExporting, setIsExporting] = useState<boolean>(false);
  const [successBanner, setSuccessBanner] = useState<string | null>(null);
  const [validationErrors, setValidationErrors] = useState<Record<string, string>>({});
  const [blockedEligibility, setBlockedEligibility] = useState<ExtractionEligibilityResult | null>(null);

  // Drawers
  const [isProvenanceOpen, setIsProvenanceOpen] = useState<boolean>(false);
  const [activeProvenanceField, setActiveProvenanceField] = useState<{
    fieldKey: string;
    fieldName: string;
    valueState: ExtractedValueStateDTO;
    onSave: (p: Partial<ExtractedValueStateDTO>) => void;
  } | null>(null);
  const [isHistoryOpen, setIsHistoryOpen] = useState<boolean>(false);

  const reviewerId = 'rev_1';
  const selectedPublication = recordsSummary.find((record) => record.publication_id === selectedPubId);

  // Fetch eligibility list, progress, summaries, matrix, and selected record
  useEffect(() => {
    let isMounted = true;
    async function loadData() {
      setIsLoading(true);
      setErrorBanner(null);
      setSuccessBanner(null);
      setValidationErrors({});
      setBlockedEligibility(null);

      try {
        // Fetch 9.6 progress, summaries, and matrix
        const [progRes, recsRes, matrixRes, eligRes] = await Promise.all([
          extractionApi.getExtractionProgress(projectId, reviewerId).catch(() => null),
          extractionApi.listExtractionRecords(projectId, reviewerId).catch(() => ({ total_records: 0, items: [] })),
          extractionApi.getExtractionMatrix(projectId, reviewerId).catch(() => null),
          extractionApi.getExtractionEligibility(projectId, reviewerId),
        ]);

        if (!isMounted) return;
        if (progRes) setProgress(progRes);
        setRecordsSummary(recsRes.items || []);
        if (matrixRes) setMatrix(matrixRes);
        setEligibilityList(eligRes.items);

        let pubIdToLoad = selectedPubId || routePubId;
        const eligiblePubs = eligRes.items.filter((item) => item.is_eligible);
        if (!pubIdToLoad && eligiblePubs.length > 0) {
          pubIdToLoad = eligiblePubs[0].publication_id;
        } else if (!pubIdToLoad && eligRes.items.length > 0) {
          pubIdToLoad = eligRes.items[0].publication_id;
        }

        if (pubIdToLoad) {
          if (pubIdToLoad !== selectedPubId) {
            setSelectedPubId(pubIdToLoad);
          }

          const currentElig = eligRes.items.find((item) => item.publication_id === pubIdToLoad);
          if (currentElig && !currentElig.is_eligible) {
            setBlockedEligibility(currentElig);
          }

          const rec = await extractionApi.getExtractionRecord(projectId, pubIdToLoad);
          if (!isMounted) return;
          setRecord(rec);

          if (rec?.latest_revision) {
            setPublicationValues(rec.latest_revision.publication_values || []);
            setGroupItems(rec.latest_revision.group_items || []);
          } else {
            setPublicationValues(
              templateVersion.publication_fields.map((f) => ({
                field_key: f.field_key,
                status: 'not_reported' as ValueStatus,
                origin: 'reported' as ValueOrigin,
              }))
            );
            setGroupItems([]);
          }

          const hist = await extractionApi.getExtractionHistory(projectId, pubIdToLoad);
          if (isMounted) setHistory(hist);
        }
      } catch (err) {
        if (!isMounted) return;
        if (err instanceof ExtractionApiError) {
          if (err.statusCode === 409) {
            setErrorBanner(`Publikacja zablokowana do ekstrakcji: ${err.message}`);
          } else {
            setErrorBanner(`Błąd pobierania danych ekstrakcji: ${err.message}`);
          }
        } else {
          setErrorBanner('Nie udało się załadować danych ekstrakcji dla publikacji.');
        }
      } finally {
        if (isMounted) setIsLoading(false);
      }
    }

    loadData();
    return () => {
      isMounted = false;
    };
  }, [projectId, routePubId, selectedPubId]);

  // Handle publication selection from table or dropdown
  const handleSelectPublication = (pubId: string) => {
    setSelectedPubId(pubId);
    setViewMode('form');
    navigate(`/projects/${projectId}/extract/${pubId}`);
  };

  // Submit Handler (Save Draft or Mark Complete)
  const handleSubmitRevision = async (markComplete: boolean) => {
    if (!selectedPubId) return;
    setIsSaving(true);
    setErrorBanner(null);
    setSuccessBanner(null);
    setValidationErrors({});

    try {
      const payload = {
        reviewer_id: reviewerId,
        publication_values: publicationValues,
        group_items: groupItems,
        mark_complete: markComplete,
      };

      const resultRev = await extractionApi.submitRevision(projectId, selectedPubId, payload);
      setPublicationValues(resultRev.publication_values);
      setGroupItems(resultRev.group_items);

      // Refresh record state and 9.6 progress/summaries
      const [updatedRec, updatedHist, updatedProg, updatedRecs, updatedMat] = await Promise.all([
        extractionApi.getExtractionRecord(projectId, selectedPubId),
        extractionApi.getExtractionHistory(projectId, selectedPubId),
        extractionApi.getExtractionProgress(projectId, reviewerId).catch(() => null),
        extractionApi.listExtractionRecords(projectId, reviewerId).catch(() => ({ total_records: 0, items: [] })),
        extractionApi.getExtractionMatrix(projectId, reviewerId).catch(() => null),
      ]);

      setRecord(updatedRec);
      setHistory(updatedHist);
      if (updatedProg) setProgress(updatedProg);
      setRecordsSummary(updatedRecs.items || []);
      if (updatedMat) setMatrix(updatedMat);

      if (markComplete && resultRev.completeness_status === 'complete') {
        setSuccessBanner(`Ekstrakcja danych została oznaczona jako ZAKOŃCZONA (Rewizja #${resultRev.revision_index}).`);
      } else {
        setSuccessBanner(`Zapisano szkic ekstrakcji (Rewizja #${resultRev.revision_index}, Status: ${resultRev.completeness_status.toUpperCase()}).`);
      }
    } catch (err) {
      if (err instanceof ExtractionApiError) {
        if (err.statusCode === 422) {
          setErrorBanner('Walidacja nie powiodła się. Popraw błędy w formularzu.');
          if (Array.isArray(err.detail)) {
            const errMap: Record<string, string> = {};
            err.detail.forEach((msg, idx) => {
              errMap[`error_${idx}`] = msg;
            });
            setValidationErrors(errMap);
          } else if (typeof err.detail === 'string') {
            setValidationErrors({ general: err.detail });
          }
        } else if (err.statusCode === 409) {
          setErrorBanner(`Brak uprawnień lub niekwalifikowalność: ${err.message}`);
        } else {
          setErrorBanner(`Błąd zapisu rewizji (HTTP ${err.statusCode}): ${err.message}`);
        }
      } else {
        setErrorBanner('Wystąpił nieoczekiwany błąd podczas zapisywania rewizji.');
      }
    } finally {
      setIsSaving(false);
    }
  };

  const openProvenanceDrawer = (
    fieldKey: string,
    fieldName: string,
    valueState: ExtractedValueStateDTO,
    onSave: (p: Partial<ExtractedValueStateDTO>) => void
  ) => {
    setActiveProvenanceField({ fieldKey, fieldName, valueState, onSave });
    setIsProvenanceOpen(true);
  };

  const handleExport = async (format: 'json' | 'csv', dataset: 'publications' | 'relationships') => {
    setIsExporting(true);
    setExportError(null);
    try {
      const blob = await extractionApi.exportDataset(projectId, format, dataset);
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `${projectId}_${dataset}.${format}`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setExportError(err instanceof ExtractionApiError ? err.message : 'Nie udało się pobrać eksportu danych.');
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <div style={{ padding: '24px', maxWidth: '1200px', margin: '0 auto' }}>
      {/* Top Header Bar */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div
            style={{
              width: '40px',
              height: '40px',
              borderRadius: 'var(--radius-md)',
              backgroundColor: 'var(--accent-subtle)',
              color: 'var(--accent-primary)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <FileSpreadsheet size={22} />
          </div>

          <div>
            <h2 style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--text-primary)', margin: 0 }}>
              7. Ekstrakcja Danych (Data Extraction Workspace)
            </h2>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
              Przegląd tabelaryczny, macierz relacji 1:N oraz formularz wprowadzania danych.
            </span>
          </div>

        </div>

        {/* View Switcher Controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <button
            type="button"
            onClick={() => setViewMode('table')}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              padding: '8px 14px',
              borderRadius: 'var(--radius-md)',
              border: viewMode === 'table' ? '1px solid var(--accent-primary)' : '1px solid var(--border-subtle)',
              backgroundColor: viewMode === 'table' ? 'var(--bg-primary)' : 'transparent',
              color: viewMode === 'table' ? 'var(--accent-primary)' : 'var(--text-secondary)',
              fontSize: '0.85rem',
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            <Table size={16} /> Widok Tabelaryczny
          </button>
          <button
            type="button"
            onClick={() => setViewMode('form')}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              padding: '8px 14px',
              borderRadius: 'var(--radius-md)',
              border: viewMode === 'form' ? '1px solid var(--accent-primary)' : '1px solid var(--border-subtle)',
              backgroundColor: viewMode === 'form' ? 'var(--bg-primary)' : 'transparent',
              color: viewMode === 'form' ? 'var(--accent-primary)' : 'var(--text-secondary)',
              fontSize: '0.85rem',
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            <BookOpen size={16} /> Formularz Ekstrakcji
          </button>
        </div>
      </div>

      {/* VIEW MODE 1: TABULAR VIEW (Progress + Summary Table + Matrix) */}
      {viewMode === 'table' && (
        <div>
          {/* Progress Header Cards */}
          <ExtractionProgressHeader progress={progress} />

          {/* Sub-tabs: Table vs Matrix */}
          <div
            style={{
              display: 'flex',
              gap: '8px',
              marginBottom: '16px',
              borderBottom: '1px solid var(--border-subtle)',
              paddingBottom: '8px',
            }}
          >
            <button
              onClick={() => setTableTab('summary')}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                padding: '8px 16px',
                borderRadius: 'var(--radius-md)',
                border: 'none',
                backgroundColor: tableTab === 'summary' ? 'var(--accent-subtle)' : 'transparent',
                color: tableTab === 'summary' ? 'var(--accent-primary)' : 'var(--text-secondary)',
                fontSize: '0.9rem',
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              <Table size={16} /> Zestawienie Publikacji ({recordsSummary.length})
            </button>
            <button
              onClick={() => setTableTab('matrix')}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                padding: '8px 16px',
                borderRadius: 'var(--radius-md)',
                border: 'none',
                backgroundColor: tableTab === 'matrix' ? 'var(--accent-subtle)' : 'transparent',
                color: tableTab === 'matrix' ? 'var(--accent-primary)' : 'var(--text-secondary)',
                fontSize: '0.9rem',
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              <Layers size={16} /> Macierz Relacji (Cross-Study Matrix)
            </button>
          </div>

          {/* Tab Content */}
          {tableTab === 'summary' ? (
            <ExtractionTableView
              records={recordsSummary}
              isLoading={isLoading}
              onSelectPublication={handleSelectPublication}
            />
          ) : (
            <ExtractionMatrixView matrix={matrix} isLoading={isLoading} />
          )}
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center', marginTop: '16px', flexWrap: 'wrap' }}>
            <Download size={16} style={{ color: 'var(--text-muted)' }} />
            <button type="button" disabled={isExporting} onClick={() => handleExport('json', 'publications')}>
              Eksport JSON
            </button>
            <button type="button" disabled={isExporting} onClick={() => handleExport('csv', 'publications')}>
              CSV publikacji
            </button>
            <button type="button" disabled={isExporting} onClick={() => handleExport('csv', 'relationships')}>
              CSV relacji
            </button>
            {exportError && <span role="alert">{exportError}</span>}
          </div>
        </div>
      )}

      {/* VIEW MODE 2: SINGLE PUBLICATION FORM WORKSPACE */}
      {viewMode === 'form' && (
        <div>
          {/* Return to Table Button & Form Header Actions */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
            <button
              type="button"
              onClick={() => setViewMode('table')}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                padding: '6px 12px',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--border-subtle)',
                backgroundColor: 'var(--bg-surface)',
                color: 'var(--text-secondary)',
                fontSize: '0.85rem',
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              <ArrowLeft size={16} /> Powrót do Widoku Tabelarycznego
            </button>

            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <button
                type="button"
                onClick={() => setIsHistoryOpen(true)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  padding: '8px 14px',
                  backgroundColor: 'var(--bg-surface)',
                  border: '1px solid var(--border-strong)',
                  borderRadius: 'var(--radius-md)',
                  color: 'var(--text-secondary)',
                  fontSize: '0.85rem',
                  fontWeight: 500,
                  cursor: 'pointer',
                }}
              >
                <History size={16} /> Historia Rewizji ({history?.total_revisions || 0})
              </button>

              <button
                type="button"
                disabled={isSaving || !!blockedEligibility}
                onClick={() => handleSubmitRevision(false)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  padding: '8px 16px',
                  backgroundColor: 'var(--bg-surface-elevated)',
                  border: '1px solid var(--border-strong)',
                  borderRadius: 'var(--radius-md)',
                  color: 'var(--text-primary)',
                  fontSize: '0.85rem',
                  fontWeight: 600,
                  cursor: isSaving || !!blockedEligibility ? 'not-allowed' : 'pointer',
                }}
              >
                <Save size={16} /> Zapisz Szkic
              </button>

              <button
                type="button"
                disabled={isSaving || !!blockedEligibility}
                onClick={() => handleSubmitRevision(true)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  padding: '8px 16px',
                  backgroundColor: 'var(--accent-primary)',
                  border: 'none',
                  borderRadius: 'var(--radius-md)',
                  color: '#ffffff',
                  fontSize: '0.85rem',
                  fontWeight: 600,
                  cursor: isSaving || !!blockedEligibility ? 'not-allowed' : 'pointer',
                }}
              >
                <CheckCircle size={16} /> Oznacz jako Zakończone
              </button>
            </div>
          </div>

          {/* Publication Selector Bar */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '16px',
              padding: '16px 20px',
              backgroundColor: 'var(--bg-surface)',
              border: '1px solid var(--border-subtle)',
              borderRadius: 'var(--radius-lg)',
              marginBottom: '20px',
            }}
          >
            <BookOpen size={20} style={{ color: 'var(--accent-primary)' }} />
            <div style={{ flex: 1 }}>
              <label style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)', display: 'block', marginBottom: '4px' }}>
                Wybierz publikację do ekstrakcji (Kwalifikowalne):
              </label>
              <select
                value={selectedPubId}
                onChange={(e) => handleSelectPublication(e.target.value)}
                style={{
                  width: '100%',
                  padding: '8px 12px',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--border-subtle)',
                  backgroundColor: 'var(--bg-primary)',
                  color: 'var(--text-primary)',
                  fontSize: '0.9rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                {eligibilityList.map((item) => (
                  <option key={item.publication_id} value={item.publication_id}>
                    {item.is_eligible ? '✓ ' : '🔒 '} Publikacja ID: {item.publication_id.slice(0, 8)}... {item.is_eligible ? '(Kwalifikowalna)' : `(Zablokowana: ${item.status})`}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {selectedPublication && (
            <div
              style={{
                padding: '14px 20px',
                backgroundColor: 'var(--bg-surface)',
                border: '1px solid var(--border-subtle)',
                borderRadius: 'var(--radius-lg)',
                marginBottom: '20px',
              }}
            >
              <strong>{selectedPublication.title}</strong>
              <div style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginTop: '4px' }}>
                {selectedPublication.authors.join('; ')}{selectedPublication.publication_year ? ` · ${selectedPublication.publication_year}` : ''}
                {' · E1: canonical publication metadata'}
              </div>
            </div>
          )}

          {/* Status Banners */}
          {errorBanner && (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '10px',
                padding: '12px 16px',
                backgroundColor: 'var(--status-error-bg)',
                border: '1px solid var(--status-error-text)',
                borderRadius: 'var(--radius-md)',
                color: 'var(--status-error-text)',
                marginBottom: '20px',
                fontSize: '0.85rem',
              }}
            >
              <AlertCircle size={18} />
              <div style={{ flex: 1 }}>{errorBanner}</div>
            </div>
          )}

          {successBanner && (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '10px',
                padding: '12px 16px',
                backgroundColor: 'var(--status-success-bg)',
                border: '1px solid var(--status-success-text)',
                borderRadius: 'var(--radius-md)',
                color: 'var(--status-success-text)',
                marginBottom: '20px',
                fontSize: '0.85rem',
              }}
            >
              <Check size={18} />
              <div style={{ flex: 1 }}>{successBanner}</div>
            </div>
          )}

          {blockedEligibility && (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '12px',
                padding: '16px',
                backgroundColor: 'var(--status-warning-bg)',
                border: '1px solid var(--status-warning-text)',
                borderRadius: 'var(--radius-lg)',
                color: 'var(--status-warning-text)',
                marginBottom: '20px',
                fontSize: '0.85rem',
              }}
            >
              <AlertCircle size={20} />
              <div>
                <strong>Publikacja niekwalifikowalna do ekstrakcji!</strong> Status eligibility:{' '}
                <code>{blockedEligibility.status}</code>. {blockedEligibility.reason_details}
              </div>
            </div>
          )}

          {/* Single Publication Form Workspace */}
          <ExtractionFormView
            templateVersion={templateVersion}
            publicationValues={publicationValues}
            groupItems={groupItems}
            onChangePublicationValues={(updatedValues: ExtractedValueStateDTO[]) => {
              setPublicationValues(updatedValues);
            }}
            onChangeGroupItems={(updatedGroups: ExtractedGroupItemStateDTO[]) => {
              setGroupItems(updatedGroups);
            }}
            onOpenProvenance={openProvenanceDrawer}
            validationErrors={validationErrors}
          />
        </div>
      )}

      {/* Provenance Drawer */}
      {isProvenanceOpen && activeProvenanceField && (
        <ProvenanceDrawer
          isOpen={isProvenanceOpen}
          onClose={() => setIsProvenanceOpen(false)}
          fieldKey={activeProvenanceField.fieldKey}
          fieldName={activeProvenanceField.fieldName}
          valueState={activeProvenanceField.valueState}
          onSave={activeProvenanceField.onSave}
        />
      )}

      {/* Revision History Drawer */}
      {isHistoryOpen && (
        <RevisionHistoryDrawer
          isOpen={isHistoryOpen}
          onClose={() => setIsHistoryOpen(false)}
          history={history}
        />
      )}
    </div>
  );
};
