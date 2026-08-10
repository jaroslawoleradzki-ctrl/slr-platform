# Architektura SLR Platform

Aplikacja jest narzędziem technicznym wspierającym realizację i dokumentowanie
SLR. Nie stanowi odrębnej metody badawczej.

Moduły MVP:
1. Search: OpenAlex, Crossref, Google Scholar manual import (z podsystemem `QueryRenderer` tłumaczonym per provider w v0.2.6)
2. Normalize
3. Deduplicate
4. Export
5. Logging
6. Web/API

Przyszłe moduły:
- screening (Phase 7: Title & Abstract oraz Full-Text Screening na podstawie konfigurowalnych kryteriów projektu, podzielony na przyrosty 7.1–7.9),
- quality assessment (Phase 8),
- extraction (Phase 9),
- evidence synthesis (Phase 10),
- PRISMA (Phase 12).

Zadania jednoznaczne realizuje kod deterministyczny. Agenci wspierają zadania
interpretacyjne, lecz nie podejmują ostatecznych decyzji naukowych.

## Architecture & Subsystems

### Query Rendering Subsystem (`app.rendering`)

SLR Platform stosuje kanoniczny, dostawczo-niezależny model zapytania `SearchQuery` (drzewo wyrażeń Boolean `SearchTerm` oraz `SearchGroup`).

Fizyczne zapytanie wysyłane do konkretnego źródła literatury jest generowane przez dedykowane renderery implementujące protokół `QueryRenderer`:

- `OpenAlexQueryRenderer`: Przekształca `SearchQuery` na składnię `search` OpenAlex z cudzysłowami fraz `"..."`, wielkimi literami operatorów `AND`, `OR`, `NOT` oraz grupowaniem `()`.
- `CrossrefQueryRenderer`: Przekształca `SearchQuery` na ciąg słów kluczowych `query` Crossref z zachowaniem fraz `"..."`, deterministycznym spłaszczaniem operatorów oraz jawnym oznaczaniem uproszczenia semantyki (`is_lossless=False`) wraz z ostrzeżeniami audytowymi.

Obiekty `SearchRun`, provenancja publikacji (`ProvenanceEntry`) oraz surowe odpowiedzi w archiwum (`RawResponseArchiveEntry`) przechowują dokładnie ten fizyczny ciąg zapytania, który został wykonany u danego dostawcy.

W punkcie końcowym API `POST /projects/{project_id}/search-strategy/executions`:
- `SearchStrategyExecutionResponse.rendered_query`: Kanoniczny podgląd zapytania Boolean (`search_query.to_boolean_query()`), stanowiący niezależną od dostawcy reprezentację podglądową.
- `SearchStrategyExecutionResponse.provider_queries`: Lista faktycznie wykonanych zapytań fizycznych dla poszczególnych providerów odczytana z obiektów `SearchRun` (wraz z flagą `is_lossless` oraz ostrzeżeniami `warnings`).

### Screening Subsystem (`app.domain.screening`, `app.repositories`, `app.api.routers.screening`)

Wykonywalny przepływ Title & Abstract Screening jest project-scoped i
niedestrukcyjny:

```text
Project
  → Search
  → SearchResultSnapshot
  → Import
  → Working Collection
  → Normalization
  → Deduplication
  → ScreeningInputService
  → TitleAbstractScreeningService
  → ScreeningDecisionService
  → ScreeningDecisionRepository
```

`SearchResultSnapshot` jest autorytatywnym, trwałym zapisem canonical
`Publication` z konkretnego wykonania wyszukiwania. Import odczytuje snapshot po
stronie serwera, więc klient nie jest źródłem metadanych ani provenance.
`ScreeningInputService` buduje canonical/deduplicated input bez zmiany Working
Collection: APPROVE jest scalane przez istniejącą merge policy, REJECT pozostaje
osobno, a PENDING lub konflikt merge blokuje gotowość.

Podsystem kryteriów i decyzji screeningu zapewnia rejestrację oraz wykonywanie
kryteriów kwalifikacji i wykluczenia w ramach projektów SLR:

