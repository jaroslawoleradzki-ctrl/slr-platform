# Przegląd integralności danych badawczych — OpenSpec `slr-v0-7-5-import-review-fixes`

- **Zmiana:** `slr-v0-7-5-import-review-fixes` (worktree `feature/slr-v0.7.5`, base `5d641f5`)
- **Typ przeglądu:** niezależny przegląd integralności danych badawczych (read-only)
- **Wykonujący:** agent `slr-research-reviewer` z użyciem skill `slr-research-integrity`
- **Data:** 2026-10-29
- **Zakres kodu:** zmiany frontendowe (UI lifecycle/odświeżanie) + nowe testy regresyjne (frontend + backend); brak zmian w backendzie, migracjach i schemacie

## 1. Zakres i metoda

Przegląd objął:
- `frontend/src/components/imports/ImportReviewModal.tsx`
- `frontend/src/components/imports/FileDropzone.tsx`
- `frontend/src/pages/SourcesIngestionPage.tsx`
- `app/services/import_review_service.py` (ścieżka `accept`/`reject`)
- `app/services/prisma_metrics_service.py`, `app/services/sources_summary_service.py`
- `app/domain/import_review.py` (`effective_import_status`)
- `app/repositories/import_review_repository.py`, migracja `0038_import_review_decisions.sql`
- nowe testy: `frontend/tests/ImportWarningResolution.test.tsx`, `frontend/tests/SourcesIngestionRefresh.test.tsx`,
  `tests/unit/services/test_sources_summary_service.py::test_acceptance_changes_only_warning_derived_summary_counters`,
  `tests/unit/services/test_import_review_service.py::test_acceptance_preserves_publications_source_records_and_research_tables`,
  `tests/unit/api/test_import_review_api.py` (idempotencja akceptacji),
  `tests/integration/test_v074_import_review_integration.py::test_warning_import_acceptance_updates_sources_without_changing_prisma`

Metoda: analiza statyczna ścieżek kodu, śledzenie populacji od importu do wyjścia (PRISMA), weryfikacja niezmienności
bazy przy odświeżaniu UI, przegląd testów pod kątem pokrycia invariantów. Żadne pliki nie zostały zmodyfikowane;
nie wykonano migracji ani zapisów do bazy. Testy uruchomiono na jednorazowych bazach SQLite.

## 2. Populacja badawcza i dotknięte rekordy

Zmiana dotyczy wyłącznie **importów ze statusem `warning`**, dla których badacz podejmuje decyzję `accept`/`reject`.

Populacja kanoniczna (aktywny korpus) po akceptacji:
- pozostaje **bez zmian** — akceptacja nie wywołuje żadnych zapisów w `project_publications`,
  `import_source_records`, `import_skip_audit`, `duplicate_review_decisions`, `pre_screening_*`,
  `screening_*`, `quality_assessments`, `extraction_records`, `synthesis_*`.

Jedyny zapis do bazy przy akceptacji to `INSERT` do tabeli `import_review_decisions`
(append-only, ograniczone `UNIQUE(project_id, import_id)`). Status `import_history.status`
pozostaje `"warning"`; efektywny status (`success`) jest **wyliczany** przez `effective_import_status`,
nie zapisywany.

Przy odrzuceniu (niezmienione w v0.7.5): usuwane są wyłącznie publikacje kanoniczne należące
wyłącznie do danego importu (z snapshotem), a źródła/skip-audit pozostają; to zachowanie jest
już pokryte testami v0.7.4 i niezmienione.

## 3. Weryfikacja wymaganych punktów

### 3.1 Czy poprawki nie zmieniają semantyki liczników PRISMA

**Wynik: PASS.**

- `app/services/import_review_service.py::accept` wykonuje tylko odczyty i pojedynczy `INSERT`
  do `import_review_decisions`. Nie wywołuje `delete_publications`, `delete_for_project` (poza
  ścieżką odrzucenia), ani żadnej aktualizacji `import_history`.
- `PrismaMetricsService.get_metrics` liczy `records_identified_imports` z `import_history`
  gdzie `record.status in ("success", "warning")` — czyli **oryginalny** status `"warning"`
  nadal liczy się jako zidentyfikowany. Akceptacja nie zmienia `record.status`, więc identyfikacja
  pozostaje stabilna.
