from collections.abc import Iterable

from display.outcomes import LitEvent


def build_show_history(events: Iterable[LitEvent]) -> list[dict]:
    return [
        {'sequence': event.sequence, 'cue': event.cue, 'segment': event.segment, 'revision': event.revision}
        for event in sorted(events, key=lambda event: event.sequence)
    ]