1. **Model domenowy (`app.domain.screening`)**:
   - `ScreeningCriterion`: Niemutowalny obiekt domenowy reprezentujący jednostkowe kryterium kwalifikacji lub wykluczenia publikacji w ramach projektu (`criterion_id: UUID`, `project_id: str`, `name`, `description`, `criterion_type`, `screening_stage`, `display_order`, `is_active`, `is_required`, `evaluation_mode`, `metadata_rule`).
   - `ScreeningCriterionType`: Enum `INCLUSION` / `EXCLUSION`.
   - `ScreeningCriterionStage`: Enum określający zakres stosowania kryterium: `TITLE_ABSTRACT`, `FULL_TEXT` lub `BOTH`.
   - `ScreeningCriterionEvaluationMode`: `MANUAL` albo `METADATA_RULE`.
     Reguły metadanych używają wyłącznie allow-listy pól canonical
     `Publication` i typed operatorów; nie wykonują arbitralnego kodu ani
     ścieżek JSON.
   - **Decyzja architektoniczna dot. etapu**: Istniejący enum `ScreeningStage` (`TITLE_ABSTRACT`, `FULL_TEXT`) pozostaje przeznaczony wyłącznie dla konkretnych zdarzeń decyzji screeningowych (`ScreeningDecision`), które nie mogą zachodzić na etapie `BOTH`. Dla zakresu stosowania kryteriów używany jest `ScreeningCriterionStage`.

2. **Warstwa persystencji (`app.repositories.screening_criterion_repository`)**:
   - `ScreeningCriterionRepository`: Protokół abstrakcyjny udekorowany `@runtime_checkable` określający kontrakt persystencji (`create`, `get`, `list_by_project`, `update`, `deactivate`).
   - `SqliteScreeningCriterionRepository`: Dedykowany adapter trwały przechowujący obiekty w tabeli SQLite `screening_criteria` (migracje `0007_screening_criteria.sql` i `0011_screening_metadata_rules.sql`).
   - **Zasady**: Ścisła izolacja projektowa (`WHERE project_id = ? AND criterion_id = ?`), deterministyczne sortowanie (`ORDER BY display_order ASC, criterion_id ASC`), brak fizycznego kasowania rekordu w celu zachowania spójności referencyjnej z historycznymi decyzjami.

3. **Warstwa API (`app.api.routers.screening`, `app.api.dto.screening`)**:
   - Project-scoped REST API (`/projects/{project_id}/screening/criteria`) obsługujące operacje `POST` (tworzenie), `GET` (pobieranie pojedyncze i lista), `PUT` (edycja atrybutów bez zmiany tożsamości `criterion_id` ani własności `project_id`) oraz `PATCH /deactivate` (soft-lifecycle).

4. **Podsystem Decyzji Screeningowych (`ScreeningDecision`, `ScreeningDecisionService`, `SqliteScreeningDecisionRepository`)**:
   - **Model domenowy**: `ScreeningDecision` rejestruje imutowalne zdarzenie decyzji dla publikacji, etapu (`TITLE_ABSTRACT` / `FULL_TEXT`) i reviewera. Przechowuje wybór wyniku (`INCLUDE` / `EXCLUDE` / `UNCERTAIN`), uzasadnienie (`rationale`), przypisanie reviewera (`reviewer_id`), znacznik czasu (`decided_at`) oraz autorytatywną migawkę ocen poszczególnych kryteriów (`CriterionAssessment`).
   - **Autorytatywny snapshot kryterium**: Klient API przekazuje wyłącznie
     manualne assessmenty. `ScreeningDecisionService` pobiera aktualne
     `ScreeningCriterion` i buduje imutowalny snapshot. Dla `METADATA_RULE`
     serwis uruchamia `ScreeningCriterionRuleEvaluator` na canonical
     `Publication` i zapisuje evaluation mode, rule oraz evaluated value;
     klient nie może spoofować wyniku automatic assessment.
   - **Reguły biznesowe w serwisie**: `ScreeningDecisionService` stanowi granicę (boundary) dla integralności decyzji. Weryfikuje istnienie i przynależność publikacji do projektu (`ProjectPublicationRepository`), przynależność i aktywność kryteriów (`is_active == True`), zgodność etapów, kompletność ocen dla aktywnych i wymaganych kryteriów etapu oraz odrzuca duplikaty. Serwis NIE wylicza wyniku `outcome` automatycznie z ocen kryteriów — wynik jest jawnie określany przez człowieka.
   - **Wzorzec persystencji decyzji**: `SqliteScreeningDecisionRepository` (tabela `screening_decisions` oraz `screening_criterion_assessments` z kompozytowym kluczem głównym `PRIMARY KEY (decision_id, criterion_id)` w migracji `migrations/0008_screening_decisions.sql`). Rejestracja decyzji ma charakter **append-only history** — zmiana decyzji tworzy nowy rekord z aktualnym timestampem. Najnowsza decyzja ustalana jest dla klucza `(project_id, publication_id, stage, reviewer_id)`.
   - **Zależności architektoniczne podsystemu**:
     ```text
     REST API (/projects/{project_id}/screening/decisions)
            ↓
     ScreeningDecisionService (weryfikacja integralności biznesowej)
            ↙                        ↘
     ProjectPublicationRepository   ScreeningCriterionRepository (authoritative snapshot)
            ↘                        ↙
          SqliteScreeningDecisionRepository
            ↓
          SQLite (migracje 0008 i 0011)
     ```
