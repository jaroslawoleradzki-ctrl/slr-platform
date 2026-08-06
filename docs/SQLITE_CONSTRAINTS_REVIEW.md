# Raport i Przegląd Ograniczeń Integralności oraz Indeksów SQLite (Zadanie 4: SQLite Constraints Review)

## 1. Executive Summary

Niniejszy dokument stanowi kompletny audyt architektoniczny i dokumentacyjny ograniczeń integralności danych oraz indeksów bazy danych SQLite dla systemu SLR Platform w obrębie całego pipeline'u przetwarzania:
`Search Strategy` → `Sources & Imports` → `Working Collection` → `Normalization` → `Deduplication`.

**Główne wnioski z audytu:**
1. **Brak kluczy obcych (`FOREIGN KEY`) i brak trwałej tabeli nadrzędnej `projects`**: W obecnym schemacie bazy danych żaden z kluczy `project_id` nie jest powiązany kluczem obcym `FOREIGN KEY`, ponieważ tabela główna projektów (`projects`) jeszcze fizycznie nie istnieje w bazie (jest reprezentowana w kodzie jako stała zbioru ID). Repozytoria wywołują `sqlite3.connect()` bez wysyłania `PRAGMA foreign_keys = ON;`.
2. **Ograniczenia wartości słownikowych (`CHECK`)**: Pola statusów (`status` w `import_history` oraz `normalization_executions`) oraz typów wejściowych (`source_type`, `format`, `provider`) nie posiadają więzów `CHECK` w schemacie SQL, chociaż w kodzie domenowym ich dopuszczalne wartości są ściśle zdefiniowane.
3. **Zapytania bazy danych a wydajność indeksowa (`EXPLAIN QUERY PLAN`)**:
   - Zapytanie `import_history.list_for_project` używa istniejącego indeksu złożonego `idx_import_history_project_created(project_id, created_at DESC)`.
   - Zapytanie `project_publications.get_publications` oraz `count_by_project` używają istniejącego indeksu `idx_project_publications_project_position(project_id, position)`.
   - Indeks `import_history(project_id, status)` **nie jest obecnie wymagany**, gdyż `SourcesSummaryService` oraz `IntegrityAuditService` pobierają całą historię dla danego `project_id` za pomocą `idx_import_history_project_created`.
4. **Analiza istniejących danych (Baza `data/slr-platform.db`)**: W badanej lokalnej bazie nie stwierdzono niezgodności `project_id` pomiędzy istniejącymi tabelami. Jednak ze względu na brak nadrzędnej tabeli `projects` zasada istnienia projektu pozostaje niemożliwa do zweryfikowania w samych relacjach SQL.

---

## 2. Zakres i metoda przeglądu

Przegląd został przeprowadzony metodą bezpośredniej analizy kodowej i bazy danych bez dokonywania jakichkolwiek modyfikacji danych ani schematu:
- **Analiza kodu źródłowego**: Przeanalizowano wszystkie pliki migracji w katalogu `migrations/` (`0001` - `0006`) oraz implementacje repozytoriów SQLite w `app/repositories/`.
- **Diagnostyka struktury schematu (read-only)**: Za pomocą narzędzia `sqlite3 -readonly data/slr-platform.db` pobrano DDL ze `sqlite_master` oraz wykonano polecenia `PRAGMA table_info`, `PRAGMA index_list`, `PRAGMA foreign_key_list` oraz `EXPLAIN QUERY PLAN`.
- **Weryfikacja historycznych danych**: Uruchomiono read-only zapytania SQL badające obecność osieroconych rekordów, duplikatów identyfikatorów oraz wartości w polach domenowych.

---

## 3. Infrastruktura migracyjna a tabele domenowe

Przegląd rozróżnia tabele domenowe pipeline'u od tabeli infrastruktury migracyjnej:
- **Tabela infrastruktury**: `schema_migrations` (rejestruje nazwy zaaplikowanych plików SQL `version TEXT PRIMARY KEY` oraz czas aplikacji `applied_at`). Nie bierze udziału w logice biznesowej pipeline'u.
- **Tabele domenowe pipeline'u**: `search_strategies`, `import_history`, `project_publications`, `normalization_executions`, `duplicate_review_decisions`.

---

## 4. Mapa i obecny stan tabel pipeline'u (DDL & PRAGMA)

### 4.1. Tabela `search_strategies`
- **Rola w pipeline**: Odpowiada za wersjonowanie strategii wyszukiwania dla projektu (`Search Strategy`).
- **Aktualny DDL**:
  ```sql
  CREATE TABLE search_strategies (
      project_id TEXT PRIMARY KEY,
      strategy_id TEXT NOT NULL UNIQUE,
      version INTEGER NOT NULL CHECK (version >= 1),
      document TEXT NOT NULL CHECK (json_valid(document)),
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL
  );
  ```
