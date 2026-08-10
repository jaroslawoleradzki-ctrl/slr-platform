# Model danych SLR Platform

## 1. Warstwy danych

### RawRecord

Niezmieniona odpowiedź źródła bibliograficznego.

Minimalne pola:
- `source`
- `source_record_id`
- `retrieved_at`
- `query_id`
- `raw_file`
- `payload_hash`

### CanonicalPublication

Ujednolicony rekord publikacji.

Pola podstawowe:
- `record_id`
- `schema_version`
- `title`
- `abstract`
- `authors`
- `publication_year`
- `publication_date`
- `doi`
- `issn`
- `isbn`
- `venue`
- `publisher`
- `document_type`
- `language`
- `keywords`
- `urls`

### ProvenanceEntry

Informacja o pochodzeniu konkretnego pola lub rekordu:
- źródło;
- identyfikator źródłowy;
- data pobrania;
- identyfikator zapytania;
- identyfikator uruchomienia wyszukiwania;
- migawka wykonanego zapytania;
- ścieżka do surowych danych;
- zastosowana transformacja.

### DeduplicationDecision

- identyfikatory porównywanych rekordów;
- metoda dopasowania;
- wynik;
- podobieństwo;
- uzasadnienie;
- decyzja automatyczna lub ręczna;
- osoba lub agent podejmujący decyzję;
- znacznik czasu.

### ScreeningCriterion

Kryterium włączenia lub wyłączenia zdefiniowane dla konkretnego projektu (project-scoped).

Pola modelu domenowego i schematu tabeli SQLite (`screening_criteria` w `migrations/0007_screening_criteria.sql`):
- `criterion_id`: `UUID` / `TEXT PRIMARY KEY` (stabilna tożsamość wygenerowana przez backend)
- `project_id`: `str` / `TEXT NOT NULL` (izolacja w ramach projektu, niewymienny po utworzeniu)
- `name`: `str` / `TEXT NOT NULL` (nazwa kryterium)
- `description`: `str | None` / `TEXT` (opcjonalny opis/instrukcja)
- `criterion_type` (`ScreeningCriterionType`): `INCLUSION` / `EXCLUSION` (przechowywane jako ciąg tekstowy `'inclusion'` / `'exclusion'`)
- `screening_stage` (`ScreeningCriterionStage`): `TITLE_ABSTRACT` / `FULL_TEXT` / `BOTH` (przechowywane jako ciąg tekstowy `'title_abstract'` / `'full_text'` / `'both'`)
- `display_order`: `int` (ge=0) / `INTEGER NOT NULL DEFAULT 0` (kolejność wyświetlania)
- `is_active`: `bool` / `INTEGER NOT NULL DEFAULT 1` (wartości `1` dla True, `0` dla False)
- `is_required`: `bool` / `INTEGER NOT NULL DEFAULT 1` (wartości `1` dla True, `0` dla False)

Indeks bazodanowy:
- `idx_screening_criteria_project` na `(project_id, display_order, criterion_id)` zapewniający optymalną izolację projektową oraz deterministyczne sortowanie `ORDER BY display_order ASC, criterion_id ASC`.

Uwaga: Dostępność pełnego tekstu (full-text availability/status) jest informacją techniczną o publikacji w workflow (np. URL, link DOI), a NIE wbudowanym kryterium kwalifikacji. To konfigurowalne ScreeningCriterion danego projektu określa, czy brak pełnego tekstu prowadzi do wykluczenia.

### ScreeningDecision

Decyzja screeningu podjęta dla konkretnej publikacji na danym etapie.

Pola:
- `decision_id`
- `project_id`
- `publication_id` (`record_id`)
- `stage`: `TITLE_ABSTRACT` / `FULL_TEXT`
- `outcome`: `INCLUDE` / `EXCLUDE` / `UNCERTAIN`
- `criterion_assessments`: oceny według poszczególnych kryteriów
- `rationale`: uzasadnienie decyzji
- `reviewer_id`: identyfikator osoby podejmującej decyzję
- `criteria_version`: referencja do wersji/migawki użytych kryteriów
- `created_at`: znacznik czasu

### SearchRun

- identyfikator uruchomienia;
- projekt;
- źródło;
- zapytanie;
- zakres dat;
- liczba pobranych rekordów;
- liczba błędów;
- rozpoczęcie i zakończenie;
- wersja konfiguracji lub commit Git.

## 2. Zasady

1. Dane surowe są niezmienne.
2. Normalizacja tworzy nową reprezentację.
3. Każda transformacja jest logowana.
4. Rekord kanoniczny może mieć wiele źródeł.
5. Decyzje człowieka i AI są przechowywane oddzielnie.
6. Usunięcie duplikatu nie usuwa danych źródłowych.
