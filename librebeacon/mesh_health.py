"""Read-only Meshtastic gateway and node diagnostics from Home Assistant.

The gateway's 'Connected' state is a statement from HA, not a promise that
someone's radio is in range. Don't turn a pretty green indicator into a lie.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import re


@dataclass(frozen=True)
class GatewayStatus:
    entity_id: str
    label: str
    status: str
    detail: str
    checked_at: datetime
    verified_type: bool


@dataclass(frozen=True)
class NodeTelemetry:
    node_id: int
    status: str
    detail: str
    measured_at: datetime | None = None


def _aware(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError('Use an aware timestamp for the check')
    return value.astimezone(timezone.utc)


def discover_gateways(states: list[dict], *, now: datetime) -> list[GatewayStatus]:
    """Never infer live radio coverage from an entity update or a gateway name.

    A gateway entity normally has device_class=gateway in its state attributes.
    Custom components may omit that attribute. Those candidates stay unverified
    until we see the expected type; their name isn't enough to trust.
    """
    checked = _aware(now)
    if not isinstance(states, list):
        raise ValueError('Home Assistant did not supply an entity list')
    found: list[GatewayStatus] = []
    seen: set[str] = set()
    for item in states:
        if not isinstance(item, dict):
            continue
        entity = item.get('entity_id')
        if not isinstance(entity, str) or not entity.startswith('meshtastic.'):
            continue
        attrs = item.get('attributes')
        attrs = attrs if isinstance(attrs, dict) else {}
        typed = attrs.get('device_class') == 'gateway'
        if not typed and not entity.startswith('meshtastic.gateway_'):
            continue
        if entity in seen:
            # Duplicate records aren't proof of two independent gateways.
            continue
        seen.add(entity)
        label = attrs.get('friendly_name')
        if not isinstance(label, str) or not label.strip():
            label = entity
        label = label.strip()[:90]
        state = item.get('state')
        state = state.casefold() if isinstance(state, str) else ''
        if not typed:
            status, detail = ('UNVERIFIED', 'Likely gateway by name; entity type is not confirmed.')
        elif state == 'connected':
            status, detail = ('HA REPORTS CONNECTED', 'Home Assistant reports its gateway connected. Radio reachability is not checked.')
        elif state in ('disconnected', 'unavailable'):
            status, detail = ('DISCONNECTED', 'Home Assistant reports this gateway disconnected or unavailable.')
        else:
            status, detail = ('UNKNOWN', 'No recognised current gateway connection state was reported.')
        found.append(GatewayStatus(entity, label, status, detail, checked, typed))
    return sorted(found, key=lambda item: item.entity_id)


def _read_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip() or value.lower() in ('unavailable', 'unknown'):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        return None
    return parsed.astimezone(timezone.utc) if parsed.tzinfo else None


def node_last_heard(states: list[dict], node_id: int, *, now: datetime,
                    stale_after_minutes: int = 30) -> NodeTelemetry:
    """Observational only. Hearing from a node isn't delivery to that node.

    The upstream sensor uses a node number in its generated object ID. Check
    the whole suffix, so 123 can't accidentally match 1234. Multiple gateways
    may expose separate readings. We won't silently pick whichever looks nice.
    """
    checked = _aware(now)
    if type(node_id) is not int or node_id <= 0 or node_id > 0xFFFFFFFF:
        raise ValueError('Invalid Meshtastic node number')
    if type(stale_after_minutes) is not int or not 1 <= stale_after_minutes <= 1440:
        raise ValueError('Invalid observation age limit')
    if not isinstance(states, list):
        raise ValueError('Home Assistant did not supply an entity list')
    pattern = re.compile(rf'^sensor\.meshtastic_(?:[a-z0-9_]+_)?{node_id}_node_last_heard$')
    records = [item for item in states if isinstance(item, dict)
               and isinstance(item.get('entity_id'), str)
               and pattern.fullmatch(item['entity_id'])]
    if len(records) != 1:
        detail = ('Several last-heard sensors match this node. Check the gateway manually.'
                  if records else 'No matching last-heard sensor exposed by Home Assistant.')
        return NodeTelemetry(node_id, 'NOT VERIFIED', detail)
    measured = _read_timestamp(records[0].get('state'))
    if measured is None:
        return NodeTelemetry(node_id, 'NOT VERIFIED', 'Last-heard timestamp is missing or invalid.')
    age = checked - measured
    if age < timedelta(minutes=-2):
        return NodeTelemetry(node_id, 'CLOCK ERROR', 'Last-heard time is in the future; check the clocks.', measured)
    if age > timedelta(minutes=stale_after_minutes):
        return NodeTelemetry(node_id, 'OLD OBSERVATION',
                             f'Last radio observation was {int(age.total_seconds() // 60)} minutes ago.', measured)
    return NodeTelemetry(node_id, 'RECENT OBSERVATION',
                         f'Home Assistant recorded a packet {max(0, int(age.total_seconds() // 60))} minutes ago. This is not proof of reachability.',
                         measured)


def gateway_summary(gateways: list[GatewayStatus], *, now: datetime) -> str:
    current = _aware(now)
    if not gateways:
        return ('No Meshtastic gateway entity was found. Check Home Assistant > Devices & services > '
                'Meshtastic and confirm the gateway is configured. No radio reachability has been tested.')
    lines = [f'Last checked: {current.astimezone().strftime("%H:%M:%S")}. Live state requested from Home Assistant.']
    for entry in gateways:
        lines.append(f'{entry.label} — {entry.status}\n{entry.detail}')
    lines.append('A connected gateway cannot guarantee that any receiver can hear a message. '
                 'Notification request acceptance is not a delivery receipt.')
    return '\n\n'.join(lines)
