> **Uwaga / Note:** Ten plik jest historyczną listą startową. Od v0.7.3
> nadrzędnym dokumentem dla agentów jest [`AGENTS.md`](../AGENTS.md), a
> procedury operacyjne znajdują się w [`docs/agents/`](agents/README.md).
> Punkt 5 poniżej (brak commit/push) dotyczy wyłącznie sesji review-only;
> sesje implementacyjne kończą się commitem na dedykowanej gałęzi zgodnie z
> `AGENTS.md`. / This is a legacy checklist; `AGENTS.md` is authoritative.

1. Przeczytaj:
   - PROJECT_STATUS.md
   - ROADMAP.md
   - IMPLEMENTATION_PLAN.md
   - docs/DECISIONS.md

2. Sprawdź aktualny stan repo:
   git status
   git log --oneline -5

3. Ustal bieżącą fazę implementacji.

4. Nie implementuj nic spoza aktualnego przyrostu.

5. Po zakończeniu:
   - uruchom testy,
   - Ruff,
   - mypy,
   - git diff --check,
   - przygotuj raport,
   - nie wykonuj commit ani push.