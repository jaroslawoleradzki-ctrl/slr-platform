# SLR Platform v0.7.6 — Deployment Report (Homelab)

**Deployment date:** 2026-10-30
**Target:** Homelab 192.168.100.22
**Source:** GitHub Release v0.7.6, commit `02b6fc48a8eda6d5a3819f73a73132331a610a0f`
**Image:** `slr-platform:v0.7.6` (`sha256:7a1826c22f3b9cca317cbadab8fd6c1a67b41530370f60ce09109dedd019a9df`)
**Container:** `slr-platform` (started `2026-10-30T06:53:57.98689337Z`)
**Compose project:** `slr-platform-v076` (`/home/cloud/slr-deploy-v076/compose.prod.yaml`)
**Data volume:** `/data/compose/18/data` → `/app/data` (preserved, not removed)

## Previous version
- v0.7.5 (image `slr-platform:v0.7.5`, `sha256:afb68f017f695396ea4b5628e5414db692c6cb8228e09e1a8abfe2c4de328361`,
  container up 20 h, stopped cleanly with `docker compose down`, no `-v`).
- Rollback container preserved: `slr-platform-v0.7.2-rollback` (exited).

## Backup
Two backups were created per the approved plan:

- **Pre-backup** (while v0.7.5 was running):
  `/data/compose/18/data/slr-platform-pre-v076-20261030_065302-pre.db`
  (110 067 712 bytes, SHA-256 `584923d4feeeecdeefc87debd33cf8daf86421d95955ece6779de72f34ff3d25`,
  `integrity_check = ok`, `foreign_key_check = []`).
- **Final backup** (after v0.7.5 was stopped, before v0.7.6 started):
  `/data/compose/18/data/slr-platform-pre-v076-20261030_065351-final.db`
  (110 067 712 bytes, SHA-256 `584923d4feeeecdeefc87debd33cf8daf86421d95955ece6779de72f34ff3d25`,
  `integrity_check = ok`, `foreign_key_check = []`).

Both use the SQLite Backup API executed inside the container (root), then verified
read-only. No production data was modified; all older backups and images are retained.

## Migration
- None required. v0.7.6 adds no migration (last: `0038_import_review_decisions.sql` from v0.7.4).
- Schema unchanged; `schema_migrations` still ends at `0038_import_review_decisions.sql`.

## Deployment steps executed
1. Image built from the `v0.7.6` tag into `/home/cloud/slr-release-v076`
   (`docker build -t slr-platform:v0.7.6 -f docker/Dockerfile .`, successful, digest above).
2. Staging directory created: `/home/cloud/slr-deploy-v076/` with `compose.prod.yaml`
   (image tag `slr-platform:v0.7.6`, same bind mounts and `.env`) and a copied `.env`
   (mode `600`); `docker compose config` validated.
3. Pre-backup taken while v0.7.5 was running.
4. Old container stopped via `docker compose down` (no `-v`, volumes preserved).
5. Final backup taken against the static database file.
6. New container started: `docker compose -f compose.prod.yaml -p slr-platform-v076 up -d`.
7. Container `slr-platform` now running image `slr-platform:v0.7.6`.

## Post-deployment verification
- Container status: **Up**, 0 restarts, started `2026-10-30T06:53:57.98689337Z`.
- Health endpoint (`/api/health`): `{"status":"ok"}` — PASS.
- Version endpoint (`/api/version`): `{"name":"SLR Platform","version":"0.7.6"}` — PASS.
- Frontend (`/`): HTTP 200 — PASS.
- Projects endpoint (`/api/v1/projects`): 200, 3 projects returned — PASS.
- Sources-summary endpoint: 200, 3 source summaries — PASS.
- Imports endpoint: 200 — PASS.
- Extraction progress endpoint: 200 in 2.19 s (baseline 2.29 s on v0.7.5).
- DB integrity (`PRAGMA integrity_check`): `ok` — PASS.
- `PRAGMA foreign_key_check`: `[]` (no violations) — PASS.
- Container logs since start: **0** lines matching `error|traceback|exception` — PASS.
- Existing data preserved: `/data/compose/18/data/slr-platform.db` (110 067 712 bytes) untouched;
  both backups retained.

## Observations / residual risk
- The v0.7.5 container logged 10 × `sqlite3.OperationalError: unable to open database file`
  at `2026-10-29T10:52:38` (2 minutes after the v0.7.5 start), all on
  `GET /api/v1/projects/lean-green-phd-d05d3d/extraction/progress`. The container ulimit
  is `nofile = 1024`. No such errors occurred during the v0.7.6 startup window.
  Raising the file-descriptor limit (e.g. `ulimits.nofile` in compose) is **not** part of
  this release and requires separate approval.
- The container has no Docker `HEALTHCHECK`; readiness was verified via HTTP and logs.
- Production timing for the v0.7.6 hot-path change is **not claimed**; the measurement
  gate was waived by the project owner on 2026-10-29. The single observed extraction-progress
  call (2.19 s) is informational only.

## Rollback

**Variant A — image only (no database restore):**
```bash
docker compose -f /home/cloud/slr-deploy-v076/compose.prod.yaml -p slr-platform-v076 down
docker compose -f /home/cloud/slr-deploy-v075/compose.prod.yaml -p slr-platform-v075 up -d
```
No schema downgrade is required (v0.7.6 adds no migrations).

**Variant B — image + database restore (requires separate explicit approval):**
Perform Variant A, then, after hash + `integrity_check` verification, replace
`/data/compose/18/data/slr-platform.db` with the chosen backup
(`slr-platform-pre-v076-20261030_065351-final.db` or the pre-backup).
Never use broad `DELETE`/`UPDATE` SQL.

## Status końcowy

**GO** — wdrożenie v0.7.6 na Homelab zakończone pomyślnie. Wszystkie testy powdrożeniowe
PASS. Dane zachowane. Dwa backupy utworzone i zweryfikowane. Obraz v0.7.5 i stary katalog
deployu zachowane. Rollback (wariant A i B) dostępny.
