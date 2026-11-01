"""Simulated network failures only; nothing here sends radio packets."""
import json
import sys
import types
import unittest
from threading import Event
from unittest.mock import patch

from librebeacon.mesh_stream import (
    ReplyHeartbeat, PING_INTERVAL_SECONDS, PING_TIMEOUT_SECONDS,
    listen_for_replies, websocket_url,
)


class HeartbeatTests(unittest.TestCase):
    def test_ping_after_quiet_interval(self):
        hb = ReplyHeartbeat(100)
        self.assertIsNone(hb.due(100 + PING_INTERVAL_SECONDS - .01))
        self.assertEqual(hb.due(100 + PING_INTERVAL_SECONDS), 2)
        self.assertIsNone(hb.due(121))
        self.assertTrue(hb.observe({'type': 'pong', 'id': 2}, 122))
        self.assertEqual(hb.due(142), 3)

    def test_wrong_pong_is_not_a_keepalive(self):
        hb = ReplyHeartbeat(100)
        hb.due(120)
        for frame in ({'type': 'pong', 'id': 1}, {'type': 'pong', 'id': 9},
                      {'type': 'event', 'id': 2}, {}):
            self.assertFalse(hb.observe(frame, 121))
        with self.assertRaises(TimeoutError):
            hb.due(130)

    def test_late_pong_cannot_reanimate_dead_connection(self):
        hb = ReplyHeartbeat(0)
        hb.due(20)
        with self.assertRaises(TimeoutError):
            hb.observe({'id': 2, 'type': 'pong'}, 20 + PING_TIMEOUT_SECONDS)

    def test_unsolicited_pong_has_no_effect(self):
        hb = ReplyHeartbeat(0)
        self.assertFalse(hb.observe({'id': 2, 'type': 'pong'}, 1))
        self.assertEqual(hb.due(20), 2)

    def test_ws_scheme_uses_ha_base(self):
        self.assertEqual(websocket_url('https://example.test:8123'),
                         'wss://example.test:8123/api/websocket')
        self.assertEqual(websocket_url('http://homeassistant.local:8123'),
                         'ws://homeassistant.local:8123/api/websocket')


class FakeTimeout(Exception):
    pass


class Clock:
    def __init__(self):
        self.now = 0

    def monotonic(self):
        return self.now


class FakeSocket:
    def __init__(self, clock, *, answer_pings=True, incorrect_pongs=False, deliver_event=False):
        self.clock = clock
        self.answer_pings = answer_pings
        self.incorrect_pongs = incorrect_pongs
        self.deliver_event = deliver_event
        self.incoming = [
            {'type': 'auth_required'}, {'type': 'auth_ok'},
            {'type': 'result', 'id': 1, 'success': True},
        ]
        self.sent = []
        self.closed = False
        self.event_delivered = False
        self.timeout = None

    def settimeout(self, timeout):
        self.timeout = timeout

    def send(self, text):
        cmd = json.loads(text)
        self.sent.append(cmd)
        if cmd['type'] == 'ping' and self.answer_pings:
            self.incoming.append({'type': 'pong', 'id': cmd['id'] + (1 if self.incorrect_pongs else 0)})

    def recv(self):
        if self.incoming:
            return json.dumps(self.incoming.pop(0))
        if self.deliver_event and not self.event_delivered:
            self.event_delivered = True
            return json.dumps({'type': 'event', 'id': 1,
                               'event': {'event_type': 'meshtastic_api_text_message', 'data': {}}})
        self.clock.now += 2
        raise FakeTimeout

    def close(self):
        self.closed = True


class ListenerTests(unittest.TestCase):
    def run_listener(self, *, answer=True, incorrect=False, event=False):
        clock = Clock()
        ws = FakeSocket(clock, answer_pings=answer, incorrect_pongs=incorrect, deliver_event=event)
        stub = types.SimpleNamespace(create_connection=lambda *a, **kw: ws,
                                     WebSocketTimeoutException=FakeTimeout)
        stop = Event()
        statuses, events = [], []
        original_send = ws.send

        def bounded_send(text):
            original_send(text)
            # Stop an otherwise healthy fake after two pings.
            if answer and not incorrect and sum(m.get("type") == "ping" for m in ws.sent) >= 2:
                stop.set()

        ws.send = bounded_send

        def status(value):
            statuses.append(value)

        def received(value):
            events.append(value)
            if event:
                stop.set()

        with patch.dict(sys.modules, {'websocket': stub}), patch('librebeacon.mesh_stream.time.monotonic', clock.monotonic):
            listen_for_replies('http://example.test:8123', 'not-a-real-token', stop, received, status)
        return ws, statuses, events

    def test_missing_pongs_disconnects(self):
        ws, statuses, _ = self.run_listener(answer=False)
        self.assertTrue(ws.closed)
        self.assertTrue(any('disconnected' in s for s in statuses))
        self.assertTrue(any(m.get('type') == 'ping' for m in ws.sent))

    def test_wrong_pong_disconnects(self):
        ws, statuses, _ = self.run_listener(incorrect=True)
        self.assertTrue(ws.closed)
        self.assertTrue(any('disconnected' in s for s in statuses))

    def test_quiet_socket_with_valid_pongs_stays_alive(self):
        ws, statuses, _ = self.run_listener()
        self.assertTrue(ws.closed)
        self.assertEqual(statuses[-1], 'Reply listening stopped')
        self.assertEqual(len([s for s in ws.sent if s.get('type') == 'ping']), 2)

    def test_events_still_pass_through(self):
        ws, statuses, events = self.run_listener(event=True)
        self.assertEqual(len(events), 1)
        self.assertTrue(ws.closed)
        self.assertEqual(statuses[-1], 'Reply listening stopped')

    def test_no_token_does_not_open_socket(self):
        stop = Event()
        status = []
        listen_for_replies('http://example.test:8123', '', stop, lambda x: None, status.append)
        self.assertEqual(status, ['No Home Assistant access token'])


if __name__ == '__main__':
    unittest.main()
