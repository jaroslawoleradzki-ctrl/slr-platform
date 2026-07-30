# Normalization audit — 0.2.0

## Stan przed integracją

Backend posiadał już provider-independent normalizers dla tytułu, DOI,
autorów i ORCID (`app/normalization/*`) oraz `PublicationNormalizer`. Były one
używane podczas części mapowania/search, ale nie istniał project-scoped endpoint
uruchamiający normalizację istniejącej kolekcji ani model execution. Frontend
czytał `MOCK_PROJECTS.normalization`, w tym statyczne wartości 2105/2042/63.

| Element GUI | Frontend source | Endpoint | Backend service | Storage | Stan |
|---|---|---|---|---|---|
| status | `NormalizationPage.tsx` | `GET/POST /projects/{id}/normalization` | `normalization_service.py` | SQLite latest run | live po uruchomieniu |
| processed/clean/warnings | `NormalizationPage.tsx` | j.w. | `normalize_project` | SQLite latest run | live |
| DOI, autorzy, ORCID, title | typy/normalizers | j.w. | `PublicationNormalizer` | publikacje repozytorium | live |
| audit trail/rules | `NormalizationPage.tsx` | j.w. | wynik wykonania | SQLite JSON | live |
| project scope | `ProjectContext.tsx` | ścieżka z project id | repozytorium publikacji | per project | live |
| ISSN validation | ekran/tekst pomocniczy | brak | brak globalnej reguły | — | niezaimplementowane |
| execution persistence | `ProjectContext.tsx` | GET | `SqliteNormalizationExecutionRepository` | SQLite latest run | live |

## Zrealizowane podłączenie

Dodano minimalne endpointy:

- `POST /projects/{project_id}/normalization` — normalizuje kolekcję projektu i
  zwraca summary oraz audit trail;
- `GET /projects/{project_id}/normalization` — zwraca ostatni wynik procesu.

Normalizacja korzysta wyłącznie z istniejącego `PublicationNormalizer` i
zapisuje znormalizowane obiekty przez `replace_publications` istniejącego
repozytorium. Audit zawiera rzeczywiste liczniki zmian dla DOI, autorów, ORCID
i title canonicalization. Nie dodano nowego algorytmu ISSN ani deduplikacji.

Frontend pobiera wynik dla aktywnego projektu, resetuje mockową normalizację,
obsługuje stan nieuruchomiony, pusty projekt, sukces, błąd i ponowne uruchomienie.

## Trwałość i ograniczenia

Publikacje są przechowywane w `SqliteProjectPublicationRepository`, natomiast
wynik ostatniego runu jest przechowywany trwale w SQLite przez
`SqliteNormalizationExecutionRepository`. Refresh i restart backendu zachowują
summary oraz audit trail. Przechowywany jest wyłącznie ostatni run projektu;
ponowne wykonanie zastępuje poprzedni rekord.

Crossref, Semantic Scholar, pełny audit/provenance, walidacja ISSN, background
jobs, deduplikacja i screening pozostają poza zakresem.

## Najmniejszy następny przyrost

Przyszłe przyrosty mogą dodać pełną historię wykonań, bez zmiany algorytmów
normalizacji.
