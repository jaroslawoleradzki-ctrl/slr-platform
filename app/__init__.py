# Ensure SQLite connections are closed on context exit and use a busy timeout.
# See app/core/sqlite.py for rationale.
from app.core import sqlite as _sqlite  # noqa: F401
