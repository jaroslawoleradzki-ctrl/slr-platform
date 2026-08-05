from __future__ import annotations

from contextlib import contextmanager
import os
import sqlite3
from pathlib import Path
from typing import Generator



class SqliteTransactionManager:
    """Manages shared SQLite connections and transactions for atomic multi-repository operations."""

    def __init__(self, database_path: str | Path) -> None:
        self._database_path = Path(database_path)

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Connection, None, None]:
        connection = sqlite3.connect(self._database_path)
        try:
            with connection:
                yield connection
        finally:
            connection.close()


def default_transaction_manager() -> SqliteTransactionManager:
    path = os.environ.get("SLR_DATABASE_PATH", "data/slr-platform.db")
    return SqliteTransactionManager(path)
