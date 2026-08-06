# Data Integrity Cleanup

## Wprowadzenie

Po wydaniu v0.2.4 aplikacja posiada pierwszy działający pipeline przetwarzania danych projektu:

```text
Search
  → Sources & Imports
  → Normalization
  → Deduplication
```

Przed rozpoczęciem prac nad Screeningiem należy uporządkować integralność danych oraz granice odpowiedzialności pomiędzy komponentami tego pipeline'u. Niniejszy dokument stanowi backlog długu technicznego, a nie roadmapę nowych funkcjonalności.

Zakres prac nie obejmuje nowych możliwości produktu ani zmian UX. Celem jest zwiększenie stabilności architektury, jednoznaczności źródeł danych, atomowości zapisu i przewidywalności testów przy zachowaniu obecnego zachowania funkcjonalnego aplikacji.

## Zadanie 1 — Integrity Audit [COMPLETED]

**Cel**

Stworzenie modułu diagnostycznego sprawdzającego spójność danych pojedynczego projektu w całym istniejącym pipeline'ie.

**Uzasadnienie**

Working Collection, Import History, Provenance, wyniki Normalization oraz dane wykorzystywane przez Deduplication są przechowywane i odczytywane przez odrębne komponenty. Potrzebny jest jeden, deterministyczny mechanizm wykrywający rozbieżności między tymi obszarami przed ich ujawnieniem w kolejnych etapach workflow.

**Zakres**

- weryfikacja liczebności i identyfikatorów rekordów w Working Collection;
- porównanie Working Collection z audytem Import History;
- kontrola kompletności i poprawności powiązań Provenance;
- kontrola zgodności ostatniego wykonania Normalization z aktualnym zbiorem projektu;
- kontrola, czy Deduplication analizuje właściwy zbiór projektu i czy zapisane decyzje odnoszą się do istniejących grup;
- raportowanie wykrytych niespójności wraz z identyfikatorem projektu i kontekstem diagnostycznym;
- wyłącznie diagnostyka — moduł nie naprawia, nie usuwa ani nie modyfikuje danych.

**Kryteria ukończenia (Definition of Done)**

- jedno polecenie pozwala zweryfikować integralność wskazanego projektu;
- wynik jednoznacznie rozróżnia stan poprawny, ostrzeżenia i błędy integralności;
- każda kontrola ma deterministyczny wynik oraz testy dla stanu poprawnego i niespójnego;
- uruchomienie audytu nie zmienia bazy danych;
- raport obejmuje Working Collection, Import History, Provenance, Normalization i Deduplication.

**Priorytet:** HIGH

**Zależności:** brak; zadanie definiuje reguły integralności wykorzystywane przez kolejne prace.

## Zadanie 2 — Transaction Boundary [COMPLETED]

**Cel**

Zapewnienie atomowego zapisu publikacji do Working Collection i odpowiadającego mu wpisu Import History w jednej transakcji SQLite.

**Status:** COMPLETED

**Opis nowej granicy transakcji:**
Atomowy zapis publikacji do Working Collection (`project_publications`), stworzenie rekordu w historii importu (`import_history`) oraz ewentualne usunięcie nieaktualnej normalizacji (`normalization_executions`) zostały wyizolowane w usłudze `ProjectImportService` i ujęte w jedną transakcję SQLite zaradzaną przez `SqliteTransactionManager` (`with connection:`).

**Rollback:**
Dowolny błąd w trakcie wykonywania zapisu publikacji, tworzenia wpisu w historii, usuwania starej normalizacji czy operacji SQL powoduje wycofanie całej transakcji SQLite (`ROLLBACK`). Stan Working Collection, Import History oraz Normalization Execution powraca do stanu początkowego 1:1.

**Semantyka `records_count`:**
Wartość `records_count` w historii odpowiada wyłącznie liczbie publikacji rzeczywiście dodanych do Working Collection (`group_result.imported_count`), a nie liczbie wejściowych rekordów z pliku/API. Dla ponownego importu samych duplikatów `records_count == 0` przy statusie `"warning"`.

**Uwaga architektoniczna (Bootstrap / Migracje):**
Inicjalizacja schematu bazy i wywoływanie `_apply_migrations()` w konstruktorach repozytoriów SQLite zostały pozostawione bez zmian w ich obecnym kształcie i podlegają przeglądowi w ramach Zadania 4 / Zadania 5.

**Zakres**

