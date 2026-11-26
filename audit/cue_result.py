from audit.ingest import DisplayLedger
from display.outcomes import LitEvent


def find_cue_result(ledger: DisplayLedger, show: str, screen: str,
                    cue: str, segment: int) -> LitEvent | None:
    for event in ledger.list_for_screen(show, screen):
        if (event.show, event.screen, event.cue, event.segment) == (show, screen, cue, segment):
            return event
    return None
