# Recovered independent Verify report

Recovered from the prior Verify answer (only trailing whitespace normalized) in Codex session `01a19106-aa51-72f1-8695-f6e41622315f`. Reviewer identified by the owner as GPT-6.1 Sol High. This is historical evidence, not a new verification of the follow-up changes. Line references refer to the pre-follow-up worktree.

**NOT READY FOR MERGE.** Niezależna weryfikacja wykryła błąd aktualności projekcji po `rebuild` oraz istotne luki w testach. Deklaracja „19/19 ukończonych” nie jest w pełni potwierdzona.

| Wymaganie | Ocena | Wynik |
|---|---|---|
| GET nie zapisuje danych | **PASS** | Odczyt korzysta z transakcji `mode=ro`; testy nie wykazały zmian projekcji ani historii. |
| Atomowość normalizacji i wskazanych mutacji | **PASS** | Wspólne połączenie i rollback potwierdzone testami. |
| Aktualność projekcji po wszystkich operacjach | **FAIL** | Po `rebuild` pozostają identyfikatory usuniętej grupy. |
| Rollback przy błędach | **PASS** | Przechodzą testy błędów publikacji, projekcji, snapshotów i podsumowania. |
| Zachowanie decyzji i snapshotów | **PASS** | W sprawdzonych ścieżkach materializacja nie przepisuje historii; historyczny `PENDING` nie zastępuje decyzji. |
| Screening i PRISMA | **PASS** | Testy regresyjne przeszły; algorytmy nie zostały zmienione. |
| Pierwsze ładowanie pokazuje właściwe grupy i readiness | **BLOCKED** | API odpowiada, UI kończy ładowanie, ale E2E nie sprawdza zgodności wyświetlonych wyników z odpowiedzią. |
| Rozwiązanie zgłoszonego incydentu runtime | **BLOCKED** | Incydentu nie odtworzono. Zielony test syntetyczny nie potwierdza jego usunięcia. |
| Pełna ochrona przed konfliktami SQLite | **BLOCKED** | Test współbieżności nie wymusza konkretnego przeplotu ani nie sprawdza pełnego stanu odpowiedzi. |

**Wykryte problemy**

1. **HIGH — nieaktualne identyfikatory grup po `rebuild`.**
   [corpus_derived_state_service.py:108](/tmp/slr-platform-fix-deduplication-read-path-and-first-load/app/services/corpus_derived_state_service.py:108) materializuje i zatwierdza projekcję. Następnie [linia 120](/tmp/slr-platform-fix-deduplication-read-path-and-first-load/app/services/corpus_derived_state_service.py:120) wykonuje reconciliation, które może usunąć merge i decyzję. Projekcja nie jest ponownie uzgadniana.

   Odtworzyłem istniejący scenariusz merge → usunięcie publikacji → rebuild, dodając wyłącznie syntetyczne rekordy źródłowe w tymczasowej bazie. Wynik:

   ```text
   GET groups after rebuild: 0
   source group IDs after rebuild:
   ['841d298c-eba5-5dbb-b958-b449b1ecc646',
    '841d298c-eba5-5dbb-b958-b449b1ecc646', None]
   ```

   Istniejący [test:252](/tmp/slr-platform-fix-deduplication-read-path-and-first-load/tests/unit/services/test_normalization_dedup_active_corpus.py:252) sprawdza grupy i usunięcie merge, lecz pomija projekcję źródłową. Należy uzgodnić projekcję z końcowym stanem reconciliation i objąć ten przypadek testem atomowości.

2. **MEDIUM — E2E pierwszego ładowania może przejść z błędnym wynikiem.**
   [deduplication-first-load.spec.ts:34](/tmp/slr-platform-fix-deduplication-read-path-and-first-load/frontend/e2e/deduplication-first-load.spec.ts:34) oczekuje HTTP 200, widoczności karty, braku błędu i wpisu `performance`. Nie sprawdza liczby ani członków grup, readiness ani zgodności UI z JSON. Pusta odpowiedź może spełnić te asercje. Konfiguracja uruchamia też serwer Vite dev, choć design przewiduje test zbudowanego frontendu.

   Spośród siedmiu testów trzy dotyczą importów z mockami, dwa przechwytują błędy deduplikacji, jeden sprawdza rzeczywiste pierwsze ładowanie w opisany ograniczony sposób, a jeden rzeczywistą akceptację importu. W ostatnim [page.goto:46](/tmp/slr-platform-fix-deduplication-read-path-and-first-load/frontend/e2e/v076-workflow-status-real-backend.spec.ts:46) przeładowuje dokument przed sprawdzeniem Dashboardu. Nie dowodzi więc jego aktualizacji bez przeładowania.

