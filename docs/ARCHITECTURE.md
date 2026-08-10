# Architektura SLR Platform

Aplikacja jest narzędziem technicznym wspierającym realizację i dokumentowanie
SLR. Nie stanowi odrębnej metody badawczej.

Moduły MVP:
1. Search: OpenAlex, Crossref, Google Scholar manual import
2. Normalize
3. Deduplicate
4. Export
5. Logging
6. Web/API

Przyszłe moduły:
- screening (Phase 7: Title & Abstract oraz Full-Text Screening na podstawie konfigurowalnych kryteriów projektu, podzielony na przyrosty 7.1–7.9),
- quality assessment (Phase 8),
- extraction (Phase 9),
- evidence synthesis (Phase 10),
- PRISMA (Phase 12).

Zadania jednoznaczne realizuje kod deterministyczny. Agenci wspierają zadania
interpretacyjne, lecz nie podejmują ostatecznych decyzji naukowych.
