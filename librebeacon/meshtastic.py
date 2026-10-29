"""Home Assistant Meshtastic recipient evidence, not a second radio driver.

The integration's node notifications expose node_id + user_id. Channels don't.
A nice name isn't proof of anything, and neither is a user ticking a box.
"""
from __future__ import annotations
from dataclasses import dataclass
import re

_SHARING_WORDS = frozenset({'broadcast', 'channel', 'everyone', 'public', 'group', 'all', 'global'})


def is_mesh_entity(entity_id: str) -> bool:
    return isinstance(entity_id, str) and entity_id.casefold().startswith('notify.mesh_')


def appears_shared(entity_id: str, friendly_name: str = '') -> bool:
    words = re.findall(r'[a-z0-9]+', f'{entity_id} {friendly_name}'.casefold())
    return bool(_SHARING_WORDS.intersection(words))


def valid_node_id(value: object) -> bool:
    # Firmware node numbers are unsigned 32-bit. A boolean is not a node ID.
    return type(value) is int and 0 < value <= 0xFFFFFFFF


@dataclass(frozen=True)
class MeshChoice:
    entity_id: str
    friendly_name: str
    selectable: bool
    explanation: str
    node_id: int | None = None


def discover_mesh_choices(states: list[dict]) -> list[MeshChoice]:
    """Check integration-provided node attributes. Unknown is not 'available'.

    This is stronger than checking names, but not cryptographic identity proof.
    Someone still has to check who owns the receiver. Boring, necessary.
    """
    choices: list[MeshChoice] = []
    for state in states:
        if not isinstance(state, dict):
            continue
        entity_id = state.get('entity_id', '')
        if not is_mesh_entity(entity_id):
            continue
        attrs = state.get('attributes')
        attrs = attrs if isinstance(attrs, dict) else {}
        friendly = attrs.get('friendly_name', '')
        friendly = friendly if isinstance(friendly, str) else ''
        node_id = attrs.get('node_id')
        user_id = attrs.get('user_id')
        identity_ok = valid_node_id(node_id) and user_id == f'!{node_id:08x}'
        # MeshtasticChannelNotify has no node_id/user_id. A renamed channel
        # must never get through just because it sounds like a person.
        if appears_shared(entity_id, friendly):
            reason = 'Possible shared channel or broadcast'
        elif state.get('state') in ('unavailable', 'unknown_gateway'):
            reason = 'Home Assistant marks the destination unavailable'
        elif not identity_ok:
            reason = 'No verified node-type attributes (check the Meshtastic integration)'
        else:
            reason = ''
        choices.append(MeshChoice(entity_id, friendly, not bool(reason),
                    reason or 'Node attributes present; confirm the actual owner before use',
                    node_id if identity_ok else None))
    return sorted(choices, key=lambda item: item.entity_id)


def require_mesh_choice(entity_id: str, states: list[dict], *, expected_node_id: int | None = None) -> MeshChoice:
    """Fail closed when a destination changed identity or lost its attributes."""
    if not is_mesh_entity(entity_id):
        raise ValueError('This is not a Meshtastic notification entity')
    if expected_node_id is not None and not valid_node_id(expected_node_id):
        raise ValueError('The saved Meshtastic node identity is invalid')
    matches = [item for item in discover_mesh_choices(states) if item.entity_id == entity_id]
    if len(matches) != 1 or not matches[0].selectable:
        raise ValueError('Mesh recipient identity unavailable; check its node in Home Assistant')
    if expected_node_id is not None and matches[0].node_id != expected_node_id:
        raise ValueError('Meshtastic recipient identity has changed; remove and re-add it')
    return matches[0]
