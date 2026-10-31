#!/usr/bin/env python3
"""Create a consistent, private backup of the existing SLR HomeLab stack."""

from __future__ import annotations

import hashlib
import http.client
import json
import os
import shutil
import ssl
import stat
import subprocess
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit


@dataclass(frozen=True)
class BackupConfig:
    container: str
    compose_project: str
    compose_file: Path | None
    env_file: Path | None
    expected_data_source: Path
    expected_database_path: Path
    backup_root: Path
    docker_bin: str = "docker"
    portainer_url: str = "https://127.0.0.1:9443"
    portainer_stack_id: int = 18
    portainer_endpoint_id: int = 3
    portainer_token_file: Path = Path("/home/cloud/.config/portainer-slr/api-token")
    portainer_pin_file: Path = Path("/home/cloud/.config/portainer-slr/tls-sha256")


class BackupError(RuntimeError):
    """An expected operational error while creating or validating a backup."""


def _config_from_environment() -> BackupConfig:
    """Allow explicit path overrides for isolated tests; production defaults are fixed."""

    def value(name: str, default: str) -> str:
        return os.environ.get(f"SLR_BACKUP_{name}", default)

    return BackupConfig(
        container=value("CONTAINER", "slr-platform"),
        compose_project=value("PROJECT", "slr-platform"),
        compose_file=Path(value("COMPOSE_FILE", "")) if value("COMPOSE_FILE", "") else None,
        env_file=Path(value("ENV_FILE", "")) if value("ENV_FILE", "") else None,
        expected_data_source=Path(
            value("EXPECTED_DATA_SOURCE", "/data/compose/18/data")
        ),
        expected_database_path=Path(
            value("EXPECTED_DATABASE_PATH", "/app/data/slr-platform.db")
        ),
        backup_root=Path(value("ROOT", "/home/cloud/slr-backups/slr-platform")),
        docker_bin=value("DOCKER_BIN", "docker"),
        portainer_url=value("PORTAINER_URL", "https://127.0.0.1:9443"),
        portainer_stack_id=int(value("PORTAINER_STACK_ID", "18")),
        portainer_endpoint_id=int(value("PORTAINER_ENDPOINT_ID", "3")),
        portainer_token_file=Path(value("PORTAINER_TOKEN_FILE", "/home/cloud/.config/portainer-slr/api-token")),
        portainer_pin_file=Path(value("PORTAINER_PIN_FILE", "/home/cloud/.config/portainer-slr/tls-sha256")),
    )


def _run(command: list[str]) -> str:
    try:
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise BackupError(f"Required command is unavailable: {command[0]}") from exc
    except subprocess.CalledProcessError as exc:
        # Compose/Docker errors may contain environment values or file contents.
        raise BackupError(f"Command {command[0]} failed (exit {exc.returncode}); output withheld") from exc
    return result.stdout.strip()


def _inspect_stack(config: BackupConfig) -> None:
    template = (
        '{{.State.Status}}|{{index .Config.Labels '
        '"com.docker.compose.project"}}|{{index .Config.Labels '
        '"com.docker.compose.project.config_files"}}'
    )
    details = _run(
        [config.docker_bin, "inspect", "--format", template, config.container]
    )
    fields = details.split("|", maxsplit=2)
    if len(fields) != 3:
        raise BackupError("Docker returned incomplete stack metadata")
    state, project, compose_paths = fields
    if state != "running":
        raise BackupError(f"Container {config.container} is not running")
    if project != config.compose_project:
        raise BackupError(f"Container is not part of {config.compose_project}")
    if config.compose_file is not None and str(config.compose_file) not in compose_paths.split(","):
        raise BackupError("Container does not use the expected Compose file")

    mount_template = (
        '{{range .Mounts}}{{if eq .Destination "/app/data"}}'
        "{{.Source}}{{end}}{{end}}"
    )
    data_source = _run(
        [
            config.docker_bin,
            "inspect",
            "--format",
            mount_template,
            config.container,
        ]
    )
    if Path(data_source) != config.expected_data_source:
        raise BackupError("The application data mount does not match the expected path")

    for path, label in (
        (config.compose_file, "Compose file"),
        (config.env_file, "environment file"),
    ):
        if path is None:
            continue
        if path.is_symlink() or not path.is_file():
            raise BackupError(f"{label} is missing or is not a regular file: {path}")
    if config.env_file is not None and stat.S_IMODE(config.env_file.stat().st_mode) & 0o077:
        raise BackupError("The environment file has group or world permissions")


