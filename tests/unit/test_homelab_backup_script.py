import os
import re
import sqlite3
import stat
import subprocess
import sys
import textwrap
from pathlib import Path

SCRIPT = Path("scripts/backup_homelab.py")


FAKE_DOCKER = textwrap.dedent(
    """\
    #!/usr/bin/env python3
    import os
    import shutil
    import subprocess
    import sys
    from pathlib import Path

    args = sys.argv[1:]
    root = Path(os.environ["FAKE_DOCKER_ROOT"])
    container_tmp = root / "container-tmp"
    container_tmp.mkdir(parents=True, exist_ok=True)
    if args[0] == "inspect":
        template = args[2]
        if ".State.Status" in template:
            print("|".join((
                os.environ.get("FAKE_STATUS", "running"),
                os.environ.get("FAKE_PROJECT", os.environ["SLR_BACKUP_PROJECT"]),
                os.environ["SLR_BACKUP_COMPOSE_FILE"],
            )))
        else:
            print(os.environ["SLR_BACKUP_DATA_SOURCE"])
    elif args[0] == "exec":
        code = args[4]
        supplied = args[5:]
        if "os.readlink" in code:
            print(os.environ["SLR_BACKUP_DATABASE_PATH"])
        else:
            mapped = []
            for value in supplied:
                if value == os.environ["SLR_BACKUP_DATABASE_PATH"]:
                    mapped.append(os.environ["FAKE_SOURCE_DB"])
                elif value.startswith("/tmp/"):
                    mapped.append(str(container_tmp / Path(value).name))
                else:
                    mapped.append(value)
            result = subprocess.run([sys.executable, "-c", code, *mapped])
            raise SystemExit(result.returncode)
    elif args[0] == "cp":
        source, destination = args[1:]
        if ":/tmp/" in source:
            _, path = source.split(":", 1)
            shutil.copy2(container_tmp / Path(path).name, destination)
            if os.environ.get("FAKE_CORRUPT_BACKUP") == "1":
                with open(destination, "r+b") as backup:
                    backup.write(b"not-a-sqlite-database")
        elif ":/tmp/" in destination:
            _, path = destination.split(":", 1)
            shutil.copy2(source, container_tmp / Path(path).name)
        else:
            raise SystemExit("unexpected docker cp arguments")
    else:
        raise SystemExit("unexpected docker command: " + " ".join(args))
    """
)


def _prepare_fixture(tmp_path: Path, *, corrupt_backup: bool = False) -> dict[str, str]:
    compose = tmp_path / "compose.prod.yaml"
    compose.write_text("services: {}\n", encoding="utf-8")
    compose.chmod(0o640)
    env_file = tmp_path / ".env"
    env_file.write_text("SOME_SETTING=fixture-only\n", encoding="utf-8")
    env_file.chmod(0o600)

    source_db = tmp_path / "source.db"
    with sqlite3.connect(source_db) as connection:
        connection.execute("CREATE TABLE fixture (value TEXT NOT NULL)")
        connection.execute("INSERT INTO fixture VALUES ('disposable')")

    fake_docker = tmp_path / "docker"
    fake_docker.write_text(FAKE_DOCKER, encoding="utf-8")
    fake_docker.chmod(0o755)
    return {
        "SLR_BACKUP_CONTAINER": "slr-platform",
        "SLR_BACKUP_PROJECT": "slr-platform-v078",
        "SLR_BACKUP_COMPOSE_FILE": str(compose),
        "SLR_BACKUP_ENV_FILE": str(env_file),
        "SLR_BACKUP_DATA_SOURCE": "/data/compose/18/data",
        "SLR_BACKUP_DATABASE_PATH": "/app/data/slr-platform.db",
        "SLR_BACKUP_EXPECTED_DATA_SOURCE": "/data/compose/18/data",
        "SLR_BACKUP_EXPECTED_DATABASE_PATH": "/app/data/slr-platform.db",
        "SLR_BACKUP_ROOT": str(tmp_path / "backups"),
        "SLR_BACKUP_DOCKER_BIN": str(fake_docker),
        "FAKE_DOCKER_ROOT": str(tmp_path / "docker-state"),
        "FAKE_SOURCE_DB": str(source_db),
        "FAKE_CORRUPT_BACKUP": "1" if corrupt_backup else "0",
    }


def _run_backup(tmp_path: Path, *, corrupt_backup: bool = False) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update(_prepare_fixture(tmp_path, corrupt_backup=corrupt_backup))
    return subprocess.run(
        [sys.executable, str(SCRIPT.resolve())],
        cwd=Path.cwd(),
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_backup_script_uses_online_backup_and_preserves_configuration_permissions(
    tmp_path: Path,
) -> None:
    result = _run_backup(tmp_path)

    assert result.returncode == 0, result.stderr
    assert "BACKUP_SUCCESS" in result.stdout
    backup_dir = next((tmp_path / "backups").iterdir())
    assert re.fullmatch(r"slr-platform-v078-\d{8}T\d{6}Z", backup_dir.name)
    assert stat.S_IMODE(backup_dir.stat().st_mode) == 0o700
    assert (backup_dir / "compose.prod.yaml").read_text(encoding="utf-8") == (
        "services: {}\n"
    )
    assert (backup_dir / ".env").read_text(encoding="utf-8") == (
        "SOME_SETTING=fixture-only\n"
    )
    assert stat.S_IMODE((backup_dir / "compose.prod.yaml").stat().st_mode) == 0o640
    assert stat.S_IMODE((backup_dir / ".env").stat().st_mode) == 0o600
    database_backup = backup_dir / "database.sqlite3"
    with sqlite3.connect(database_backup) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert connection.execute("SELECT value FROM fixture").fetchone() == (
            "disposable",
        )
    assert {line.split("  ", maxsplit=1)[1] for line in (backup_dir / "SHA256SUMS").read_text().splitlines()} == {
        ".env",
        "compose.prod.yaml",
        "database.sqlite3",
    }


def test_backup_script_retains_existing_backups(tmp_path: Path) -> None:
    backup_root = tmp_path / "backups"
    backup_root.mkdir(mode=0o700)
    backup_root.chmod(0o700)
    sentinel = backup_root / "previous-backup.txt"
    sentinel.write_text("keep", encoding="ascii")

    result = _run_backup(tmp_path)

    assert result.returncode == 0, result.stderr
    assert sentinel.read_text(encoding="ascii") == "keep"


def test_backup_script_reports_integrity_failure_without_success(tmp_path: Path) -> None:
    result = _run_backup(tmp_path, corrupt_backup=True)

    assert result.returncode != 0
    assert "BACKUP_FAILED" in result.stderr
    assert "BACKUP_SUCCESS" not in result.stdout


def test_backup_script_refuses_an_inactive_container(tmp_path: Path) -> None:
    env = os.environ.copy()
    env.update(_prepare_fixture(tmp_path))
    env["FAKE_STATUS"] = "exited"
    result = subprocess.run(
        [sys.executable, str(SCRIPT.resolve())],
        cwd=Path.cwd(),
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert "BACKUP_FAILED" in result.stderr
    assert "BACKUP_SUCCESS" not in result.stdout


def test_backup_script_refuses_a_different_compose_project(tmp_path: Path) -> None:
    env = os.environ.copy()
    env.update(_prepare_fixture(tmp_path))
    env["FAKE_PROJECT"] = "another-project"
    result = subprocess.run(
        [sys.executable, str(SCRIPT.resolve())],
        cwd=Path.cwd(),
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert "BACKUP_FAILED" in result.stderr
    assert "BACKUP_SUCCESS" not in result.stdout
