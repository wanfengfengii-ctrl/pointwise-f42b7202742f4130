from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from audit.cue_result import find_cue_result
from display.outcomes import LitEvent
from display.playback import DisplayCommand
from errors import positive

if TYPE_CHECKING:
    from control.runtime import Runtime


@dataclass(frozen=True)
class AdvanceResult:
    status: str
    show: str
    screen: str
    cue: str
    segment: int
    revision: str | None = None
    sequence: int | None = None
    lines: tuple[str, ...] | None = None


def _result(runtime: Runtime, event: LitEvent) -> AdvanceResult:
    runtime.receive_display(event)
    return AdvanceResult('lit', event.show, event.screen, event.cue, event.segment,
                         event.revision, event.sequence, event.lines)


def _screen_fact(runtime: Runtime, identity: tuple) -> LitEvent | None:
    event = runtime.screen.find_segment(*identity)
    if event is not None and (event.show, event.screen, event.cue, event.segment) == identity:
        return event
    return None


def advance(runtime: Runtime, show_id: str, screen: str, cue: str, segment: int) -> AdvanceResult:
    positive(segment, 'segment')
    show = runtime.live_show(show_id, screen)
    runtime.editions.get(show.initial_revision).get_segment(cue, segment)
    identity = (show_id, screen, cue, segment)
    event = runtime.receipts.get_progress(*identity) or find_cue_result(runtime.ledger, *identity)
    event = event or _screen_fact(runtime, identity)
    if event is not None:
        return _result(runtime, event)
    waiting = AdvanceResult('pending', *identity)
    if segment == 1:
        revision, _ = runtime.receipts.opening_revision(show_id, show.initial_revision)
        command = DisplayCommand(*identity, revision)
    else:
        command = DisplayCommand(*identity)
    runtime.screen.send_segment(command)
    event = _screen_fact(runtime, identity)
    return waiting if event is None else _result(runtime, event)
