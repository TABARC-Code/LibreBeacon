"""One optional backup radio contact, never a message storm.

No reply is not the same as no help. If I lose the listening connection,
I stop the timer rather than pretending I've checked somebody's radio.
Everything here is in memory. A reboot clears it, as it should for now.
"""
from __future__ import annotations
from dataclasses import dataclass
from math import isfinite
import re


@dataclass
class PendingFallback:
    primary: str
    backup: str
    reference: str
    due: float
    expires: float
    state: str = 'waiting'
    outcome: str = ''


class MeshFallback:
    """Single-stage backup, once per incident. All clocks are monotonic seconds."""
    def __init__(self):
        self.pending: PendingFallback | None = None

    @staticmethod
    def validate(primary: str, backup: str, minutes: int) -> None:
        if not isinstance(primary, str) or not isinstance(backup, str) or not primary or not backup or primary == backup:
            raise ValueError('Choose two different, approved mesh contacts')
        if type(minutes) is not int or not 2 <= minutes <= 20:
            raise ValueError('Fallback delay must be between 2 and 20 minutes')

    def arm(self, primary: str, backup: str, reference: str, *,
            minutes: int, now: float, listener_ready: bool) -> bool:
        self.validate(primary, backup, minutes)
        if not isinstance(reference, str) or not re.fullmatch(r'LB-[0-9A-F]{16}', reference):
            raise ValueError('A sent radio request reference is required')
        if not isinstance(now, (int, float)) or not isfinite(now):
            raise ValueError('Invalid incident clock')
        if not listener_ready:
            return False
        if self.pending is not None:
            return False  # One backup plan in a session. No quiet re-arming after a send.
        self.pending = PendingFallback(primary, backup, reference, now + 60 * minutes, now + 1800)
        return True

    def reply(self, reference: str, destination: str, response: str) -> None:
        item = self.pending
        if item is None or item.reference != reference or item.primary != destination:
            return
        if item.state != 'waiting':
            return
        if response == 'OK':
            item.state, item.outcome = 'cancelled', 'Matching OK reply observed. Backup held.'
        elif response == 'CANT':
            item.state = 'cant'

    def cancel(self, reason: str = 'Operator cancelled the pending backup') -> None:
        if self.pending is not None and self.pending.state in ('waiting', 'cant', 'sending'):
            if self.pending.state == 'sending':
                reason += ' A request already started cannot be recalled.'
            self.pending.state, self.pending.outcome = 'cancelled', reason

    def due(self, *, now: float, listener_ready: bool) -> str | None:
        item = self.pending
        if item is None or item.state not in ('waiting', 'cant'):
            return None
        if not isinstance(now, (int, float)) or not isfinite(now):
            return None
        if not listener_ready:
            # A CANT reply doesn't make a dead listener trustworthy again.
            self.cancel('Reply listener stopped. Backup cancelled.')
            return None
        if now >= item.expires:
            item.state, item.outcome = 'expired', 'Fallback window expired; no new request.'
            return None
        if item.state == 'cant' or now >= item.due:
            item.state, item.outcome = 'sending', 'Backup request attempted once; no automatic retry.'
            return item.backup
        return None

    def sent(self, *, accepted: bool) -> None:
        if self.pending is not None and self.pending.state == 'sending':
            self.pending.state = 'sent' if accepted else 'failed'
            self.pending.outcome = ('Backup request accepted by Home Assistant; delivery unconfirmed.'
                                    if accepted else 'Backup request failed; no repeat attempted.')

    def describe(self) -> str:
        p = self.pending
        if p is None:
            return 'No backup pending this session.'
        return p.outcome or f'Waiting for primary radio reply; backup limited to {p.backup}.'



def require_backup_send(fallback: MeshFallback, settings, route, *, listener_ready: bool) -> None:
    """Last check before HA gets a radio message.

    A queued worker is not permission to use yesterday's contact list.
    The person may have switched everything off while the network was slow.
    """
    from .contacts import read_routes
    from .meshtastic import is_mesh_entity

    item = fallback.pending
    if not listener_ready or item is None or item.state != 'sending':
        raise ValueError('Backup cancelled or reply listener unavailable')
    if not settings.enabled or not settings.enable_emergency_contacts or not settings.emergency_contact_consent:
        raise ValueError('Automatic contact messages are now disabled')
    if (not settings.mesh_fallback_enabled or
            settings.mesh_fallback_primary != item.primary or
            settings.mesh_fallback_backup != item.backup or
            route.target != item.backup):
        raise ValueError('Backup contact selection changed')
    current = read_routes(settings.emergency_routes)
    if (route not in current or not is_mesh_entity(route.target) or
            not route.enabled or not route.consent or route.mesh_node_id is None):
        raise ValueError('Backup contact is no longer approved')
