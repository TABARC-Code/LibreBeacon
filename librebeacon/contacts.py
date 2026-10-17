"""Contact destinations and dispatch live here, away from the desktop controls.

A contact is a nickname plus an existing Home Assistant destination. There are
no telephone numbers or mail passwords in this file. A new transport can join
here without taking over the glucose-reading code.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .homeassistant import HomeAssistant, HomeAssistantError, VALID_ENTITY


@dataclass(frozen=True)
class ContactRoute:
    label: str
    target: str
    consent: bool = False
    enabled: bool = False

    def validate(self) -> 'ContactRoute':
        if not isinstance(self.label, str) or not isinstance(self.target, str) \
                or type(self.consent) is not bool or type(self.enabled) is not bool:
            raise ValueError('Contact settings have unexpected field types')
        if not self.label.strip() or len(self.label.strip()) > 80:
            raise ValueError('Give this contact a short, recognisable name')
        if not VALID_ENTITY.fullmatch(self.target) or not self.target.startswith(('notify.', 'script.')):
            raise ValueError('Choose one Home Assistant notify entity or script for this contact')
        # Channel-wide meshes expose the notification to more listeners.
        # Names are imperfect; the UI and user still need to verify the route.
        if self.target.startswith('notify.mesh_') and any(word in self.target for word in
            ('_channel', '_broadcast', 'mesh_all', '_everyone')):
            raise ValueError('Choose an individual Meshtastic recipient, not a broadcast channel')
        if self.enabled and not self.consent:
            raise ValueError(f'{self.label}: confirm the recipient agreed before enabling')
        return self

    def as_dict(self) -> dict:
        return {'label': self.label, 'target': self.target,
                'consent': self.consent, 'enabled': self.enabled}


def read_routes(items: list[dict]) -> list[ContactRoute]:
    routes = []
    seen = set()
    for raw in items:
        if not isinstance(raw, dict):
            raise ValueError('Invalid contact record')
        route = ContactRoute(**{key: raw.get(key, default) for key, default in
                                   [('label', ''), ('target', ''), ('consent', False), ('enabled', False)]}).validate()
        if route.target in seen:
            raise ValueError(f'Destination {route.target} is already configured. Add it just once.')
        seen.add(route.target)
        routes.append(route)
    return routes


def emergency_message(include_value: bool = False, mmol: float | None = None) -> str:
    # Do not put health details on a shared radio channel unless someone chose that.
    text = ('LibreBeacon supplementary alert: a configured critical-low glucose '
            'condition was detected. Please check on the person directly and use '
            'their approved monitoring system. This message is not an emergency service.')
    if include_value and mmol is not None:
        text += f' Reading: {mmol:.1f} mmol/L.'
    return text


def dispatch_route(client: HomeAssistant, route: ContactRoute, message: str) -> None:
    route.validate()
    if not route.enabled or not route.consent:
        raise ValueError('The contact is not enabled and consented')
    if route.target.startswith('notify.'):
        client.send_notification(route.target, message)
    else:
        client.run_script(route.target, event='critical_low', message=message)


def dispatch_emergency(routes: list[ContactRoute], client: HomeAssistant,
                       message: str, on_result: Callable[[str, bool, str], None]) -> None:
    """Attempt each configured destination even when one fails.

    A successful request only means the upstream service accepted the action.
    It isn't proof that a person received, saw, or understood the message.
    """
    for route in routes:
        if not route.enabled or not route.consent:
            continue
        try:
            dispatch_route(client, route, message)
        except Exception as exc:
            # A faulty provider must not prevent trying another consenting contact.
            # Keep trace details out of contact-facing UI until we have redaction.
            on_result(route.label, False, exc.__class__.__name__)
        else:
            on_result(route.label, True, 'Request accepted; delivery unconfirmed')
