from display.local_state import ScreenStateStore
from editions.revisions import FrozenEdition, check_compatibility
from errors import conflict, missing


class Cutover:
    def __init__(self, state: ScreenStateStore):
        self.state = state

    def prepare(self, show: str, screen: str, request: str, edition: FrozenEdition, epoch: int) -> None:
        with self.state.transaction() as connection:
            session = self.state.session(connection, show, screen)
            prior = self.state.cutover_row(connection, show, screen, request)
            if prior is not None:
                if (prior['revision'], prior['epoch']) != (edition.revision, epoch):
                    raise conflict('screen correction request has different content')
                return
            if session['closed']:
                raise conflict('the screen session is closed')
            initial = self.state.edition(connection, session['initial_revision'])
            check_compatibility(initial, edition)
            self.state.remember_edition(connection, edition)
            self.state.insert_cutover(connection, show, screen, request, edition.revision, epoch)

    def apply(self, show: str, screen: str, request: str) -> None:
        with self.state.transaction() as connection:
            session = self.state.session(connection, show, screen)
            prepared = self.state.cutover_row(connection, show, screen, request)
            if prepared is None:
                raise missing('correction has not been prepared on this screen')
            if session['closed']:
                raise conflict('the screen session is closed')
            if prepared['applied']:
                return
            self.state.mark_cutover_applied(
                connection, show, screen, request, prepared['epoch']
            )
