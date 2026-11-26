import json
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
from urllib.parse import urlencode

from control.http_api import make_handler, request_json
from control.runtime import LocalScreenLink, build_runtime


EXAMPLES = Path(__file__).resolve().parent.parent / 'examples'


def example(name):
    return json.loads((EXAMPLES / f'{name}.json').read_text(encoding='utf-8'))


def event(sequence, cue, segment, revision):
    return {'sequence': sequence, 'cue': cue, 'segment': segment, 'revision': revision}


class ControlledScreen(LocalScreenLink):
    def __init__(self, state):
        super().__init__(state)
        self.paused_segments = set()
        self.waiting = {}
        self.hidden_segments = set()
        self.paused_cutovers = set()
        self.hidden_cutovers = set()

    def send_segment(self, command):
        identity = (command.show, command.screen, command.cue, command.segment)
        if identity in self.paused_segments:
            commands = self.waiting.setdefault(identity, [])
            if command not in commands:
                commands.append(command)
            return
        super().send_segment(command)

    def release_segment(self, identity):
        queued = self.waiting.pop(identity)
        self.paused_segments.remove(identity)
        for command in queued:
            super().send_segment(command)

    def find_segment(self, show, screen, cue, segment):
        if (show, screen, cue, segment) in self.hidden_segments:
            return None
        return super().find_segment(show, screen, cue, segment)

    def list_events(self, show, screen):
        return [result for result in super().list_events(show, screen)
                if (result.show, result.screen, result.cue, result.segment) not in self.hidden_segments]

    def apply_cutover(self, receipt):
        if (receipt.show, receipt.screen, receipt.request) not in self.paused_cutovers:
            super().apply_cutover(receipt)

    def find_cutover(self, show, screen, request):
        if (show, screen, request) in self.hidden_cutovers:
            return None
        return super().find_cutover(show, screen, request)


class HTTPCase(unittest.TestCase):
    binding = {'show': 'S7', 'screen': 'P1'}
    first_segment = ('S7', 'P1', 'C17', 1)
    first_correction = ('S7', 'P1', 'Q1')

    def setUp(self):
        directory = TemporaryDirectory(prefix='qingyu-test-')
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        self.server = None
        self.addCleanup(self.stop_server)
        self.start_server()

    def start_server(self, link_factory=ControlledScreen):
        self.app = build_runtime(self.directory, link_factory=link_factory)
        self.screen = self.app.screen
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(self.app))
        self.thread = Thread(target=self.server.serve_forever, kwargs={'poll_interval': 0.02})
        self.thread.start()

    def stop_server(self):
        if self.server is not None:
            self.server.shutdown()
            self.thread.join()
            self.server.server_close()
            self.server = None

    def post(self, path, expected=200, **fields):
        status, body = request_json('127.0.0.1', self.server.server_port, 'POST', path, fields)
        self.assertEqual(status, expected, (path, body))
        return body

    def get(self, path, expected=200, **fields):
        status, body = request_json('127.0.0.1', self.server.server_port,
                                    'GET', path + '?' + urlencode(fields))
        self.assertEqual(status, expected, (path, body))
        return body

    def raw(self, method, path, **fields):
        if method == 'GET':
            return request_json('127.0.0.1', self.server.server_port, method, path + '?' + urlencode(fields))
        return request_json('127.0.0.1', self.server.server_port, method, path, fields)

    def publish(self, data=None):
        return self.post('/publish', 201, **(example('original') if data is None else data))

    def open_example(self):
        old = self.publish()
        new = self.publish(example('amendment'))
        self.post('/open', **self.binding, revision=old['revision'])
        return old['revision'], new['revision']

    def advance(self, cue, segment, expected=200):
        return self.post('/advance', expected, **self.binding, cue=cue, segment=segment)

    def correct(self, revision, request='Q1', expected=200):
        return self.post('/correct', expected, **self.binding, revision=revision, request=request)

    def events(self):
        return self.get('/history', **self.binding)['events']

    def status(self, request='Q1', expected=200):
        return self.get('/correction_status', expected, show=self.binding['show'], request=request)