- Rejected imports są wykluczane z metryk przez `review_decisions` (niezmienione).
- `records_removed_prescreening` obejmuje odrzucone importy (`rejected_import_removed`); akceptacja
  nie zwiększa tego licznika (brak `prisma_treatment="removed_before_screening..."`).
- `records_after_normalization`, `records_before_dedup`, `records_after_technical_merger`,
  `canonical_publications` wyliczane z `project_publications` — niezmienione.
- Nowy test integracyjny `test_warning_import_acceptance_updates_sources_without_changing_prisma`
  asseruje `after_metrics == before_metrics` (model_dump) po akceptacji. PASS.

### 3.2 Czy zatwierdzanie importów nie tworzy duplikatów publikacji

**Wynik: PASS.**

- `accept()` nie wywołuje `import_source_publications`, `add_publications`, ani żadnej mutacji
  `project_publications`. Jedyny zapis to `import_review_decisions`.
- `effective_import_status("warning", "accepted") == "success"` zmienia wyłącznie **etykietę**
  w read-modelu (`SourcesSummaryService`, frontend), nie tworzy wierszy publikacji.
- Test `test_accept_records_one_decision_without_changing_publications` potwierdza
  `publications.get_publications(PROJECT_ID) == [publication]` po akceptacji. PASS.
- Test `test_acceptance_preserves_publications_source_records_and_research_tables` potwierdza
  niezmienność snapshotu tabel. PASS.

### 3.3 Czy historia decyzji i pochodzenie rekordów pozostają zachowane

**Wynik: PASS.**

- `ImportReviewRepository.create` wykonuje wyłącznie `INSERT` (append-only); konflikt (duplikat
  `(project_id, import_id)`) podnosi `ImportReviewConflictError`, nie nadpisuje.
- Akceptacja zapisuje snapshot ostrzeżeń (`warning_snapshot`), listę `affected_source_record_ids`,
  `affected_publication_ids`, `retained_source_record_count`, `reviewer_id`, `decided_at` i rationale.
- `import_history.status` pozostaje `"warning"` (test API: `history.get(...).status == "warning"`),
  co zachowuje pierwotny status importu; decyzja jest w osobnej tabeli.
- Provenance publikacji (`ProvenanceEntry`, source-record identity) nie jest modyfikowane.
- Idempotencja akceptacji: ponowny POST zwraca tę samą decyzję (`decision_id` identyczny,
  rationale pierwszego wywołania zachowane), bez nowego wiersza. Test API PASS.
- `delete_for_project` w repozytorium decyzji jest używane wyłącznie przy kasowaniu projektu
  (poza ścieżką akceptacji). Brak użycia w `accept`.

### 3.4 Czy odświeżanie UI nie zmienia danych w bazie

**Wynik: PASS.**

- `FileDropzone.onChanged` wywołuje `refreshWorkflowStatus(effectiveProjectId)` (wyłącznie GET-y:
  `getSearchStrategy`, `getBibliographicImports`, `getNormalization`, `getDuplicateGroups`,
  `getPrismaMetrics`, `getResumableFetchAllSearches`, screening/QA/extraction overviews) oraz
  `onRefresh` = `fetchSummary` = `getSourcesSummary`. Wszystkie to GET.
- `SourcesIngestionPage.handleDecisionApplied` wykonuje wyłącznie `setSourcesSummary` (aktualizacja
  stanu React), bez żadnego wywołania API.
- `SourcesIngestionPage` nie wywołuje żadnej mutacji; `Ponów` wywołuje `fetchSummary` (GET).
- Brak `method: 'POST'/'PUT'/'DELETE'` w ścieżce odświeżania po decyzji.

### 3.5 Czy testy regresyjne pokrywają oba zgłoszone błędy

**Wynik: PASS (z zastrzeżeniem — patrz §5).**

Pokrycie BUG-01 (stare liczniki/stary wiersz):
- `SourcesIngestionRefresh.test.tsx > shows a refresh error and retry action even when an older summary exists`
- `SourcesIngestionRefresh.test.tsx > updates the row immediately and keeps visible counts stable after a slow refresh`
- Backend: `test_acceptance_changes_only_warning_derived_summary_counters`, `test_warning_import_acceptance_updates_sources_without_changing_prisma`

