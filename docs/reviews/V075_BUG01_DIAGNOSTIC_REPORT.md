# Diagnostyka BUG-01 — liczniki menu/dashboard po zatwierdzeniu importów (v0.7.5)

**Data:** 2026-10-29
**Projekt:** Lean & Green PhD (`lean-green-phd-d05d3d`)
**Tryb:** wyłącznie diagnostyka — bez modyfikacji kodu, bazy, rollbacku, deploymentu.

## 1. Oczekiwane zachowanie (wg specyfikacji v0.7.5)

Spec (`specs/import-warning-resolution/spec.md`, Requirement "Acceptance updates only warning-derived counters"):
- Po akceptacji importu ostrzeżenia: aktywny wiersz importu → `Zaimportowano` (`effective_status=success`).
- `successful_imports_count` +1, `warning_imports_count` −1 dla danego źródła.
- `records_added_count`, working-collection total, canonical publications, source records, PRISMA — bez zmian.
- Decyzja jest terminalna niezależnie od odświeżania read-modelu.

Zatwierdzone 5 z 8 ostrzeżeń importów RIS (5 accepted, 3 pending, 3 success providers).

## 2. Rzeczywiste zachowanie (produkcja)

| Element | Wartość | Uwaga |
|---|---|---|
| Sources & Imports (lista) | 11 importów | zgodne z API |
| `successful_imports_count` (ris) | 5 | zgodne z 5 accepted |
| `warning_imports_count` (ris) | 3 | zgodne z 3 pending |
| `records_added_count` (ris) | 446 | niezmienione |
| Dashboard — Etap 2 (Sources) | 11 importów, stan `warning` | **nie zmienił się** — 3 ostrzeżenia pozostają |
| Dashboard — Etap 4 (Dedup) | 155 grup | nie dotyczy akceptacji (non-destructive) |
| Screening | 2/1348 oceniono | nie dotyczy akceptacji |
| Dashboard | "Ładowanie statusu projektu..." ~2.3 s | **długi czas ładowania** |

Backend API zwraca poprawne `effective_status` (5 success z accepted + 3 success providers = 8 success, 3 warning). Dane w SQLite spójne z API (5 decisions `accepted`, import_history.status nadal `warning`).

## 3. Przyczyna błędu

v0.7.5 naprawiło **wyłącznie** przepływ na stronie Sources:
- dialog zamyka się natychmiast po POST,
- `handleDecisionApplied` aktualizuje lokalny `import_history` (wiersz) na stronie Sources,
- `fetchSummary` (getSourcesSummary) aktualizuje `source_summaries` (liczniki) w tle.

**Nie naprawiło** dwóch rzeczy:

**A. Wspólny `workflowStatus` (sidebar + dashboard) nie jest aktualizowany po akceptacji.**
`handleDecisionApplied` aktualizuje tylko stan lokalny strony Sources, nie wspólny `workflowStatus` w `ProjectContext`. Sidebar (etap Sources: `warning`/`completed`) i dashboard (karta Sources) korzystają z `workflowStatus`, który aktualizuje się dopiero po zakończeniu `refreshWorkflowStatus` (fan-out 10 endpointów). Jeśli użytkownik przejdzie na dashboard przed zakończeniem odświeżania, widzi stan sprzed decyzji.

**B. `refreshWorkflowStatus` jest ciężki i wolny na dużych danych.**
Czasy endpointów na projekcie produkcyjnym:
- `extraction/progress`: ~2.3 s
- `screening/full-text`: ~1.9 s
- `duplicate-groups`: ~1.7 s
- `prisma/metrics`: ~0.9 s

`refreshWorkflowStatus` używa `Promise.allSettled`, więc czeka na najwolniejszy endpoint (~2.3 s). Dashboard wyświetla "Ładowanie statusu projektu..." przez cały ten czas, przy każdym wejściu (brak cache, brak aktualizacji przyrostowej).

**C. Semantyka "liczników" jest myląca.**
Etap Sources na dashboardzie pokazuje `imports.length` (11) i stan `warning`/`completed` zależny od `hasWarning` (czy JAKIKOLWIEK import ma effective_status `warning`). Ponieważ 3 importy pozostają niezaakceptowane, stan pozostaje `warning` i licznik pozostaje 11 — **to jest poprawne zachowanie**, a nie błąd. Użytkownik może oczekiwać zmiany, ale kontrakt non-destructive (ADR/spec) nie przewiduje zmiany `imports.length` ani stanu etapu, dopóki wszystkie ostrzeżenia nie zostaną rozstrzygnięte.

