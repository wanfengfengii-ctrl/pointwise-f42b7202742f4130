import json
from dataclasses import asdict

from editions.revisions import FrozenEdition, build_edition, restore_edition
from errors import missing
from storage import Database


class EditionCatalog:
    def __init__(self, database: Database):
        self.database = database
        database.initialize('''
            CREATE TABLE IF NOT EXISTS editions (
                number INTEGER PRIMARY KEY,
                revision TEXT NOT NULL UNIQUE,
                payload TEXT NOT NULL
            );
        ''')

    def publish(self, width: int, cues) -> FrozenEdition:
        with self.database.transaction(write=True) as connection:
            number = connection.execute(
                'SELECT COALESCE(MAX(number), 0) + 1 FROM editions'
            ).fetchone()[0]
            edition = build_edition(f'R{number}', width, cues)
            connection.execute(
                'INSERT INTO editions VALUES (?, ?, ?)',
                (number, edition.revision, json.dumps(asdict(edition), ensure_ascii=False)),
            )
        return edition

    def get(self, revision: str) -> FrozenEdition:
        with self.database.transaction() as connection:
            row = connection.execute(
                'SELECT payload FROM editions WHERE revision = ?', (revision,)
            ).fetchone()
        if row is None:
            raise missing(f'unknown finalized revision {revision}')
        return restore_edition(json.loads(row['payload']))