- **Constrainty & Indeksy**:
  - `PRIMARY KEY (project_id)` (tworzy automatyczny indeks `sqlite_autoindex_search_strategies_1`).
  - `UNIQUE (strategy_id)` (tworzy automatyczny indeks `sqlite_autoindex_search_strategies_2`).
  - `CHECK (version >= 1)` oraz `CHECK (json_valid(document))`.
  - Jawny indeks wydajnościowy: `idx_search_strategies_updated_at` na `(updated_at)`.
  - `FOREIGN KEY`: Brak.

### 4.2. Tabela `import_history`
- **Rola w pipeline**: Rejestruje operacje importu (ścieżka providerów OpenAlex/Crossref oraz plików RIS/BibTeX).
- **Aktualny DDL**:
  ```sql
  CREATE TABLE import_history (
      import_id TEXT PRIMARY KEY,
      project_id TEXT NOT NULL,
      source_type TEXT NOT NULL DEFAULT 'file',
      filename TEXT,
      format TEXT,
      provider TEXT,
      query TEXT,
      records_count INTEGER NOT NULL CHECK (records_count >= 0),
      total_available INTEGER,
      status TEXT NOT NULL,
      warnings TEXT NOT NULL DEFAULT '[]',
      created_at TEXT NOT NULL,
      fingerprint TEXT
  );
  ```
- **Constrainty & Indeksy**:
  - `PRIMARY KEY (import_id)` (tworzy automatyczny indeks `sqlite_autoindex_import_history_1`).
  - `CHECK (records_count >= 0)`.
  - Jawny indeks częściowy unikalności: `idx_import_history_project_fingerprint` na `(project_id, fingerprint) WHERE fingerprint IS NOT NULL`.
  - Jawny indeks sortowania i odczytu: `idx_import_history_project_created` na `(project_id, created_at DESC)`.
  - `FOREIGN KEY`: Brak.

### 4.3. Tabela `project_publications` (Working Collection)
- **Rola w pipeline**: Główna robocza kolekcja publikacji projektu.
- **Aktualny DDL**:
  ```sql
  CREATE TABLE project_publications (
      project_id TEXT NOT NULL,
      record_id TEXT NOT NULL,
      position INTEGER NOT NULL CHECK (position >= 0),
      title TEXT NOT NULL,
      title_normalized TEXT,
      publication_year INTEGER,
      authors TEXT NOT NULL CHECK (json_valid(authors)),
      identifiers TEXT NOT NULL CHECK (json_valid(identifiers)),
      provenance TEXT NOT NULL CHECK (json_valid(provenance)),
      created_at TEXT NOT NULL,
      document TEXT NOT NULL CHECK (json_valid(document)),
      PRIMARY KEY (project_id, record_id)
  );
  ```
- **Constrainty & Indeksy**:
  - `PRIMARY KEY (project_id, record_id)` (tworzy automatyczny złożony indeks `sqlite_autoindex_project_publications_1`).
  - `CHECK (position >= 0)` oraz sprawdziany poprawności struktury JSON (`authors`, `identifiers`, `provenance`, `document`).
  - Jawny indeks: `idx_project_publications_project_position` na `(project_id, position)`.
  - `FOREIGN KEY`: Brak.

### 4.4. Tabela `normalization_executions`
- **Rola w pipeline**: Rejestr ostatniego wykonania etapu normalizacji dla projektu.
- **Aktualny DDL**:
  ```sql
  CREATE TABLE normalization_executions (
      project_id TEXT PRIMARY KEY,
      run_id TEXT NOT NULL UNIQUE,
      status TEXT NOT NULL,
      processed_records INTEGER NOT NULL CHECK (processed_records >= 0),
      clean_records INTEGER NOT NULL CHECK (clean_records >= 0),
      warnings_count INTEGER NOT NULL CHECK (warnings_count >= 0),
      errors_count INTEGER NOT NULL CHECK (errors_count >= 0),
      started_at TEXT NOT NULL,
      completed_at TEXT NOT NULL,
      audit_trail TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(audit_trail)),
      rules_applied TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(rules_applied)),
      error_message TEXT
  );
  ```
- **Constrainty & Indeksy**:
  - `PRIMARY KEY (project_id)` (tworzy automatyczny indeks `sqlite_autoindex_normalization_executions_1`).
  - `UNIQUE (run_id)` (tworzy automatyczny indeks `sqlite_autoindex_normalization_executions_2`).
  - Liczne sprawdziany `CHECK (n >= 0)` oraz `json_valid(...)`.
  - Jawny indeks: `idx_normalization_executions_completed_at` na `(completed_at DESC)`.
  - `FOREIGN KEY`: Brak.

