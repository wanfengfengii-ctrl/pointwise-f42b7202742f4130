from editions.catalog import EditionCatalog
from shows.lifecycle import Show, start_show
from shows.local_state import ShowStore
from shows.screens import ScreenRegistry


def open_show(shows: ShowStore, screens: ScreenRegistry, editions: EditionCatalog,
              show_id: str, screen_id: str, revision: str) -> Show:
    screen = screens.get(screen_id)
    edition = editions.get(revision)
    proposed = start_show(shows.get(show_id), screen.screen, edition.revision)
    return shows.save_open(proposed)
