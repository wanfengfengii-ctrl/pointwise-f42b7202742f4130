import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path


class Database:
    def __init__(self, path: Path):
        self.path = path

    @contextmanager
    def transaction(self, *, write: bool = False):
        with closing(sqlite3.connect(self.path, timeout=10, isolation_level=None)) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute('PRAGMA foreign_keys = ON')
            with connection:
                connection.execute('BEGIN IMMEDIATE' if write else 'BEGIN')
                yield connection

    def initialize(self, schema: str) -> None:
        with closing(sqlite3.connect(self.path, timeout=10)) as connection:
            with connection:
                connection.executescript('BEGIN IMMEDIATE;\n' + schema + '\nCOMMIT;')
