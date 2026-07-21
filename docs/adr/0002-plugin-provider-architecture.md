# ADR-0002: Architektura dostawców danych oparta na pluginach

- Status: Accepted
- Data: 2026-07-21

## Kontekst

Platforma ma obsługiwać wiele źródeł bibliograficznych i metod importu.

## Decyzja

Każde źródło danych implementuje wspólny kontrakt dostawcy:

- pobranie rekordów;
- zapis odpowiedzi surowej;
- mapowanie do modelu kanonicznego;
- raportowanie błędów i limitów;
- identyfikacja źródła i zapytania.

## Konsekwencje

OpenAlex, Crossref i ręczny import Google Scholar mogą rozwijać się niezależnie.
