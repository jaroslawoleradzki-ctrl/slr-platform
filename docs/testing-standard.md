# Standard testowania

## Testy jednostkowe

Obejmują:
- normalizację rekordów;
- czyszczenie DOI;
- normalizację tytułów;
- reguły deduplikacji;
- walidację konfiguracji.

## Testy integracyjne

Obejmują:
- adaptery źródeł;
- zapis danych surowych;
- pełny przepływ raw → canonical → export.

## Dane testowe

- krótkie;
- anonimowe;
- zapisane w repozytorium;
- niezależne od aktywnego połączenia z API, o ile test nie jest jawnie integracyjny.

## Zasada regresji

Każdy naprawiony błąd powinien otrzymać test, który wcześniej nie przechodził.
