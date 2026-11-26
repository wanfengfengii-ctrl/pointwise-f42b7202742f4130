import json

from errors import BusinessError
from tests.support import HTTPCase, event, example


class TestCorrections(HTTPCase):
    def test_cutover_between_cues(self):
        old, new = self.open_example()
        self.advance('C17', 1)
        self.advance('C17', 2)
        self.assertEqual(self.correct(new)['status'], 'confirmed')
        self.assertEqual(self.advance('C18', 1)['revision'], new)
        self.assertEqual(self.post('/close', show='S7')['phase'], 'closed')
        self.advance('C18', 1, 409)
        self.get('/preview', 409, **self.binding, cue='C18')
        self.correct(old, request='Q2', expected=409)
        self.assertEqual(self.events(), [event(1, 'C17', 1, old), event(2, 'C17', 2, old), event(3, 'C18', 1, new)])
        self.get('/history', 404, show='S7', screen='P9')
        self.get('/history', 404, show='S9', screen='P1')
        self.post('/close', 404, show='S9')

    def test_shape_compatibility(self):
        old, new = self.open_example()
        variants = []
        renamed = example('amendment')
        renamed['cues'][1]['cue'] = 'C19'
        variants.append(renamed)
        reordered = example('amendment')
        reordered['cues'].reverse()
        reordered['cues'][0]['order'] = 17
        reordered['cues'][1]['order'] = 18
        variants.append(reordered)
        resegmented = example('amendment')
        resegmented['cues'][0]['segments'].pop()
        variants.append(resegmented)
        for index, variant in enumerate(variants, 1):
            request = f'bad-{index}'
            bad = self.publish(variant)['revision']
            self.correct(bad, request=request, expected=400)
            self.status(request, expected=404)
        self.assertEqual(self.advance('C17', 1)['revision'], old)
        self.assertEqual(self.correct(new)['revision'], new)
        self.assertEqual(self.advance('C17', 2)['revision'], old)
        self.assertEqual(self.advance('C18', 1)['lines'], ['右侧入'])

    def test_unlit_old_command(self):
        old, new = self.open_example()
        self.get('/preview', **self.binding, cue='C17')
        self.screen.paused_segments.add(self.first_segment)
        self.advance('C17', 1, 202)
        self.assertEqual(self.screen.waiting[self.first_segment][0].revision, old)
        self.assertEqual(self.events(), [])
        self.correct(new)
        with self.assertRaisesRegex(BusinessError, 'opening command has expired'):
            self.screen.release_segment(self.first_segment)
        self.assertEqual(self.events(), [])
        self.assertEqual(self.advance('C17', 1)['lines'], ['请稍候'])
        self.assertEqual(self.events(), [event(1, 'C17', 1, new)])

    def test_return_to_same_revision_does_not_release_old_command(self):
        old, new = self.open_example()
        self.screen.paused_segments.add(self.first_segment)
        self.advance('C17', 1, 202)
        self.correct(new)
        self.correct(old, request='Q2')
        with self.assertRaisesRegex(BusinessError, 'opening command has expired'):
            self.screen.release_segment(self.first_segment)
        self.assertEqual(self.events(), [])
        self.assertEqual(self.advance('C17', 1)['revision'], old)

    def test_displayed_prefix_lost_reply(self):
        old, new = self.open_example()
        self.screen.hidden_segments.add(self.first_segment)
        self.advance('C17', 1, 202)
        first = self.screen.outcomes.find_segment(*self.first_segment)
        self.assertEqual((first.revision, first.sequence), (old, 1))
        self.assertEqual(self.events(), [])
        self.screen.paused_cutovers.add(self.first_correction)
        self.screen.hidden_cutovers.add(self.first_correction)
        submitted = self.raw('POST', '/correct', **self.binding, revision=new, request='Q1')
        queried = self.raw('GET', '/correction_status', show='S7', request='Q1')
        tail = self.raw('POST', '/advance', **self.binding, cue='C17', segment=2)
        opening = self.raw('POST', '/advance', **self.binding, cue='C18', segment=1)
        self.screen.paused_cutovers.remove(self.first_correction)
        self.screen.hidden_cutovers.remove(self.first_correction)
        retried = self.raw('POST', '/correct', **self.binding, revision=new, request='Q1')
        next_segment = self.raw('POST', '/advance', **self.binding, cue='C18', segment=1)
        before_report = self.events()
        self.app.receive_display(first)
        self.screen.hidden_segments.remove(self.first_segment)
        self.app.receive_display(first)
        after_report = self.events()
        actual = {
            'correction_before_screen': [submitted[0], queried[0]],
            'tail': [tail[0], tail[1].get('revision')], 'early_next': opening[0],
            'correction_after_screen': retried[0], 'next': [next_segment[0], next_segment[1].get('revision')],
            'history_before_report': before_report, 'history_after_report': after_report,
        }
        expected = {
            'correction_before_screen': [202, 202], 'tail': [200, old], 'early_next': 202,
            'correction_after_screen': 200, 'next': [200, new],
            'history_before_report': [event(2, 'C17', 2, old), event(3, 'C18', 1, new)],
            'history_after_report': [event(1, 'C17', 1, old), event(2, 'C17', 2, old), event(3, 'C18', 1, new)],
        }
        self.assertEqual(actual, expected, 'SUBTITLE_CUTOVER_DISPLAY_MISMATCH')
        self.assertEqual([record.sequence for record in self.app.ledger.list_for_screen('S7', 'P1')], [2, 3, 1])
        print('POINTWISE_SCENARIO ' + json.dumps({
            'case_id': 't7', 'input': {'show': 'S7', 'screen': 'P1', 'request': 'Q1', 'drafts': [old, new],
                                      'delayed_report': ['C17', 1], 'paused_application_during_tail': True},
            'expected': expected['tail'], 'actual': actual['tail'],
            'downstream_expected': expected['history_after_report'],
            'downstream_actual': actual['history_after_report'],
            'code_paths': ['control/corrections.py', 'control/advance.py', 'display/playback.py',
                           'display/cutover.py', 'audit/ingest.py', 'audit/show_summary.py'],
            'oracle': 'C17 started on R1 before Q1. C18 started after Q1. Delivery order is 2, 3, 1, 1.',
        }, ensure_ascii=False))

    def test_pending_does_not_stop_tail(self):
        old, new = self.open_example()
        self.advance('C17', 1)
        self.screen.hidden_cutovers.add(self.first_correction)
        self.assertEqual(self.correct(new, expected=202)['status'], 'pending')
        applied = self.screen.outcomes.find_cutover(*self.first_correction)
        self.assertEqual(applied.revision, new)
        self.assertEqual(self.status(expected=202)['status'], 'pending')
        self.assertEqual(self.advance('C17', 2)['revision'], old)
        self.assertEqual(self.advance('C18', 1, 202)['status'], 'pending')
        self.screen.hidden_cutovers.remove(self.first_correction)
        self.assertEqual(self.correct(new), self.status())
        self.assertEqual(self.advance('C18', 1)['revision'], new)

    def test_replay_after_newer(self):
        old, new = self.open_example()
        self.advance('C17', 1)
        self.screen.hidden_cutovers.add(self.first_correction)
        self.correct(new, expected=202)
        self.screen.hidden_cutovers.clear()
        first = self.status()
        alternate = example('amendment')
        alternate['cues'][1]['segments'] = ['中间入']
        newest = self.publish(alternate)['revision']
        self.correct(newest, request='Q2')
        self.assertEqual(self.correct(new), first)
        self.correct(old, expected=409)
        self.assertEqual(self.status(), first)
        self.assertEqual(self.advance('C17', 2)['revision'], old)
        displayed = self.advance('C18', 1)
        self.assertEqual((displayed['revision'], displayed['lines']), (newest, ['中间入']))
