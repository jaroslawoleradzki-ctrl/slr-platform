# Review: feature/v0.6.7-search-correctness

Data review: 2026-08-26
Reviewer: GPT-5.6 Sol
Tryb: read-only dla implementacji i testów; jedyną zmianą roboczą jest niniejszy raport.

## 1. Scope

- Branch: `origin/feature/v0.6.7-search-correctness`
- Base porównania wymagany w zleceniu: `origin/development`
- HEAD `origin/development`: `ad7256f857df4e75ea2606c42987df909e5ee1b6`
- HEAD `origin/feature/v0.6.7-search-correctness`: `0759b0017971ad67e67fe70283cf4b17e17c59f5`
- Merge-base: `0759b0017971ad67e67fe70283cf4b17e17c59f5`
- Parent historycznego commita feature: `a1d7534e9fbc79c79c7cf22a5db6e73037dfede1` (`v0.6.5`)
- Formalny zakres commitów brancha według polecenia `origin/development..origin/feature/...`: **pusty**.
- Historyczny commit wprowadzający zakres feature pomiędzy `v0.6.5` a tipem brancha, przejrzany w całości:
  - `0759b00 feat(search): checkpoint v0.6.7 correctness fixes`
- Finalny diff `origin/development...origin/feature/...`: **pusty** (0 plików), ponieważ tip feature jest przodkiem development.
- Historyczny diff `0759b00^..0759b00`: 42 pliki, 3385 insertions, 1266 deletions.

Pliki historycznie zmienione przez commit `0759b00`:

```text
app/api/dto/search_strategy.py
app/api/routers/search_strategy.py
app/domain/publication.py
app/domain/search.py
app/providers/openalex.py
app/providers/search/crossref.py
app/providers/search/semantic_scholar.py
app/providers/semantic_scholar.py
app/rendering/base.py
app/rendering/crossref.py
app/rendering/openalex.py
app/rendering/semantic_scholar.py
app/repositories/search_result_snapshot_repository.py
app/services/canonical_query_validator.py
app/services/fetch_all_search.py
app/services/live_search.py
app/services/metadata_enrichment.py
app/services/result_merger.py
app/services/search_engine.py
docs/SEARCH_PIPELINE.md
docs/plans/v0.6.7-search-fixes.md
docs/reviews/v0.6.7-search-review-opus.md
frontend/src/components/search/FetchAllProgressPanel.tsx
frontend/src/components/search/SearchResultsSection.tsx
frontend/src/pages/SearchStrategyPage.tsx
frontend/src/services/api/projectApi.ts
frontend/src/types/index.ts
frontend/tests/SearchResultsSection.test.tsx
migrations/0028_search_run_audits.sql
tests/unit/api/test_search_strategy_api.py
tests/unit/providers/test_crossref_provenance.py
tests/unit/providers/test_semantic_scholar_provider.py
tests/unit/rendering/test_crossref_renderer.py
tests/unit/rendering/test_openalex_renderer.py
tests/unit/rendering/test_query_rendering_integration.py
tests/unit/rendering/test_semantic_scholar_renderer.py
tests/unit/repositories/test_search_result_snapshot_repository.py
tests/unit/services/test_fetch_all_search.py
tests/unit/services/test_live_search.py
tests/unit/services/test_metadata_enrichment.py
tests/unit/services/test_result_merger.py
tests/unit/services/test_search_canonical_regression.py
```

## 2. Executive Summary

**Werdykt: FAIL**

| Severity | Liczba |
|---|---:|
| BLOCKER | 3 |
| MAJOR | 9 |
| MINOR | 3 |

Branch w historycznym tipie wprowadza wartościowe elementy: jawny canonical AST, trójwartościową walidację, recall-first dla brakujących pól, provider-specific rendering, enrichment po DOI, scalanie provenance oraz jawne liczniki. Canonical validator sam w sobie poprawnie realizuje logikę Kleene'a dla AND/OR/NOT, casefold/NFKC i ciągłe dopasowanie tokenów.

Cały pipeline nie spełnia jednak celu „search correctness”. Najpełniejszy rekord nie jest walidowany po merge, część legalnych canonical queries nie ma recall-safe candidate retrieval, a Crossref ma niesoundowny plan dla `OR` zawierającego `NOT`. Dodatkowo są błędy statusów failure, kompletności paginacji, deduplikacji bez DOI, semantyki liczników i atomowości persistence.

Istotny kontekst: późniejsze commity istniejące wyłącznie na `development`, zwłaszcza `ff0db5b` i `6a06c84`, naprawiają część problemów wykrytych w tipie feature (post-merge validation i semantykę `merged_result_count`). Nie zmienia to wyniku review wskazanego brancha: branch jest już przodkiem development, nie ma unikalnego diffu i nie może służyć jako aktualny change set do merge.

## 3. Branch History Assessment

### Rzeczywisty stan

- Lokalny checkout podczas review: `development` na `ad7256f`, zgodny z `origin/development`.
- Working tree przed review: czysty.
- Lokalny branch feature wskazywał dokładnie zdalny tip `0759b00`.
- Drugi worktree zawierał niezależny branch `feature/v0.6.7-search-audit-hardening`; nie był modyfikowany ani używany jako podstawa oceny.
- `git merge-base --is-ancestor origin/feature/... origin/development` zwraca sukces.
- `git rev-list --left-right --count origin/development...origin/feature/...` zwraca `12 0`.

### Commity należące wyłącznie do feature

Brak. Polecenie:

```text
git log origin/development..origin/feature/v0.6.7-search-correctness
```

nie zwraca żadnego commita. Historyczny zakres feature składał się z jednego commita `0759b00`, ale ten commit jest już osiągalny z `development` przez późniejszą historię.

### Commity istniejące tylko na development

```text
ad7256f Merge remote-tracking branch 'origin/main' into development
efeed7c Merge branch 'feature/v0.6.7-durable-search-resume' into development
b475dd8 fix(search): handle checkpoint strategy validation errors explicitly
695d7a5 fix(search): address review findings for durable search resume
6a06c84 fix(search): restore merged_result_count semantics to pre-canonical-validation count
ff0db5b fix(search): apply post-merge canonical validation to eliminate false positives
8eb08e3 chore(release): merge development v0.6.6 into main
02121a9 chore(release): integrate v0.6.6 UI navigation improvements
2b0c224 chore(release): prepare v0.6.6
754fa6f feat(search): add durable provider resume
65e1b7f chore: integrate UI navigation improvements for v0.6.6
21109af fix(ui): improve search and workflow navigation layout
```

