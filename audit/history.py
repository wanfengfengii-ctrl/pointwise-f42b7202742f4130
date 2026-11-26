from collections.abc import Callable

from audit.ingest import DisplayLedger
from audit.show_summary import build_show_history
from display.outcomes import LitEvent
from errors import missing
from shows.lifecycle import ShowPhase
from shows.local_state import ShowStore


def history(shows: ShowStore, ledger: DisplayLedger, read_events: Callable[[str, str], list[LitEvent]],
            show_id: str, screen: str) -> dict:
    show = shows.get(show_id)
    if show.phase == ShowPhase.UNSTARTED or show.screen != screen:
        raise missing(f'no show {show_id} bound to screen {screen}')
    for event in read_events(show_id, screen):
        if (event.show, event.screen) == (show_id, screen):
            ledger.accept(event)
    return {'show': show_id, 'screen': screen, 'events': build_show_history(ledger.list_for_screen(show_id, screen))}
