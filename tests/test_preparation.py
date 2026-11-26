import json

from editions.layout import display_columns, wrap_segment
from shows.lifecycle import ShowPhase
from tests.support import HTTPCase, example


class TestPreparation(HTTPCase):
    def test_layout_and_open(self):
        script = [{'cue': 'C17', 'order': 17, 'segments': ['abc def', '请入座']}]
        edition = self.post('/publish', 201, width=6, cues=script)
        lines = edition['cues'][0]['segments'][0]['lines']
        self.assertEqual(lines, ['abc', 'def'])
        opened = self.post('/open', **self.binding, revision=edition['revision'])
        self.assertEqual(opened, {'show': 'S7', 'screen': 'P1', 'phase': 'live', 'initial_revision': 'R1'})
        preview = self.get('/preview', **self.binding, cue='C17', segment=1)
        self.assertEqual(preview['revision'], 'R1')
        self.assertEqual(preview['segments'], [{'segment': 1, 'lines': ['abc', 'def']}])
        print('POINTWISE_SCENARIO ' + json.dumps({
            'case_id': 't1', 'input': {'width': 6, 'cues': script},
            'expected': ['abc', 'def'], 'actual': lines,
            'downstream_expected': [{'segment': 1, 'lines': ['abc', 'def']}],
            'downstream_actual': preview['segments'],
            'code_paths': ['editions/layout.py', 'shows/binding.py', 'control/preview.py'],
            'oracle': 'Two three-column words and the one-column space need seven columns.',
        }, ensure_ascii=False))

    def test_script_order(self):
        data = example('original')
        data['cues'][0]['cue'] = 'Z'
        data['cues'][1]['cue'] = 'A'
        edition = self.publish(data)
        self.assertEqual([(cue['cue'], cue['order']) for cue in edition['cues']], [('Z', 17), ('A', 18)])
        data['cues'].reverse()
        self.post('/publish', 400, **data)
        data['cues'].reverse()
        data['cues'][1]['cue'] = 'Z'
        self.post('/publish', 400, **data)

    def test_width(self):
        self.assertEqual(display_columns('e\u0301 中'), 4)
        self.assertEqual(wrap_segment('ab中cde', 6), ('ab中cd', 'e'))
        self.assertEqual(wrap_segment('abc def', 7), ('abc def',))
        self.assertEqual(wrap_segment('甲\t乙 abc', 6), ('甲 乙', 'abc'))
        self.assertEqual(wrap_segment('e\u0301e\u0301好', 2), ('e\u0301e\u0301', '好'))
        for invalid_text, width in [('中', 1), ('\u0301a', 6), ('a\x00b', 6), ('  ', 6), ('a', 0), ('a', True)]:
            with self.subTest(text=invalid_text, width=width):
                self.post('/publish', 400, width=width,
                          cues=[{'cue': 'A', 'order': 1, 'segments': [invalid_text]}])

    def test_reject_three_segments(self):
        good = self.publish()
        data = example('original')
        data['cues'][0]['segments'].append('第三段')
        self.post('/publish', 400, **data)
        self.post('/open', 404, show='S0', screen='P1', revision='R2')
        opened = self.post('/open', **self.binding, revision=good['revision'])
        self.assertEqual(opened['initial_revision'], 'R1')

    def test_atomic_publish(self):
        first = self.publish()
        self.post('/publish', 400, width=1, cues=[
            {'cue': 'C17', 'order': 17, 'segments': ['x']},
            {'cue': 'C18', 'order': 18, 'segments': ['中']},
        ])
        self.post('/open', 404, show='S0', screen='P1', revision='R2')
        self.post('/open', **self.binding, revision=first['revision'])
        self.assertEqual(self.publish()['revision'], 'R2')

    def test_unknown_screen(self):
        edition = self.publish()
        self.post('/open', 404, show='S7', screen='X', revision=edition['revision'])
        self.assertEqual(self.app.shows.get('S7').phase, ShowPhase.UNSTARTED)
        self.post('/open', 404, **self.binding, revision='R9')
        self.assertEqual(self.app.shows.get('S7').phase, ShowPhase.UNSTARTED)
        self.assertEqual(self.post('/open', **self.binding, revision=edition['revision'])['screen'], 'P1')
