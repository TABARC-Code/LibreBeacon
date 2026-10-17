"""Small client of Home Assistant's documented REST API."""
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.parse import quote, urlsplit
from urllib.error import HTTPError, URLError
import json
import re

VALID_ENTITY = re.compile(r'^[a-z_]+\.[a-z0-9_]+$')

class HomeAssistantError(RuntimeError):
    pass

class NoRedirect(HTTPRedirectHandler):
    """Prevent a redirect from forwarding bearer credentials to a new host."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

class HomeAssistant:
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url.strip().rstrip('/')
        self.token = token
        parsed = urlsplit(self.base_url)
        if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password or parsed.path not in ('', '/') or parsed.query or parsed.fragment:
            raise HomeAssistantError('Enter the server base address, for example http://homeassistant.local:8123')
        if not token.strip():
            raise HomeAssistantError('An access token is required')

    def request(self, method: str, path: str, payload: dict | None = None):
        url = self.base_url + '/api/' + path
        body = json.dumps(payload).encode('utf-8') if payload is not None else None
        request = Request(url, data=body, method=method,
                          headers={'Authorization': f'Bearer {self.token}', 'Content-Type': 'application/json'})
        try:
            with build_opener(NoRedirect()).open(request, timeout=8) as response:
                return json.loads(response.read().decode('utf-8'))
        except HTTPError as exc:
            raise HomeAssistantError(f'Home Assistant returned HTTP {exc.code}') from exc
        except (URLError, TimeoutError, ValueError) as exc:
            raise HomeAssistantError(f'Connection failed: {exc.__class__.__name__}') from exc

    def states(self) -> list[dict]:
        result = self.request('GET', 'states')
        if not isinstance(result, list):
            raise HomeAssistantError('Unexpected entity list')
        return result

    def state(self, entity: str) -> dict:
        if not VALID_ENTITY.fullmatch(entity):
            raise HomeAssistantError('Invalid entity ID')
        return self.request('GET', 'states/' + quote(entity, safe='.'))

    def send_notification(self, entity: str, message: str) -> None:
        """Send to one selected notify entity. No implicit default or broadcast."""
        if not entity.startswith('notify.') or not VALID_ENTITY.fullmatch(entity):
            raise HomeAssistantError('Choose a specific Home Assistant notify entity')
        self.request('POST', 'services/notify/send_message', {
            'entity_id': entity, 'message': message
        })

    def run_script(self, entity: str, *, event: str, message: str) -> None:
        if not entity.startswith('script.') or not VALID_ENTITY.fullmatch(entity):
            raise HomeAssistantError('Choose a valid Home Assistant script entity')
        self.request('POST', 'services/script/turn_on', {
            'entity_id': entity,
            'variables': {'event': event, 'message': message, 'title': 'LibreBeacon notification'}
        })
