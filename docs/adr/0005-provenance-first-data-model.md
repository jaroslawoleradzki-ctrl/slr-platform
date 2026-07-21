# ADR-0005: Model danych z pełnym pochodzeniem rekordu

- Status: Accepted
- Data: 2026-07-21

## Decyzja

Każdy rekord kanoniczny zachowuje informację o:
- źródle;
- identyfikatorze źródłowym;
- zapytaniu;
- czasie pobrania;
- pliku odpowiedzi surowej;
- transformacjach;
- wersji schematu.

## Konsekwencje

Można odtworzyć pochodzenie każdej publikacji i sposób jej przetworzenia.
