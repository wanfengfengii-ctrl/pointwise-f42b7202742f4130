from http.client import HTTPConnection

from tests.support import HTTPCase, event


class TestHTTP(HTTPCase):
    def test_public_route_errors_preserve_display(self):
        old, _ = self.open_example()
        self.get('/preview', 404, **self.binding, cue='missing')
        self.get('/preview', 400, **self.binding, cue='C17', segment='x')
        self.get('/correction_status', 404, show='S7', request='unknown')
        self.post('/advance', 400, **self.binding, cue='C17', segment=True)
        self.post('/advance', 400, **self.binding, cue='C17', segment=3)
        self.get('/not-an-endpoint', 404)
        self.assertEqual(self.events(), [])
        connection = HTTPConnection('127.0.0.1', self.server.server_port, timeout=10)
        try:
            connection.request('POST', '/publish', b'{malformed')
            response = connection.getresponse()
            self.assertEqual(response.status, 400)
            self.assertIn(b'invalid_request', response.read())
        finally:
            connection.close()
        self.assertEqual(self.advance('C17', 1)['revision'], old)
        self.post('/close', show='S7')
        self.assertEqual(self.events(), [event(1, 'C17', 1, old)])

    def test_old_queued_segment_cannot_light_after_close(self):
        self.open_example()
        self.screen.paused_segments.add(self.first_segment)
        self.advance('C17', 1, 202)
        self.post('/close', show='S7')
        from errors import BusinessError
        with self.assertRaisesRegex(BusinessError, 'screen session is closed'):
            self.screen.release_segment(self.first_segment)
        self.assertEqual(self.events(), [])
