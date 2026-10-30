# SLR Platform v0.7.7 — Deployment Report (Homelab)

**Deployment date:** 2026-10-30
**Target:** Homelab 192.168.100.22
**Source:** GitHub Release v0.7.7, commit `f31b1bc0d3ddf79b3ebe75d0c850051360e9c891`
**Image:** `slr-platform:v0.7.7` (`sha256:5a67a26c06af1db0f2e4ab00ace90b84b30849977cd40635cb6c3e3e9e1ccb9e`)
**Container:** `slr-platform` (started `2026-10-30T07:29:28.734998866Z`)
**Compose project:** `slr-platform-v077` (`/home/cloud/slr-deploy-v077/compose.prod.yaml`)
**Data volume:** `/data/compose/18/data` → `/app/data` (preserved)

## Previous version
- v0.7.6 (image `slr-platform:v0.7.6`, container stopped cleanly, no `-v`).

## Backup
- Pre-backup: `/data/compose/18/data/slr-platform-pre-v077-20261030_072917-pre.db`
  (110 067 712 B, SHA-256 `2b2aef5e5c2563ab73232b7d345db1b8f71c460d9fe214d0fc5cc052b36d26b5`,
  `integrity_check = ok`, `foreign_key_check = []`).
- Final backup: `/data/compose/18/data/slr-platform-pre-v077-20261030_072925-final.db`
  (110 067 712 B, same SHA-256, `integrity_check = ok`, `foreign_key_check = []`).

## Migration
- None required. Schema unchanged (last: `0038_import_review_decisions.sql`).

## Deployment steps executed
1. Image built from the `v0.7.7` tag into `/home/cloud/slr-release-v077`.
2. Staging directory `/home/cloud/slr-deploy-v077/` created from `slr-deploy-v076`,
   image tag updated to `slr-platform:v0.7.7`; `docker compose config` validated.
3. Pre-backup taken while v0.7.6 was running.
4. Old container stopped via `docker compose down` (no `-v`).
5. Final backup taken against the static database file.
6. New container started: `docker compose -f compose.prod.yaml -p slr-platform-v077 up -d`.

## Post-deployment verification
- Container status: **Up**, 0 restarts.
- Health endpoint (`/api/health`): `{"status":"ok"}` — PASS.
- Version endpoint (`/api/version`): `{"name":"SLR Platform","version":"0.7.7"}` — PASS.
- Frontend (`/`): HTTP 200 — PASS.
- `Cache-Control` on `index.html`: `no-cache, no-store, must-revalidate` — PASS.
- New bundle served: `index-lcnkkhkx.js` — PASS.
- DB integrity: `ok`, `foreign_key_check = []` — PASS.
- Container logs since start: **0** lines matching `error|traceback|exception` — PASS.
- Existing data preserved; both backups retained.

## Status końcowy

**GO** — hotfix v0.7.7 wdrożony. Przyczyna pierwotnego „nic się nie zmieniało”
(zbuforowany `index.html` w przeglądarce) usunięta nagłówkiem `Cache-Control`.
Dane zachowane, backupy zweryfikowane, rollback dostępny.
