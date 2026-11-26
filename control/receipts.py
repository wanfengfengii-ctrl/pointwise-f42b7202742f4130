import json
from dataclasses import dataclass

from display.outcomes import LitEvent
from errors import conflict, missing
from storage import Database


@dataclass(frozen=True)
class CorrectionReceipt:
    show: str
    screen: str
    request: str
    revision: str
    epoch: int
    status: str

    @classmethod
    def from_row(cls, row):
        return cls(row['show'], row['screen'], row['request'], row['revision'], row['epoch'], row['status'])


class ReceiptStore:
    def __init__(self, database: Database):
        self.database = database
        database.initialize('''
            CREATE TABLE IF NOT EXISTS corrections (
                show TEXT NOT NULL,
                screen TEXT NOT NULL,
                request TEXT NOT NULL,
                revision TEXT NOT NULL,
                epoch INTEGER NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('pending', 'confirmed')),
                PRIMARY KEY (show, request),
                UNIQUE (show, epoch)
            );
            CREATE TABLE IF NOT EXISTS segment_receipts (
                show TEXT NOT NULL,
                screen TEXT NOT NULL,
                sequence INTEGER NOT NULL,
                cue TEXT NOT NULL,
                segment INTEGER NOT NULL,
                revision TEXT NOT NULL,
                lines TEXT NOT NULL,
                PRIMARY KEY (show, screen, cue, segment)
            );
        ''')

    @staticmethod
    def _find(connection, show: str, request: str) -> CorrectionReceipt | None:
        row = connection.execute('SELECT * FROM corrections WHERE show = ? AND request = ?',
                                 (show, request)).fetchone()
        return None if row is None else CorrectionReceipt.from_row(row)

    def accept_correction(self, show: str, screen: str, request: str, revision: str) -> CorrectionReceipt:
        with self.database.transaction(write=True) as connection:
            received = self._find(connection, show, request)
            if received is not None:
                if (received.screen, received.revision) != (screen, revision):
                    raise conflict('correction request already has a different screen or revision')
                return received
            epoch = connection.execute(
                'SELECT COALESCE(MAX(epoch), 0) + 1 FROM corrections WHERE show = ?', (show,)
            ).fetchone()[0]
            receipt = CorrectionReceipt(show, screen, request, revision, epoch, 'pending')
            connection.execute('INSERT INTO corrections VALUES (?, ?, ?, ?, ?, ?)',
                               (show, screen, request, revision, epoch, receipt.status))
            return receipt

    def get_correction(self, show: str, request: str, *, required: bool = True) -> CorrectionReceipt | None:
        with self.database.transaction() as connection:
            receipt = self._find(connection, show, request)
        if receipt is None and required:
            raise missing(f'unknown correction request {request} for show {show}')
        return receipt

    def record_dispatch(self, show: str, request: str) -> CorrectionReceipt:
        with self.database.transaction(write=True) as connection:
            connection.execute('''
                UPDATE corrections SET status = 'confirmed' WHERE show = ? AND request = ?
            ''', (show, request))
            return self._find(connection, show, request)

    def pending(self, show: str) -> list[CorrectionReceipt]:
        with self.database.transaction() as connection:
            rows = connection.execute('''
                SELECT * FROM corrections WHERE show = ? AND status = 'pending' ORDER BY epoch
            ''', (show,)).fetchall()
        return [CorrectionReceipt.from_row(row) for row in rows]

    def opening_revision(self, show: str, initial: str) -> tuple[str, int]:
        with self.database.transaction() as connection:
            row = connection.execute('''
                SELECT revision, epoch FROM corrections WHERE show = ? AND status = 'confirmed'
                ORDER BY epoch DESC LIMIT 1
            ''', (show,)).fetchone()
        return (initial, 0) if row is None else (row['revision'], row['epoch'])

    def get_progress(self, show: str, screen: str, cue: str, segment: int) -> LitEvent | None:
        with self.database.transaction() as connection:
            row = connection.execute('''
                SELECT * FROM segment_receipts WHERE show = ? AND screen = ? AND cue = ? AND segment = ?
            ''', (show, screen, cue, segment)).fetchone()
        return None if row is None else LitEvent.from_row(row)

    def record_display_result(self, event: LitEvent) -> None:
        with self.database.transaction(write=True) as connection:
            connection.execute('''
                INSERT INTO segment_receipts VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(show, screen, cue, segment) DO NOTHING
            ''', (event.show, event.screen, event.sequence, event.cue, event.segment,
                  event.revision, json.dumps(event.lines, ensure_ascii=False)))