def _read_private_file(path: Path) -> str:
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd) as file:
            st = os.fstat(file.fileno())
            if not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid() or st.st_mode & 0o077:
                raise BackupError("API credential/trust file must be privately owned (0600)")
            return file.read().strip()
    except OSError as exc:
        raise BackupError("Cannot securely read API credential/trust file") from exc


def _portainer_get(config: BackupConfig, path: str) -> dict:
    token = _read_private_file(config.portainer_token_file)
    pin = _read_private_file(config.portainer_pin_file).lower()
    if not token or any(c.isspace() for c in token) or len(pin) != 64 or any(c not in "0123456789abcdef" for c in pin):
        raise BackupError("Invalid API credential or certificate fingerprint")
    url = urlsplit(config.portainer_url)
    if url.scheme != "https" or not url.hostname or url.username or url.password or url.query or url.fragment or url.path not in ("", "/"):
        raise BackupError("Portainer URL must be an HTTPS origin without credentials")
    connection = http.client.HTTPSConnection(url.hostname, url.port or 443,
        context=ssl._create_unverified_context(), timeout=30)
    try:
        connection.connect()
        if connection.sock is None or hashlib.sha256(connection.sock.getpeercert(binary_form=True)).hexdigest() != pin:
            raise BackupError("Portainer TLS fingerprint does not match trusted certificate")
        connection.request("GET", "/api" + path, headers={"X-API-Key": token})
        response = connection.getresponse()
        data = response.read()
        if response.status != 200:
            raise BackupError(f"Portainer read failed (HTTP {response.status}); response withheld")
        result = json.loads(data)
        if not isinstance(result, dict):
            raise BackupError("Unexpected Portainer response")
        return result
    except (OSError, ValueError, http.client.HTTPException) as exc:
        raise BackupError("Portainer configuration read failed; details withheld") from exc
    finally:
        connection.close()


def _save_portainer_configuration(config: BackupConfig, directory: Path) -> None:
    stack = _portainer_get(config, f"/stacks/{config.portainer_stack_id}")
    if (stack.get("Name") != config.compose_project or stack.get("Type") != 2
            or stack.get("EndpointId") != config.portainer_endpoint_id
            or stack.get("Status") != 1 or stack.get("WorkflowID") or stack.get("AutoUpdate")):
        raise BackupError("Portainer stack identity/state differs from the managed production stack")
    result = _portainer_get(config, f"/stacks/{config.portainer_stack_id}/file")
    content = result.get("StackFileContent")
    if not isinstance(content, str) or not content.strip():
        raise BackupError("Portainer returned no Compose configuration")
    for name, text in (("compose.prod.yaml", content), (".env", "")):
        path = directory / name
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as file:
            file.write(text)
    metadata = {"stack_id": config.portainer_stack_id,
        "endpoint_id": config.portainer_endpoint_id, "project": config.compose_project,
        "configuration_source": "Portainer API", "secrets_location": "private Compose backup"}
    path = directory / "stack-metadata.json"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as file:
        file.write(json.dumps(metadata, indent=2) + "\n")