- identyfikacja wszystkich ścieżek zapisujących importy providerów i plików;
- zdefiniowanie granicy transakcji obejmującej Working Collection i Import History;
- zachowanie poprawnej delty `records_count`, w tym wartości `0` dla ponownego importu duplikatów;
- atomowy rollback wszystkich zmian w przypadku błędu dowolnej części operacji;
- testy awarii przed i po zapisie każdego zasobu;
- brak zmiany znaczenia Import History i obecnych reguł deduplikacji importu.

**Kryteria ukończenia (Definition of Done)**

- nie istnieje ścieżka udanego importu zapisująca publikacje bez odpowiadającego wpisu Import History;
- wpis historii nie zwiększa agregatu o więcej rekordów niż faktycznie dodano do Working Collection;
- błąd operacji pozostawia oba zasoby w stanie sprzed rozpoczęcia transakcji;
- import nowych rekordów, import mieszany i ponowny import samych duplikatów są objęte testami transakcyjnymi;
- Integrity Audit nie wykrywa rozbieżności po żadnym wspieranym wariancie importu.

**Priorytet:** HIGH

**Zależności:** Zadanie 1 — Integrity Audit, który dostarcza reguły walidujące rezultat transakcji.

## Zadanie 3 — Backend Read Models [COMPLETED]

**Cel**

Przeniesienie agregacji danych Sources & Imports z frontendu do jawnego modelu odczytowego backendu.

**Status:** COMPLETED

**Opis zmian:**
Stworzono backendowy DTO `SourcesSummaryResponse` oraz serwis `SourcesSummaryService` serwujący dedykowany endpoint `GET /projects/{project_id}/sources-summary`. Licznik `working_collection.total_records` pobierany jest bezpośrednio z `ProjectPublicationRepository.count_by_project()`, a podsumowania per źródło (`source_summaries`) oraz historia importów (`import_history`) są wyliczane i deterministycznie sortowane na backendzie. Z frontendu (`SourcesIngestionPage.tsx`) całkowicie usunięto domenowe sumowania `reduce()` i grupowania importów.

**Zakres**

- określenie agregatów wymaganych przez Sources & Imports;
- zdefiniowanie backendowego DTO zawierającego gotowe wartości per źródło oraz dane niezbędne do prezentacji historii;
- implementacja odczytu opartego na obowiązujących źródłach prawdy projektu;
- usunięcie obliczeń domenowych z frontendu po udostępnieniu DTO;
- testy kontraktowe dla pustego projektu, wielu importów, duplikatów i importów z różnych źródeł.

**Kryteria ukończenia (Definition of Done)**

- backend udostępnia kompletne, jednoznacznie nazwane DTO dla Sources & Imports;
- wartości agregatów są zgodne z regułami Integrity Audit;
- frontend wyłącznie renderuje wartości zwrócone przez backend;
- żaden komponent frontendowy nie sumuje samodzielnie `records_count` w celu ustalenia stanu kolekcji projektu;
- kontrakt DTO i jego przypadki brzegowe są objęte testami.

**Priorytet:** MEDIUM

**Zależności:** Zadanie 1 — reguły spójności; Zadanie 2 — stabilna granica zapisu danych źródłowych.

## Zadanie 4 — SQLite Constraints Review [ARCHITECTURE COMPLETED / IMPLEMENTATION PENDING]

**Cel**

Przeprowadzenie przeglądu ograniczeń integralności i indeksów w istniejącym schemacie SQLite.

**Status:** ARCHITECTURE COMPLETED / IMPLEMENTATION PENDING

