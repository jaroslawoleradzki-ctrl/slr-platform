# SLR Platform v0.7.5 — Deployment Report (Homelab)

**Deployment date:** 2026-10-29
**Target:** Homelab 192.168.100.22
**Source:** GitHub Release v0.7.5, commit `85540256221dad1d4c771ea154aa1f1eb2fd035d`
**Image:** `slr-platform:v0.7.5` (`sha256:afb68f017f695396ea4b5628e5414db692c6cb8228e09e1a8abfe2c4de328361`)
**Container:** `slr-platform` (`dc259fc33656d7f7957fcbbb2b8306eea3ed23df4e4dfdc8e902b93fc9a4017b`)
**Compose project:** `slr-platform-v075` (`/home/cloud/slr-deploy-v075/compose.prod.yaml`)
**Data volume:** `/data/compose/18/data` → `/app/data` (preserved, not removed)

## Previous version
- v0.7.4 (image `slr-platform:v0.7.4`, container up 39h, image `sha256:ddd095ac9f4944c31537059b44a2e3b9e87c13dee18c1f309d41398f4a16be29`)
- Rollback container preserved: `slr-platform-v0.7.2-rollback` (exited).

## Backup
- **Path:** `/data/compose/18/data/slr-platform-pre-v075-20261029_114911.db`
- **Method:** SQLite Backup API (`connection.backup()`) executed inside the running container.
- **Size:** 110,067,712 bytes (~105 MB)
- **SHA-256:** `4083dcc0aa08a19a1aaa21b608e2197dff7fe5791167080de6a40bbe702ddc7a`
- **integrity_check:** `ok`
- **foreign_key_check:** `[]` (no violations)

## Migration
- None required. v0.7.5 adds no migration (last: `0038_import_review_decisions.sql` from v0.7.4).
- Schema unchanged.

## Deployment steps executed
1. Mirror pushed: `git push homelab main` and `git push homelab v0.7.5`.
2. Source cloned on Homelab: `/home/cloud/slr-release-v075` @ tag `v0.7.5`.
3. Image built: `docker build -t slr-platform:v0.7.5 -f docker/Dockerfile .` (success).
4. Deploy dir created: `/home/cloud/slr-deploy-v075/` with `compose.prod.yaml` + `.env`.
5. Old container stopped via `docker compose down` (no `-v`, volumes preserved).
6. New container started: `docker compose -f compose.prod.yaml -p slr-platform-v075 up -d`.
7. Container `slr-platform` now running image `slr-platform:v0.7.5`.

## Post-deployment verification
- Container status: **Up** (started < 1 min ago).
- Health endpoint (`/api/health`): `{"status":"ok"}` — PASS.
- Version endpoint (`/api/version`): `{"name":"SLR Platform","version":"0.7.5"}` — PASS.
- Frontend (`/`): HTTP 200, title "SLR Platform — Systematic Literature Review Workbench" — PASS.
- Projects endpoint: 200, projects returned — PASS.
- Imports endpoint: 200, 11 imports — PASS.
- Sources-summary endpoint: 200, 4 source summaries, 11 import history — PASS.
- DB integrity (`PRAGMA integrity_check`): `ok` — PASS.
- Container logs: no errors/tracebacks/exceptions — PASS.
- Existing data preserved: `/data/compose/18/data/slr-platform.db` (105 MB) untouched; backup retained.

## Rollback (if needed)
- Stop new container: `docker compose -f /home/cloud/slr-deploy-v075/compose.prod.yaml -p slr-platform-v075 down` (no `-v`).
- Start previous: `docker compose -f /home/cloud/slr-deploy-v073/compose.prod.yaml -p slr-platform-v073 up -d` (image `slr-platform:v0.7.4` still available).
- If DB restore needed: copy `slr-platform-pre-v075-20261029_114911.db` back after hash + integrity verification.
- Never use broad DELETE/UPDATE SQL.

## Status końcowy

**GO** — wdrożenie v0.7.5 na Homelab zakończone pomyślnie. Wszystkie testy powdrożeniowe PASS. Dane zachowane. Backup utworzony i zweryfikowany. Rollback dostępny. STOP.