def _validate_saved_configuration(config: BackupConfig, directory: Path) -> None:
    """Render the saved configuration without deploying; require live equivalence."""
    rendered = json.loads(_run([config.docker_bin, "compose", "-p", config.compose_project,
        "-f", str(directory / "compose.prod.yaml"), "config", "--format", "json"]))
    current = json.loads(_run([config.docker_bin, "inspect", config.container]))[0]
    services = rendered.get("services", {})
    if set(services) != {"slr-platform"}:
        raise BackupError("Backup must describe exactly the SLR service")
    service = services["slr-platform"]
    host, runtime = current["HostConfig"], current["Config"]
    mounts = {(v.get("type"), v.get("source"), v.get("target"), not v.get("read_only", False))
        for v in service.get("volumes", [])}
    live_mounts = {(v["Type"], v["Source"], v["Destination"], v["RW"]) for v in current["Mounts"]}
    ports = {(str(p["target"]) + "/" + p.get("protocol", "tcp"), str(p["published"]), p.get("host_ip", "0.0.0.0"))
        for p in service.get("ports", [])}
    live_ports = {(key, p["HostPort"], p["HostIp"] or "0.0.0.0")
        for key, values in host["PortBindings"].items() for p in values}
    live_env = dict(value.split("=", 1) for value in runtime["Env"])
    live_limits = {v["Name"]: {"soft": v["Soft"], "hard": v["Hard"]} for v in host["Ulimits"]}
    networks = {rendered["networks"][name]["name"] for name in service.get("networks", {})}
    logging = service.get("logging", {})
    checks = [service.get("image") == runtime["Image"], mounts == live_mounts, ports == live_ports,
        service.get("environment") == live_env, service.get("restart") == host["RestartPolicy"]["Name"],
        service.get("ulimits") == live_limits, service.get("command") == runtime["Cmd"],
        service.get("working_dir") == runtime["WorkingDir"],
        networks == set(current["NetworkSettings"]["Networks"]),
        logging.get("driver") == host["LogConfig"]["Type"],
        (logging.get("options") or {}) == (host["LogConfig"].get("Config") or {}),
        "build" not in service, not service.get("env_file"),
        not rendered.get("secrets"), not rendered.get("configs")]
    if not all(checks):
        raise BackupError("Saved Compose is not self-contained or differs from running configuration")


def _resolve_database_path(config: BackupConfig) -> Path:
    code = (
        "import os,pathlib; cwd=pathlib.Path(os.readlink('/proc/1/cwd')); "
        "raw=pathlib.Path(os.environ.get('SLR_DATABASE_PATH', 'data/slr-platform.db')); "
        "print((raw if raw.is_absolute() else cwd/raw).resolve())"
    )
    resolved = Path(
        _run(
            [
                config.docker_bin,
                "exec",
                config.container,
                "python",
                "-c",
                code,
            ]
        )
    )
    if resolved != config.expected_database_path:
        raise BackupError(
            "Runtime database path does not match the verified path "
            f"{config.expected_database_path}"
        )
    if not resolved.is_absolute() or not resolved.is_relative_to(Path("/app/data")):
        raise BackupError("Runtime database path is outside the persistent data mount")
    return resolved


def _integrity_check_code() -> str:
    return (
        "import sqlite3,sys; "
        "db=sqlite3.connect('file:'+sys.argv[1]+'?mode=ro',uri=True,timeout=30); "
        "result=db.execute('PRAGMA integrity_check').fetchone(); db.close(); "
        "print(result[0] if result else 'missing result'); "
        "sys.exit(0 if result == ('ok',) else 2)"
    )


def _backup_database(
    config: BackupConfig,
    database_path: Path,
    remote_backup: str,
) -> None:
    code = (
        "import os,sqlite3,sys; source,destination=sys.argv[1:3]; "
        "src=sqlite3.connect('file:'+source+'?mode=ro',uri=True,timeout=30); "
        "dst=sqlite3.connect(destination,timeout=30); "
        "src.backup(dst,pages=256,sleep=0.05); "
        "result=dst.execute('PRAGMA integrity_check').fetchone(); "
        "dst.close(); src.close(); "
        "os.chmod(destination,0o600); "
        "print(result[0] if result else 'missing result'); "
        "sys.exit(0 if result == ('ok',) else 2)"
    )
    integrity = _run(
        [
            config.docker_bin,
            "exec",
            config.container,
            "python",
            "-c",
            code,
            str(database_path),
            remote_backup,
        ]
    )
    if integrity != "ok":
        raise BackupError(f"SQLite Online Backup API integrity check failed: {integrity}")


def _verify_copied_database(config: BackupConfig, remote_verify: str) -> None:
    integrity = _run(
        [
            config.docker_bin,
            "exec",
            config.container,
            "python",
            "-c",
            _integrity_check_code(),
            remote_verify,
        ]
    )
    if integrity != "ok":
        raise BackupError(f"Copied SQLite backup failed integrity check: {integrity}")


