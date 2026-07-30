# Diagnosis: OpenAlex UI count versus SLR Platform result count

Data diagnozy: 2026-07-30. Branch: `development`. Projekt: `lean_energy`.

## 1. Observed behavior

Test diagnostyczny odtworzył zgłoszone zachowanie:

- `POST /projects/lean_energy/search-strategy/executions` zwrócił HTTP 200,
  `result_count: 8` i tablicę `results` długości 8;
- bezpośredni pierwszy request do OpenAlex zwrócił HTTP 200,
  `meta.count: 42847`, 25 elementów `results` oraz niepusty
  `next_cursor`;
- aplikacja pobrała cztery strony po 25 rekordów (100 rekordów), poprawnie
  zmapowała wszystkie 100, a następnie odrzuciła 92 rekordy, ponieważ ich
  rok był wcześniejszy niż 2020.

Liczba 8 nie pochodzi z UI, DTO, danych testowych ani `slice`. Jest skutkiem
nałożenia zakresu lat **po pobraniu tylko pierwszych 100 wyników
uszeregowanych według trafności**.

## 2. Exact application query

### Zapisana strategia

Istotna część dokumentu zapisanego w `data/slr-platform.db`:

```json
{
  "project_id": "lean_energy",
  "name": "Lean Energy Strategy",
  "concept_groups": [
    {
      "group_id": "cg-1",
      "name": "Lean",
      "terms": ["lean manufacturing"],
      "operator": "or"
    }
  ],
  "group_operator": "and",
  "constraints": {
    "publication_year_from": 2020,
    "publication_year_to": 2026,
    "languages": ["en", "pl"],
    "publication_types": ["article"],
    "additional_limits": {}
  },
  "providers": ["openalex"]
}
```

Open Access jest wyłączony (`additional_limits` nie zawiera
`open_access: true`). `SearchStrategyPage` przenosi wszystkie powyższe
ograniczenia do `EditableSearchStrategy`, ale warstwa transportowa usuwa
języki, typy i Open Access.

### Pełny payload wykonania wysłany przez frontend

```json
{
  "publication_year_from": 2020,
  "publication_year_to": 2026,
  "providers": ["openalex"],
  "concept_groups": [
    {
      "id": "cg-1",
      "name": "Lean",
      "terms": ["lean manufacturing"]
    }
  ]
}
```

Nie ma w nim `languages`, `publication_types`, `open_access`,
`group_operator` ani operatorów poszczególnych grup. DTO backendu również
nie dopuszcza tych pól.

`build_search_query()` oznacza każdy termin jako `exact_phrase=True`.
Autorytatywny wynik renderowania:

```text
"lean manufacturing"
```

Przepływ kodu:

1. `SearchStrategyPage` zapisuje strategię, buduje `EditableSearchStrategy`
   i wywołuje Context.
2. `ProjectContext.executeSearchStrategy()` klonuje strategię, zeruje
   poprzedni wynik i przekazuje ją bez modyfikacji do serwisu API.
3. `projectApiService` serializuje tylko lata, providerów i grupy pojęć.
4. endpoint waliduje okrojony kontrakt i buduje generyczny Boolean query.
5. `SearchEngine` zapisuje ten sam `rendered_query` w `SearchRun`.
6. `OpenAlexProvider` przekazuje tekst bez translacji do `OpenAlexClient`.

Referencje: `frontend/src/pages/SearchStrategyPage.tsx:208`,
`frontend/src/context/ProjectContext.tsx:91`,
`frontend/src/services/api/projectApi.ts:120`,
`app/api/dto/search_strategy.py:39`, `app/services/live_search.py:47`.

## 3. Exact OpenAlex request

Pierwszy request:

```http
GET https://api.openalex.org/works
  ?search=%22lean%20manufacturing%22
  &per-page=25
  &cursor=%2A
```

Parametry logiczne:

| Parametr | Wartość |
|---|---|
| `search` | `"lean manufacturing"` (cudzysłowy są częścią wartości) |
| `filter` | brak |
| `per-page` | `25` |
| `cursor` | `*`, następnie cursory z `meta.next_cursor` |
| `sort` | brak; OpenAlex stosuje domyślne sortowanie trafności dla search |

Nie jest wysyłany `mailto`, klucz API ani sekret. Nie jest wysyłany żaden
filtr lat, języka, typu publikacji lub OA.

Kod klienta tworzy dokładnie `search`, `per-page` i `cursor`
(`app/providers/openalex.py:101`). Provider uruchomiony przez live search ma
`paginate=True`, domyślne `per_page=25` i `max_results=100`
(`app/services/live_search.py:104`,
`app/providers/search/openalex.py:238`).

OpenAlex zwrócił w `meta.x_query` interpretację:

