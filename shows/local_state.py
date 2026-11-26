from errors import conflict
from shows.lifecycle import Show, ShowPhase, finish_show, start_show
from storage import Database


class ShowStore:
    def __init__(self, database: Database):
        self.database = database
        database.initialize('''
            CREATE TABLE IF NOT EXISTS shows (
                show TEXT PRIMARY KEY,
                phase TEXT NOT NULL CHECK (phase IN ('live', 'closed')),
                screen TEXT NOT NULL,
                initial_revision TEXT NOT NULL
            );
        ''')

    @staticmethod
    def _from_row(row) -> Show:
        return Show(row['show'], ShowPhase(row['phase']), row['screen'], row['initial_revision'])

    def _get(self, connection, show_id: str) -> Show:
        row = connection.execute('SELECT * FROM shows WHERE show = ?', (show_id,)).fetchone()
        return Show(show_id) if row is None else self._from_row(row)

    def get(self, show_id: str) -> Show:
        with self.database.transaction() as connection:
            return self._get(connection, show_id)

    def save_open(self, proposed: Show) -> Show:
        with self.database.transaction(write=True) as connection:
            current = self._get(connection, proposed.show)
            opened = start_show(current, proposed.screen, proposed.initial_revision)
            if current.phase == ShowPhase.UNSTARTED:
                connection.execute('INSERT INTO shows VALUES (?, ?, ?, ?)', (
                    opened.show, opened.phase, opened.screen, opened.initial_revision,
                ))
            return opened

    def save_closed(self, proposed: Show) -> Show:
        with self.database.transaction(write=True) as connection:
            closed = finish_show(self._get(connection, proposed.show))
            if closed != proposed:
                raise conflict('show binding changed during closing')
            connection.execute('UPDATE shows SET phase = ? WHERE show = ?', (closed.phase, closed.show))
            return closed

    def list_live(self) -> list[Show]:
        with self.database.transaction() as connection:
            rows = connection.execute('SELECT * FROM shows WHERE phase = ?', (ShowPhase.LIVE,)).fetchall()
        return [self._from_row(row) for row in rows]