3. **MEDIUM — niewystarczający test współbieżności.**
   [test_v073_r2_duplicate_review.py:178](/tmp/slr-platform-fix-deduplication-read-path-and-first-load/tests/integration/test_v073_r2_duplicate_review.py:178) synchronizuje start żądań, ale nie moment odczytu względem zapisu. Asercje sprawdzają przede wszystkim zgodność liczników z długością list. Potrzebne są wymuszony przeplot i porównanie pełnego wyniku z dopuszczalnym stanem przed lub po imporcie.

   Ponadto transakcja odczytu pozostaje otwarta podczas budowania i serializacji grup ([project_duplicate_service.py:205](/tmp/slr-platform-fix-deduplication-read-path-and-first-load/app/services/project_duplicate_service.py:205)). W trybie rollback journal może opóźniać commit pisarza. Obecne testy nie rozstrzygają ryzyka dla większego korpusu.

4. **MEDIUM — diagnostyka nie mierzy pełnego czasu odpowiedzi.**
   [deduplication.py:68](/tmp/slr-platform-fix-deduplication-read-path-and-first-load/app/api/routers/deduplication.py:68) zapisuje status i czas przed serializacją odpowiedzi przez FastAPI i jej wysłaniem. Szczegółowe logi serwisu nie zawierają tokenu korelacyjnego routera. Wymaganie rozróżnienia etapów aż do dostarczenia odpowiedzi jest spełnione częściowo.

**Audyt 19 zadań**

`BLOCKED` oznacza tutaj brak wystarczających niezależnych dowodów.

| Zadanie | Ocena | Uzasadnienie |
|---|---|---|
| 1.1 | PASS | Mapa granic transakcji istnieje i odpowiada sprawdzonym ścieżkom. |
| 1.2 | FAIL | Niepełny pomiar odpowiedzi i korelacja etapów. |
| 1.3 | BLOCKED | Historycznych pomiarów porównawczych nie potwierdziłem niezależnie. |
| 2.1 | PASS | Odczyt bez zmian projekcji i historii. |
| 2.2 | PASS | Regresje grup, screeningu i PRISMA przechodzą. |
| 2.3 | FAIL | Test nie dowodzi deklarowanej spójności przy przeplocie. |
| 2.4 | PASS | Testy rollbacku normalizacji przechodzą; chronologia TDD pozostaje niepotwierdzona. |
| 2.5 | PASS | Testowane granice mutacji wycofują zapisy. |
| 2.6 | PASS | Historyczne członkostwo chroni zapisaną decyzję. |
| 2.7 | PASS | Testy frontendowych stanów i błędów przechodzą. |
| 2.8 | FAIL | Niewystarczająca asercja rzeczywistych grup/readiness. |
| 3.1 | PASS | GET jest odczytowy. |
| 3.2 | FAIL | Końcowy stan po rebuild może mieć nieaktualną projekcję. |
| 3.3 | PASS | Decyzja jest autorytatywna wobec snapshotu. |
| 3.4 | PASS | Zachowana struktura i niezmienność snapshotów. |
| 4.1 | FAIL | Zielony E2E nie potwierdza wszystkich zadeklarowanych rezultatów. |
| 4.2 | BLOCKED | Porównanie historycznych pomiarów pozostaje deklaracją Apply. |
| 4.3 | PASS | Kontrole uruchomiono; pełny backend nadal ma jeden błąd. |
| 4.4 | FAIL | Raport zawyża potwierdzone pokrycie i kompletność. |

To **11 PASS, 6 FAIL, 2 BLOCKED**, mimo 19 zaznaczonych checkboxów.

**Rzeczywiste wyniki ponownej weryfikacji**

- Backend: **2733 passed, 1 failed**.
- Playwright: **7 passed**.
- Frontend: **367 passed**, type-check i build przeszły.
- Ruff, mypy, OpenSpec strict, migration safety i diff hygiene przeszły.

Jedyny błąd backendu rzeczywiście dotyczy zewnętrznego katalogu modeli: [test_agent_foundation_configuration.py:785](/tmp/slr-platform-fix-deduplication-read-path-and-first-load/tests/unit/test_agent_foundation_configuration.py:785) oczekuje `opencode/nemotron-3-ultra-free`. Test i konfiguracje agentów nie są zmienione w diffie tej zmiany. Błąd jest niezwiązany z deduplikacją, lecz pozostaje niezaliczoną bramką.

**CI można uruchomić diagnostycznie. Zmiana nie jest gotowa do merge:** najpierw wymaga usunięcia błędu projekcji i uzupełnienia wskazanych dowodów, następnie zielonego CI dla konkretnego commitu. Nie zmieniałem kodu, testów ani specyfikacji; nie modyfikowałem danych badawczych.
