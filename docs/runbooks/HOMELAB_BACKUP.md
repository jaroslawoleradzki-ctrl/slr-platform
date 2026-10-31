# HomeLab SLR Platform backup

The manual backup script is `scripts/backup_homelab.py`. Its defaults match the
verified HomeLab installation:

- Compose project: `slr-platform-v078`
- Container: `slr-platform`
- Compose file: `/home/cloud/slr-deploy-v078/compose.prod.yaml`
- Environment file: `/home/cloud/slr-deploy-v078/.env`
- SQLite database in the container: `/app/data/slr-platform.db`
- Persistent host data mount: `/data/compose/18/data`
- Backup root: `/home/cloud/slr-backups/slr-platform-v078`

Run the script from the repository root. It streams the script over SSH and
executes it on HomeLab; it does not install or change the running stack:

```bash
ssh cloud@192.168.100.22 'python3 -' < scripts/backup_homelab.py
```

Each run creates a UTC timestamped directory below the backup root with mode
`0700`. It copies the Compose and `.env` files while preserving their file
modes, then uses Python's SQLite Online Backup API from the running container.
The source database is opened read-only; the online backup is first written to
the container's temporary directory, copied to the backup directory, copied
back into a temporary container path, and checked with `PRAGMA integrity_check`.
SHA-256 checksums are written for the database and both configuration files.

The script checks that the expected container is running, belongs to the
expected Compose project, uses the expected Compose file, and has the verified
persistent data mount. It fails closed if those paths or the runtime database
path differ. Success prints `BACKUP_SUCCESS` and the backup directory. Failure
prints `BACKUP_FAILED`; any partial backup is retained with an
`INCOMPLETE.txt` marker for inspection. Existing backups are never removed.

The `.env` copy contains credentials. Keep the backup root restricted to its
owner and use the project's approved secure storage procedure before moving a
backup elsewhere.

## Manual Portainer update from `development`

After the desired commit is merged, build or publish an image from that exact
`development` commit before updating the stack. In Portainer, open **Stacks** →
`slr-platform-v078` → **Editor**, select the Compose configuration for the
existing stack, and change the `slr-platform` image to the prepared image tag.
Keep the existing `.env` and both explicit bind mounts unchanged, then use
**Update the stack**. Verify the new container and `/api/health` before
considering the update complete.

The repository-root `compose.yaml` is for local development: its `./data` and
`./projects` mounts are relative to the checkout. Do not use it as the HomeLab
production stack source, because those relative paths do not point to the
verified persistent HomeLab directories. Preserve
`/data/compose/18/data:/app/data` and
`/data/compose/18/projects:/app/projects` in the Portainer configuration.
