# Sources & Imports / Sources & Ingestion — audyt

Data audytu: 2026-07-30  
Branch: `development`  
Wersja: `0.1.8` (working tree)

## 1. Obecny stan modułu

Ekran jest dostępny pod `/projects/:projectId/sources` i renderuje karty providerów oraz historię importów. Jest to obecnie ekran oparty na danych `MOCK_PROJECTS`, a nie na backendowym zasobie Sources/Ingestion.

Backend posiada działające wyszukiwanie OpenAlex/Crossref oraz endpoint importu **zaznaczonych wyników wyszukiwania** do Working Collection. Nie posiada endpointu statusu providerów, endpointu uploadu RIS/BibTeX ani endpointu historii importów plików.

Parsery RIS i BibTeX istnieją jako moduły backendowe i są testowane jednostkowo, ale nie są wywoływane przez ekran Sources.

## 2. Mapa elementów GUI do kodu i danych

| Element GUI | Plik frontendowy | Endpoint/API | Backend/service | Baza danych | Źródło | Status |
|---|---|---|---|---|---|---|
| Status OpenAlex | `SourcesIngestionPage.tsx`, `ProviderStatusCard.tsx` | brak | brak status endpointu; live client istnieje w `app/providers/openalex.py` i jest używany przez Search Strategy | brak | `MOCK_PROJECTS.providers[*]` | demo/staticzne |
| Licznik rekordów OpenAlex | `ProviderStatusCard.tsx` | brak | brak agregacji do statusu | brak | `MOCK_PROJECTS`: `840` | demo/staticzny |
| Data ostatniego wykonania OpenAlex | `ProviderStatusCard.tsx` | brak | brak historii wykonań Sources | brak | `MOCK_PROJECTS`: `2026-07-28T14:20:00Z` | demo/staticzna |
| Status Crossref | `ProviderStatusCard.tsx` | brak | live Crossref istnieje dla Search Strategy, ale nie jest podłączony do karty | brak | `MOCK_PROJECTS.providers[*]` | demo/staticzny |
| Licznik Crossref | `ProviderStatusCard.tsx` | brak | brak | brak | `MOCK_PROJECTS`: `620` | demo/staticzny |
| Status Semantic Scholar | `ProviderStatusCard.tsx` | brak | klient/mapper istnieją, ale `LiveSearchService` nie buduje tego providera | brak | `MOCK_PROJECTS`: `connected=true`, `completed` | demo/staticzny i niespójny z wykonaniem |
| Licznik Semantic Scholar | `ProviderStatusCard.tsx` | brak | brak | brak | `MOCK_PROJECTS`: `410` | demo/staticzny |
| Hybrid Data Mode | `frontend/src/config/version.ts` | brak | brak | nie dotyczy | stała `RUNTIME_MODE` | jawnie oznaczony tryb hybrydowy |
| Upload RIS | `FileDropzone.tsx` | brak endpointu plikowego | parser `app/providers/import_file/ris/*` nie jest wywoływany przez API | brak | opcjonalny callback, na stronie nieprzekazany | makieta/partial |
| Upload BibTeX | `FileDropzone.tsx` | brak endpointu plikowego | parser `app/providers/import_file/bibtex/*` nie jest wywoływany przez API | brak | opcjonalny callback, na stronie nieprzekazany | makieta/partial |
| Drag and drop | `FileDropzone.tsx` | brak | brak | brak | lokalny stan `dragActive`; przekazanie tylko nazwy i formatu | częściowo działające wizualnie |
| Walidacja rozszerzenia | `FileDropzone.tsx` | brak | brak | brak | `.bib` oznacza BibTeX, każda inna nazwa oznacza RIS | brak odrzucenia niepoprawnych rozszerzeń |
| Parsowanie pliku | brak wywołania w frontendzie | brak | `parse_ris`, `parse_bibtex` oraz mappery/providerzy | brak | kod i testy jednostkowe | działa tylko bezpośrednio w kodzie/testach |
| Zapis rekordów | brak upload workflow | `POST /projects/{project_id}/search-results/imports` dotyczy tylko wyników search | `DemoProjectPublicationRepository.import_source_publications` | in-memory | rekordy search przekazane przez JSON | działa tylko dla wybranych wyników search |
| Historia importów | `FileDropzone.tsx` | brak | brak repozytorium historii plików | brak | `activeProject.imports` z mocka | demo/staticzna |
| Liczba rekordów w imporcie | `FileDropzone.tsx` | brak | brak | brak | `ImportFileRecord.recordsCount` w mocku | demo/staticzna |
| Status importu | `FileDropzone.tsx` | brak | brak | brak | `success/warning` w mocku | demo/staticzny |
| Powiązanie importu z projektem | `SourcesIngestionPage.tsx` | brak uploadu z `project_id` | brak | brak | aktywny projekt + mock | nie jest realizowane dla plików |

## 3. Elementy działające end-to-end