Pokrycie BUG-02 (zablokowany modal):
- `ImportWarningResolution.test.tsx > closes a successful accept without waiting for a slow refresh`
- `... > closes a successful rejection without waiting for a slow refresh`
- `... > shows a pending indicator only on the accept action`
- `... > shows a pending indicator only on the rejection confirmation`
- `... > keeps the dialog open with blockers when the decision request fails`
- `... > does not report a failed post-decision refresh as a failed decision`
- `... > submits only one decision request for repeated activation`

## 4. Znaleziska

### HIGH
Brak.

### MEDIUM
Brak.

### LOW (rozwiązane w ramach remediacji)

1. **Snapshot test downstream tabel wzmocniony (LOW-1).**
   Plik: `tests/unit/services/test_import_review_service.py::test_acceptance_preserves_publications_source_records_and_research_tables`.
   Fixture wstawia teraz niepuste wiersze do `screening_decisions`, `quality_assessments` (z szablonem),
   `extraction_records` (z szablonem i wersją) oraz `synthesis_analytical_relations`, a także asercję
   liczby wierszy po akceptacji. Snapshot (wszystkie tabele poza `import_review_decisions` i
   `schema_migrations`) pozostaje identyczny. Test PASS.

2. **Liczniki per-źródło (LOW-2) — weryfikacja i brak zmiany kodu.**
   `handleDecisionApplied` aktualizuje natychmiastowo tylko `import_history` (wiersz), nie `source_summaries`.
   Wynika to z zatwierdzonego designu: liczniki źródłowe są **pochodne i wyliczane po stronie serwera**
   (Decision 4: „UI must not invent counter changes”). Scenariusz spec wymaga aktualizacji liczników
   „WHEN … the Sources summary refresh succeeds”. Odświeżanie odbywa się w tle (`fetchSummary` w
   `FileDropzone.onChanged` przez `Promise.allSettled`), bez przeładowania strony; przy niepowodzeniu
   pokazywany jest banner `role="alert"` z `Ponów`. Zmiana semantyki PRISMA nie była wymagana ani
   wykonana. Test `SourcesIngestionRefresh.test.tsx` potwierdza przejście wiersza `Ostrzeżenie` →
   `Zaimportowano` przed zakończeniem odświeżania.

3. **`onChanged` fire-and-forget (zachowane, zgodne z designem).**
   `ImportReviewModal` wywołuje `void Promise.resolve(onChanged()).catch(() => undefined)`. Decyzja jest
   terminalna; błąd odświeżania jest widoczny na stronie Źródła. Zgodne z designem.

4. **`handleDecisionApplied` aktualizuje `reviewer_id`/`reviewed_at` z odpowiedzi decyzji.**
   Spójne z odpowiedzią backendu; type-check PASS.

### Weryfikacja przeglądarkowa/E2E (LOW-3) — WYKONANA
- Dodano `frontend/e2e/import-review.spec.ts` uruchamiany przez Playwright (Chromium) z zmockowanym
  backendem (route interception), bez przeładowania strony i bez uruchamiania FastAPI.
- 3 scenariusze, wszystkie PASS:
  1. Akceptacja aktualizuje wiersz do `Zaimportowano` i zamyka modal.
  2. Spinner widoczny tylko na `Akceptuję`; `Odrzucam` i `Zamknij` wyłączone w trakcie; modal zamyka
     się po zakończeniu.
  3. Nieudane odświeżenie utrzymuje modal zamknięty i pokazuje banner z `Ponów`.
- Brak istniejącego frameworka przeglądarkowego w repo; dodano `@playwright/test` jako devDependency.
  Testy vitest (47 plików / 358 testów) nadal PASS i nie skanują katalogu `e2e/`.

## 5. Uzgodnienie liczników i provenance

