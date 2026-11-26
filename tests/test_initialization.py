import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from control.runtime import build_runtime, load_screen_manifest
from errors import BusinessError
from tests.support import HTTPCase, event


class TestInitialization(HTTPCase):
    def test_repeat_init(self):
        old, new = self.open_example()
        self.advance('C17', 1)
        confirmation = self.correct(new)
        with self.app.screens.database.transaction(write=True) as connection:
            connection.execute('UPDATE screens SET width = ? WHERE screen = ?', (9, 'P1'))
        self.stop_server()
        self.start_server()
        self.assertEqual(self.app.screens.get('P1').width, 9)
        with self.app.screens.database.transaction() as connection:
            screens = connection.execute('SELECT screen, width FROM screens ORDER BY screen').fetchall()
            self.assertEqual([tuple(row) for row in screens], [('P1', 9)])
        self.post('/open', 404, show='S8', screen='P9', revision=old)
        self.assertEqual(self.status(), confirmation)
        self.assertEqual(self.events(), [event(1, 'C17', 1, old)])
        self.assertEqual(self.publish()['revision'], 'R3')


class TestScreenManifest(unittest.TestCase):
    def test_new_defaults_only_fill_missing_screens(self):
        with TemporaryDirectory(prefix='qingyu-config-') as directory:
            root = Path(directory)
            manifest = root / 'screens.json'
            manifest.write_text(json.dumps({'screens': [{'screen': 'P1', 'width': 8}]}), encoding='utf-8')
            first = build_runtime(root / 'data', load_screen_manifest(manifest))
            self.assertEqual(first.screens.get('P1').width, 8)
            manifest.write_text(json.dumps({'screens': [
                {'screen': 'P1', 'width': 6}, {'screen': 'P2', 'width': 10},
            ]}), encoding='utf-8')
            second = build_runtime(root / 'data', load_screen_manifest(manifest))
            self.assertEqual((second.screens.get('P1').width, second.screens.get('P2').width), (8, 10))
            with self.assertRaises(BusinessError):
                second.editions.get('R1')
