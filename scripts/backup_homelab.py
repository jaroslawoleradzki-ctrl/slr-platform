#!/usr/bin/env python3
"""Create a consistent, private backup of the existing SLR HomeLab stack."""

from __future__ import annotations

import hashlib
import os
import shutil
import stat
import subprocess
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class BackupConfig:
    container: str
    compose_project: str
    compose_file: Path
    env_file: Path
    expected_data_source: Path
    expected_database_path: Path
    backup_root: Path
    docker_bin: str = "docker"


class BackupError(RuntimeError):
    """An expected operational error while creating or validating a backup."""


def _config_from_environment() -> BackupConfig:
    """Allow explicit path overrides for isolated tests; production defaults are fixed."""

    def value(name: str, default: str) -> str:
        return os.environ.get(f"SLR_BACKUP_{name}", default)

    return BackupConfig(
        container=value("CONTAINER", "slr-platform"),
        compose_project=value("PROJECT", "slr-platform-v078"),
        compose_file=Path(
            value("COMPOSE_FILE", "/home/cloud/slr-deploy-v078/compose.prod.yaml")
        ),
        env_file=Path(value("ENV_FILE", "/home/cloud/slr-deploy-v078/.env")),
        expected_data_source=Path(
            value("EXPECTED_DATA_SOURCE", "/data/compose/18/data")
        ),
        expected_database_path=Path(
            value("EXPECTED_DATABASE_PATH", "/app/data/slr-platform.db")
        ),
        backup_root=Path(value("ROOT", "/home/cloud/slr-backups/slr-platform-v078")),
        docker_bin=value("DOCKER_BIN", "docker"),
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
        detail = (exc.stderr or exc.stdout or "command failed").strip()
        raise BackupError(detail) from exc
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
    if str(config.compose_file) not in compose_paths.split(","):
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
        if path.is_symlink() or not path.is_file():
            raise BackupError(f"{label} is missing or is not a regular file: {path}")
    if stat.S_IMODE(config.env_file.stat().st_mode) & 0o077:
        raise BackupError("The environment file has group or world permissions")


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
    for name in ("database.sqlite3", "compose.prod.yaml", ".env"):
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
    backup_dir = backup_root / f"slr-platform-v078-{timestamp}"
    backup_dir.mkdir(mode=0o700)
    backup_dir.chmod(0o700)

    token = uuid.uuid4().hex
    remote_backup = f"/tmp/slr-platform-backup-{token}.sqlite3"
    remote_verify = f"/tmp/slr-platform-verify-{token}.sqlite3"
    try:
        shutil.copy2(config.compose_file, backup_dir / "compose.prod.yaml")
        shutil.copy2(config.env_file, backup_dir / ".env")
        for original, copied, label in (
            (config.compose_file, backup_dir / "compose.prod.yaml", "Compose file"),
            (config.env_file, backup_dir / ".env", "environment file"),
        ):
            if stat.S_IMODE(original.stat().st_mode) != stat.S_IMODE(copied.stat().st_mode):
                raise BackupError(f"Permissions were not preserved for {label}")

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
        detail = f"{exc}; incomplete backup retained at: {backup_dir}"
        raise BackupError(detail) from exc
    finally:
        _remove_remote_temporary_files(config, (remote_backup, remote_verify))

    return backup_dir


def main() -> int:
    backup_dir: Path | None = None
    original_umask = os.umask(0o077)
    try:
        backup_dir = create_backup(_config_from_environment())
    except (BackupError, OSError) as exc:
        print(f"BACKUP_FAILED: {exc}", file=sys.stderr)
        if backup_dir is not None:
            print(f"Incomplete backup retained at: {backup_dir}", file=sys.stderr)
        return 1
    finally:
        os.umask(original_umask)
    print(f"BACKUP_SUCCESS: {backup_dir} (SQLite integrity_check: ok)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
