from dataclasses import dataclass

from errors import invalid, name, positive


@dataclass(frozen=True)
class ScriptCue:
    cue: str
    order: int
    segments: tuple[str, ...]


def parse_script(raw) -> tuple[ScriptCue, ...]:
    if not isinstance(raw, list) or not raw:
        raise invalid('cues must be a nonempty list')
    seen = set()
    previous_order = 0
    script = []
    for row in raw:
        if not isinstance(row, dict):
            raise invalid('each cue must be an object')
        cue = name(row.get('cue'), 'cue')
        order = positive(row.get('order'), 'order')
        segments = row.get('segments')
        if cue in seen:
            raise invalid(f'duplicate cue {cue}')
        if order <= previous_order:
            raise invalid('cue order must increase in submission order')
        if not isinstance(segments, list) or not 1 <= len(segments) <= 2:
            raise invalid(f'{cue} must have one or two segments')
        if any(not isinstance(text, str) or not text.strip() for text in segments):
            raise invalid(f'{cue} contains a missing or blank segment')
        script.append(ScriptCue(cue, order, tuple(segments)))
        seen.add(cue)
        previous_order = order
    return tuple(script)