### 4.5. Tabela `duplicate_review_decisions`
- **Rola w pipeline**: Trwałe decyzje recenzenta dla grup duplikatów.
- **Aktualny DDL**:
  ```sql
  CREATE TABLE duplicate_review_decisions (
      project_id TEXT NOT NULL,
      group_id TEXT NOT NULL,
      decision TEXT NOT NULL CHECK (decision IN ('APPROVE', 'REJECT')),
      rationale TEXT,
      updated_at TEXT NOT NULL,
      PRIMARY KEY (project_id, group_id)
  );
  ```
- **Constrainty & Indeksy**:
  - `PRIMARY KEY (project_id, group_id)` (tworzy automatyczny indeks złożony `sqlite_autoindex_duplicate_review_decisions_1`).
  - `CHECK (decision IN ('APPROVE', 'REJECT'))`.
  - Jawny indeks: `idx_duplicate_review_decisions_project` na `(project_id)`.
  - `FOREIGN KEY`: Brak.

---

## 5. Weryfikacja wartości słownikowych w kodzie produkcyjnym

Na podstawie audytu kodu źródłowego ustalono precyzyjny podział wartości dozwolonych przez model produkcyjny a faktycznie występujących w lokalnej bazie testowej:

1. **`import_history.status`**:
   - *Dozwolone w modelu domenowym* (`ImportHistoryRecord` / DTO): `'success'`, `'warning'`, `'failed'`.
   - *Obecne w lokalnej bazie (`data/slr-platform.db`)*: tylko `'success'`.
2. **`import_history.source_type`**:
   - *Dozwolone w modelu domenowym*: `'provider'`, `'file'`.
   - *Obecne w lokalnej bazie*: `'provider'`, `'file'`.
3. **`import_history.format`**:
   - *Dozwolone w modelu domenowym*: `'RIS'`, `'BibTeX'` (lub `NULL` dla providerów).
   - *Obecne w lokalnej bazie*: `'RIS'`, `'BibTeX'`, `NULL`.
4. **`import_history.provider`**:
   - *Dozwolone w modelu domenowym*: `'openalex'`, `'crossref'`, `'semantic_scholar'` (lub `NULL` dla plików).
   - *Obecne w lokalnej bazie*: `'openalex'`, `'crossref'`, `NULL`.
5. **`normalization_executions.status`**:
   - *Dozwolone w modelu domenowym* (`NormalizationExecution`): `'completed'`, `'warning'`, `'error'`.
   - *Obecne w lokalnej bazie*: 0 rekordów (pusta tabela).

---

## 6. Katalog reguł integralności (Klasyfikacja A/B/C/D)

| ID | Reguła Domenowa | Obecny Stan SQL | Rekomendacja | Klasyfikacja | Ryzyko Migracji | Powiązany Query Pattern / EXPLAIN |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **R-01** | `import_history.status` w zbiorze `('success', 'warning', 'failed')` | Brak `CHECK` | Dodanie `CHECK (status IN ('success', 'warning', 'failed'))` | **A (SQLite)** | Wymaga audytu | `list_for_project`: Używa `idx_import_history_project_created(project_id, created_at DESC)` |
| **R-02** | `import_history.source_type` w zbiorze `('provider', 'file')` | Brak `CHECK` | Dodanie `CHECK (source_type IN ('provider', 'file'))` | **A (SQLite)** | Wymaga audytu | N/A |
| **R-03** | Spójność `format` / `provider` w stosunku do `source_type` | Brak w SQL | Walidacja domenowa w serwisie importu | **B (Domena)** | Brak | N/A |
| **R-04** | Spójność `records_count` vs delta Working Collection | Walidowane w `ProjectImportService` | Serwis aplikacyjny + `IntegrityAuditService` | **B (Domena)** | Brak | N/A |
| **R-05** | Klucze Obce `FOREIGN KEY` dla `project_id` | Brak FK i brak `PRAGMA foreign_keys` | Utworzenie tabeli `projects` + DDL FK + `PRAGMA foreign_keys = ON;` | **C (Obrona wielowarstwowa)** | Wymaga przebudowy tabel SQLite | Wszystkie zapytania po `project_id` |
| **R-06** | `normalization_executions.status` w zbiorze `('completed', 'warning', 'error')` | Brak `CHECK` | Dodanie `CHECK (status IN ('completed', 'warning', 'error'))` | **A (SQLite)** | Wymaga audytu | N/A |
| **R-07** | Powiązanie decyzji recenzenta `duplicate_review_decisions.group_id` z grupą deduplikacji | Audytowane w `IntegrityAuditService` | Zachowanie pełnej walidacji w domenie | **B (Domena)** | Brak | Grupy duplikatów są wyliczane w pamięci |
| **R-08** | Unikalność wersji strategii `(project_id, version)` jako UNIQUE | Brak unikalności wersji w DDL | Walidacja w domenie | **D (Nie rekomendować)** | Wysokie | Zmieniałoby strukturę `search_strategies` |

