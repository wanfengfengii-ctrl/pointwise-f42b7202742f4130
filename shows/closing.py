from typing import Callable

from shows.lifecycle import Show, ShowPhase, finish_show
from shows.local_state import ShowStore


def close_show(shows: ShowStore, show_id: str, stop_display: Callable[[Show], None]) -> Show:
    current = shows.get(show_id)
    closed = finish_show(current)
    if current.phase == ShowPhase.LIVE:
        stop_display(current)
    return shows.save_closed(closed)
