# ADR-0001: Architektura hybrydowa

- Status: Accepted
- Data: 2026-07-21

## Kontekst

Platforma ma automatyzować techniczne etapy systematycznego przeglądu literatury, ale nie może zastępować decyzji badacza.

## Decyzja

Stosujemy architekturę hybrydową:

- moduły deterministyczne: wyszukiwanie, normalizacja, eksport, logowanie;
- moduły wspierane przez AI: screening, ocena jakości, ekstrakcja i przegląd niejednoznacznych duplikatów;
- człowiek zatwierdza decyzje naukowe.

## Konsekwencje

- wyniki techniczne są powtarzalne;
- rekomendacje AI muszą być audytowalne;
- decyzje badacza muszą być przechowywane oddzielnie od sugestii modelu.
