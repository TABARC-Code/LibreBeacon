"""Incident-bound Meshtastic replies. A radio packet isn't a welfare check.

Keep the evidence narrow. No chat transcripts, no contact names, no glucose
figures. One day an actual recipient confirmation flow might grow out of this;
right now it's only a matched message from a configured node.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import re

_REPLY = re.compile(r'^(LB-[0-9A-F]{16}) (OK|CANT)$')
_REFERENCE = re.compile(r'^LB-[0-9A-F]{16}$')

# HA's timestamp is when it observed the packet. A badly delayed event
# shouldn't masquerade as a fresh reply after Windows reconnects.
MAX_EVENT_AGE = timedelta(minutes=2)
RETAIN_AFTER_EXPIRY = timedelta(minutes=60)
MAX_TRACKED_INCIDENTS = 512


def node_number(value: object) -> int:
    """Accept a node's decimal number or the standard !1234abcd representation."""
    if type(value) is int:
        result = value
    elif isinstance(value, str):
        clean = value.strip()
        if re.fullmatch(r'![0-9a-fA-F]{8}', clean):
            result = int(clean[1:], 16)
        elif re.fullmatch(r'[0-9]{1,10}', clean):
            result = int(clean, 10)
        else:
            raise ValueError('Enter a decimal node number or ! followed by eight hex digits')
    else:
        raise ValueError('Invalid node number')
    if not 0 < result <= 0xFFFFFFFF:
        raise ValueError('Node number outside valid range')
    return result


@dataclass
class IncidentReply:
    reference: str
    destination: str
    recipient_node: int
    gateway_node: int
    kind: str
    created_at: datetime
    expires_at: datetime
    response: str = ''
    response_at: datetime | None = None


class MeshReplyTracker:
    """In-memory, fail-closed matching; closing the app discards active incidents."""
    def __init__(self):
        self.incidents: dict[str, IncidentReply] = {}
        self.seen_packets: set[tuple[str, int, int, int]] = set()

    def prune(self, *, now: datetime | None = None) -> int:
        """Drop old reply records and the packet IDs attached to them.

        The active window is 30 minutes. We keep expired statuses for one
        more hour, then let them go. None of this is written to disk.
        """
        current = datetime.now(timezone.utc) if now is None else now
        if not isinstance(current, datetime) or current.tzinfo is None:
            raise ValueError('Use an aware time to clean up reply tracking')
        current = current.astimezone(timezone.utc)
        stale = {ref for ref, item in self.incidents.items()
                 if current > item.expires_at + RETAIN_AFTER_EXPIRY}
        for ref in stale:
            del self.incidents[ref]
        if stale:
            self.seen_packets = {key for key in self.seen_packets if key[0] not in stale}
        return len(stale)

    def register(self, reference: str, destination: str, recipient_node: int,
                 gateway_node: int, kind: str, *, now: datetime | None = None) -> IncidentReply:
        at = now or datetime.now(timezone.utc)
        if (not isinstance(at, datetime) or at.tzinfo is None or
                not isinstance(reference, str) or not _REFERENCE.fullmatch(reference) or
                kind not in ('test', 'critical_low') or
                not isinstance(destination, str) or not destination.startswith('notify.mesh_')):
            raise ValueError('Invalid mesh incident')
        at = at.astimezone(timezone.utc)
        self.prune(now=at)
        recipient, gateway = node_number(recipient_node), node_number(gateway_node)
        if recipient == gateway or reference in self.incidents:
            raise ValueError('Duplicate reference or gateway and recipient are identical')
        if len(self.incidents) >= MAX_TRACKED_INCIDENTS:
            raise ValueError('Reply tracker full; start a fresh session before tracking more messages')
        # This expiry is a tracking rule, not a clinical timeout.
        item = IncidentReply(reference, destination, recipient, gateway, kind,
                             at, at + timedelta(minutes=30))
        self.incidents[reference] = item
        return item

    def receive(self, envelope: object, *, now: datetime | None = None) -> IncidentReply | None:
        """Only direct text events from the pinned radio, for an open incident.

        The integration's event 'node' is cross-checked with 'data.from'. No
        auto-escalation follows this. If we can't bind the gateway, we don't
        pretend a friendly radio name makes it safe.
        """
        at = now or datetime.now(timezone.utc)
        if not isinstance(at, datetime) or at.tzinfo is None or not isinstance(envelope, dict):
            return None
        at = at.astimezone(timezone.utc)
        self.prune(now=at)
        if envelope.get('event_type') != 'meshtastic_api_text_message':
            return None
        data = envelope.get('data')
        if not isinstance(data, dict) or not isinstance(data.get('data'), dict):
            return None
        packet = data['data']
        dest = packet.get('to')
        if not isinstance(dest, dict) or dest.get('channel') is not None:
            return None  # Public/channel messages must never count as replies.
        msg = packet.get('message')
        # Only the exact ASCII reference and OK/CANT reply are admissible.
        # Don't encode untrusted text just to count it: JSON can carry a
        # lone surrogate, which would raise and stop the desktop event loop.
        if not isinstance(msg, str) or len(msg) > 64:
            return None
        match = _REPLY.fullmatch(msg)
        if not match:
            return None
        record = self.incidents.get(match.group(1))
        if not record or record.response:
            return None
        if at < record.created_at or at >= record.expires_at:
            return None
        try:
            sender = node_number(packet.get('from'))
            gateway = node_number(packet.get('gateway'))
            receiver = node_number(dest.get('node'))
            outer_sender = node_number(data.get('node'))
            packet_id = data.get('message_id')
            # Message IDs can be absent on older installations. No ACK claim.
            # A duplicate text reply is suppressed by the incident response.
            if packet_id is not None and (type(packet_id) is not int or packet_id < 0):
                return None
        except ValueError:
            return None
        if (sender != record.recipient_node or outer_sender != sender or
                gateway != record.gateway_node or receiver != gateway):
            return None
        fired = envelope.get('time_fired')
        if not isinstance(fired, str):
            return None
        try:
            sent_at = datetime.fromisoformat(fired.replace('Z', '+00:00'))
            if sent_at.tzinfo is None:
                return None
            sent_at = sent_at.astimezone(timezone.utc)
            if (not record.created_at <= sent_at < record.expires_at or
                    sent_at - at > timedelta(seconds=2) or
                    at - sent_at > MAX_EVENT_AGE):
                return None
        except (ValueError, OverflowError):
            # An extreme but parseable UTC offset can overflow conversion.
            return None
        if packet_id is not None:
            # Scope deduplication to the reference: packet IDs aren't globally
            # unique over a long-running radio installation.
            key = (record.reference, sender, gateway, packet_id)
            if key in self.seen_packets:
                return None
            self.seen_packets.add(key)
        record.response = match.group(2)
        record.response_at = at
        return record

    def status(self, reference: str, *, now: datetime | None = None) -> str:
        incident = self.incidents.get(reference)
        if incident is None:
            return 'No reply tracking for this request'
        if incident.response == 'OK':
            return 'Matching radio reply: OK (attendance not confirmed)'
        if incident.response == 'CANT':
            return 'Matching radio reply: CANT (recipient cannot attend)'
        current = now or datetime.now(timezone.utc)
        return 'Reply window expired' if current >= incident.expires_at else 'Awaiting matching radio reply'
