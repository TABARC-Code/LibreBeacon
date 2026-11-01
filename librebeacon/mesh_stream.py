"""Read Home Assistant's authenticated Meshtastic event stream, not radio ports.

Only connect on request; background threads don't belong in Tk's event loop.
No incoming text gets written to disk. A socket failing is just a socket
failing, not evidence about the person or their glucose.
"""
from __future__ import annotations
import json
from urllib.parse import urlsplit


def websocket_url(base_url: str) -> str:
    from .homeassistant import HomeAssistant
    HomeAssistant(base_url, 'url-check')
    parts = urlsplit(base_url)
    return f'{"wss" if parts.scheme == "https" else "ws"}://{parts.netloc}/api/websocket'


def listen_for_replies(base_url: str, token: str, stop, on_event, on_status) -> None:
    """One session: no automatic reconnect, no silent replay of missed events."""
    if not isinstance(token, str) or not token:
        on_status('No Home Assistant access token'); return
    try:
        import websocket  # websocket-client; optional at module import time
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
            ws.send(json.dumps({'type':'auth','access_token':token}))
            if receive().get('type') != 'auth_ok':
                raise ValueError('Home Assistant authentication failed')
            ws.send(json.dumps({'id':1,'type':'subscribe_events','event_type':'meshtastic_api_text_message'}))
            answer = receive()
            if answer.get('type') != 'result' or answer.get('id') != 1 or answer.get('success') is not True:
                raise ValueError('Home Assistant refused Meshtastic events subscription')
            on_status('Listening for Meshtastic replies; Windows must remain awake')
            while not stop.is_set():
                try:
                    item = receive()
                except websocket.WebSocketTimeoutException:
                    continue
                if item.get('type') == 'event' and item.get('id') == 1:
                    on_event(item.get('event'))
            on_status('Reply listening stopped')
        finally:
            ws.close()
    except Exception:
        # Never leak tokens, URLs or incoming message contents in diagnostics.
        on_status('Reply listener disconnected. Restart it to observe new replies; earlier messages may be missed.')
