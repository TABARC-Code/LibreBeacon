"""Home Assistant mesh destination checks. No direct radio work in here.

A friendly name is a hint, not a signed certificate. We filter obvious public
routes and ask somebody to check the intended node before it can be saved.
"""
from __future__ import annotations
from dataclasses import dataclass
import re


# Avoid substring matching: 'Allison' is a person; 'all' is usually a group.
_SHARING_WORDS = frozenset({'broadcast', 'channel', 'everyone', 'public', 'group', 'all', 'global'})


def is_mesh_entity(entity_id: str) -> bool:
    return isinstance(entity_id, str) and entity_id.casefold().startswith('notify.mesh_')


def appears_shared(entity_id: str, friendly_name: str = '') -> bool:
    words = re.findall(r'[a-z0-9]+', f'{entity_id} {friendly_name}'.casefold())
    return bool(_SHARING_WORDS.intersection(words))


@dataclass(frozen=True)
class MeshChoice:
    entity_id: str
    friendly_name: str
    selectable: bool
    explanation: str


def discover_mesh_choices(states: list[dict]) -> list[MeshChoice]:
    """Only offers plausible direct nodes. It cannot prove who's holding a radio."""
    choices: list[MeshChoice] = []
    for state in states:
        if not isinstance(state, dict):
            continue
        entity_id = state.get('entity_id', '')
        if not is_mesh_entity(entity_id):
            continue
        attrs = state.get('attributes') or {}
        friendly_name = attrs.get('friendly_name', '') if isinstance(attrs, dict) else ''
        if not isinstance(friendly_name, str):
            friendly_name = ''
        if appears_shared(entity_id, friendly_name):
            choices.append(MeshChoice(entity_id, friendly_name, False, 'Possible channel or shared destination'))
        elif state.get('state') == 'unavailable':
            choices.append(MeshChoice(entity_id, friendly_name, False, 'Home Assistant marks it unavailable'))
        else:
            choices.append(MeshChoice(entity_id, friendly_name, True,
                                      'Check this is the intended person, then send a labelled test'))
    return sorted(choices, key=lambda item: item.entity_id)


def require_mesh_choice(entity_id: str, states: list[dict]) -> MeshChoice:
    """Fail closed when a saved node's destination now points somewhere else.

    This checks Home Assistant's current entity, not whether the recipient has
    seen a message. A missing gateway shouldn't trigger an optimistic send.
    """
    if not is_mesh_entity(entity_id):
        raise ValueError('This is not a Meshtastic notification entity')
    matches = [item for item in discover_mesh_choices(states) if item.entity_id == entity_id]
    if len(matches) != 1 or not matches[0].selectable:
        raise ValueError('Mesh recipient not available as a plausible individual node; check Home Assistant')
    return matches[0]