### Ocena historii

- Branch **nie jest oparty na aktualnym development**; kończy się na historycznym checkpointcie opartym bezpośrednio na `v0.6.5`.
- Historia nie jest rozjechana dwustronnie (brak commitów tylko na feature), lecz jest **jednostronnie przestarzała o 12 commitów**.
- Three-dot diff względem aktualnego development jest pusty. Próba merge do development byłaby no-op / „already up to date”, a nie integracją feature.
- `git diff --check 0759b00^..0759b00` zgłasza trailing whitespace w `tests/unit/services/test_metadata_enrichment.py:49` i dodatkową pustą linię EOF w planie; nie wpływa to na klasyfikację correctness.

### Review commit-by-commit

`0759b00 feat(search): checkpoint v0.6.7 correctness fixes` został przejrzany jako jeden duży, nietrywialny commit. Łączy model domenowy, trzy klienty/providerów, renderery, orchestration, persistence, migrację, API, frontend, testy oraz dokumentację. Taka atomowość utrudnia izolację regresji. Findings poniżej odnoszą się do jego finalnego drzewa. Finalny diff całego brancha względem bieżącego development jest pusty i nie zawiera dodatkowego kodu do oceny.

## 4. Findings

### BLOCKER

#### B-1 — Finalna canonical validation nie działa na najpełniejszym rekordzie

- **Severity:** BLOCKER
- **Plik:** `app/services/search_engine.py:191-293`; `app/services/fetch_all_search.py:408-511`
- **Funkcja/zakres:** `SearchEngine.execute`; `FetchAllSearchService._run_single_provider` i `_finalize_job`
- **Problem:** pipeline wykonuje normalization/enrichment i canonical validation osobno dla rekordów providerów, odrzuca `NON_MATCH`, a dopiero potem scala pozostałe rekordy. Po `ResultMerger.merge()` nie ma finalnej walidacji. Rekord będący `INDETERMINATE` może więc pozostać wynikiem mimo że drugi rekord tego samego DOI dostarcza abstrakt dowodzący `NON_MATCH`; drugi rekord zostaje odrzucony zanim może wzbogacić pierwszy.
- **Scenariusz reprodukcji:** canonical `lean AND energy`; rekord A ma DOI X, tytuł „Lean manufacturing”, brak abstract → `INDETERMINATE`; rekord B ma ten sam DOI, ten sam tytuł i pełny abstract bez „energy” → `NON_MATCH`. Rzeczywisty eksperyment na drzewie brancha dał: `provider_validations=['indeterminate','non_match']`, `branch_final_status='indeterminate'`; merge obu rekordów przed finalną walidacją daje `full_merge_status='non_match'`.
- **Oczekiwane zachowanie:** provider filtering → normalization → merge/enrichment → final canonical validation na najpełniejszym rekordzie; finalny rekord zostaje odrzucony.
- **Aktualne zachowanie:** bogatszy rekord jest usuwany przed merge, ubogi rekord zostaje zwrócony i zapisany.
- **Konsekwencja:** false positive, niespójne snapshoty, zawyżony final/result count i błędna deklaracja „canonical validated”.
- **Uzasadnienie severity:** główny cel brancha i podstawowy kontrakt search correctness są złamane w obu ścieżkach: live i fetch-all.
- **Czy istniejący test wykrywa:** nie. Testy enrichment sprawdzają komponenty osobno; brak testu realnego orchestration validate→merge→final validate. Późniejszy commit development `ff0db5b` dodaje taki etap, co niezależnie potwierdza lukę w tym tipie.
- **Rekomendowany kierunek:** zachować recall-first kandydatów do czasu merge, scalić pełne metadane, następnie wykonać finalną trójwartościową walidację w live i fetch-all; osobno zdefiniować metryki pre- i post-final-validation.

#### B-2 — Field-scoped canonical queries nie mają recall-safe candidate retrieval

