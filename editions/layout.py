from dataclasses import dataclass
from unicodedata import category, east_asian_width

from editions.script import ScriptCue
from errors import invalid, positive


@dataclass(frozen=True)
class DisplaySegment:
    text: str
    lines: tuple[str, ...]


@dataclass(frozen=True)
class DisplayCue:
    cue: str
    order: int
    segments: tuple[DisplaySegment, ...]


def _character_units(text: str):
    unit = []
    columns = 0
    for character in text:
        kind = category(character)[0]
        if kind == 'M':
            if not unit or unit[0] == ' ':
                raise invalid('a combining mark needs a preceding base character')
            unit.append(character)
            continue
        if kind == 'C' or (character.isspace() and character != ' '):
            raise invalid(f'character U+{ord(character):04X} cannot be displayed')
        if unit:
            yield ''.join(unit), columns
        unit = [character]
        columns = 2 if east_asian_width(character) in ('W', 'F') else 1
    if unit:
        yield ''.join(unit), columns


def display_columns(line: str) -> int:
    return sum(columns for _, columns in _character_units(line))


def _hard_wrap(units, width: int):
    pieces = []
    columns = 0
    for text, size in units:
        if size > width:
            raise invalid('a character unit exceeds the screen width')
        if columns + size > width:
            yield ''.join(pieces), columns
            pieces = []
            columns = 0
        pieces.append(text)
        columns += size
    if pieces:
        yield ''.join(pieces), columns


def wrap_segment(text: str, width: int) -> tuple[str, ...]:
    positive(width, 'width')
    if not isinstance(text, str) or not text.strip():
        raise invalid('segment must contain displayable text')
    if any(character in '\x1c\x1d\x1e\x1f' for character in text):
        raise invalid('segment contains an unsupported control character')
    lines = []
    row = []
    columns = 0
    for word in text.split():
        units = tuple(_character_units(word))
        size = sum(unit_width for _, unit_width in units)
        if row and columns + 1 + size > width:
            lines.append(' '.join(row))
            row = []
            columns = 0
        if size > width:
            chunks = list(_hard_wrap(units, width))
            lines.extend(piece for piece, _ in chunks[:-1])
            last_piece, columns = chunks[-1]
            row = [last_piece]
        else:
            columns += size + bool(row)
            row.append(word)
    lines.append(' '.join(row))
    return tuple(lines)


def layout_script(script: tuple[ScriptCue, ...], width: int) -> tuple[DisplayCue, ...]:
    positive(width, 'width')
    return tuple(
        DisplayCue(cue.cue, cue.order, tuple(
            DisplaySegment(text, wrap_segment(text, width)) for text in cue.segments
        )) for cue in script
    )
