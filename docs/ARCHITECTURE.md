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