**Artefakt wyjściowy:** [docs/SQLITE_CONSTRAINTS_REVIEW.md](file:///Users/jarek/Git/slr-platform/docs/SQLITE_CONSTRAINTS_REVIEW.md)

**Podsumowanie wyników przeglądu:**
Przeprowadzono audyt architektoniczny dla tabel pipeline'u (`search_strategies`, `import_history`, `project_publications`, `normalization_executions`, `duplicate_review_decisions`) oraz tabeli infrastrukturalnej `schema_migrations`. Zidentyfikowano brak więzów `FOREIGN KEY` (z powodu braku nadrzędnej tabeli `projects`), brak klauzul `CHECK` dla słowników statusów i typów oraz zweryfikowano zapytania bazy za pomocą `EXPLAIN QUERY PLAN`. Sformułowano katalog reguł (A/B/C/D), priorytety późniejszych migracji (HIGH/MEDIUM/LOW) oraz ocenę ryzyka przebudowy tabel. Sam przegląd nie modyfikował DDL tabel w SQLite; fizyczne wdrożenie migracji SQL oczekuje na realizację.

**Zakres**

- przegląd ograniczeń `UNIQUE`;
- przegląd kluczy `FOREIGN KEY` oraz reguł usuwania i aktualizacji;
- przegląd ograniczeń `CHECK` dla statusów, liczników i pól zależnych;
- przegląd indeksów wspierających odczyty projektowe i kontrole integralności;
- identyfikacja danych historycznych, które mogłyby naruszyć proponowane ograniczenia;
- przygotowanie oceny ryzyka i kolejności ewentualnego wprowadzania ograniczeń.

**Kryteria ukończenia (Definition of Done)**

- istnieje udokumentowana lista obecnych i brakujących ograniczeń dla każdej tabeli objętej pipeline'em;
- każda rekomendacja wskazuje chronioną regułę, ryzyko migracji i wymagane indeksy;
- lista rozróżnia zabezpieczenia możliwe do egzekwowania w SQLite od walidacji domenowej;
- znane dane historyczne zostały sprawdzone pod kątem zgodności z proponowanymi regułami;
- sam przegląd nie zmienia schematu ani danych.

**Priorytet:** MEDIUM

**Zależności:** Zadanie 1 — katalog reguł integralności; Zadanie 2 — docelowa granica transakcji.

## Zadanie 5 — Repository Contracts [COMPLETED]

**Cel**

Zweryfikowanie i doprecyzowanie odpowiedzialności kontraktów repozytoriów uczestniczących w pipeline'ie danych projektu.

**Status:** COMPLETED

**Opis zmian:**
Doprecyzowano abstrakcyjne protokoły wszystkich repozytoriów (`ProjectPublicationRepository`, `ImportHistoryRepository`, `NormalizationExecutionRepository`, `DuplicateReviewDecisionRepository`, `SearchStrategyRepository`) w `app/repositories/`. Oznaczono je dekoratorem `@runtime_checkable`, opisano odpowiedzialności domenowe w docstringach oraz wyeliminowano wyciek sterownika `sqlite3` ze styków interfejsów Protocol. Opcjonalne parametry połączenia transakcyjnego zachowano w klasach implementacji SQLite, a spójność kontraktów potwierdzono nowym zestawem testów `tests/unit/repositories/test_repository_contracts.py`.

**Uzasadnienie**

Jednoznaczne granice repozytoriów ograniczają duplikowanie zapytań, ukryte agregacje oraz zależności między zapisem danych operacyjnych i audytowych. Kontrakty powinny odzwierciedlać pojedynczą odpowiedzialność bez przejmowania orkiestracji procesu.

**Zakres**

- przegląd `ProjectPublicationRepository` jako dostępu do Working Collection;
- przegląd `ImportHistoryRepository` jako trwałego audytu operacji importu;
- przegląd repozytorium Normalization jako trwałości wykonania i jego wyniku;
- przegląd repozytorium Deduplication, w tym trwałości decyzji review;
- wskazanie metod wykraczających poza odpowiedzialność danego repozytorium;
- zdefiniowanie zasad dotyczących transakcji, agregacji, identyfikatorów i obsługi braku danych;
- aktualizacja testów kontraktowych bez zmiany zachowania funkcjonalnego.

**Kryteria ukończenia (Definition of Done)**

- każde repozytorium posiada jedną, opisaną odpowiedzialność;
- orkiestracja wielu repozytoriów nie znajduje się w implementacji pojedynczego repozytorium;
- kontrakty nie zawierają ukrytych agregacji przeznaczonych wyłącznie dla konkretnego ekranu;
- zachowanie implementacji SQLite i implementacji testowych jest zgodne z tym samym zestawem testów kontraktowych;
- zależności pomiędzy repozytoriami i warstwą transakcyjną są jawne.

**Priorytet:** MEDIUM

**Zależności:** Zadanie 2 — granica transakcji; Zadanie 3 — oddzielenie read modeli; Zadanie 4 — wynik przeglądu schematu.

## Zadanie 6 — Test Fixtures [COMPLETED]

**Cel**

Zastąpienie długowiecznych, ręcznie przygotowanych projektów testowych deterministycznymi fixture tworzonymi na potrzeby konkretnego testu.

**Status:** COMPLETED

**Opis zmian:**
Utworzono deterministyczne fabryki domeny SLR (`make_publication`, `make_author`, `make_import_history`, `make_normalization_execution`, `make_duplicate_decision`) w `tests/fixtures/factories.py` oraz odizolowane fixture projektowe (`empty_project`, `project_100`, `project_duplicates`, `project_normalized`) w `tests/fixtures/project_fixtures.py`. Wyeliminowano lokalne helpery mockujące oraz powielony setup danych w `test_integrity_audit_service.py`.

**Uzasadnienie**

Współdzielone bazy i ręcznie modyfikowane projekty utrudniają odtworzenie błędów oraz mogą maskować zależności od kolejności testów. Jawne fixture zapewnią izolację, powtarzalność i czytelne oczekiwania dotyczące danych wejściowych.

**Zakres**

- fixture `empty_project`;
- fixture `project_100`;
- fixture `project_duplicates`;
- fixture `project_normalized`;
- fixture `project_screening` przygotowująca wyłącznie dane graniczne dla przyszłych testów, bez implementowania Screeningu;
- fabryki deterministycznych publikacji, provenance, historii importu, wykonania normalizacji i decyzji deduplikacji;
- izolowana baza SQLite tworzona i usuwana przez mechanizm testowy;
- migracja testów integralności i repozytoriów z danych długowiecznych na fixture.

**Kryteria ukończenia (Definition of Done)**

- testy automatyczne nie zależą od ręcznie przygotowanej ani współdzielonej bazy danych;
- każda fixture ma jawnie określoną liczebność, źródła i oczekiwany stan integralności;
- wielokrotne uruchomienie testów daje identyczny wynik niezależnie od kolejności;
- fixture nie korzystają z sieci ani z danych środowiska deweloperskiego;
- przypadki poprawne i celowo niespójne są łatwe do utworzenia w testach Integrity Audit.

**Priorytet:** LOW

**Zależności:** Zadanie 1 — zestaw scenariuszy integralności; Zadania 2–5 — ustabilizowane kontrakty zapisu, odczytu i repozytoriów.

## Zadanie 7 — CLI Integrity Check

**Cel**

Dodanie prostego narzędzia CLI uruchamianego jako:

```bash
python -m app.tools.integrity
```

Narzędzie ma umożliwiać wykonanie pełnej diagnostyki integralności projektu bez GUI.

**Uzasadnienie**

Reguły diagnostyczne powinny być dostępne podczas lokalnego rozwoju, obsługi incydentów i kontroli przed migracją danych. CLI zapewni powtarzalny punkt wejścia bez duplikowania logiki audytu.

**Zakres**

- cienka warstwa uruchomieniowa wykorzystująca moduł Integrity Audit;
- wskazanie projektu i ścieżki bazy za pomocą jednoznacznych argumentów;
- czytelny wynik tekstowy dla stanu poprawnego, ostrzeżeń i błędów;
- stabilne kody wyjścia odpowiednie do użycia w automatyzacji;
- tryb wyłącznie do odczytu, bez operacji naprawczych;
- testy parsowania argumentów, kodów wyjścia i prezentacji wyniku.

**Kryteria ukończenia (Definition of Done)**

- pełną diagnostykę wskazanego projektu można uruchomić bez GUI;
- CLI korzysta z tych samych reguł i struktur wyniku co Integrity Audit;
- stan poprawny kończy się kodem `0`, a wykryte błędy integralności kodem niezerowym;
- komunikaty wskazują projekt, wykonaną kontrolę i wykrytą niespójność;
- uruchomienie CLI nie modyfikuje danych ani schematu.

**Priorytet:** LOW

**Zależności:** Zadanie 1 — gotowy moduł diagnostyczny; Zadanie 6 — deterministyczne fixture do testów CLI.

## Poza zakresem

Sprint Data Integrity Cleanup nie obejmuje:

- Screeningu;
- Quality Assessment;
- Extraction;
- Synthesis;
- funkcji wykorzystujących AI;
- fizycznego merge publikacji;
- nowych funkcjonalności produktu;
- zmian UX.

## Kolejność realizacji

1. Integrity Audit [COMPLETED]
2. Transaction Boundary [COMPLETED]
3. Backend Read Models [COMPLETED]
4. SQLite Constraints [ARCHITECTURE COMPLETED / IMPLEMENTATION PENDING]
5. Repository Contracts [COMPLETED]
6. Test Fixtures [COMPLETED]
7. CLI Integrity Check
