# ADR-0004: Google Scholar jako import ręczny

- Status: Accepted
- Data: 2026-07-21

## Kontekst

Google Scholar nie udostępnia stabilnego oficjalnego API do masowego pobierania rekordów.

## Decyzja

Nie stosujemy scrapingu. Dane z Google Scholar są importowane z plików:
- RIS;
- BibTeX;
- CSV;
- eksportu Publish or Perish.

## Konsekwencje

Proces jest zgodny z zasadą audytowalności, ale wymaga ręcznego kroku badacza.