| Wielkość | Przed akceptacją | Po akceptacji | Zmiana? |
|---|---|---|---|
| `import_history.status` | `warning` | `warning` (niezmieniony) | Nie |
| `effective_status` (wyliczany) | `warning` | `success` | Tak (tylko etykieta) |
| `successful_imports_count` (per źródło) | n | n+1 | Tak (pochodna) |
| `warning_imports_count` (per źródło) | n | n-1 | Tak (pochodna) |
| `records_added_count` | n | n | Nie |
| Working collection total | n | n | Nie |
| Canonical publications | n | n | Nie |
| Source records | n | n | Nie |
| Skip-audit | n | n | Nie |
| Duplicate/screening/QA/extraction/synthesis | n | n | Nie |
| PRISMA `total_identified`, `records_removed_prescreening`, `records_after_*` | n | n | Nie |
| `import_review_decisions` (decyzje) | 0 | 1 (append-only) | Tak (nowa decyzja) |

Provenance: `ProvenanceEntry`, source-record identity, import provenance, audit trails (`import_history`,
`import_skip_audit`, `normalization_executions`) pozostają nietknięte. Decyzja jest append-only i atrybuowana
(reviewer_id, decided_at, rationale).

## 6. Weryfikacja braku automatyzacji decyzji naukowych

- Akceptacja importu jest **jawną decyzją badacza** (przycisk `Akceptuję` + `reviewer_id` z tożsamości
  recenzenta). System nie podejmuje jej autonomicznie.
- `accept()` wymaga `reviewer_id` (walidowany, niepusty); brak auto-akceptacji.
- Odrzucenie wymaga `confirm_rejection=True` (jawne potwierdzenie) i jest blokowane przez zależny
  stan badawczy (screening, QA, extraction, synthesis, finalizacja itd.).
- Żadna AI/rekomendacja nie jest używana w ścieżce decyzji.
- Zgodne z ADR-0006.

## 7. Wyniki testów (dowody)

```text
bash scripts/agent/safe_pytest.sh tests/unit/services/test_import_review_service.py \
  tests/unit/services/test_sources_summary_service.py tests/unit/api/test_import_review_api.py \
  tests/integration/test_v074_import_review_integration.py
38 passed, 1 warning

npm --prefix frontend test -- ImportWarningResolution.test.tsx SourcesIngestionRefresh.test.tsx
Test Files  2 passed (2)
Tests      12 passed (12)

npm --prefix frontend run type-check   # tsc --noEmit: OK
npm --prefix frontend run build        # vite build: OK
uv run --frozen --no-sync ruff check app tests scripts   # All checks passed
uv run --frozen --no-sync mypy app                      # Success: no issues
openspec validate --all --strict                         # 4 passed, 0 failed
python3 scripts/agent/safe_git_inspect.py diff --check   # (bez błędów)
```

## 8. Wnioski i werdykt

Zmiana v0.7.5 jest **wyłącznie frontendowa** (lifecycle modalu, odświeżanie read-modelu) plus nowe
testy regresyjne. Nie wprowadza mutacji bazy danych poza ścieżką odrzucenia (niezmienioną z v0.7.4).
Akceptacja pozostaje niezniszczająca, zmieniając wyłącznie status efektywny i liczniki pochodne.
PRISMA, provenance, source records, skip-audit, historia decyzji i rekordy badawcze pozostają
nietknięte. Nie stwierdzono automatyzacji decyzji naukowych.

Zastrzeżenia LOW (wzmocnienie snapshotu testowego, tymczasowa nieaktualność liczników per-źródło
przed odświeżeniem, brak weryfikacji przeglądarkowej) nie są blokerami integralności danych.

### WERDYKT: GO

Zmiana może przejść do merge po spełnieniu następujących warunków (poza zakresem integralności danych):

1. Jawna autoryzacja człowieka na merge/archive/release/deploy.
2. Weryfikacja przeglądarkowa/E2E pozostaje `NOT VERIFIED` — do uzupełnienia przed release.
3. Opcjonalne wzmocnienie testu snapshotu o rekordy screening/QA/extraction/synthesis (LOW-1).

### Oświadczenie końcowe

Żadna decyzja naukowa nie została zautomatyzowana. Zmiana nie modyfikuje metodologii, kryteriów,
populacji ani etapów PRISMA. Wszystkie mutacje danych badawczych pozostają jawne, atrybuowane
i audytowalne.>
