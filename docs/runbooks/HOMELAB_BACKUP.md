# HomeLab SLR Platform backup

Run locally on HomeLab as `cloud` with Docker access:

```bash
python3 /home/cloud/slr-platform-update/scripts/backup_homelab.py
```

The default configuration source is the stored Compose of Portainer stack 18,
`slr-platform`, in environment 3. The old deployment directory is not needed.
The script reads the API token from
`/home/cloud/.config/portainer-slr/api-token` and the trusted certificate SHA-256
fingerprint from `/home/cloud/.config/portainer-slr/tls-sha256`. Both files must
be regular, owned by the executing user and private (`0600`); their directory
must be `0700`. The TLS certificate is pinned before the token is transmitted.
Tokens and raw API/command error bodies are never included in output.
After token revocation or certificate replacement, securely update these files
before the next backup; API failure does not fall back to stale configuration.

Production defaults:

- Portainer: `https://127.0.0.1:9443`; project/container `slr-platform`.
- Live database: `/app/data/slr-platform.db` in the running container.
- Host bind mounts remain `/data/compose/18/data` and `/data/compose/18/projects`.
- New backups: `/home/cloud/slr-backups/slr-platform/slr-platform-<UTC timestamp>`.
- Existing backups in `slr-platform-v078` are retained unchanged.

Each backup directory is `0700`. It contains `database.sqlite3`, the exact
Portainer `compose.prod.yaml` (`0600`), an empty compatibility `.env`, nonsecret
`stack-metadata.json`, and SHA-256 checksums. The Compose contains runtime
credentials: keep it private and never copy it into Git or reports. The API
credential itself is not backed up. A restore uses this self-contained Compose;
it does not need the retired `.env`, original Git checkout or Portainer API.

Before database backup, Docker Compose renders the saved file without deploying
and the script compares environment, image, mounts, ports, network, command,
restart, logging and ulimits against the live container. Git-managed, inactive,
wrong-environment or non-self-contained stack configurations are rejected.
The SQLite Online Backup API reads the live database and creates a consistent
copy in container `/tmp`; after copying it out, the script copies it back to a
separate temporary path and runs `PRAGMA integrity_check`. Temporary files are
removed; existing backups and production data are never removed.

To verify configuration restoration, copy only the configuration into a fresh
private temporary directory and run `docker compose -p slr-platform -f
<temporary-directory>/compose.prod.yaml config --quiet`. This is validation,
not deployment. Confirm rendered configuration against the current container;
never use `up`, `down`, or restore a database over the live database as a test.
Database restoration must be a separate approved maintenance operation.

This script backs up SQLite and deployment configuration. It does not recursively
copy the host `projects` directory or other application assets. Keep the existing
independent filesystem backup policy for those assets.

`SLR_BACKUP_*` overrides support isolated tests or explicit local Compose/env
sources. Default API settings can be overridden with `PORTAINER_URL`,
`PORTAINER_STACK_ID`, `PORTAINER_ENDPOINT_ID`, `PORTAINER_TOKEN_FILE` and
`PORTAINER_PIN_FILE` under that prefix. Legacy local-file mode requires both
`SLR_BACKUP_COMPOSE_FILE` and `SLR_BACKUP_ENV_FILE` and retains the previous
permission-preserving copy behavior.
