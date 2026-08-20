from __future__ import annotations

from pathlib import Path


def get_app_version() -> str:
    """Read the single source of truth application version from the root VERSION file."""
    try:
        version_file = Path(__file__).parents[2] / "VERSION"
        if version_file.is_file():
            content = version_file.read_text(encoding="utf-8").strip()
            if content:
                return content
    except Exception:
        pass
    return "0.5.3"
