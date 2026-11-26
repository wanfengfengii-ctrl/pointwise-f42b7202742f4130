from threading import Lock

from editions.layout import DisplaySegment


class PreloadBuffer:
    def __init__(self):
        self._candidates: dict[tuple[str, str, str, int, str], DisplaySegment] = {}
        self._lock = Lock()

    def stage(self, show: str, screen: str, cue: str, segment: int,
              revision: str, candidate: DisplaySegment) -> None:
        with self._lock:
            self._candidates[show, screen, cue, segment, revision] = candidate

    def get(self, show: str, screen: str, cue: str, segment: int,
            revision: str) -> DisplaySegment | None:
        with self._lock:
            return self._candidates.get((show, screen, cue, segment, revision))

    def discard(self, show: str, screen: str, cue: str | None = None,
                segment: int | None = None) -> None:
        with self._lock:
            keys = [key for key in self._candidates
                    if key[:2] == (show, screen) and (cue is None or key[2:4] == (cue, segment))]
            for key in keys:
                del self._candidates[key]