- `GET/PUT /projects/{project_id}/search-strategy` działa z backendem.
- `POST /projects/{project_id}/search-strategy/executions` wykonuje rzeczywiste wyszukiwanie OpenAlex; Crossref jest podłączony w warstwie Search Strategy.
- OpenAlex stosuje filtry strategii po stronie providera przed paginacją.
- `POST /projects/{project_id}/search-results/imports` zapisuje wybrane wyniki wyszukiwania do procesowego, in-memory Working Collection.
- Import wybranych wyników jest idempotentny i izolowany przez projekt/provider/`source_id`; potwierdzają to testy API i repozytorium.
- Parsery RIS/BibTeX poprawnie mapują treść na domenowy `Publication`, ale tylko jako bezpośrednie moduły backendowe.

## 4. Elementy częściowo podłączone

- Karty providerów mają model statusu (`connected`, `status`, `resultsCount`, `lastRunTimestamp`), ale wartości nie pochodzą z wykonania ani endpointu.
- `FileDropzone` reaguje na drag/drop i wywołuje opcjonalny callback, lecz `SourcesIngestionPage` nie przekazuje callbacku.
- Przycisk „Wybierz Plik” nie otwiera `<input type="file">`; wywołuje callback z fikcyjną nazwą `custom_import_export.ris`.
- Istniejący endpoint importu zapisuje wyłącznie już zmapowane rekordy search, nie multipart/file content.

## 5. Elementy demo/statyczne

Źródłem danych dla ekranu są `MOCK_PROJECTS` w `frontend/src/mocks/projectData.ts`, stan początkowy w `frontend/src/context/ProjectContext.tsx` oraz `getProjects()` w `frontend/src/services/api/projectApi.ts`, który zwraca kopię mocka i nie wykonuje requestu.

`RUNTIME_MODE = "Hybrid Data Mode (Deduplication API + Demo Data)"` jest stałą informacyjną. Nie znaleziono przełącznika wyłączającego tryb demo. Użytkownik ekranu Sources widzi dane demo nawet wtedy, gdy backend jest dostępny.

## 6. Elementy niezaimplementowane

Nie istnieją: endpoint statusu/health per provider; endpoint historii wykonań providerów dla Sources; endpoint multipart uploadu z `project_id`; frontendowy wybór rzeczywistego pliku; walidacja rozszerzeń, pustych plików i zawartości na granicy API; połączenie uploadu z parserem; zapis historii importu plików; trwała baza rekordów/importów dla tego workflow; odświeżenie historii po imporcie pliku; wykonanie Semantic Scholar przez Search Strategy/Sources.

## 7. Wyniki testów providerów i API

Istniejące testy providerów OpenAlex, Crossref i Semantic Scholar przechodzą. Testy Search Strategy potwierdzają realne wykonanie OpenAlex/Crossref oraz import zaznaczonych wyników search. Nie ma testu endpointu provider-status ani testu file-upload, ponieważ takich endpointów nie ma.

`GET /health` zwraca ogólny status aplikacji (`{"status":"ok"}`), ale nie potwierdza dostępności zewnętrznego providera.

## 8. Wyniki testu RIS

Użyto lokalnego, nietrwałego tekstu testowego (nie dodano pliku do repozytorium): 2 poprawne rekordy RIS dały 2 obiekty `Publication`; tytuły i identyfikatory źródłowe zmapowano poprawnie; pusty RIS dał pustą listę; uszkodzony RIS bez `ER` dał kontrolowany `ValueError`.

Parser/import provider działa jednostkowo, lecz nie działa end-to-end z ekranu Sources, ponieważ brak upload API i połączenia callbacku.

## 9. Wyniki testu BibTeX

Użyto lokalnego, nietrwałego tekstu testowego: 2 poprawne rekordy BibTeX dały 2 obiekty `Publication`; tytuły, DOI i identyfikatory źródłowe zmapowano poprawnie; pusty BibTeX dał pustą listę; rekord bez tytułu dał kontrolowany `ValueError`.

Parser i mapper działają, ale nie ma workflowu UI/API.

## 10. Problemy znalezione

1. Ekran deklaruje status połączeń z live API, lecz wszystkie wartości kart są statycznymi danymi projektu.
2. Semantic Scholar jest prezentowany jako połączony i zakończony mimo braku integracji w `LiveSearchService`.
3. UI sugeruje wybór pliku, ale nie ma elementu file input i nie przekazuje callbacku.
4. Dowolne rozszerzenie inne niż `.bib` jest klasyfikowane jako RIS; brak odrzucenia `.pdf`, pustych plików i uszkodzonych treści na granicy UI/API.
5. Historia importów i liczby rekordów są wyłącznie danymi mock.
6. Import plików nie ma powiązania z `project_id`; istniejące powiązanie dotyczy tylko importu wybranych wyników wyszukiwania.
7. In-memory Working Collection nie jest trwała i znika po restarcie backendu.

## 11. Minimalne naprawy wykonane

