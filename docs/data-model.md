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

### ScreeningDecision

- etap: title/abstract albo full text;
- decyzja: include, exclude, uncertain;
- powód;
- decyzja człowieka;
- rekomendacja AI;
- pewność AI;
- znacznik czasu.

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
