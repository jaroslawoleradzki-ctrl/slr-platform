import json
import tomllib
from pathlib import Path

from app.core.version import get_app_version


def test_application_version_is_synchronized() -> None:
    expected_version = "0.6.4"

    assert get_app_version() == expected_version
    assert Path("VERSION").read_text(encoding="utf-8").strip() == expected_version

    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    assert pyproject["project"]["version"] == expected_version

    frontend_package = json.loads(
        Path("frontend/package.json").read_text(encoding="utf-8")
    )
    frontend_lock = json.loads(
        Path("frontend/package-lock.json").read_text(encoding="utf-8")
    )
    assert frontend_package["version"] == expected_version
    assert frontend_lock["version"] == expected_version
    assert frontend_lock["packages"][""]["version"] == expected_version
