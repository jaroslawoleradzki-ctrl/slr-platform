# ADR-0007: Kontrakt stanów pól ekstrakcji danych

- Status: Accepted
- Data: 2026-08-15

## Kontekst

Phase 9 przechowuje rewizje ekstrakcji jako niemutowalne snapshoty. W wersji
0.4.8 formularz materializował pole, którego badacz jeszcze nie ocenił, jako
`NOT_REPORTED` z pochodzeniem `REPORTED`. Łączyło to dwa odmienne twierdzenia:
brak oceny i świadome stwierdzenie, że autorzy nie podali informacji. Model
pozwalał również na semantycznie sprzeczne połączenia statusu i pochodzenia oraz
na oznaczenie niemal pustej rewizji jako kompletnej.

Historyczne rewizje mogą już zawierać takie kombinacje. Nie wolno ich zmieniać
ani reinterpretować bez decyzji badacza.

## Decyzja

### 1. Stan nieoceniony

Kanonicalnym stanem pola, którego badacz jeszcze nie ocenił, jest trwały
`UNASSESSED`.

Wybrano stan trwały zamiast braku wiersza wartości, ponieważ snapshot rewizji
ma jednoznacznie pokazywać, które pola formularza pozostawały nieocenione w
chwili zapisu. Brak wiersza pozostałby niejednoznaczny: mógłby oznaczać
nieocenienie, usunięte pole starego szablonu albo niepełną serializację.

`UNASSESSED` nie zawiera wartości, origin ani proweniencji. Nie może spełnić
wymaganego pola przy oznaczaniu rewizji jako `COMPLETE`.

### 2. Status i pochodzenie

`ValueOrigin` opisuje pochodzenie **wyodrębnionej wartości**, a nie sam fakt,
że badacz podjął decyzję o braku, nieadekwatności albo niepewności. Obecny
model ma tylko dwa pochodzenia wartości: `REPORTED` i `REVIEWER_CODED`; nie
ma pochodzenia `metadata-derived`. Kanoniczne dane bibliograficzne (np. E1)
są systemowo związane z publikacją i nie są sztucznie zapisywane jako stan
wartości ekstrakcyjnej.

| Status | Znaczenie | Wartość: dozwolona / wymagana | Origin: dozwolony / wymagany | Proweniencja źródłowa: dozwolona / wymagana | Notatka badacza: dozwolona / wymagana | Może spełnić pole wymagane przy `COMPLETE` |
|---|---|---|---|---|---|---|
| `UNASSESSED` | Pole nie zostało jeszcze ocenione. | Nie / nie | Nie / nie (`None`) | Nie / nie | Nie / nie | Nie |
| `PRESENT` | Wyodrębniono wartość zgodną z typem pola. | Tak / tak | Tak / tak: `REPORTED` lub `REVIEWER_CODED` | Tak / warunkowo: dla `REPORTED` co najmniej jedno z: strona, sekcja, lokalizator lub cytat; dla `REVIEWER_CODED` opcjonalna | Tak / warunkowo: dla `REVIEWER_CODED` wymagana, dla `REPORTED` opcjonalna | Tak, jeśli status jest dozwolony przez definicję pola |
| `NOT_REPORTED` | Badacz świadomie ustalił, że źródło nie raportuje informacji. | Nie / nie | Nie / nie (`None`) | Nie / nie | Tak / nie | Tak, jeśli status jest dozwolony przez definicję pola |
| `NOT_APPLICABLE` | Badacz świadomie ustalił, że pole nie ma zastosowania do badania. | Nie / nie | Nie / nie (`None`) | Nie / nie | Tak / nie | Tak, jeśli status jest dozwolony przez definicję pola |
| `UNCLEAR` | Badacz nie może wydać rozstrzygającej oceny na podstawie dostępnego materiału. | Tak / nie: ewentualna wartość ma charakter tymczasowy | Bez wartości: nie / nie (`None`); z wartością: tak / tak, według reguł `PRESENT` | Bez wartości: nie / nie; z wartością: według origin wartości | Tak / tak: musi wyjaśniać niejednoznaczność | Tak, tylko jeśli status jest dozwolony przez definicję pola i spełnia powyższe reguły |

`REPORTED` oznacza wyłącznie bezpośrednio raportowaną przez autorów wartość.
`REVIEWER_CODED` oznacza, że konkretna **wartość** jest wynikiem kodowania lub
interpretacji badacza i dlatego wymaga notatki uzasadniającej. Nie oznacza
samej decyzji `NOT_REPORTED`, `NOT_APPLICABLE` ani `UNCLEAR`.

