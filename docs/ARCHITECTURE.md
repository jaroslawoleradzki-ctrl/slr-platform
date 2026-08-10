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

### Screening Subsystem (`app.domain.screening`)

W Phase 7.1 zaimplementowano czysty model domenowy konfigurowalnych kryteriów screeningu:

- `ScreeningCriterion`: Niemutowalny obiekt domenowy reprezentujący jednostkowe kryterium kwalifikacji lub wykluczenia publikacji w ramach projektu (`criterion_id: UUID`, `project_id: str`, `name`, `description`, `criterion_type`, `screening_stage`, `display_order`, `is_active`, `is_required`).
- `ScreeningCriterionType`: Enum `INCLUSION` / `EXCLUSION`.
- `ScreeningCriterionStage`: Enum określający zakres stosowania kryterium: `TITLE_ABSTRACT`, `FULL_TEXT` lub `BOTH`.
- **Decyzja architektoniczna dot. etapu**: Istniejący enum `ScreeningStage` (`TITLE_ABSTRACT`, `FULL_TEXT`) pozostaje przeznaczony wyłącznie dla konkretnych zdarzeń decyzji screeningowych (`ScreeningDecision`), które nie mogą zachodzić na etapie `BOTH`. Dla zakresu stosowania kryteriów wprowadzono osobny `ScreeningCriterionStage`.
- **Granice przyrostu 7.1**: Model jest czysto domenowy — nie definiuje persystencji SQLite, endpointów REST API, komponentów GUI, scoringu ani automatycznego wyliczania decyzji.
