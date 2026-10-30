# SLR Platform v0.7.8 — Deployment Report (Homelab)

**Deployment date:** 2026-10-30
**Target:** Homelab 192.168.100.22
**Source:** GitHub Release v0.7.8, commit `8fef7b9a2a2016bdda94d7218b2fe8de01de909d`
**Image:** `slr-platform:v0.7.8` (`sha256:b35b06f5ec07913cc1f76734fd15b1f514c3989e55704de02d1bebd7231edba1`)
**Container:** `slr-platform` (started `2026-10-30T08:52:28.734998866Z`)
**Compose project:** `slr-platform-v078` (`/home/cloud/slr-deploy-v078/compose.prod.yaml`)
**Data volume:** `/data/compose/18/data` → `/app/data` (preserved)

## Previous version
- v0.7.7 (image `slr-platform:v0.7.7`, container stopped cleanly, no `-v`).

## Backup
- Pre-backup: `/data/compose/18/data/slr-platform-pre-v078-20261030_085210-pre.db`
  (110 067 712 bytes, SHA-256 `765efe0af443e1772803c5a558407f253b23a8a7050845af92355d8518bc0c1f`,
  `integrity_check = ok`, `foreign_key_check = []`).
- Final backup: `/data/compose/18/data/slr-platform-pre-v078-20261030_085217-final.db`
  (110 067 712 bytes, same SHA-256, `integrity_check = ok`, `foreign_key_check = []`).

## Migration
- None required. Schema unchanged (last: `0038_import_review_decisions.sql`).

## Deployment steps executed
1. Image built from the `v0.7.8` tag into `/home/cloud/slr-release-v078`.
2. Staging directory `/home/cloud/slr-deploy-v078/` created from `slr-deploy-v077`,
   image tag updated to `slr-platform:v0.7.8`, `ulimits.nofile` set to 65536;
   `docker compose config` validated.
3. Pre-backup taken while v0.7.7 was running.
4. Old container stopped via `docker compose down` (no `-v`).
5. Final backup taken against the static database file.
6. New container started: `docker compose -f compose.prod.yaml -p slr-platform-v078 up -d`.

## Post-deployment verification
- Container status: **Up**, 0 restarts.
- Health endpoint (`/api/health`): `{"status":"ok"}` — PASS.
- Version endpoint (`/api/version`): `{"name":"SLR Platform","version":"0.7.8"}` — PASS.
- Frontend (`/`): HTTP 200 — PASS.
- `Cache-Control` on `index.html`: `no-cache, no-store, must-revalidate` — PASS.
- Bundle served: `index-D5pDTf7U.js` — PASS.
- `ulimits.nofile`: soft=65536, hard=65536 — PASS.
- DB `journal_mode`: `wal` — PASS.
- DB integrity (`PRAGMA integrity_check`): `ok` — PASS.
- `PRAGMA foreign_key_check`: `[]` (no violations) — PASS.
- Screening reviewer-ids endpoint: `["jarek"]` — PASS.
- Container logs since start: **0** lines matching `error|traceback|exception` — PASS.
- Existing data preserved; both backups retained.

## Load test (15 concurrent requests to extraction/progress)
- **15/15 returned HTTP 200**, **0 HTTP 500**, 0 new `unable to open database file` errors.
- Previously: 12/15 returned 500. Fix confirmed effective.

## Security review (pre-deployment)
- SQLite patch: connections close on context exit (transaction semantics preserved),
  busy_timeout 10 s, WAL mode, global patch guarded by lock. No connection reuse
  after `with`. Backups produce single files. Pass.
- Screening reviewer-ids endpoint: read-only SELECT filtered by project_id + stage,
  parameterized, no auth (consistent with app model), returns only reviewer ids with
  decisions. Pass.

## Observations / residual risk
- Historical DB-open burst (10 × 29.10, 5 × 30.10) resolved by this release.
- Container has no Docker `HEALTHCHECK`; readiness verified via HTTP and logs.
- Screening decisions are still keyed by reviewer_id; recovery endpoint covers the
  single-reviewer case automatically and offers a picker for multiple.

## Rollback

**Variant A — image only (no database restore):**
```bash
docker compose -f /home/cloud/slr-deploy-v078/compose.prod.yaml -p slr-platform-v078 down
docker compose -f /home/cloud/slr-deploy-v077/compose.prod.yaml -p slr-platform-v077 up -d
```
No schema downgrade required (v0.7.8 adds no migrations). Note: rollback leaves the
DB in WAL mode, which v0.7.7 handles fine.

**Variant B — image + database restore (requires separate explicit approval):**
Perform Variant A, then restore from
`slr-platform-pre-v078-20261030_085217-final.db` after hash + `integrity_check`
verification. Never use broad `DELETE`/`UPDATE` SQL.

## Status końcowy

**GO** — wdrożenie v0.7.8 na Homelab zakończone pomyślnie. Wszystkie testy
powdrożeniowe PASS, w tym test 15 równoległych żądań (0 błędów). Dane zachowane.
Dwa backupy utworzone i zweryfikowane. Obrazy i katalogi v0.7.5/v0.7.6/v0.7.7
zachowane. Rollback (wariant A i B) dostępny.