- **Severity:** BLOCKER
- **Plik:** `app/rendering/openalex.py:12-38`; `app/rendering/semantic_scholar.py:39-74`; `app/rendering/crossref.py:37-65`
- **Funkcja/zakres:** renderery providerów
- **Problem:** canonical model dopuszcza `AUTHOR`, `VENUE` i `KEYWORDS`, lecz renderery usuwają scope i wysyłają sam tekst. Semantic Scholar bulk oficjalnie dopasowuje query do title/abstract, a OpenAlex Works `search` do title/abstract/full text. Artykuł autora „Ada Lovelace”, którego nazwisko nie występuje w treści, nie wejdzie do candidate set dla `author:"Ada Lovelace"`; lokalna walidacja nie może odzyskać rekordu, którego provider nie zwrócił. Warning S2 nie naprawia recall; OpenAlex/Crossref nie klasyfikują tego ryzyka adekwatnie.
- **Scenariusz reprodukcji:** canonical `SearchTerm(field=AUTHOR, value="Ada Lovelace")`; renderer S2 wysyła `"Ada Lovelace"` do `/paper/search/bulk`. Publikacja rzeczywiście autorstwa Ada, ale bez nazwiska w title/abstract, spełnia canonical query i nie spełnia fizycznego content query.
- **Oczekiwane zachowanie:** provider-specific author/venue/keyword retrieval tworzące candidate superset albo jawne odrzucenie niewspieranego canonical AST przed uruchomieniem providera.
- **Aktualne zachowanie:** wykonanie jest oznaczone jako lossy/warning lub wręcz zwykłe, a rekordy są bezpowrotnie pomijane.
- **Konsekwencja:** false negatives i obniżenie recall — krytyczne dla SLR.
- **Uzasadnienie severity:** system deklaruje obsługę field scopes w canonical AST, ale co najmniej dwóch providerów nie może zrealizować nawet recall-safe planu.
- **Czy istniejący test wykrywa:** nie. Test S2 sprawdza wyłącznie warning/flagę; brak kontraktowego testu candidate-superset dla każdego `SearchField`.
- **Rekomendowany kierunek:** macierz wspieranych pól per provider, dedykowane filtry/endpoints/plany candidate retrieval oraz fail-fast dla AST bez gwarancji recall. Źródła semantyki: [OpenAlex Search](https://developers.openalex.org/guides/searching), [Semantic Scholar Graph API](https://api.semanticscholar.org/api-docs/graph).

#### B-3 — Crossref traci wyniki dla `OR` zawierającego `NOT`

- **Severity:** BLOCKER
- **Plik:** `app/rendering/crossref.py:41-65`
- **Funkcja/zakres:** `build_crossref_candidate_queries`
- **Problem:** plan dla `NOT` zwraca pustą listę, a `OR` scala tylko niepuste plany. Dla `(NOT excluded) OR anchor` fizyczny plan to wyłącznie `anchor`, choć canonical query dopasowuje również każdy rekord bez `excluded`.
- **Scenariusz reprodukcji:** na branchu `(NOT (excluded) OR anchor)` renderuje się do Crossref planu `['anchor']`, podczas gdy publikacja „Completely unrelated publication” z abstraktem „Other topic” ma canonical status `MATCH`.
- **Oczekiwane zachowanie:** wszystkie canonical matches znajdują się w candidate set albo query jest jawnie odrzucone jako niewykonalne dla Crossref.
- **Aktualne zachowanie:** znaczna część zbioru `NOT excluded` nigdy nie jest pobierana.
- **Konsekwencja:** nieograniczone false negatives i fałszywe wrażenie lokalnego egzekwowania pełnej logiki Boolean.
- **Uzasadnienie severity:** bezpośrednie złamanie recall-first i operatora NOT wymienionego w kontrakcie.
- **Czy istniejący test wykrywa:** nie. Testy obejmują tylko bezpieczny przypadek `positive AND NOT negative`; brak `OR(NOT ..., ...)`, zagnieżdżonego negatywnego OR i top-level NOT.
- **Rekomendowany kierunek:** analiza polarności AST. Plan pozytywnych anchorów jest sound tylko wtedy, gdy każdy match musi spełnić co najmniej jeden pobierany pozytywny anchor; pozostałe kształty należy odrzucić albo wykonać inną, udokumentowaną strategią corpus retrieval.

### MAJOR

#### M-1 — Awaria wszystkich providerów kończy fetch-all jako `completed`

- **Severity:** MAJOR
- **Plik:** `app/services/fetch_all_search.py:491-616`; `app/api/dto/search_strategy.py:148-175,222-245`
- **Funkcja/zakres:** `_finalize_job`; status DTO
- **Problem:** job otrzymuje `completed` zawsze, gdy nie anulowano go, niezależnie od liczby providerów w stanie `failed`. Live response ma stały status `validated`, nawet jeśli wszystkie runy zawiodły.
- **Scenariusz reprodukcji:** jeden wybrany provider rzuca `RuntimeError("down")` przed pierwszym rekordem. Rzeczywisty wynik: `job_status='completed'`, `provider_status='failed'`, `has_result=True`, jeden `provider_error`.
- **Oczekiwane zachowanie:** brak udanego providera → terminal `failed`; mieszany sukces → jednoznaczny `partial`/completed-with-errors.
- **Aktualne zachowanie:** top-level sukces z pustym resultem; klient musi sam interpretować provider_errors.
- **Konsekwencja:** false SUCCESS, automatyzacje i UI mogą uznać nieprzeprowadzone wyszukiwanie za zakończone.
- **Uzasadnienie severity:** błąd stanu operacyjnego i audytu, bez utraty danych istniejących.
- **Czy istniejący test wykrywa:** nie; test obejmuje jeden sukces + jeden fail i wręcz utrwala top-level `completed`. Brak all-failed.
- **Rekomendowany kierunek:** zdefiniować agregację statusów (`failed`, `partial`, `completed`) na podstawie wszystkich provider states i ujednolicić kontrakt live/fetch-all/frontend.

#### M-2 — Crossref maskuje repeated cursor jako pełne zakończenie planu

- **Severity:** MAJOR
- **Plik:** `app/providers/search/crossref.py:182-237`
- **Funkcja/zakres:** `CrossrefProvider.search_with_raw`
- **Problem:** `raw_next == physical_cursor` jest traktowane jako `query_complete`, po czym provider przechodzi do następnego candidate query. Dla ostatniego query zwraca `next_cursor=None`, więc fetch-all oznacza provider jako `complete`, chociaż nie udowodniono końca bieżącego zbioru.
- **Scenariusz reprodukcji:** Crossref zwraca niepustą stronę i ten sam cursor. Provider kończy bieżący anchor; przy pojedynczym anchorze zwraca `has_more=False`.
- **Oczekiwane zachowanie:** repeated cursor → jawny partial/progress-stalled z zachowaniem pobranych danych.
- **Aktualne zachowanie:** fałszywa kompletność i potencjalne pominięcie dalszych wyników tego anchoru.
- **Konsekwencja:** false negatives oraz błędne statusy completeness.
- **Uzasadnienie severity:** pagination może cicho utracić wyniki; nie jest to jedynie problem telemetryczny.
- **Czy istniejący test wykrywa:** test `test_search_with_raw_repeating_cursor_returns_has_more_false` utrwala błędne zachowanie zamiast oczekiwać partial.
- **Rekomendowany kierunek:** provider output powinien przenosić przyczynę zatrzymania/completeness; repeated cursor nie może być utożsamiony z końcem candidate query. Oficjalny kontrakt kursora: [Crossref REST API tips](https://www.crossref.org/documentation/retrieve-metadata/rest-api/tips-for-using-the-crossref-rest-api/).

#### M-3 — ResultMerger nie deduplikuje rekordów bez DOI

- **Severity:** MAJOR
- **Plik:** `app/services/result_merger.py:12-30,126-131`
- **Funkcja/zakres:** `ResultMerger.merge`, `_first_doi`
- **Problem:** jedynym kluczem merge jest pierwszy DOI. Wspólny PMID, OpenAlex ID, identyczny provider/source ID lub konserwatywny fallback title/year nie są używane.
- **Scenariusz reprodukcji:** ten sam artykuł z PubMed i Semantic Scholar ma wspólny PMID, brak DOI; oba rekordy pozostają osobnymi wynikami i snapshotami.
- **Oczekiwane zachowanie:** deterministyczna hierarchia bezpiecznych identyfikatorów/fallbacków, przynajmniej wspólne silne ID; niepewne podobieństwo może pozostać jako grupa do review.
- **Aktualne zachowanie:** każdy rekord bez DOI jest zawsze osobny.
- **Konsekwencja:** duplikaty w wynikach, zawyżony final count, zaniżony `deduplicated_count`, powielone importy.
- **Uzasadnienie severity:** brak DOI jest normalnym przypadkiem bibliograficznym; wpływ dotyczy wyniku użytkowego i metryk.
- **Czy istniejący test wykrywa:** testy jawnie oczekują rozdzielenia rekordów bez DOI i dla PMID/OpenAlex, więc maskują lukę względem celu branchu.
- **Rekomendowany kierunek:** zdefiniować konserwatywną, udokumentowaną hierarchię DOI → inne silne ID → bezpieczny fallback; oddzielić auto-merge od candidate duplicate groups.

#### M-4 — Merge jest zależny od kolejności i nie wybiera najpełniejszych danych

- **Severity:** MAJOR
- **Plik:** `app/services/result_merger.py:32-124`
- **Funkcja/zakres:** `_merge_two`
- **Problem:** canonical record to pierwszy rekord, a pola są uzupełniane tylko gdy pierwsza wartość jest `None`/pusta. Dwa niepuste abstracts, listy autorów lub konflikty metadata nigdy nie są oceniane pod kątem kompletności/jakości; kolejność providerów zmienia wynik.
- **Scenariusz reprodukcji:** dwa rekordy tego samego DOI: pierwszy ma krótki/truncated abstract, drugi pełny. Merge zachowuje pierwszy. Odwrócenie kolejności zmienia finalny dokument i może zmienić canonical validation.
- **Oczekiwane zachowanie:** stabilna polityka wyboru najpełniejszej wartości z deterministycznym tie-breakerem i zachowaniem provenance/conflict evidence.
- **Aktualne zachowanie:** first-wins dla wszystkich niepustych pól.
- **Konsekwencja:** utrata danych, niereprodukowalność względem kolejności providerów, ryzyko false MATCH/NON_MATCH po finalnej walidacji.
- **Uzasadnienie severity:** branch deklaruje final validation na pełnych danych, ale merger nie gwarantuje pełnego rekordu.
- **Czy istniejący test wykrywa:** tylko przypadek `None` + wartość; brak konfliktujących niepustych wartości i testu permutacji provider order.
- **Rekomendowany kierunek:** jawna merge policy per pole, deterministyczny ranking jakości, rejestr konfliktów i testy permutacyjne.

#### M-5 — Liczniki mieszają etapy pipeline, a UI nadaje im fałszywe etykiety

- **Severity:** MAJOR
- **Plik:** `app/services/search_engine.py:206-293`; `app/services/fetch_all_search.py:408-439,502-601`; `frontend/src/components/search/FetchAllProgressPanel.tsx:109-142` w drzewie commita
- **Funkcja/zakres:** liczenie provider/canonical/kept/dedup/final oraz prezentacja
- **Problem:** `fetched_count` liczy unikalne source IDs, nie surowe rekordy API; canonical counters powstają przed metadata constraints; `kept_count` jest przed cross-provider merge, choć frontend opisuje je jako „Zapisano”; `deduplicated_count` dotyczy tylko DOI w kept subset. UI wylicza „Po deduplikacji” jako `(accepted + indeterminate) - deduplicated`, mieszając zbiór przed constraints z dedupem po constraints. `total_count` sumuje provider-reported candidate totals z nakładających się baz, a nie finalne canonical results. Historyczne `total_provider_results` po branchu oznacza wyniki po canonical filter, mimo nazwy sugerującej fetched/provider results.
- **Scenariusz reprodukcji:** 10 canonical-retained, 4 przechodzą constraints, 1 z tych 4 jest duplikatem. Faktycznie zapisane finalne rekordy: 3; `kept_total=4` („Zapisano”), UI „Po deduplikacji” pokazuje 9.
- **Oczekiwane zachowanie:** każdy licznik ma jeden jawny etap i równania kontrolne; UI pokazuje rzeczywisty final count.
- **Aktualne zachowanie:** poprawne lokalnie liczby są łączone w semantycznie niepoprawne metryki.
- **Konsekwencja:** błędny audit/PRISMA-like reporting i myląca prezentacja użytkownikowi.
- **Uzasadnienie severity:** metryki są częścią reproducibility i decyzji o kompletności, nie kosmetyką.
- **Czy istniejący test wykrywa:** nie; frontend sprawdza obecność etykiet, nie wartości przy constraints+dedup. Backend nie ma invariantów przekrojowych.
- **Rekomendowany kierunek:** nazwy etapowe (`raw_retrieved`, `unique_provider_records`, `canonical_*`, `constraint_kept`, `merged`, `final`) i testy równań na jednym scenariuszu end-to-end; nie zmieniać znaczenia istniejących pól bez wersjonowania.

#### M-6 — Snapshoty i audit nie są zapisywane atomowo

- **Severity:** MAJOR
- **Plik:** `app/api/routers/search_strategy.py:242-316`; `app/services/fetch_all_search.py:513-563`; `app/repositories/search_result_snapshot_repository.py:97-181`
- **Funkcja/zakres:** zapis rezultatów i `save_audit`
- **Problem:** każdy snapshot i każdy audit otwiera własne połączenie/transaction. Brak jednej granicy transakcji dla całego search run. Błąd na drugim snapshotcie albo audit po snapshotach pozostawia częściowo zapisany run.
- **Scenariusz reprodukcji:** repository zapisuje pierwszy merged result, drugi insert powoduje `IntegrityError`/I/O error. Pierwszy commit pozostaje, response kończy się błędem; audit może nie istnieć albo nie odpowiadać snapshotom.
- **Oczekiwane zachowanie:** all-or-nothing dla finalnego run snapshot + audit albo jawny, spójny partial checkpoint z dedykowanym statusem.
- **Aktualne zachowanie:** częściowa trwałość zależna od miejsca wyjątku.
- **Konsekwencja:** niespójne snapshoty, utrudniony retry, możliwe duplicate errors przy ponowieniu.
- **Uzasadnienie severity:** materialna niespójność persistence i provenance.
- **Czy istniejący test wykrywa:** nie; repository tests sprawdzają pojedyncze inserty i deletion, brak fault injection na N-tym zapisie.
- **Rekomendowany kierunek:** wspólna transakcja przekazywana do repository albo atomowa metoda `save_run(snapshot_batch, audit_batch)`; test rollback i idempotent retry.

#### M-7 — Multi-provider live pagination zwraca `has_more=true` bez używalnego kursora

- **Severity:** MAJOR
- **Plik:** `app/api/routers/search_strategy.py:268-277,335-366`; `app/services/search_engine.py:113-147`
- **Funkcja/zakres:** `execute_search_strategy`, wspólny argument `cursor`
- **Problem:** przy więcej niż jednym udanym providerze response ustawia `next_cursor=None`, ale `has_more` jest `any(provider.has_more)`. Jeden scalar cursor jest przekazywany wszystkim providerom, mimo że cursory są provider-specific.
- **Scenariusz reprodukcji:** OpenAlex i Crossref zwracają po pierwszej stronie i różne next cursors. Response: `has_more=true`, `next_cursor=null`; nie istnieje poprawne żądanie następnej strony obu providerów.
- **Oczekiwane zachowanie:** mapa cursorów per provider lub jawne ograniczenie live pagination do jednego providera i skierowanie multi-provider do fetch-all.
- **Aktualne zachowanie:** kontrakt deklaruje dalsze dane bez sposobu ich pobrania.
- **Konsekwencja:** utrata recall w standardowym live search i ryzyko ponownego pobrania pierwszej strony.
- **Uzasadnienie severity:** bezpośrednia funkcjonalna wada pagination.
- **Czy istniejący test wykrywa:** brak scenariusza dwóch providerów z niezależnymi cursorami; testowany jest tylko pojedynczy cursor.
- **Rekomendowany kierunek:** provider-scoped continuation state oraz spójne `has_more`/cursor invariants.

#### M-8 — Enrichment maskuje wszystkie awarie i provider run nadal wygląda na sukces

- **Severity:** MAJOR
- **Plik:** `app/services/metadata_enrichment.py:96-149`; `app/providers/openalex.py:153-173`; `app/providers/semantic_scholar.py:299-326`
- **Funkcja/zakres:** DOI lookups i failover
- **Problem:** szerokie `except Exception` zamieniają timeout, 401/403, 429 po retries, malformed JSON i błąd programistyczny w zwykłe „brak enrichment”. Nie zachowuje się cause ani klasy błędu w SearchRun/audit.
- **Scenariusz reprodukcji:** oba enrichment API zwracają 401 lub timeout. Wszystkie rekordy bez abstract zostają `INDETERMINATE`, są zachowane recall-first, a główny provider run kończy się `COMPLETED` z ogólnym warningiem o missing field.
- **Oczekiwane zachowanie:** 404/not-found może być kontrolowanym miss; awarie techniczne muszą być jawnie liczone/audytowane i wpływać na partial/lossiness, bez porzucania recall.
- **Aktualne zachowanie:** outage jest nieodróżnialny od braku rekordu.
- **Konsekwencja:** gwałtowny wzrost false positives, brak reprodukowalności i fałszywy sukces operacyjny.
- **Uzasadnienie severity:** wyniki pozostają dostępne, ale ich precision i audit są materialnie błędne.
- **Czy istniejący test wykrywa:** testuje 404 failover, nie rozróżnia auth/rate-limit/timeout/malformed response ani nie sprawdza audytu błędu.
- **Rekomendowany kierunek:** typed enrichment outcomes, selektywne except, zachowanie exception cause, counters/warnings per failure class i partial enrichment status.

#### M-9 — Nowy test fetch-all wykonuje niezmockowany ruch sieciowy i blokuje suite

- **Severity:** MAJOR
- **Plik:** `tests/unit/services/test_fetch_all_search.py:677-720`; `app/services/fetch_all_search.py:320-334`
- **Funkcja/zakres:** `test_cross_provider_doi_dedup_persists_one_snapshot_with_both_provenances`
- **Problem:** test tworzy rekordy z DOI i bez abstract. Produkcyjny `_run` zawsze buduje realny `MetadataEnrichmentService`, więc test próbuje OpenAlex/Semantic Scholar zamiast być czystym unit testem. W środowisku bez sieci zawiesza się na timeout/retry; przy sieci wynik i czas zależą od zewnętrznych usług.
- **Scenariusz reprodukcji:** uruchomienie samego pliku dochodzi do tego testu po 66 zielonych przypadkach w grupie i nie kończy się; po jego deselect: `22 passed, 1 deselected in 2.82s`.
- **Oczekiwane zachowanie:** wstrzyknięty fake/no-op enricher lub jawnie zamockowane DOI endpoints.
- **Aktualne zachowanie:** test unit ma ukryte zależności sieciowe.
- **Konsekwencja:** brak wiarygodnego release gate i niemożność uzyskania pełnego wyniku backend suite offline.
- **Uzasadnienie severity:** test dodany przez branch blokuje wymaganą suite i może przechodzić/failować zależnie od internetu.
- **Czy istniejący test wykrywa:** to sam wadliwy test; suite nie ma guardu zabraniającego outbound network.
- **Rekomendowany kierunek:** dependency injection enrichtment w `FetchAllSearchService`, hermetyczny mock transport i globalny testowy network deny z szybkim błędem.

### MINOR

#### m-1 — Semantic Scholar jest oznaczany jako lossless mimo stemmingu

- **Severity:** MINOR
- **Plik:** `app/rendering/semantic_scholar.py:39-74`
- **Funkcja/zakres:** `SemanticScholarQueryRenderer.render`
- **Problem:** `is_lossless=True` gdy nie usunięto punctuation/scope, ale bulk API stemmuje wszystkie termy, podczas gdy canonical validator wymaga literalnych, znormalizowanych tokenów.
- **Scenariusz reprodukcji:** prosty term bez punctuation renderuje się identycznie i dostaje `lossless`, lecz provider może zwrócić wariant stemmingowy, który canonical lokalnie odrzuci.
- **Oczekiwane zachowanie:** physical translation oznaczona jako candidate/lossy albo precyzyjna definicja flagi jako „end-to-end po local validation”.
- **Aktualne zachowanie:** audit/UI mówi „LOSSLESS TRANSLATION”.
- **Konsekwencja:** myląca provenance; local validation ogranicza wpływ na final precision.
- **Uzasadnienie severity:** końcowa walidacja może skorygować nadmiarowy candidate set, więc brak bezpośredniej utraty recall w typowym ANY.
- **Czy istniejący test wykrywa:** test oczekuje `is_lossless=True` dla prostego termu.
- **Rekomendowany kierunek:** doprecyzować kontrakt flagi i uwzględnić stemming/provider scope.

#### m-2 — Audit Crossref zapisuje pseudo-query, nie rzeczywiste physical queries

- **Severity:** MINOR
- **Plik:** `app/rendering/crossref.py:14-33`; `app/api/routers/search_strategy.py:296-315`; `app/services/fetch_all_search.py:518-538`
- **Funkcja/zakres:** rendered query i `SearchRunAudit.physical_query`
- **Problem:** audit zapisuje np. `"A" || "B"`, ale Crossref otrzymuje dwa oddzielne requesty `query="A"` i `query="B"`. `||` nie jest fizycznym requestem Crossref; cursor/page mapping per candidate też nie jest zapisany.
- **Scenariusz reprodukcji:** plan z pięcioma anchorami daje jeden audit string, bez informacji który anchor miał które pages/errors.
- **Oczekiwane zachowanie:** lista physical requests z query, filters, cursor/page, timestamp i outcome.
- **Aktualne zachowanie:** syntetyczny skrót przedstawiany jako physical query.
- **Konsekwencja:** niepełna reprodukowalność, choć canonical query i ogólny plan pozostają znane.
- **Uzasadnienie severity:** nie zmienia bieżącego zbioru wyników, ale osłabia audit.
- **Czy istniejący test wykrywa:** test persistence oczekuje pseudo-stringa.
- **Rekomendowany kierunek:** oddzielić `plan_summary` od kolekcji rzeczywistych request descriptors.

#### m-3 — FK audytu do projektu jest deklarowany, ale repository go nie egzekwuje

- **Severity:** MINOR
- **Plik:** `migrations/0028_search_run_audits.sql:1-18`; `app/repositories/search_result_snapshot_repository.py:142-181`
- **Funkcja/zakres:** SQLite audit persistence
- **Problem:** tabela deklaruje `REFERENCES projects`, ale połączenia repository nie wykonują `PRAGMA foreign_keys=ON`. Testy zapisują audity dla nieistniejących project IDs i przechodzą.
- **Scenariusz reprodukcji:** `save_audit(project_id="missing")` zapisuje orphan row zamiast naruszenia FK.
- **Oczekiwane zachowanie:** spójna polityka FK we wszystkich połączeniach albo brak pozornego constraintu i jawna walidacja aplikacyjna.
- **Aktualne zachowanie:** constraint jest dokumentacyjny, nie wykonawczy.
- **Konsekwencja:** możliwe orphan audits przy błędzie ścieżki wywołania.
- **Uzasadnienie severity:** normalny router najpierw sprawdza projekt i deletion usuwa audity jawnie, więc typowa ścieżka ogranicza ryzyko.
- **Czy istniejący test wykrywa:** nie; fixtures nie tworzą projektów przed `save_audit`, więc utrwalają wyłączone FK.
- **Rekomendowany kierunek:** centralna fabryka połączeń z `foreign_keys=ON` i test orphan rejection/cascade.

## 5. Search Correctness Assessment

### Canonical query correctness

Sam validator jest logicznie poprawny dla trójwartościowych AND/OR/NOT:

- AND: dowolny `NON_MATCH` dominuje; inaczej `INDETERMINATE`; inaczej `MATCH`.
- OR: dowolny `MATCH` dominuje; inaczej `INDETERMINATE`; inaczej `NON_MATCH`.
- NOT odwraca MATCH/NON_MATCH i zachowuje INDETERMINATE.
- Zagnieżdżone grupy są ewaluowane rekurencyjnie.
- Tokenizacja: Unicode NFKC + `casefold()` + `\w+`; case-insensitive.
- Phrase: ciągłe tokeny w poprawnej kolejności, bez dopasowania przez granicę title/abstract.
- Missing abstract dla `ANY`: brak dopasowania w title daje `INDETERMINATE`, co chroni recall; title dowodzący term daje MATCH.
- Missing explicit field daje `INDETERMINATE`.

Luki komponentu/testów: brak macierzy truth-table dla nested NOT/OR, wszystkich `SearchField`, punctuation/diacritics oraz konfliktujących kompletnych records. Najważniejsza wada jest jednak orchestration (B-1), nie algebra validatora.

### Provider correctness

- **OpenAlex:** Boolean AND/OR/NOT i quotes są zgodne z oficjalnym `search`; provider traktuje wyniki jako candidate set, ponieważ OpenAlex przeszukuje również full text. Cursor i retry są ogólnie poprawne. Field scopes pozostają niesoundowne (B-2). Oficjalne zasady: [OpenAlex Search](https://developers.openalex.org/guides/searching).
- **Semantic Scholar:** przejście na `/paper/search/bulk`, operatory `+`, `|`, `-`, quotes, parentheses i continuation token odpowiadają oficjalnemu API; filter params są zgodne. S2 dopasowuje title/abstract i stemmuje terms, co powoduje B-2/m-1. Oficjalne zasady: [Semantic Scholar Graph API](https://api.semanticscholar.org/api-docs/graph).
- **Crossref:** bounded positive-anchor plan jest recall-safe dla pozytywnych AND/OR i `positive AND NOT negative`; nie jest sound dla negatywnej alternatywy (B-3). Composite cursor działa w zwykłych przypadkach, ale repeated cursor jest maskowany (M-2). Retry nie duplikuje pojedynczej odpowiedzi, a job-level source-id set usuwa powtórzenia między stronami.

### Merge/dedup correctness

- DOI jest normalizowany przez strip prefix + lowercase.
- Provenance obu rekordów jest zachowywane i deduplikowane deterministycznie dla stałej kolejności.
- Brak fallback identifiers (M-3).
- Merge nie jest komutatywny i nie wybiera najbogatszych niepustych danych (M-4).
- Provider ordering wpływa na canonical record, source attribution i potencjalny final match.

### Recall-first behaviour i ryzyka

- Missing fields → retain INDETERMINATE poprawnie chroni recall lokalnie.
- **False positive risk: wysoki** przez B-1 i M-8.
- **False negative risk: wysoki/krytyczny** przez B-2, B-3, M-2 i M-7.
- Finalna walidacja nie pracuje na najpełniejszym rekordzie w tipie feature.

### Metric correctness — etap po etapie

| Pole | Etap na branchu | Ocena |
|---|---|---|
| `records_retrieved` / response `retrieved_count` | liczba zmapowanych rekordów providera przed canonical filter (live); fetch używa unikalnych source IDs | nazwa nie jest spójna między ścieżkami |
| `total_provider_results` | suma rekordów po provider-level canonical reject | nazwa sugeruje wcześniejszy etap |
| `canonical_accepted` | MATCH przed metadata constraints i merge | poprawne lokalnie |
| `canonical_rejected` | NON_MATCH przed merge | nie obejmuje finalnych zmian po merge |
| `canonical_indeterminate` | INDETERMINATE przed constraints i merge | poprawne lokalnie, ale nie finalne |
| `kept_count` | accepted/indeterminate po metadata constraints, przed cross-provider merge | nie jest liczbą zapisanych rekordów |
| `merged_result_count` | `len(merged_publications)` po pre-merge canonical filter | semantyka zmieniona względem wcześniejszego pipeline; później korygowana na development |
| `deduplicated_count` | różnica retained→DOI merge / per-provider DOI duplicates | nie obejmuje source-id dedup ani non-DOI |
| `returned_count` / final | liczba merged + constrained snapshots | najbliższa final count, lecz przed brakującą final validation |
| `total_count` | suma provider candidate totals/fallback fetched | nie jest ani unique, ani canonical, ani final |

Wymagane są invarianty i jawne nazewnictwo etapów; obecne pola nie mogą być używane zamiennie.

## 6. Persistence / Provenance Assessment

Pozytywne elementy:

- snapshot wymaga provenance zgodnego z provider/source/run;
- merged record zachowuje wieloźródłowe provenance;
- audit zapisuje canonical ID/version/hash, endpoint, query, lossiness, warnings i counters;
- project deletion jawnie usuwa snapshots i audits;
- migration jest addytywna.

Problemy:

- brak atomowej granicy transaction runa (M-6);
- Crossref audit nie odtwarza rzeczywistych physical requests (m-2);
- FK nie jest egzekwowany (m-3);
- enrichment failures/cause nie trafiają do audit (M-8);
- duplicate snapshot retry nie ma batch idempotency; częściowy zapis może utrudnić ponowienie.

Snapshot schema pozostaje backward-compatible, ale nowy audit nie ma odczytowego API ani pełnego powiązania z trwałym SearchRun. `ON CONFLICT(search_run_id)` aktualizuje tylko część pól; kolizja/reuse run ID zachowałaby stare identity fields i nowe counters, choć UUID ogranicza prawdopodobieństwo.

## 7. Failure Mode Assessment

| Scenariusz | Aktualne zachowanie | Ocena |
|---|---|---|
| jeden provider success / jeden fail | wyniki sukcesu zachowane, provider error widoczny | częściowo poprawne; top-level nie ma jawnego `partial` |
| wszystkie providery fail | top-level `completed`/`validated`, pusty result | błędne (M-1) |
| timeout/retry exhaustion głównego providera | provider failed, inne kontynuują | poprawne częściowo |
| enrichment timeout/auth/malformed | cicho potraktowane jak brak enrichment | błędne (M-8) |
| malformed provider record | mapper rzuca; cały provider page/run fail | bez false success na poziomie runa, ale wszystkie-fail nadal M-1 |
| zero results z jawnym końcem | complete, zero counters | poprawne |
| repeated outer cursor | fetch-all partial | poprawne dla uniform loop |
| repeated Crossref physical cursor | ukryte jako koniec anchoru | błędne (M-2) |
| persistence error | częściowe commity, top-level error/failed | niespójne (M-6) |
| cancellation | zachowuje pobrane dane, status cancelled | zgodne z dokumentacją, ale final persistence nadal nieatomowe |
| interruption procesu | registry in-memory, brak resume w tym branchu | utrata job state; nie klasyfikowano jako finding durable-resume, zgodnie ze scope |

Review nie przypisuje branchowi findings wynikających wyłącznie z późniejszego `durable-search-resume`; odnotowuje jedynie, że obecny development zawiera późniejsze commity i dlatego historyczny branch jest nieaktualny.

## 8. Test Assessment

Testy uruchamiano na dokładnym drzewie `0759b00` wyeksportowanym przez `git archive` do `/tmp/slr-v067-review.SQNdo6`, aby nie testować późniejszych poprawek z development. Nie checkoutowano, nie merge'owano i nie modyfikowano branchy.

### Uruchomione komendy i wyniki

1. Celowane core search/canonical/enrichment/merger/repository:

```text
uv run --extra dev pytest -q \
  tests/unit/services/test_search_canonical_regression.py \
  tests/unit/services/test_metadata_enrichment.py \
  tests/unit/services/test_result_merger.py \
  tests/unit/services/test_search_engine.py \
  tests/unit/services/test_live_search.py \
  tests/unit/repositories/test_search_result_snapshot_repository.py

61 passed in 0.49s
```

2. Providerzy i renderery:

```text
uv run --extra dev pytest -q \
  tests/unit/providers/test_crossref.py \
  tests/unit/providers/test_crossref_provenance.py \
  tests/unit/providers/test_openalex.py \
  tests/unit/providers/test_openalex_mapping.py \
  tests/unit/providers/test_semantic_scholar.py \
  tests/unit/providers/test_semantic_scholar_mapping.py \
  tests/unit/providers/test_semantic_scholar_provider.py \
  tests/unit/rendering/test_crossref_renderer.py \
  tests/unit/rendering/test_openalex_renderer.py \
  tests/unit/rendering/test_semantic_scholar_renderer.py \
  tests/unit/rendering/test_query_rendering_integration.py

276 passed in 22.12s
```

3. Fetch-all bez wadliwego testu sieciowego:

```text
uv run --extra dev pytest -q tests/unit/services/test_fetch_all_search.py \
  -k 'not cross_provider_doi_dedup_persists_one_snapshot_with_both_provenances'

22 passed, 1 deselected in 2.82s
```

Uruchomienie z tym testem dochodzi do niego i nie kończy się z powodu realnych DOI enrichment requests (M-9).

4. Backend full unit suite:

```text
uv run --extra dev pytest --collect-only -q tests/unit
2071 tests collected

timeout 180s env SLR_DATABASE_PATH=/tmp/slr-v067-full-unit.db \
  uv run --extra dev pytest -q tests/unit
```

Pełna suite nie uzyskała terminalnego wyniku. Po czterech pierwszych testach zatrzymała się na pierwszej ścieżce FastAPI `TestClient`. Izolowany `test_search_strategy_api` również nie wrócił; `faulthandler_timeout=10` pokazał main thread czekający w `starlette.testclient` i portal event loop. Collection zgłaszała `StarletteDeprecationWarning`: bieżący FastAPI TestClient z `httpx` jest deprecated i sugeruje `httpx2`. Jest to ograniczenie resolved środowiska testowego, nie dowód przejścia suite. Szeroki run z pominięciem `tests/unit/api` osiągnął 87%, po czym zatrzymał się na service teście korzystającym z tego samego HTTP TestClient. Został przerwany, aby nie raportować pozornego PASS.

5. Frontend tests:

```text
npm test -- --run
Test Files 40 passed (40)
Tests 307 passed (307)
```

6. Frontend typecheck i build:

```text
npm run type-check
PASS

npm run build
PASS (warning: bundle chunk 678.99 kB > 500 kB)
```

### Wartość testów i luki

Mocne strony:

- realistyczna truth table dla głównego 3-block query;
- testy missing abstract → INDETERMINATE i recall-first;
- testy realnych mock HTTP payloads providerów, retry i token/cursor;
- testy DOI normalization, provenance merge i audit persistence;
- frontend contract/type/build przechodzą.

Krytyczne luki:

- brak realnego testu final validation po production ResultMerger (B-1);
- brak candidate-superset tests dla wszystkich AST shapes i fields (B-2/B-3);
- brak all-providers-failed (M-1);
- repeated Crossref cursor test utrwala złą kompletność (M-2);
- testy mergera jawnie utrwalają brak non-DOI fallback i nie testują permutacji (M-3/M-4);
- brak przekrojowych invariantów liczników (M-5);
- brak fault-injection transaction rollback (M-6);
- brak multi-provider continuation (M-7);
- brak rozróżnienia enrichment 404 vs outage (M-8);
- branch-added unit test wykonuje realną sieć (M-9).

Zielone podzbiory nie obalają findings: większość testów sprawdza komponenty w izolacji albo oczekuje obecnego, błędnego kontraktu.

## 9. Regression Risk

**Ocena: wysoka.**

Najwyższe ryzyka:

1. False negatives dla field scopes, negatywnych alternatyw i pagination stalls.
2. False positives przez brak post-merge validation i ciche enrichment failure.
3. Mylące metryki oraz top-level success po całkowitej awarii.
4. Niespójne trwałe dane po błędzie w środku batcha.
5. Brak pełnego, hermetycznego backend release gate.

Architektura rozszerza publiczny DTO i frontend addytywnie, więc ryzyko type-level backward incompatibility jest umiarkowane. Ryzyko semantycznej kompatybilności liczników jest wysokie: istniejące nazwy zaczynają oznaczać inne etapy, a UI wykonuje działania arytmetyczne na nieporównywalnych zbiorach.

Historia dodatkowo zwiększa ryzyko operacyjne: branch jest przodkiem development i nie zawiera późniejszych poprawek. Rebase/cherry-pick historycznego checkpointu bez świadomego uwzględnienia obecnej historii grozi cofnięciem fixes z `ff0db5b`, `6a06c84`, durable resume i audit hardening.

## 10. Final Recommendation

**Czy `feature/v0.6.7-search-correctness` może zostać zmergowany do `development` bez dalszych zmian? — NIE.**

Powody są dwa:

1. Technicznie branch nie ma już żadnych unikalnych commitów i jest przodkiem development; merge byłby no-op, nie dostarczeniem feature.
2. Historyczny tip `0759b00` nie spełnia search correctness i zawiera trzy blockery oraz dziewięć major findings.

Przed potraktowaniem tego brancha lub jego odtworzonego change setu jako merge-ready muszą zostać rozwiązane dokładnie:

- **B-1** — final validation na najpełniejszym rekordzie po merge w live i fetch-all;
- **B-2** — recall-safe obsługa albo fail-fast dla field-scoped queries;
- **B-3** — sound Crossref planning dla AST z negacją;
- **M-1** — poprawna agregacja all-failed/partial status;
- **M-2** — repeated Crossref cursor jako partial, nie complete;
- **M-3** — jawna strategia dedup rekordów bez DOI;
- **M-4** — deterministyczny wybór najpełniejszych metadata;
- **M-5** — spójna, wersjonowana semantyka liczników i UI;
- **M-6** — atomowa persistence runa albo formalny, spójny partial checkpoint;
- **M-7** — provider-scoped continuation dla multi-provider live search;
- **M-8** — jawne/audytowalne enrichment failures;
- **M-9** — hermetyczne testy bez niezmockowanej sieci oraz działający pełny backend gate.

Findings MINOR `m-1`–`m-3` powinny zostać naprawione przed release v0.6.7, lecz nie są samodzielnym merge blockerem po usunięciu powyższych problemów.

Rekomendowane działanie repozytoryjne nie jest merge/rebase tego brancha. Należy kontynuować z aktualnego `development`, zweryfikować które z powyższych findings zostały już naprawione przez 12 późniejszych commitów, dodać brakujące regresje i dopiero utworzyć aktualny, niepusty change set do ponownego review.
