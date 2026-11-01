"""Read Home Assistant's authenticated Meshtastic event stream, not radio ports.

Only connect when asked. The WebSocket gets a periodic Home Assistant ping:
an idle connection can look perfectly healthy while the network has vanished.
No incoming text goes to disk. Don't mistake a live socket for a live radio.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import time
from urllib.parse import urlsplit


PING_INTERVAL_SECONDS = 20.0
PING_TIMEOUT_SECONDS = 10.0


def websocket_url(base_url: str) -> str:
    from .homeassistant import HomeAssistant
    HomeAssistant(base_url, 'url-check')
    parts = urlsplit(base_url)
    return f'{"wss" if parts.scheme == "https" else "ws"}://{parts.netloc}/api/websocket'


@dataclass
class ReplyHeartbeat:
    """HA's application-level ping/pong. All timings are monotonic seconds."""
    last_check: float
    pending_id: int | None = None
    pending_since: float | None = None
    next_id: int = 2  # ID 1 belongs to the event subscription.

    def due(self, now: float) -> int | None:
        if self.pending_id is not None:
            if now - self.pending_since >= PING_TIMEOUT_SECONDS:
                raise TimeoutError('Home Assistant stopped responding to heartbeat checks')
            return None
        if now - self.last_check < PING_INTERVAL_SECONDS:
            return None
        request_id = self.next_id
        self.next_id += 1
        self.pending_id, self.pending_since, self.last_check = request_id, now, now
        return request_id

    def observe(self, message: dict, now: float) -> bool:
        if message.get('type') != 'pong' or message.get('id') != self.pending_id or self.pending_id is None:
            return False
        # A pong that arrives after the deadline isn't a healthy connection.
        # Otherwise Windows waking up could make a stale reply look current.
        if now - self.pending_since >= PING_TIMEOUT_SECONDS:
            raise TimeoutError('Home Assistant replied after the heartbeat deadline')
        self.pending_id = None
        self.pending_since = None
        self.last_check = now
        return True


def listen_for_replies(base_url: str, token: str, stop, on_event, on_status) -> None:
    """One bounded session. No automatic reconnect or replay of missed events."""
    if not isinstance(token, str) or not token:
        on_status('No Home Assistant access token'); return
    try:
        import websocket  # websocket-client; installed separately from tkinter
        ws = websocket.create_connection(websocket_url(base_url), timeout=8)
        try:
            ws.settimeout(2)

            def receive():
                value = ws.recv()
                if not isinstance(value, str) or len(value) > 65536:
                    raise ValueError('Unexpected Home Assistant message')
                result = json.loads(value)
                if not isinstance(result, dict):
                    raise ValueError('Unexpected Home Assistant reply')
                return result

            if receive().get('type') != 'auth_required':
                raise ValueError('Home Assistant did not request authentication')
            ws.send(json.dumps({'type': 'auth', 'access_token': token}))
            if receive().get('type') != 'auth_ok':
                raise ValueError('Home Assistant authentication failed')
            ws.send(json.dumps({'id': 1, 'type': 'subscribe_events',
                                'event_type': 'meshtastic_api_text_message'}))
            answer = receive()
            if answer.get('type') != 'result' or answer.get('id') != 1 or answer.get('success') is not True:
                raise ValueError('Home Assistant refused Meshtastic events subscription')

            heartbeat = ReplyHeartbeat(time.monotonic())
            on_status('Listening for Meshtastic replies; Windows must remain awake')
            while not stop.is_set():
                item = None
                try:
                    item = receive()
                except websocket.WebSocketTimeoutException:
                    pass  # A quiet mesh is ordinary. The next ping still has to work.
                now = time.monotonic()
                if item is not None:
                    heartbeat.observe(item, now)
                    if item.get('type') == 'event' and item.get('id') == 1:
                        on_event(item.get('event'))
                if stop.is_set():
                    break
                ping_id = heartbeat.due(now)
                if ping_id is not None:
                    ws.send(json.dumps({'id': ping_id, 'type': 'ping'}))
            on_status('Reply listening stopped')
        finally:
            ws.close()
    except Exception:
        # No token, incoming text, URLs or exception bodies in the display.
        on_status('Reply listener disconnected. Check Home Assistant and restart listening; earlier replies may be missed.')
