"""Contact destinations and dispatch live here, away from the desktop controls.

A contact is a nickname plus an existing Home Assistant destination. There are
no telephone numbers or mail passwords in this file. A new transport can join
here without taking over the glucose-reading code.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .homeassistant import HomeAssistant, HomeAssistantError, VALID_ENTITY
from .meshtastic import is_mesh_entity, appears_shared, require_mesh_choice, valid_node_id
from .mesh_messages import MeshText, build_mesh_message, check_mesh_text


@dataclass(frozen=True)
class ContactRoute:
    label: str
    target: str
    consent: bool = False
    enabled: bool = False
    mesh_node_id: int | None = None

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
        if is_mesh_entity(self.target) and appears_shared(self.target):
            raise ValueError('Choose an individual Meshtastic recipient, not a shared channel')
        if is_mesh_entity(self.target):
            if self.mesh_node_id is not None and not valid_node_id(self.mesh_node_id):
                raise ValueError('Meshtastic node identity must be a positive 32-bit number')
            if self.enabled and self.mesh_node_id is None:
                raise ValueError('Review and re-add this mesh contact to pin its node identity')
        elif self.mesh_node_id is not None:
            raise ValueError('Mesh identity cannot be attached to an ordinary contact')
        if self.enabled and not self.consent:
            raise ValueError(f'{self.label}: confirm the recipient agreed before enabling')
        return self

    def as_dict(self) -> dict:
        record = {'label': self.label, 'target': self.target,
                  'consent': self.consent, 'enabled': self.enabled}
        if is_mesh_entity(self.target) and self.mesh_node_id is not None:
            record['mesh_node_id'] = self.mesh_node_id
        return record


def read_routes(items: list[dict]) -> list[ContactRoute]:
    routes = []
    seen = set()
    seen_labels = set()
    for raw in items:
        if not isinstance(raw, dict):
            raise ValueError('Invalid contact record')
        values = {key: raw.get(key, default) for key, default in
                  [('label', ''), ('target', ''), ('consent', False),
                   ('enabled', False), ('mesh_node_id', None)]}
        # Old saves carried a name alone. Leave the contact visible, but
        # disable it. Removing or re-adding is safer than a guessed identity.
        if is_mesh_entity(values['target']) and values['mesh_node_id'] is None:
            values['enabled'] = False
        route = ContactRoute(**values).validate()
        if route.target in seen:
            raise ValueError(f'Destination {route.target} is already configured. Add it just once.')
        if route.label.strip().casefold() in seen_labels:
            raise ValueError('Give each contact a different nickname')
        seen.add(route.target)
        seen_labels.add(route.label.strip().casefold())
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


def dispatch_route(client: HomeAssistant, route: ContactRoute, message: str, *,
                   mesh_kind: str | None = None, mesh_text: MeshText | None = None,
                   include_value: bool = False, mmol: float | None = None) -> str:
    """Send through HA and return a mesh reference when there is one.

    Preserve ordinary notify/script wording. Mesh contacts get a deliberately
    short format instead of trying to squeeze a whole email onto LoRa.
    """
    route.validate()
    if not route.enabled or not route.consent:
        raise ValueError('The contact is not enabled and consented')
    if is_mesh_entity(route.target):
        if mesh_kind not in ('test', 'critical_low'):
            raise ValueError('Choose a labelled mesh test or critical-low message')
        if mesh_text is not None and mesh_kind != 'test':
            raise ValueError('Only a test message may be prepared before dispatch')
        prepared = (check_mesh_text(mesh_text, mesh_kind) if mesh_text is not None
                    else build_mesh_message(mesh_kind, include_value=include_value, mmol=mmol))
        # Check the current target, not a stale list from setup. Someone may
        # have swapped the node. Radio networking already has enough surprises.
        require_mesh_choice(route.target, [client.state(route.target)],
                            expected_node_id=route.mesh_node_id)
        client.send_notification(route.target, prepared.body)
        return prepared.reference
    if mesh_kind is not None or mesh_text is not None:
        raise ValueError('Mesh message options cannot be sent to other contacts')
    if route.target.startswith('notify.'):
        client.send_notification(route.target, message)
    else:
        client.run_script(route.target, event='critical_low', message=message)
    return ''


def dispatch_emergency(routes: list[ContactRoute], client: HomeAssistant,
                       message: str, on_result: Callable[[str, bool, str, str], None],
                       *, include_value: bool = False, mmol: float | None = None) -> None:
    """Attempt approved routes independently. An HA response is not delivery.

    The reference is local bookkeeping for M4, not an authenticated reply.
    No retries here; one alert shouldn't occupy the neighbourhood's radios.
    """
    for route in routes:
        if not route.enabled or not route.consent:
            continue
        try:
            ref = dispatch_route(client, route, message,
                                 mesh_kind='critical_low' if is_mesh_entity(route.target) else None,
                                 include_value=include_value, mmol=mmol)
        except Exception as exc:
            # Keep errors generic. A provider exception could include an address.
            on_result(route.label, False, exc.__class__.__name__, '')
        else:
            on_result(route.label, True, 'Request accepted; delivery unconfirmed', ref)
