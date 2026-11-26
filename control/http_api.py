from __future__ import annotations

import json
from dataclasses import asdict
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import TYPE_CHECKING
from urllib.parse import parse_qs, urlsplit

from audit.history import history
from control.advance import advance
from control.corrections import correct, correction_status
from control.preview import preview
from errors import BusinessError, invalid, missing, name
from shows.binding import open_show
from shows.closing import close_show

if TYPE_CHECKING:
    from control.runtime import Runtime


def _dispatch(runtime: Runtime, method: str, path: str, data: dict) -> tuple[int, dict]:
    if (method, path) == ('GET', '/health'):
        return 200, {'ready': True}
    if (method, path) == ('POST', '/publish'):
        return 201, asdict(runtime.editions.publish(data.get('width'), data.get('cues')))
    if (method, path) == ('POST', '/open'):
        show = open_show(runtime.shows, runtime.screens, runtime.editions,
                         name(data.get('show'), 'show'), name(data.get('screen'), 'screen'),
                         name(data.get('revision'), 'revision'))
        runtime.ensure_screen(show)
        return 200, asdict(show)
    if (method, path) == ('POST', '/close'):
        return 200, asdict(close_show(runtime.shows, name(data.get('show'), 'show'), runtime.stop_screen))
    if (method, path) == ('GET', '/correction_status'):
        result = correction_status(runtime, name(data.get('show'), 'show'), name(data.get('request'), 'request'))
        return (202 if result.status == 'pending' else 200), asdict(result)
    if (method, path) not in {('GET', '/preview'), ('GET', '/history'),
                              ('POST', '/advance'), ('POST', '/correct')}:
        raise missing('unknown HTTP endpoint')
    show = name(data.get('show'), 'show')
    screen = name(data.get('screen'), 'screen')
    if path == '/history':
        return 200, history(runtime.shows, runtime.ledger, runtime.screen.list_events, show, screen)
    if path == '/preview':
        value = data.get('segment')
        try:
            segment = None if value is None else int(value)
        except ValueError as error:
            raise invalid('segment must be a positive integer') from error
        return 200, asdict(preview(runtime, show, screen, name(data.get('cue'), 'cue'), segment))
    if path == '/advance':
        result = advance(runtime, show, screen, name(data.get('cue'), 'cue'), data.get('segment'))
    else:
        result = correct(runtime, show, screen, name(data.get('revision'), 'revision'),
                         name(data.get('request'), 'request'))
    return (202 if result.status == 'pending' else 200), asdict(result)


def make_handler(runtime: Runtime) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def _fields(self, query: str) -> dict:
            if self.command == 'GET':
                fields = parse_qs(query, keep_blank_values=True)
                if any(len(values) != 1 for values in fields.values()):
                    raise invalid('query fields must occur once')
                return {field: values[0] for field, values in fields.items()}
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if length <= 0:
                    raise ValueError('no request body')
                data = json.loads(self.rfile.read(length).decode('utf-8'))
            except (ValueError, OverflowError, RecursionError) as error:
                raise invalid('body must be a UTF-8 JSON object') from error
            if not isinstance(data, dict):
                raise invalid('body must be a UTF-8 JSON object')
            return data

        def _respond(self) -> None:
            try:
                try:
                    url = urlsplit(self.path)
                except ValueError as error:
                    raise invalid('invalid request URL') from error
                fields = self._fields(url.query)
                with runtime.operator_lock:
                    status, body = _dispatch(runtime, self.command, url.path, fields)
            except BusinessError as error:
                status, body = error.status, {'error': error.code, 'message': str(error)}
            payload = json.dumps(body, ensure_ascii=False).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self) -> None:
            self._respond()

        def do_POST(self) -> None:
            self._respond()

        def log_message(self, format, *args) -> None:
            # The API returns domain errors in the response body.
            return

    return Handler


def serve(runtime: Runtime, host: str, port: int) -> None:
    with ThreadingHTTPServer((host, port), make_handler(runtime)) as server:
        server.serve_forever()


def request_json(host: str, port: int, method: str, target: str,
                 fields: dict | None = None) -> tuple[int, dict]:
    client = HTTPConnection(host, port, timeout=10)
    try:
        body = None if fields is None else json.dumps(fields, ensure_ascii=False).encode('utf-8')
        headers = {} if body is None else {'Content-Type': 'application/json; charset=utf-8'}
        client.request(method, target, body=body, headers=headers)
        response = client.getresponse()
        return response.status, json.loads(response.read())
    finally:
        client.close()