---

## 7. Analiza istniejących danych i ocena ryzyka migracji

### 7.1. Wyniki zapytań diagnostycznych na `data/slr-platform.db` (read-only):
1. **Relacje `project_id` pomiędzy tabelami**:
   - Brak niespójności identyfikatorów `project_id` pomiędzy `import_history`, `duplicate_review_decisions`, `normalization_executions` a `project_publications`.
   - **Brak możliwości potwierdzenia istnienia projektu**: Ponieważ tabela nadrzędna `projects` nie istnieje w bazie, istnienie samego projektu jest niemożliwe do zweryfikowania na poziomie ograniczeń SQL (jest egzekwowane jako stała w kodzie aplikacji).
2. **Unikalność `record_id` publikacji**:
   - 0 duplikatów `(project_id, record_id)` wewnątrz tych samych projektów.
3. **Spójność statusów i wartości słownikowych**:
   - W analizowanej lokalnej bazie nie wykryto naruszeń reguł słownikowych, które dało się sprawdzić w trybie read-only.

### 7.2. Realistyczna ocena ryzyka migracyjnego:
- W analizowanej lokalnej bazie nie wykryto naruszeń sprawdzalnych reguł, jednak baza przykładowa nie jest w 100% reprezentatywna dla wszystkich środowisk uruchomieniowych.
- Część reguł (np. osierocenie względem głównej tabeli projektów) nie była możliwa do weryfikacji ze względu na brak tabeli `projects`.
- Wprowadzanie nowych klauzul `CHECK` lub `FOREIGN KEY` w SQLite wymaga przebudowy tabel (skryptów typu `CREATE TABLE new ... INSERT INTO new SELECT ... DROP ... RENAME`).
- **Ostateczna ocena ryzyka**: Wdrożenie migracji wymaga pełnego audytu diagnostycznego każdej docelowej bazy przed uruchomieniem skryptów DDL.

---

## 8. Rekomendowana kolejność późniejszych migracji

W przyszłych zadaniach (Zadanie 4/5) rekomenduje się wdrażanie zmian w następującej kolejności:

### Priorytet HIGH:
1. Utworzenie nadrzędnej tabeli `projects` oraz dodanie klauzul `FOREIGN KEY (project_id) REFERENCES projects(id)` w tabelach podrzędnych.
2. Włączenie `PRAGMA foreign_keys = ON;` przy każdym otwarciu połączenia SQLite w repozytoriach (wymagane łącznie z migracją DDL kluczy obcych).

### Priorytet MEDIUM:
3. Dodanie klauzul `CHECK (status IN (...))` oraz `CHECK (source_type IN (...))` w `import_history` oraz `normalization_executions`.

### Priorytet LOW:
4. Optymalizacja indeksów unikalnych lub częściowych pod kątem nowych warunków biznesowych.

---

## 9. Reguły, których NIE należy przenosić do bazy SQLite

1. **Poprawność wyliczenia delty `records_count`**:
   - Wymaga porównania stanu kolekcji sprzed i po imporcie, co powinno pozostać w serwisie aplikacyjnym `ProjectImportService`.
2. **Deduplikacja i powiązania grup duplikatów (`group_id`)**:
   - Grupy duplikatów budowane są dynamicznie przez algorytmy deduplikacji w pamięci, a trwale zapisuje się wyłącznie decyzje recenzenta. Walidacja osierocenia decyzji recenzenta musi pozostać w `IntegrityAuditService`.
3. **Zgodność spójności provenance i struktur json publikacji**:
   - Walidacja poprawności domenowej obiektów `Publication` i `ProvenanceEntry` powierzona jest modelom Pydantic w warstwie aplikacji.

---

## 10. Otwarte pytania dla Zadania 5 — Repository Contracts

1. **Standard obsługi transakcji i połączenia**: Czy kontrakt repozytorium powinien jawnie przyjmować opcjonalny parametr `connection: sqlite3.Connection | None = None` w oficjalnej specyfikacji Protocol?
2. **Standard zgłaszania wyjątków bazy danych**: Czy repozytoria powinny mapować powszechne wyjątki SQLite (`sqlite3.IntegrityError`, `sqlite3.OperationalError`) na jednolite wyjątki domenowe (np. `DuplicateRecordError`, `RepositoryTransactionError`)?

---

## 11. Jednoznaczne potwierdzenie

- **Brak zmian schematu**: Żadna tabela ani indeks w bazie nie zostały zmodyfikowane.
- **Brak migracji**: Nie utworzono ani nie wykonano nowych plików migracyjnych SQL.
- **Brak zmian danych**: Żaden rekord w bazie danych nie został dodany, zmieniony ani usunięty.
