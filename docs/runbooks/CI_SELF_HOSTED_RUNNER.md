# SLR Platform CI on AI-node (self-hosted GitHub Actions runner)

Status: active. Every SLR Platform GitHub Actions job executes on AI-node
(`192.168.100.29`) through a runner dedicated to this repository.

## Contract

- Runner name: `ai-node-slr-platform`
- Repository scope: `jaroslawoleradzki-ctrl/slr-platform` (repo-level runner)
- Runner group: `Default` (repo-scoped, not shared with another repository)
- Required labels: `self-hosted`, `linux`, `slr-platform`
- Workflow selector: `runs-on: [self-hosted, linux, slr-platform]`
- Runner installation: `/home/cloud/actions-runner-slr-platform`
- Work folder: `/home/cloud/actions-runner-slr-platform/_work`
- Service: user-level systemd unit
  `actions.runner.jaroslawoleradzki-ctrl-slr-platform.ai-node-slr-platform.service`

GitHub-hosted runners are forbidden. `scripts/ci/check_runner_policy.sh` is the
first CI job and fails the pipeline if any workflow contains a hosted label
(`ubuntu-*`, `windows-*`, `macos-*`), a dynamic `runs-on`, or a missing
`slr-platform` label. There is no hosted-runner fallback: if the runner is
offline, the job queues on AI-node rather than running elsewhere.

## FINNARO reference (read-only)

FINNARO uses the same architecture: repo-scoped runner `ai-node-finance` in
`/home/cloud/actions-runner`, registered to
`jaroslawoleradzki-ctrl/finance-platform`, launched by a systemd service, with
workflows selecting `[self-hosted, Linux, X64, ai-node]`.

That setup was inspected read-only as a reference. The FINNARO runner,
directory, service, credentials, secrets, work folder and production resources
are not modified, restarted, reused or shared by SLR Platform. SLR Platform has
its own installation directory, credentials, work folder, caches, systemd unit
and repository-scoped registration.

## Installation / registration runbook

Prerequisites:

1. Shell access to AI-node as the `cloud` user.
2. A GitHub token with repository administration rights for
   `jaroslawoleradzki-ctrl/slr-platform`. Registration-token creation requires
   admin permission on the repository (the token should not be stored in the
   repository or in workflow files).
3. `loginctl enable-linger cloud`, so the user-level service survives logout
   and starts with the machine.

Registration (only needed when rebuilding the runner):

```bash
mkdir -p /home/cloud/actions-runner-slr-platform
cd /home/cloud/actions-runner-slr-platform
curl -fsSL -o actions-runner-linux-x64.tar.gz \
  https://github.com/actions/runner/releases/download/v2.338.2/actions-runner-linux-x64-2.338.2.tar.gz
tar xzf actions-runner-linux-x64.tar.gz

TOKEN=$(gh api -X POST \
  repos/jaroslawoleradzki-ctrl/slr-platform/actions/runners/registration-token \
  --jq .token)

./config.sh --unattended \
  --url https://github.com/jaroslawoleradzki-ctrl/slr-platform \
  --token "$TOKEN" \
  --name ai-node-slr-platform \
  --labels slr-platform \
  --work _work

cp bin/runsvc.sh ./runsvc.sh
chmod +x runsvc.sh
printf '%s\n' \
  '/home/cloud/.local/bin:/home/cloud/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin' \
  > .path
```

The registration token is short-lived; do not commit it. `config.sh` writes the
runner credentials to the dedicated directory only.

Systemd user unit
(`~/.config/systemd/user/actions.runner.jaroslawoleradzki-ctrl-slr-platform.ai-node-slr-platform.service`):

```ini
[Unit]
Description=GitHub Actions Runner (jaroslawoleradzki-ctrl-slr-platform.ai-node-slr-platform)
After=network-online.target

[Service]
ExecStart=/home/cloud/actions-runner-slr-platform/runsvc.sh
WorkingDirectory=/home/cloud/actions-runner-slr-platform
Environment=LANG=en_US.UTF-8
KillMode=process
KillSignal=SIGTERM
TimeoutStopSec=5min
Restart=always
RestartSec=10

[Install]
WantedBy=default.target
```

Enable and start:

```bash
loginctl enable-linger cloud
systemctl --user daemon-reload
systemctl --user enable --now \
  actions.runner.jaroslawoleradzki-ctrl-slr-platform.ai-node-slr-platform.service
```

Health checks:

```bash
systemctl --user status \
  actions.runner.jaroslawoleradzki-ctrl-slr-platform.ai-node-slr-platform.service --no-pager
gh api repos/jaroslawoleradzki-ctrl/slr-platform/actions/runners \
  --jq '.runners[] | {name,status,busy,labels:[.labels[].name]}'
```

Expected: `status` is `online`, labels include `self-hosted`, `Linux`, `X64`
and `slr-platform`. Label matching is case-insensitive, so the workflow's
lowercase `linux` matches the runner's built-in `Linux` label.

## Test isolation

- Python dependencies are installed into
  `$RUNNER_TEMP/slr-ci-<run_id>-backend/venv`, never into the repository
  checkout or another repository's environment.
- uv cache and downloaded Python interpreters live in the same per-run scratch
  directory.
- npm uses a per-run `npm_config_cache`; setup-node caching is disabled.
- Tests receive `SLR_DATABASE_PATH` and `TMPDIR` inside a unique per-run
  directory (`/dev/shm/slr-platform-ci-<run_id>-<job>` on AI-node, with a
  runner-temp fallback). The SQLite-heavy suite is roughly 9x faster on tmpfs
  than on ext4; the directory is removed after the job. The repository's
  `data/*.db` files are asserted absent after the run. No production database
  or FINNARO resource is reachable from CI.
- Every job runs in the runner's isolated work folder
  `/home/cloud/actions-runner-slr-platform/_work/slr-platform/slr-platform`.

## Failure policy

If registration permissions are unavailable, or the runner is offline, CI is
incomplete: do not substitute `ubuntu-latest` or any GitHub-hosted runner. Keep
the workflow as-is, document the missing prerequisite, and resolve runner
access first. A green local shell run is not CI verification; only a completed
GitHub Actions run on `ai-node-slr-platform` counts.

## Verification evidence

Acceptance requires a real GitHub Actions run whose jobs show
`runs-on: [self-hosted, linux, slr-platform]` and execute on AI-node. Record the
run URL in the change/release notes after it succeeds.