```text
works where full text has (stemmed "lean manufacturing")
```

oraz równoważny filtr wewnętrzny:

```text
fulltext.search:"lean manufacturing"
```

Zatem aplikacyjne `exact_phrase=True` oznacza frazę, ale nie wyszukiwanie
niestemowane i nie ograniczenie do tytułu/abstraktu.

## 4. Raw OpenAlex metadata

Metadane czterech stron używanych przez aplikację:

| Strona | HTTP | `meta.count` | `results.length` | `next_cursor` |
|---:|---:|---:|---:|---|
| 1 | 200 | 42847 | 25 | `IlsyOTku...NTA2J10i` |
| 2 | 200 | 42847 | 25 | `IlsyNDIu...OTQ0NyddIg==` |
| 3 | 200 | 42847 | 25 | `IlsyMDYu...OTI3NDAnXSI=` |
| 4 | 200 | 42847 | 25 | `IlsxODIu...MzNTkwNSddIg==` |

Cursor po setnym rekordzie nadal jest niepusty. Provider kończy mimo to,
ponieważ osiągnął `max_results=100`, a nie dlatego, że OpenAlex nie ma
dalszych wyników.

Pierwszy rekord surowej puli:

```json
{
  "id": "https://openalex.org/W1984103729",
  "title": "Lean manufacturing: context, practice bundles, and performance",
  "publication_year": 2002
}
```

Ostatni (setny) rekord surowej puli:

```json
{
  "id": "https://openalex.org/W2008935905",
  "title": "Development of a framework for implementation of lean manufacturing systems",
  "publication_year": 2009
}
```

## 5. Application limits

Przeszukanie repozytorium pod kątem `limit`, `per_page`, `per-page`,
`page_size`, `max_results`, `slice`, `[:8]`, `take`, `pagination` i
`cursor` wykazało:

- OpenAlexClient: domyślne `per_page=25`, dozwolone 1–200;
- OpenAlexProvider: domyślne `max_results=100`;
- live search: jawnie `paginate=True`, ale nie nadpisuje `max_results`;
- po osiągnięciu 100 provider nie pobiera dalszych stron, nawet jeżeli
  `next_cursor` istnieje;
- endpoint filtruje lata dopiero po zakończeniu pobierania i mapowania;
- `SearchStrategyExecutionResponse.result_count` to `len(results)`, a nie
  OpenAlex `meta.count`;
- brak `[:8]`, `slice(0, 8)`, `take(8)`, page size 8 lub testowego źródła 8
  rekordów w badanym przepływie.

Liczba 8 pochodzi z backendowego filtra lat zastosowanego do ograniczonej
puli 100 rekordów. Provider narzuca limit 100; frontend nie narzuca limitu 8.

## 6. Mapping losses

Bilans:

| Etap | Liczba |
|---|---:|
| OpenAlex `meta.count` (cały zbiór zapytania bez filtrów API) | 42847 |
| Surowe rekordy pobrane przez aplikację | 100 |
| Poprawnie zmapowane i znormalizowane | 100 |
| Odrzucone przez mapowanie | 0 |
| Odrzucone przez filtr lat endpointu | 92 |
| Zwrócone w DTO | 8 |

Mapowanie jest wykonywane atomowo dla strony/provider run: niepoprawny
obiekt lub brak tytułu rzuciłby wyjątek i provider pojawiłby się w
`provider_errors`. W teście `provider_errors` było puste, a wszystkie 100
rekordów zostało zmapowanych.

Każdy z 92 odrzuconych rekordów miał tę samą przyczynę:
`publication_year < 2020`. Nie było brakującego/niepoprawnego roku ani roku
po 2026. Pozycje odrzucone w puli 1–100:

```text
1–19, 21–37, 39–45, 47–68, 70–74, 76–78, 80–87, 89–95, 97–100
```

Pozycje zachowane to 20, 38, 46, 69, 75, 79, 88 i 96. Ich lata to
odpowiednio 2020, 2021, 2021, 2022, 2020, 2022, 2023 i 2020. Jest to
jednoznaczne wyjaśnienie przyczyny dla każdego pobranego rekordu: wszystkie
pozycje z pierwszej listy zostały odrzucone wyłącznie jako
`year_before_2020`; wszystkie z drugiej przeszły.

Filtr znajduje się w `app/api/routers/search_strategy.py:182`. Nie filtruje
języka, typu ani OA.

## 7. Frontend display limits

`SearchResultsSection`:

- pokazuje `result.result_count` w podtytule;
- renderuje `result.results.map(...)` bez stronicowania, `slice` lub limitu;
- „Zaznacz wszystkie widoczne” operuje na całej tablicy DTO.

