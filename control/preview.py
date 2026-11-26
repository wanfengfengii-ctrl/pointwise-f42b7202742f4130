from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from audit.cue_result import find_cue_result
from errors import positive

if TYPE_CHECKING:
    from control.runtime import Runtime


@dataclass(frozen=True)
class PreviewSegment:
    segment: int
    lines: tuple[str, ...]


@dataclass(frozen=True)
class PreviewResult:
    show: str
    screen: str
    cue: str
    revision: str
    segments: tuple[PreviewSegment, ...]


def preview(runtime: Runtime, show_id: str, screen: str, cue: str,
            segment: int | None = None) -> PreviewResult:
    show = runtime.live_show(show_id, screen)
    identity = (show_id, screen, cue, 1)
    first = runtime.receipts.get_progress(*identity) or find_cue_result(runtime.ledger, *identity)
    if first is None:
        first = runtime.screen.find_segment(*identity)
    if first is not None and (first.show, first.screen, first.cue, first.segment) == identity:
        revision = first.revision
    else:
        revision, _ = runtime.receipts.opening_revision(show_id, show.initial_revision)
    edition = runtime.editions.get(revision)
    cue_data = edition.get_cue(cue)
    if segment is not None:
        positive(segment, 'segment')
        candidates = [(segment, edition.get_segment(cue, segment))]
    else:
        candidates = list(enumerate(cue_data.segments, 1))
    result = []
    for number, candidate in candidates:
        runtime.screen.preloads.stage(show_id, screen, cue, number, revision, candidate)
        result.append(PreviewSegment(number, candidate.lines))
    return PreviewResult(show_id, screen, cue, revision, tuple(result))
