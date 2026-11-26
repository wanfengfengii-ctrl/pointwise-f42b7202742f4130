from dataclasses import dataclass

from editions.layout import DisplayCue, DisplaySegment, layout_script
from editions.script import parse_script
from errors import invalid, missing


@dataclass(frozen=True)
class FrozenEdition:
    revision: str
    width: int
    cues: tuple[DisplayCue, ...]

    @property
    def shape(self) -> tuple:
        return tuple((cue.cue, cue.order, len(cue.segments)) for cue in self.cues)

    def get_cue(self, cue_id: str) -> DisplayCue:
        for cue in self.cues:
            if cue.cue == cue_id:
                return cue
        raise missing(f'unknown cue {cue_id}')

    def get_segment(self, cue_id: str, number: int) -> DisplaySegment:
        cue = self.get_cue(cue_id)
        if not 1 <= number <= len(cue.segments):
            raise invalid(f'unknown segment {number} in {cue_id}')
        return cue.segments[number - 1]


def build_edition(revision: str, width: int, cues) -> FrozenEdition:
    return FrozenEdition(revision, width, layout_script(parse_script(cues), width))


def check_compatibility(original: FrozenEdition, target: FrozenEdition) -> None:
    if original.shape != target.shape:
        raise invalid('a correction must preserve cue identifiers, order and segment counts')


def restore_edition(data: dict) -> FrozenEdition:
    cues = tuple(
        DisplayCue(row['cue'], row['order'], tuple(
            DisplaySegment(segment['text'], tuple(segment['lines']))
            for segment in row['segments']
        )) for row in data['cues']
    )
    return FrozenEdition(data['revision'], data['width'], cues)