W tym audycie nie wykonano zmian kodu. Żaden z powyższych braków nie jest podłączeniem istniejącego endpointu, ponieważ odpowiedni endpoint dla Sources nie istnieje. Dodanie upload API, historii i statusów byłoby nowym przyrostem, który przekracza zakres audytu.

Utworzono wyłącznie niniejszy raport.

## 12. Pozostały backlog

- project-scoped upload RIS/BibTeX;
- walidacja formatu, pustych/uszkodzonych plików i komunikaty błędów;
- zapis rekordów oraz historii importu w trwałym repozytorium;
- endpoint statusu providerów i historia wykonań;
- zasilenie kart Sources rzeczywistymi danymi zamiast mocków;
- decyzja, czy Semantic Scholar ma być aktywny, czy oznaczony jako inactive;
- testy API/UI dla pełnego uploadu i izolacji importów między projektami.

## 13. Rekomendowany następny mały przyrost

Najmniejszy sensowny przyrost to **project-scoped upload RIS/BibTeX dla jednego pliku**: jeden endpoint multipart, wybór pliku w `FileDropzone`, wykorzystanie istniejących parserów, zapis do istniejącego repozytorium oraz odpowiedź z `records_count` i statusem. Dopiero po tym należy podłączać historię importów. Nie obejmuje to masowego importu, deduplikacji ani nowych providerów.

## 14. Weryfikacja automatyczna

- `.venv/bin/pytest -q`: **871 passed**, 1 warning (deprecacja TestClient/httpx);
- `cd frontend && npm test -- --run`: **11 plików, 56 testów passed**;
- `cd frontend && npm run type-check`: **OK**;
- `cd frontend && npm run build`: **OK**;
- `git diff --check`: wykonane poniżej, bez błędów treści.

Nie wykonano commita ani pushowania. Testowe treści RIS/BibTeX były użyte wyłącznie in-memory i nie zostały zapisane w repozytorium.

## Aktualizacja audytu — domknięcie 0.1.9

Powyższy audyt opisuje stan przed pierwszym uploadem. W wersji 0.1.9 został
zrealizowany kolejny przyrost:

- `POST /projects/{project_id}/imports` pozostaje działającym uploadem RIS/BibTeX;
- historia jest teraz zapisywana trwale w SQLite przez
  `SqliteImportHistoryRepository`;
- `GET /projects/{project_id}/imports` zwraca historię newest-first i izoluje ją
  po `project_id`;
- frontend pobiera historię z backendu przy zmianie projektu oraz po udanym
  imporcie — nie dopisuje wpisu wyłącznie do stanu Reacta;
- po restarcie aplikacji historia pozostaje dostępna w tej samej bazie;
- początkowe mockowe importy nie są już prezentowane jako historia aktywnego
  projektu;
- liczniki, daty i statusy providerów zostały zastąpione neutralnymi stanami
  (`Brak danych`, `Nie uruchamiano`, `Nie skonfigurowano`), ponieważ backend
  nie zapisuje jeszcze wykonań providerów dla Sources;
- `Hybrid Data Mode` wskazuje teraz jawnie na live Search/Upload API oraz
  demo-backed project metadata.

Nadal nie istnieją: trwałe wykonania/statusy providerów, provider health-checki,
pełny moduł Sources, background jobs i masowy import.

## Aktualizacja — trwała Working Collection

W kolejnym przyroście `SqliteProjectPublicationRepository` zastąpiło
`DemoProjectPublicationRepository` w runtime dla importów i Search Strategy.
Importy RIS/BibTeX oraz selected OpenAlex zapisują publikacje do wspólnej,
project-scoped tabeli `project_publications`. Normalizacja czyta i zastępuje
rekordy w tej samej kolekcji, a publikacje oraz summary normalizacji przetrwają
restart backendu. Deduplikacja, Crossref i Semantic Scholar pozostają poza tym
przyrostem.

## Aktualizacja audytu — integracja importu selected OpenAlex

Import zaznaczonych wyników z Search Strategy zapisuje publikacje jak wcześniej,
a następnie tworzy jeden trwały rekord historii typu `provider` dla aktywnego
projektu. Rekord zawiera `provider=openalex`, rzeczywisty rendered query,
`records_count` zaimportowanych rekordów oraz `total_available`; fingerprint
zapobiega duplikatowi przy identycznym ponowieniu requestu. Błąd importu nie
tworzy wpisu historii.

Karta OpenAlex na Sources korzysta z najnowszego udanego wpisu providerowego i
pokazuje jego liczbę oraz datę. Historia wspólnie prezentuje importy plikowe i
OpenAlex newest-first, bez fikcyjnej nazwy pliku dla providera. Crossref i
Semantic Scholar pozostają neutralne (`Brak danych`/`Nie uruchamiano`), ponieważ
nie mają podłączonego źródła historii Sources ani health-checku. Pełne
provenance pozostaje przyszłym etapem.