def _remove_remote_temporary_files(
    config: BackupConfig,
    paths: tuple[str, ...],
) -> None:
    if not paths:
        return
    code = (
        "import os,sys; "
        "[os.unlink(path) for path in sys.argv[1:] if os.path.isfile(path)]"
    )
    _run(
        [
            config.docker_bin,
            "exec",
            config.container,
            "python",
            "-c",
            code,
            *paths,
        ]
    )


def _write_checksums(directory: Path) -> None:
    entries = []
    for name in sorted(p.name for p in directory.iterdir() if p.is_file() and p.name != "SHA256SUMS"):
        digest = hashlib.sha256((directory / name).read_bytes()).hexdigest()
        entries.append(f"{digest}  {name}")
    (directory / "SHA256SUMS").write_text("\n".join(entries) + "\n", encoding="ascii")
    (directory / "SHA256SUMS").chmod(0o600)


def create_backup(config: BackupConfig) -> Path:
    _inspect_stack(config)
    database_path = _resolve_database_path(config)

    backup_root = config.backup_root.resolve()
    data_root = config.expected_data_source.resolve()
    if backup_root == data_root or data_root in backup_root.parents:
        raise BackupError("Backup destination must be outside the research data directory")
    if backup_root.exists() and stat.S_IMODE(backup_root.stat().st_mode) & 0o077:
        raise BackupError(f"Backup root permissions must be private (0700): {backup_root}")
    backup_root.mkdir(parents=True, exist_ok=True, mode=0o700)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_dir = backup_root / f"{config.compose_project}-{timestamp}"
    backup_dir.mkdir(mode=0o700)
    backup_dir.chmod(0o700)

    token = uuid.uuid4().hex
    remote_backup = f"/tmp/slr-platform-backup-{token}.sqlite3"
    remote_verify = f"/tmp/slr-platform-verify-{token}.sqlite3"
    try:
        if config.compose_file is None:
            _save_portainer_configuration(config, backup_dir)
            _validate_saved_configuration(config, backup_dir)
        else:
            if config.env_file is None:
                raise BackupError("Local Compose override requires an environment file")
            shutil.copy2(config.compose_file, backup_dir / "compose.prod.yaml")
            shutil.copy2(config.env_file, backup_dir / ".env")

        _backup_database(config, database_path, remote_backup)
        database_backup = backup_dir / "database.sqlite3"
        _run(
            [
                config.docker_bin,
                "cp",
                f"{config.container}:{remote_backup}",
                str(database_backup),
            ]
        )
        database_backup.chmod(0o600)
        _run(
            [
                config.docker_bin,
                "cp",
                str(database_backup),
                f"{config.container}:{remote_verify}",
            ]
        )
        _verify_copied_database(config, remote_verify)
        _write_checksums(backup_dir)
    except Exception as exc:
        marker = backup_dir / "INCOMPLETE.txt"
        try:
            marker.write_text("Backup did not complete successfully.\n", encoding="ascii")
            marker.chmod(0o600)
        except OSError:
            pass
        safe_detail = str(exc) if isinstance(exc, BackupError) else "Backup validation failed; details withheld"
        detail = f"{safe_detail}; incomplete backup retained at: {backup_dir}"
        raise BackupError(detail) from exc
    finally:
        _remove_remote_temporary_files(config, (remote_backup, remote_verify))

    return backup_dir


def main() -> int:
    backup_dir: Path | None = None
    original_umask = os.umask(0o077)
    try:
        backup_dir = create_backup(_config_from_environment())
    except (BackupError, OSError, ValueError) as exc:
        detail = str(exc) if isinstance(exc, BackupError) else "Backup unavailable; details withheld"
        print(f"BACKUP_FAILED: {detail}", file=sys.stderr)
        if backup_dir is not None:
            print(f"Incomplete backup retained at: {backup_dir}", file=sys.stderr)
        return 1
    finally:
        os.umask(original_umask)
    print(f"BACKUP_SUCCESS: {backup_dir} (SQLite integrity_check: ok)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
