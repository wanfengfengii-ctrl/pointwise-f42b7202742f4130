from dataclasses import dataclass, replace
from enum import StrEnum

from errors import conflict, missing


class ShowPhase(StrEnum):
    UNSTARTED = 'unstarted'
    LIVE = 'live'
    CLOSED = 'closed'


@dataclass(frozen=True)
class Show:
    show: str
    phase: ShowPhase = ShowPhase.UNSTARTED
    screen: str | None = None
    initial_revision: str | None = None


def start_show(current: Show, screen: str, revision: str) -> Show:
    if current.phase == ShowPhase.UNSTARTED:
        return Show(current.show, ShowPhase.LIVE, screen, revision)
    if current.phase == ShowPhase.LIVE and (current.screen, current.initial_revision) == (screen, revision):
        return current
    raise conflict(f'show {current.show} cannot open with this binding')


def finish_show(current: Show) -> Show:
    if current.phase == ShowPhase.UNSTARTED:
        raise missing(f'unknown show {current.show}')
    return replace(current, phase=ShowPhase.CLOSED)


def require_live_binding(current: Show, screen: str) -> Show:
    if current.phase == ShowPhase.UNSTARTED or current.screen != screen:
        raise missing(f'no show {current.show} bound to screen {screen}')
    if current.phase != ShowPhase.LIVE:
        raise conflict(f'show {current.show} is closed')
    return current
