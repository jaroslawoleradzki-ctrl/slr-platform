# Portainer backup source and cleanup — 2026-10-31

Status: PASS WITH CONDITIONS (operational backup/restore checks passed;
full application CI, Ruff and mypy unavailable in this local environment).

Scope: backup tooling only; application code, database configuration, image and
running stack are unchanged. Implementation prepared in isolated worktree
`/tmp/slr-backup-source-work`, branch `fix/portainer-backup-source`.

The backup defaults now read the current self-contained Compose from Portainer
stack 18/environment 3. Token and TLS trust fingerprint reside in private files
outside Git. Certificate pinning precedes credential transmission. The script
rejects stale/Git-managed stacks, validates saved configuration against runtime,
preserves existing backup history and never prints raw API/command errors.
The new backup root is `/home/cloud/slr-backups/slr-platform`; old backup paths
remain intact. Configuration contains secrets only inside private backup files.

Regression evidence: seven new standard-library unit tests plus all five
existing backup regression functions passed (12 total). Before implementation,
the new tests failed on legacy defaults, missing API support/private-file checks
and unsafe forwarding of subprocess error text. Existing pytest-style functions
were executed directly with isolated temporary fixtures; pytest/uv, Ruff and
mypy are not installed, so those runners and the full application suite were
NOT VERIFIED. No application behavior changed.

Operational test: backup
`/home/cloud/slr-backups/slr-platform/slr-platform-20261031T185147Z` completed
using SQLite Online Backup API, copied-back integrity verification and SHA-256.
An independent read-only SQLite integrity check passed; three projects exist.
Saved Compose and empty compatibility env file were restored to a fresh private
temporary directory and validated against the running container without deploy.

Cleanup is conditional on those successful checks. The old deployment folder
and historical build log can be removed; no current container mounts or active
backup defaults depend on them. The rehearsal DB is retained: all project IDs
and project rows match current production, but 112 publication rows differ in
metadata and 200 duplicate-candidate snapshot rows differ. Do not infer that
these differences are disposable test data. No research rows were deleted.

No production deployment, container restart, image/volume deletion, prune,
GitHub write or automatic database restore is part of this change.

## Git integration follow-up

The four operational checkout files matched commit `693aea8` byte for byte.
The existing fix branch was rebased onto `origin/development` at `e84dada`;
no application or version files changed. Two import-order issues were corrected
before pushing. A temporary Ruff installation passed `ruff check app tests
scripts`, and all 12 backup regression checks passed again. The historical
local tooling limitations above describe the initial implementation session;
the PR workflow is the authoritative full CI result for integration.
