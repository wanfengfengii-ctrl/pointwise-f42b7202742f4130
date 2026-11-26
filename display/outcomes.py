import json
from dataclasses import dataclass

from display.local_state import ScreenStateStore


@dataclass(frozen=True)
class LitEvent:
    show: str
    screen: str
    sequence: int
    cue: str
    segment: int
    revision: str
    lines: tuple[str, ...]

    @classmethod
    def from_row(cls, row):
        return cls(row['show'], row['screen'], row['sequence'], row['cue'], row['segment'],
                   row['revision'], tuple(json.loads(row['lines'])))


@dataclass(frozen=True)
class CutoverOutcome:
    show: str
    screen: str
    request: str
    revision: str
    epoch: int


class ScreenOutcomes:
    def __init__(self, state: ScreenStateStore):
        self.state = state

    def find_segment(self, show: str, screen: str, cue: str, segment: int) -> LitEvent | None:
        row = self.state.read_segment(show, screen, cue, segment)
        return None if row is None else LitEvent.from_row(row)

    def find_cutover(self, show: str, screen: str, request: str) -> CutoverOutcome | None:
        row = self.state.read_cutover(show, screen, request)
        if row is None:
            return None
        return CutoverOutcome(row['show'], row['screen'], row['request'], row['revision'], row['epoch'])

    def list_events(self, show: str, screen: str) -> list[LitEvent]:
        return [LitEvent.from_row(row) for row in self.state.read_events(show, screen)]
