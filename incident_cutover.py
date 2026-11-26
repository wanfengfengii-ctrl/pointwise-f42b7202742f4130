import unittest

from tests.support import HTTPCase, event


MARKER = 'QINGYU_CUTOVER_CUE_REVISION'


class CutoverIncident(HTTPCase):
    def test_cutover_applied_but_not_observable(self):
        self.exercise_cutover(applied=True)

    def test_cutover_not_yet_applied(self):
        self.exercise_cutover(applied=False)

    def exercise_cutover(self, *, applied):
        old, new = self.open_example()
        self.screen.hidden_segments.add(self.first_segment)
        self.advance('C17', 1, 202)
        first = self.screen.outcomes.find_segment(*self.first_segment)
        self.assertIsNotNone(first)
        self.assertEqual((first.sequence, first.revision), (1, old))
        self.assertEqual(self.events(), [])

        gate = self.screen.hidden_cutovers if applied else self.screen.paused_cutovers
        gate.add(self.first_correction)
        correction = {**self.binding, 'revision': new, 'request': 'Q1'}
        query = {'show': self.binding['show'], 'request': 'Q1'}
        submitted = self.raw('POST', '/correct', **correction)
        queried = self.raw('GET', '/correction_status', **query)
        tail = self.raw('POST', '/advance', **self.binding, cue='C17', segment=2)
        early_next = self.raw('POST', '/advance', **self.binding, cue='C18', segment=1)
        before_confirmation = self.events()

        gate.remove(self.first_correction)
        if applied:
            confirmed = self.raw('GET', '/correction_status', **query)
        else:
            confirmed = self.raw('POST', '/correct', **correction)
        replayed = self.raw('POST', '/correct', **correction)
        opening = self.raw('POST', '/advance', **self.binding, cue='C18', segment=1)
        before_report = self.events()
        self.app.receive_display(first)
        self.screen.hidden_segments.remove(self.first_segment)
        self.app.receive_display(first)
        after_report = self.events()

        actual = {
            'submitted': (submitted[0], submitted[1].get('status')),
            'queried': (queried[0], queried[1].get('status')),
            'tail': (tail[0], tail[1].get('revision'), tail[1].get('lines')),
            'early_next': (early_next[0], early_next[1].get('status')),
            'before_confirmation': before_confirmation,
            'confirmed': (confirmed[0], confirmed[1].get('status'), confirmed[1].get('revision')),
            'same_receipt_on_retry': replayed == confirmed,
            'opening': (opening[0], opening[1].get('revision'), opening[1].get('lines')),
            'before_delayed_report': before_report,
            'after_delayed_report': after_report,
        }
        tail_event = event(2, 'C17', 2, old)
        next_event = event(3, 'C18', 1, new)
        expected = {
            'submitted': (202, 'pending'),
            'queried': (202, 'pending'),
            'tail': (200, old, ['请入座']),
            'early_next': (202, 'pending'),
            'before_confirmation': [tail_event],
            'confirmed': (200, 'confirmed', new),
            'same_receipt_on_retry': True,
            'opening': (200, new, ['右侧入']),
            'before_delayed_report': [tail_event, next_event],
            'after_delayed_report': [event(1, 'C17', 1, old), tail_event, next_event],
        }
        self.maxDiff = None
        self.assertEqual(actual, expected, MARKER)


if __name__ == '__main__':
    unittest.main(verbosity=2)