## 4. Dlaczego testy v0.7.5 nie wykryły problemu

- Testy frontendowe działają w jsdom z **zmockowanymi** odpowiedziami API (`vi.spyOn`). Nie trafiają do backendu, nie używają rzeczywistych danych (155 grup, 1348 rekordów).
- `SourcesIngestionRefresh.test.tsx` używa małego fixture (1 import, 378 rekordów) i asseruje tylko wiersz `Zaimportowano` + stabilność working collection. Nie weryfikuje:
  - aktualizacji `workflowStatus` (sidebar/dashboard) po akceptacji,
  - czasu ładowania dashboardu,
  - zachowania przy dużych datasetach.
- Brak testu E2E na realnym backendzie (Playwright używa route interception / mocków).
- Testy backendowe używają jednorazowych baz SQLite z małymi fixture'ami.

Wniosek: testy v0.7.5 weryfikują **zmockowane** odpowiedzi, nie rzeczywiste zachowanie aplikacji na produkcyjnych danych.

## 5. Brakujące testy (rekomendowane)

1. Test sidebar/dashboard: po akceptacji importu, `workflowStatus.sources.state` aktualizuje się (lub pozostaje `warning` z udokumentowanym powodem, jeśli zostają ostrzeżenia) — weryfikacja, że odświeżanie nie jest "zgubione".
2. Test wydajności: `refreshWorkflowStatus` na projekcie z ≥100 grupami deduplikacji i ≥1000 rekordów screening kończy się w akceptowalnym czasie (np. <2 s) lub pokazuje progresywny loading.
3. Test E2E na realnym backendzie (nie mockach) dla przepływu akceptacji → aktualizacja dashboardu.
4. Test, że `handleDecisionApplied` aktualizuje (lub celowo nie aktualizuje) `workflowStatus` — udokumentowane zachowanie.

## 6. Rekomendowana poprawka (nie zaimplementowana — wyłącznie diagnostyka)

**Priorytet 1 — aktualizacja `workflowStatus` po akceptacji:**
- Rozszerzyć `handleDecisionApplied` (lub dodać callback) o aktualizację wspólnego `workflowStatus.sources`: jeśli po decyzji nie ma żadnego importu z effective_status `warning`, ustawić `sourcesState = 'completed'`. Nie zmieniać PRISMA ani danych badawczych.

**Priorytet 2 — wydajność `refreshWorkflowStatus`:**
- Dodać per-endpoint timeout (np. 5 s) i partial results: aktualizować `workflowStatus` przy każdym rozwiązanym promise, zamiast czekać na wszystkie.
- Rozważyć cache / memoizację wyników `getDuplicateGroups` i `getPrismaMetrics` (które powtarzają obliczenia).
- Rozważyć leniwe ładowanie etapów (renderować dashboard z dostępnymi danymi, uzupełniać asynchronicznie).

**Priorytet 3 — UX:**
- Zastąpić pojedynczy "Ładowanie statusu projektu..." progresywnym wskaźnikiem per-etap.
- Pokazać, które etapy są gotowe, a które się ładują.

**Zastrzeżenie:** Priorytet 1 zmienia tylko stan UI (workflowStatus), nie bazy ani PRISMA. Priorytety 2–3 to optymalizacja wydajności. Żadna z rekomendacji nie zmienia danych badawczych.

## 7. Wnioski

- Backend i dane są spójne (API = DB). Liczniki `source_summaries` aktualizują się poprawnie po akceptacji.
- Problem jest w warstwie **frontendowej**: wspólny `workflowStatus` (sidebar/dashboard) nie jest aktualizowany po akceptacji, a `refreshWorkflowStatus` jest zbyt wolny na dużych danych.
- v0.7.5 naprawiło dialog i stronę Sources, ale **nie naprawiło** aktualizacji sidebar/dashboard ani wydajności.
- Testy v0.7.5 są oparte na mockach i małych fixture'ach — nie wykrywają problemu na produkcji.

**Rekomendacja:** otworzyć nową zmianę OpenSpec (np. `slr-v0-7-6-dashboard-refresh-performance`) obejmującą aktualizację `workflowStatus` po decyzji oraz optymalizację `refreshWorkflowStatus`. Nie modyfikować danych badawczych ani PRISMA.
