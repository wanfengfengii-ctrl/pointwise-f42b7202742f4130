from tests.support import HTTPCase, event


class TestPlayback(HTTPCase):
    def test_preview_is_not_display(self):
        old, _ = self.open_example()
        first = self.get('/preview', **self.binding, cue='C17', segment=1)
        second = self.get('/preview', **self.binding, cue='C17', segment=2)
        self.assertEqual(first['segments'], [{'segment': 1, 'lines': ['稍候', '开灯']}])
        self.assertEqual(second['segments'], [{'segment': 2, 'lines': ['请入座']}])
        self.assertEqual(self.events(), [])
        self.assertIsNone(self.app.receipts.get_progress(*self.first_segment))
        self.assertEqual(self.advance('C17', 1)['lines'], ['稍候', '开灯'])
        self.assertEqual(self.advance('C17', 2)['lines'], ['请入座'])
        self.assertEqual(self.events(), [event(1, 'C17', 1, old), event(2, 'C17', 2, old)])

    def test_segment_order(self):
        old, _ = self.open_example()
        self.advance('C17', 2, 409)
        self.advance('C18', 1, 409)
        self.assertEqual(self.events(), [])
        self.advance('C17', 1)
        self.advance('C18', 1, 409)
        self.advance('C17', 2)
        self.advance('C18', 1)
        self.assertEqual(self.events(), [event(1, 'C17', 1, old), event(2, 'C17', 2, old), event(3, 'C18', 1, old)])

    def test_result_identity(self):
        old, _ = self.open_example()
        self.screen.paused_segments.add(self.first_segment)
        pending = self.advance('C17', 1, 202)
        self.assertEqual(pending, {'status': 'pending', 'show': 'S7', 'screen': 'P1',
                                   'cue': 'C17', 'segment': 1, 'revision': None, 'sequence': None, 'lines': None})
        self.assertEqual(self.events(), [])
        self.screen.release_segment(self.first_segment)
        lit = self.advance('C17', 1)
        self.assertEqual(lit, {'status': 'lit', 'show': 'S7', 'screen': 'P1', 'cue': 'C17',
                              'segment': 1, 'revision': old, 'sequence': 1, 'lines': ['稍候', '开灯']})
        self.assertEqual(self.advance('C17', 1), lit)
        self.get('/history', 404, show='S7', screen='P2')
        self.post('/open', show='S8', screen='P1', revision=old)
        self.assertEqual(self.get('/history', show='S8', screen='P1')['events'], [])
        self.assertIsNone(self.app.receipts.get_progress('S8', 'P1', 'C17', 1))