Frontend wyświetla więc wszystkie osiem rekordów otrzymanych z backendu.
Nie redukuje większej tablicy do ośmiu
(`frontend/src/components/search/SearchResultsSection.tsx:47`,
`:56`, `:120`).

## 8. Comparison with OpenAlex UI and root cause

Nie dostarczono URL-a OpenAlex UI, eksportu filtrów ani HAR, dlatego nie da
się odtworzyć historycznego licznika około 3560 jako dokładnego requestu.
Można natomiast dowieść, że request aplikacji nie ma dziś takiego totalu:

| Wariant sprawdzony 2026-07-30 | `meta.count` |
|---|---:|
| aplikacja: full-text phrase, bez filtrów API | 42847 |
| ten sam full-text + lata 2020–2026 | 25456 |
| full-text + lata + typ `article` | 16128 |
| full-text + lata + `article` + język `en\|pl` | 11000 |
| `title.search` phrase, bez lat | 7214 |
| `title.search` phrase + lata 2020–2026 | 3162 |

Ostatni wariant ma skalę zbliżoną do zgłoszonych ~3560 i pokazuje, że wybór
pola wyszukiwania jest materialny. Nie jest jednak dowodem, że dokładnie
tego wariantu użyto w UI. Liczniki OpenAlex również zmieniają się w czasie.

Różnice pewne:

- aplikacja wysyła cudzysłowy i OpenAlex traktuje tekst jako stemmowaną
  frazę full-text;
- generyczne `AND`/`OR` są serializowane do tekstu `search`, bez
  providerowej translacji do strukturalnych filtrów OpenAlex;
- aplikacja nie wysyła filtrów lat do OpenAlex;
- aplikacja nie wysyła zapisanych typów publikacji ani języków;
- OA jest w tej strategii wyłączony, ale nawet gdyby był włączony w UI,
  obecny execution payload i DTO by go zgubiły;
- nie znamy pola i filtrów historycznego requestu UI, więc zapytań nie
  wolno nazywać równoważnymi.

Główna przyczyna wyniku 8 jest algorytmiczna: **filter-after-limit**.
Aplikacja pobiera top 100 z 42847 wyników bez filtrów, a dopiero potem
zostawia lata 2020–2026. Nie uzyskuje pierwszych 100 wyników spełniających
zakres lat i nie zachowuje `meta.count`.

Drugą, niezależną wadą kontraktu jest utrata języków, typów i OA pomiędzy
`SearchStrategyPage` a POST-em. Trzecią jest brak jawnej semantyki pola
OpenAlex (full text versus title/abstract).

## 9. Recommended fix

Na tym etapie niczego nie zmieniono. Zalecana kolejność późniejszej naprawy:

1. przenieść wszystkie obsługiwane ograniczenia do requestu OpenAlex
   (`filter`), w szczególności lata, przed paginacją i limitem;
2. rozdzielić `total_count` providera od liczby pobranej/zwróconej;
3. nazwać pole wyszukiwania i jawnie tłumaczyć AST Boolean na semantykę
   OpenAlex zamiast zakładać równoważność generycznego tekstu;
4. uczynić limit pobierania jawnym parametrem/konfiguracją i zwracać
   informację o obcięciu oraz cursor;
5. przechowywać audytowalny provider request i metadane odpowiedzi;
6. dodać test regresyjny, w którym pierwsze 100 nie spełnia filtra, ale
   dalsze rekordy go spełniają.

Nie jest rekomendowane naprawianie tej rozbieżności samą zmianą tekstu w UI:
obecne DTO nie posiada danych potrzebnych do uczciwego pokazania totalu i
stanu obcięcia.

## 10. Recommended data contract

Przykładowy kontrakt odpowiedzi:

```json
{
  "project_id": "lean_energy",
  "rendered_query": "\"lean manufacturing\"",
  "effective_constraints": {
    "publication_year_from": 2020,
    "publication_year_to": 2026,
    "languages": ["en", "pl"],
    "publication_types": ["article"],
    "open_access": false
  },
  "provider_runs": [
    {
      "provider": "openalex",
      "request": {
        "search": "\"lean manufacturing\"",
        "filter": "from_publication_date:2020-01-01,to_publication_date:2026-12-31,type:article,language:en|pl",
        "sort": "relevance_score:desc",
        "per_page": 25,
        "initial_cursor": "*"
      },
      "provider_total_count": 11000,
      "raw_retrieved_count": 100,
      "mapped_count": 100,
      "mapping_rejected_count": 0,
      "application_filtered_count": 0,
      "returned_count": 100,
      "next_cursor": "...",
      "truncated": true
    }
  ],
  "returned_count": 100,
  "results": []
}
```

