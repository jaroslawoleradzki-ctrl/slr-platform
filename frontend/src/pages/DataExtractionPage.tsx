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
  RefreshCw,
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
  ExtractionApiError,
  ValueStatus,
  ValueOrigin,
} from '../api/extractionApi';
import { ExtractionFormView } from '../components/extraction/ExtractionFormView';
import { ProvenanceDrawer } from '../components/extraction/ProvenanceDrawer';
import { RevisionHistoryDrawer } from '../components/extraction/RevisionHistoryDrawer';

export const DataExtractionPage: React.FC = () => {
  const { projectId: routeProjectId, publicationId: routePubId } = useParams<{
    projectId?: string;
    publicationId?: string;
  }>();
  const navigate = useNavigate();
  const { activeProject } = useProject();
  const projectId = routeProjectId || activeProject?.id || 'lean_energy';

  // State
  const [eligibilityList, setEligibilityList] = useState<ExtractionEligibilityResult[]>([]);
  const [selectedPubId, setSelectedPubId] = useState<string>(routePubId || '');
  const [record, setRecord] = useState<ExtractionRecordResponseDTO | null>(null);
  const [history, setHistory] = useState<ExtractionRevisionHistoryResponseDTO | null>(null);
  const [templateVersion, setTemplateVersion] = useState<ExtractionTemplateVersion | null>(null);

  const [publicationValues, setPublicationValues] = useState<ExtractedValueStateDTO[]>([]);
  const [groupItems, setGroupItems] = useState<ExtractedGroupItemStateDTO[]>([]);

  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isSaving, setIsSaving] = useState<boolean>(false);
  const [errorBanner, setErrorBanner] = useState<string | null>(null);
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

  // Fetch eligibility list, record, and history for publication
  useEffect(() => {
    let isMounted = true;
    async function loadData() {
      setIsLoading(true);
      setErrorBanner(null);
      setSuccessBanner(null);
      setValidationErrors({});
      setBlockedEligibility(null);

      try {
        const template = await extractionApi.getProjectTemplate(projectId);
        if (!isMounted) return;
        if (!template) {
          setErrorBanner('Projekt nie ma skonfigurowanego szablonu ekstrakcji danych.');
          setTemplateVersion(null);
          return;
        }
        setTemplateVersion(template);
        const eligRes = await extractionApi.getExtractionEligibility(projectId, reviewerId);
        if (!isMounted) return;
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
              template.publication_fields.map((f) => ({
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

  // Handle publication switch
  const handleSelectPublication = (pubId: string) => {
    setSelectedPubId(pubId);
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

      // Refresh record state
      const updatedRec = await extractionApi.getExtractionRecord(projectId, selectedPubId);
      setRecord(updatedRec);

      const updatedHist = await extractionApi.getExtractionHistory(projectId, selectedPubId);
      setHistory(updatedHist);

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

  const currentStatus = record?.current_status || 'not_started';

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
              7. Formularz Ekstrakcji Danych (Data Extraction Workspace)
            </h2>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
              Strukturyzowane wyciąganie wyników, metodologii i cech populacji z publikacji.
            </span>
          </div>
        </div>

        {/* Action Buttons */}
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
            <History size={16} /> Historia ({history?.total_revisions || 0})
          </button>

          <button
            type="button"
            onClick={() => handleSubmitRevision(false)}
            disabled={isSaving || Boolean(blockedEligibility)}
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
              cursor: isSaving || Boolean(blockedEligibility) ? 'not-allowed' : 'pointer',
              opacity: isSaving || Boolean(blockedEligibility) ? 0.6 : 1,
            }}
          >
            <Save size={16} /> Zapisz szkic (Draft)
          </button>

          <button
            type="button"
            onClick={() => handleSubmitRevision(true)}
            disabled={isSaving || Boolean(blockedEligibility)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '8px 18px',
              backgroundColor: 'var(--accent-primary)',
              color: '#fff',
              border: 'none',
              borderRadius: 'var(--radius-md)',
              fontSize: '0.85rem',
              fontWeight: 600,
              cursor: isSaving || Boolean(blockedEligibility) ? 'not-allowed' : 'pointer',
              opacity: isSaving || Boolean(blockedEligibility) ? 0.6 : 1,
            }}
          >
            <CheckCircle size={16} /> Oznacz jako zakończone
          </button>
        </div>
      </div>

      {/* Banners */}
      {errorBanner && (
        <div
          style={{
            padding: '12px 16px',
            backgroundColor: 'var(--status-error-bg)',
            color: 'var(--status-error-text)',
            borderRadius: 'var(--radius-md)',
            marginBottom: '16px',
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
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
            padding: '12px 16px',
            backgroundColor: 'var(--status-success-bg)',
            color: 'var(--status-success-text)',
            borderRadius: 'var(--radius-md)',
            marginBottom: '16px',
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
            fontSize: '0.85rem',
          }}
        >
          <Check size={18} />
          <div style={{ flex: 1 }}>{successBanner}</div>
        </div>
      )}

      {/* Publication Navigation & Status Selector Bar */}
      <div
        style={{
          padding: '16px 20px',
          backgroundColor: 'var(--bg-surface)',
          border: '1px solid var(--border-subtle)',
          borderRadius: 'var(--radius-lg)',
          marginBottom: '24px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '16px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flex: 1, minWidth: '300px' }}>
          <BookOpen size={18} style={{ color: 'var(--accent-primary)' }} />
          <div style={{ flex: 1 }}>
            <label htmlFor="publication-selector" style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '2px' }}>
              Wybierz publikację do ekstrakcji:
            </label>
            <select
              id="publication-selector"
              value={selectedPubId}
              onChange={(e) => handleSelectPublication(e.target.value)}
              style={{
                width: '100%',
                padding: '6px 12px',
                fontSize: '0.85rem',
                fontWeight: 600,
                backgroundColor: 'var(--bg-primary)',
                color: 'var(--text-primary)',
                border: '1px solid var(--border-strong)',
                borderRadius: 'var(--radius-md)',
              }}
            >
              {eligibilityList.map((pub) => (
                <option key={pub.publication_id} value={pub.publication_id}>
                  {pub.publication_id} ({pub.is_eligible ? 'Kwalifikowalna' : `Zablokowana: ${pub.status}`})
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Current Extraction Status Badge */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: 500 }}>
            Status ekstrakcji wpisu:
          </span>
          <span
            style={{
              fontSize: '0.8rem',
              fontWeight: 700,
              padding: '4px 12px',
              borderRadius: 'var(--radius-full)',
              backgroundColor:
                currentStatus === 'complete'
                  ? 'var(--status-success-bg)'
                  : currentStatus === 'in_progress'
                  ? 'var(--accent-subtle)'
                  : 'var(--bg-surface-elevated)',
              color:
                currentStatus === 'complete'
                  ? 'var(--status-success-text)'
                  : currentStatus === 'in_progress'
                  ? 'var(--accent-primary)'
                  : 'var(--text-muted)',
              border: '1px solid var(--border-subtle)',
            }}
          >
            {currentStatus.toUpperCase()}
          </span>
        </div>
      </div>

      {/* Blocked Eligibility Banner */}
      {blockedEligibility && (
        <div
          style={{
            padding: '20px',
            backgroundColor: 'var(--status-warning-bg)',
            color: 'var(--status-warning-text)',
            border: '1px solid var(--status-warning-text)',
            borderRadius: 'var(--radius-lg)',
            marginBottom: '24px',
            display: 'flex',
            flexDirection: 'column',
            gap: '8px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', fontWeight: 700, fontSize: '0.95rem' }}>
            <AlertCircle size={20} /> Publikacja nie kwalifikuje się obecnie do ekstrakcji danych
          </div>
          <p style={{ fontSize: '0.85rem', margin: 0 }}>
            Powód zablokowania: <strong>{blockedEligibility.status}</strong>.
            {blockedEligibility.reason_details && ` Wyszczególnienie: ${blockedEligibility.reason_details}`}
          </p>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
            Ukończ screening pełnotekstowy i ocenę jakości (QA), aby odblokować etap ekstrakcji.
          </span>
        </div>
      )}

      {/* Loading Spinner */}
      {isLoading ? (
        <div style={{ textAlign: 'center', padding: '60px', color: 'var(--text-muted)' }}>
          <RefreshCw size={32} className="spin" style={{ marginBottom: '12px' }} />
          <div>Ładowanie formularza ekstrakcji i szablonu danych...</div>
        </div>
      ) : templateVersion ? (
        <ExtractionFormView
          templateVersion={templateVersion}
          publicationValues={publicationValues}
          groupItems={groupItems}
          onChangePublicationValues={setPublicationValues}
          onChangeGroupItems={setGroupItems}
          onOpenProvenance={openProvenanceDrawer}
          validationErrors={validationErrors}
        />
      ) : (
        <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
          Brak aktywnego szablonu ekstrakcji danych.
        </div>
      )}

      {/* Provenance Drawer */}
      {activeProvenanceField && (
        <ProvenanceDrawer
          isOpen={isProvenanceOpen}
          fieldKey={activeProvenanceField.fieldKey}
          fieldName={activeProvenanceField.fieldName}
          valueState={activeProvenanceField.valueState}
          onSave={activeProvenanceField.onSave}
          onClose={() => setIsProvenanceOpen(false)}
        />
      )}

      {/* History Drawer */}
      <RevisionHistoryDrawer
        isOpen={isHistoryOpen}
        history={history}
        onClose={() => setIsHistoryOpen(false)}
      />
    </div>
  );
};
