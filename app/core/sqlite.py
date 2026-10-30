"""Central SQLite connection handling.

The codebase opens SQLite connections in many places using ``with sqlite3.connect(...)``,
whose context manager commits/rollbacks but does **not** close the connection. Under load
this leaks file descriptors and surfaces as ``sqlite3.OperationalError: unable to open
database file``. This module patches ``sqlite3.connect`` once at import time so every
connection is closed on context exit, has a busy timeout, and uses WAL mode for better
concurrency.
"""

from __future__ import annotations

import sqlite3
import threading

_ORIGINAL_CONNECT = sqlite3.connect
_WAL_ENABLED: set[str] = set()
_WAL_LOCK = threading.Lock()


class _ClosingConnection(sqlite3.Connection):
    """sqlite3.Connection whose context manager also closes the connection."""

    def __exit__(self, exc_type, exc, tb):
        try:
            return super().__exit__(exc_type, exc, tb)
        finally:
            self.close()


def _patched_connect(database, *args, **kwargs):
    kwargs.setdefault("timeout", 10.0)
    kwargs["factory"] = _ClosingConnection
    connection = _ORIGINAL_CONNECT(database, *args, **kwargs)
    try:
        connection.execute("PRAGMA busy_timeout = 10000")
        db_key = str(database)
        with _WAL_LOCK:
            if db_key not in _WAL_ENABLED:
                try:
                    mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
                    if str(mode).lower() != "wal":
                        connection.execute("PRAGMA journal_mode = WAL")
                except sqlite3.DatabaseError:
                    pass
                _WAL_ENABLED.add(db_key)
    except sqlite3.Error:
        pass
    return connection


sqlite3.connect = _patched_connect
