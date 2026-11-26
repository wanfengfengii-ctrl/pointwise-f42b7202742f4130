from tests.support import ControlledScreen, HTTPCase, event


class TestRecovery(HTTPCase):
    def test_restart_pending(self):
        old, new = self.open_example()
        self.screen.hidden_segments.add(self.first_segment)
        self.advance('C17', 1, 202)
        self.screen.hidden_cutovers.add(self.first_correction)
        pending = self.correct(new, expected=202)
        self.assertEqual(self.status(expected=202), pending)
        self.stop_server()

        def restarted_screen(state):
            link = ControlledScreen(state)
            link.hidden_cutovers.add(self.first_correction)
            return link

        self.start_server(restarted_screen)
        self.assertEqual(self.status(expected=202), pending)
        self.assertEqual(self.events(), [event(1, 'C17', 1, old)])
        self.assertEqual(self.advance('C17', 2)['revision'], old)
        self.screen.hidden_cutovers.clear()
        confirmed = self.status()
        self.assertEqual((confirmed['request'], confirmed['epoch'], confirmed['revision']), ('Q1', 1, new))
        self.assertEqual(self.correct(new), confirmed)
        self.assertEqual(self.advance('C18', 1)['revision'], new)
        self.assertEqual(self.events(), [event(1, 'C17', 1, old), event(2, 'C17', 2, old), event(3, 'C18', 1, new)])

    def test_retry_prepared_correction_after_reassembly(self):
        old, new = self.open_example()
        self.advance('C17', 1)
        self.screen.paused_cutovers.add(self.first_correction)
        self.correct(new, expected=202)
        self.assertIsNone(self.screen.outcomes.find_cutover(*self.first_correction))
        self.stop_server()
        self.start_server()
        self.status(expected=202)
        self.assertEqual(self.correct(new)['status'], 'confirmed')
        self.assertEqual(self.advance('C17', 2)['revision'], old)
        self.assertEqual(self.advance('C18', 1)['revision'], new)

    def test_recover_close_committed_at_screen(self):
        old, _ = self.open_example()
        self.advance('C17', 1)
        self.screen.state.close_session('S7', 'P1')
        self.stop_server()
        self.start_server()
        self.advance('C17', 2, 409)
        self.assertEqual(self.app.shows.get('S7').phase, 'closed')
        self.assertEqual(self.events(), [event(1, 'C17', 1, old)])
