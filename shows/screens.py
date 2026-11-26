from dataclasses import dataclass
from typing import Iterable

from errors import missing, name, positive
from storage import Database


@dataclass(frozen=True)
class Screen:
    screen: str
    width: int

    def __post_init__(self):
        name(self.screen, 'screen')
        positive(self.width, 'screen width')


class ScreenRegistry:
    def __init__(self, database: Database):
        self.database = database
        database.initialize('''
            CREATE TABLE IF NOT EXISTS screens (
                screen TEXT PRIMARY KEY,
                width INTEGER NOT NULL CHECK (width > 0)
            );
        ''')

    def get(self, screen: str) -> Screen:
        with self.database.transaction() as connection:
            row = connection.execute('SELECT width FROM screens WHERE screen = ?', (screen,)).fetchone()
        if row is None:
            raise missing(f'unknown screen {screen}')
        return Screen(screen, row['width'])

    def add_missing(self, screens: Iterable[Screen]) -> None:
        with self.database.transaction(write=True) as connection:
            connection.executemany(
                'INSERT INTO screens VALUES (?, ?) ON CONFLICT(screen) DO NOTHING',
                ((screen.screen, screen.width) for screen in screens),
            )
