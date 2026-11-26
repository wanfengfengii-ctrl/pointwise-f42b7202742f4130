from dataclasses import dataclass

from display.local_state import ScreenStateStore
from display.outcomes import LitEvent
from display.preload import PreloadBuffer
from editions.revisions import FrozenEdition
from errors import conflict


@dataclass(frozen=True)
class DisplayCommand:
    show: str
    screen: str
    cue: str
    segment: int
    revision: str | None = None


def _next_segment(edition: FrozenEdition, last) -> tuple[str, int] | None:
    if last is None:
        return edition.cues[0].cue, 1
    for index, cue in enumerate(edition.cues):
        if cue.cue != last['cue']:
            continue
        if last['segment'] < len(cue.segments):
            return cue.cue, last['segment'] + 1
        if index + 1 < len(edition.cues):
            return edition.cues[index + 1].cue, 1
        return None
    raise RuntimeError('screen event references a cue outside the bound edition')


class Playback:
    def __init__(self, state: ScreenStateStore, preloads: PreloadBuffer):
        self.state = state
        self.preloads = preloads

    def light(self, command: DisplayCommand) -> LitEvent:
        show, screen = command.show, command.screen
        cue, segment = command.cue, command.segment
        with self.state.transaction() as connection:
            session = self.state.session(connection, show, screen)
            if session['closed']:
                raise conflict('the screen session is closed')
            previous = self.state.segment_row(connection, show, screen, cue, segment)
            if previous is not None:
                return LitEvent.from_row(previous)
            last = self.state.last_event(connection, show, screen)
            initial = self.state.edition(connection, session['initial_revision'])
            if _next_segment(initial, last) != (cue, segment):
                raise conflict('requested segment is out of playback order')
            revision = session['active_revision']
            edition = self.state.edition(connection, revision)
            candidate = self.preloads.get(show, screen, cue, segment, revision)
            segment_data = candidate if candidate is not None else edition.get_segment(cue, segment)
            sequence = 1 if last is None else last['sequence'] + 1
            self.state.insert_event(connection, show, screen, sequence, cue, segment, revision, segment_data.lines)
            event = LitEvent(show, screen, sequence, cue, segment, revision, segment_data.lines)
        self.preloads.discard(show, screen, cue, segment)
        return event
