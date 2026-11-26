import json

from display.outcomes import LitEvent
from storage import Database


class DisplayLedger:
    def __init__(self, database: Database):
        self.database = database
        database.initialize('''
            CREATE TABLE IF NOT EXISTS ledger (
                show TEXT NOT NULL,
                screen TEXT NOT NULL,
                sequence INTEGER NOT NULL,
                cue TEXT NOT NULL,
                segment INTEGER NOT NULL,
                revision TEXT NOT NULL,
                lines TEXT NOT NULL,
                PRIMARY KEY (show, screen, sequence)
            );
        ''')

    def accept(self, event: LitEvent) -> bool:
        with self.database.transaction(write=True) as connection:
            cursor = connection.execute('''
                INSERT INTO ledger VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(show, screen, sequence) DO NOTHING
            ''', (event.show, event.screen, event.sequence, event.cue, event.segment,
                  event.revision, json.dumps(event.lines, ensure_ascii=False)))
            return cursor.rowcount == 1

    def list_for_screen(self, show: str, screen: str) -> list[LitEvent]:
        with self.database.transaction() as connection:
            rows = connection.execute('''
                SELECT * FROM ledger WHERE show = ? AND screen = ? ORDER BY rowid
            ''', (show, screen)).fetchall()
        return [LitEvent.from_row(row) for row in rows]