W tym ADR „proweniencja źródłowa” to `source_page`, `source_section`,
`source_locator` albo `source_quote`. `reviewer_note` jest odrębnym
uzasadnieniem metodologicznym. Dla wartości `REVIEWER_CODED` wymagana notatka
jest wystarczającym śladem decyzji w obecnym modelu; system nie wymusza
nieistniejącego lokalizatora strony. Jeśli lokalizator jest znany, może zostać
dodany. Dla `NOT_REPORTED` i `NOT_APPLICABLE` można opcjonalnie zapisać
uzasadnienie w `reviewer_note`, ale nie zapisuje się origin ani proweniencji
wartości, ponieważ wartości nie ma.

### 3. Wymagalność i kompletność

`is_required` oznacza, że przy `COMPLETE` pole musi istnieć, nie może być
`UNASSESSED`, musi używać statusu dozwolonego przez definicję pola i spełniać
macierz statusu/origin/proweniencji. `NOT_REPORTED`, `NOT_APPLICABLE` i
`UNCLEAR` nie są automatycznie błędne tylko dlatego, że pole jest wymagane:
mogą spełnić wymaganie wyłącznie wtedy, gdy dana definicja pola jawnie je
dopuszcza. Definicja może więc ograniczyć `allowed_statuses`; np. E4 i E6
mogą wymagać `PRESENT`, a inne pola mogą świadomie dopuszczać brak raportowania
lub niejednoznaczność.

`Save Draft` zapisuje semantycznie poprawny snapshot z nieocenionymi lub
niekompletnymi wymaganymi polami i zawsze ma status `IN_PROGRESS`. `Mark
Complete` wymaga pełnej walidacji: wszystkich wymaganych pól, minimalnej
liczby elementów grup, dozwolonych statusów i poprawnej proweniencji.

### 4. Tożsamość snapshotów

- `record_id` identyfikuje trwały nagłówek publikacji w projekcie.
- `revision_id` identyfikuje jeden append-only snapshot.
- `value_id` identyfikuje wiersz wartości w jednym snapshotie i jest nowy w
  każdej rewizji. Klient nie przekazuje go przy zapisie rewizji.
- `group_item_id` identyfikuje trwałe wystąpienie relacji 1:N i pozostaje
  stabilny między rewizjami.

### 5. Zgodność historyczna

Migracja strukturalna dopuszcza `UNASSESSED` oraz brak `origin`, ale nie
zmienia istniejących wierszy. Odczyt historycznej rewizji używa ścieżki
zgodnościowej, która zachowuje dawne kombinacje, natomiast każdy nowy zapis
jest walidowany według niniejszego ADR. Historyczne snapshoty pozostają
reprodukowalne i nie są przedstawiane jako potwierdzone zgodne z nowym
kontraktem.

### 6. Migracje i Phase 10

Development kończy się na `0019`; izolowana linia Phase 10 używa `0020`–`0022`.
Ta zmiana używa `0023_extraction_field_state_contract.sql`, aby zachować
globalną unikalność po przyszłym merge Phase 10.

Phase 10 zachowuje `group_item_id`, `revision_id`, klucze E4/E6/E10/E11 oraz
tożsamość szablonów. Po jego przyszłej integracji czytniki syntezy muszą
ignorować `UNASSESSED` i nie traktować rewizji `IN_PROGRESS` jako kompletnego
materiału analitycznego.

## Konsekwencje

- Frontend nie tworzy automatycznie twierdzeń metodologicznych podczas
  pierwszego renderowania.
- Backend, a nie UI, jest autorytetem kombinacji statusu/origin/proweniencji
  oraz kompletności.
- Nowe Lean Energy template versions mogą deklarować `allowed_statuses` bez
  modyfikacji już użytych, niemutowalnych wersji.
- Nowy kontrakt wymaga migracji SQLite i regresji dla danych legacy.

## Rozważone alternatywy

1. **Brak wiersza jako stan nieoceniony** — odrzucone: brak nie jest trwałym,
   jednoznacznym elementem snapshotu rewizji.
2. **Pozostawienie `NOT_REPORTED` jako domyślnego** — odrzucone: zapisuje
   twierdzenie naukowe bez oceny badacza.
3. **Walidacja tylko we frontendzie** — odrzucone: API i importy muszą być
   równie bezpieczne.
4. **Automatyczna normalizacja danych legacy** — odrzucone: zmieniałaby
   historyczne dowody bez informacji, czy brak raportowania był świadomą oceną.