Wartości w przykładzie ilustrują rozdzielenie pojęć; rzeczywisty
`provider_total_count` musi pochodzić z konkretnego wykonanego requestu.
Request execution powinien przyjmować te same `constraints`, które są
zapisywane w strategii, albo identyfikator/wersję zapisanej strategii,
zamiast utrzymywać drugi, węższy model.

## Jednoznaczne odpowiedzi

- **Czy 3560 i 8 oznaczają `total_count` vs `returned_count`?** Są to
  semantycznie licznik całego zbioru UI i liczba zwrócona przez aplikację,
  ale **nie dla dowiedzionego równoważnego requestu**. Dla dokładnego
  requestu aplikacji total OpenAlex wynosił 42847, nie 3560. Osiem jest
  `returned_count` po ograniczeniu do pierwszych 100 i filtrze lat.
- **Czy zapytania są równoważne?** Nie ma podstaw, by tak twierdzić.
  Request aplikacji jest full-text, nie zawiera filtrów API i gubi języki
  oraz typy. Dokładny request UI nie został dostarczony.
- **Czy rekordy są odrzucane?** Tak: 92 ze 100 pobranych, wszystkie wyłącznie
  dlatego, że miały rok przed 2020. Straty samego mapowania: 0.
- **Czy frontend ogranicza prezentację?** Nie. Renderuje wszystkie rekordy
  obecne w `result.results`; backend przekazał ich osiem.

## Resolution

Data wdrożenia i testu ręcznego: 2026-07-30.

Przyczyna `filter-after-limit` została usunięta. Execution payload przenosi
teraz istniejące ograniczenia `languages`, `publication_types` i
`open_access`, a `OpenAlexClient` buduje parametr `filter` przed pierwszym
requestem i przed paginacją. Zakres lat nie jest już stosowany dopiero do
pierwszych 100 nieprzefiltrowanych rekordów.

Jawne mapowanie typów formularza na słownik `GET /types` OpenAlex:

| Typ domenowy | Typ OpenAlex |
|---|---|
| `article` | `article` |
| `review` | `review` |
| `conference_paper` | `conference-paper` |
| `book_chapter` | `book-chapter` |

Nieznany typ jest odrzucany zamiast cichego pominięcia. Włączenie istniejącego
ograniczenia Open Access dodaje `is_oa:true`.

Odpowiedź execution rozróżnia teraz:

- `total_count`: `meta.count` przefiltrowanego requestu OpenAlex;
- `returned_count`: długość listy zwróconej do frontendu;
- `next_cursor`: cursor po ostatniej pobranej stronie;
- `has_more`: informację, czy provider udostępnił kolejną stronę.

Stare, mylące `result_count` zostało usunięte. Limit 100 pozostaje limitem
bieżącej porcji wyników, ale jest nakładany na zbiór już przefiltrowany po
stronie OpenAlex.

### Manual verification

Strategia:

```json
{
  "publication_year_from": 2020,
  "publication_year_to": 2026,
  "languages": ["en", "pl"],
  "publication_types": ["article"],
  "open_access": false,
  "providers": ["openalex"],
  "concept_groups": [
    {
      "id": "cg-1",
      "name": "Lean",
      "terms": ["lean manufacturing"]
    }
  ]
}
```

Dokładny pierwszy request OpenAlex:

```http
GET https://api.openalex.org/works
  ?search=%22lean%20manufacturing%22
  &filter=from_publication_date%3A2020-01-01%2Cto_publication_date%3A2026-12-31%2Clanguage%3Aen%7Cpl%2Ctype%3Aarticle
  &per-page=25
  &cursor=%2A
```

Logiczna wartość filtra:

```text
from_publication_date:2020-01-01,to_publication_date:2026-12-31,language:en|pl,type:article
```

OpenAlex potwierdził w `meta.x_query` zakres obu dat, typ `article` oraz
alternatywę języków `en or pl`.

Wynik testu endpointu aplikacji:

| Metryka | Wynik |
|---|---:|
| HTTP | 200 |
| OpenAlex `meta.count` / response `total_count` | 11000 |
| `returned_count` | 100 |
| `results.length` | 100 |
| odrzucone przez lokalną walidację | 0 |
| `has_more` | `true` |
| `next_cursor` | niepusty |
| `provider_errors` | 0 |

Wszystkie zwrócone rekordy miały rok 2020–2024, język `en` lub `pl` i typ
`article`. Po setnym rekordzie istnieje dalsza strona, więc 100 nie jest
prezentowane jako pełna liczba dopasowań. Test ręczny potwierdza rozwiązanie:
wcześniejszy bilans 100 pobranych → 92 lokalnie odrzucone → 8 zwróconych
zmienił się na 100 pobranych z przefiltrowanego zbioru → 0 odrzuconych →
100 zwróconych, przy zachowanym pełnym liczniku 11000.
