"""Dry-run the backup decisions without contacting Home Assistant or a radio.

I keep this deliberately separate from the live sender. A simulation that can
accidentally call the real contact dispatcher isn't much of a simulation.
The clock, reference and recipients are all fictional, and nothing is saved.
"""
from __future__ import annotations
from dataclasses import dataclass
from .mesh_fallback import MeshFallback


SCENARIOS = (
    'Primary replies OK',
    'Primary replies CANT',
    'No reply before timeout',
    'Reply listener disconnects',
    'Windows sleeps or stalls',
    'Fallback expires',
    'Late OK after fallback',
    'Contact selection invalid',
)

_REFERENCE = 'LB-0000000000000001'  # Fictional and impossible to mistake for a live request.
_PRIMARY = 'notify.mesh_demo_primary'
_BACKUP = 'notify.mesh_demo_backup'
_START = 1000.0


@dataclass(frozen=True)
class SimulationReport:
    scenario: str
    events: tuple[str, ...]
    state: str
    backup_would_send: bool

    @property
    def text(self) -> str:
        lines = ['SIMULATION ONLY - no glucose readings used, no radio messages sent.',
                 'Recipients: fictional primary and backup nodes.',
                 f'Scenario: {self.scenario}', '']
        lines.extend(self.events)
        lines.append('')
        lines.append(f'Backup action: {"WOULD TRY one request" if self.backup_would_send else "NONE"}.')
        lines.append(f'Local decision state: {self.state}. No live settings changed.')
        return '\n'.join(lines)


def simulate_fallback(scenario: str) -> SimulationReport:
    """Exercise the actual fallback state machine against a controlled clock.

    Not a mock of the network; there is no network object in this module.
    Two minutes is enough to show timing, but we never sleep for two minutes.
    """
    if scenario not in SCENARIOS:
        raise ValueError('Choose a known simulation scenario')
    policy = MeshFallback()
    events: list[str] = []

    if scenario == 'Contact selection invalid':
        try:
            MeshFallback.validate(_PRIMARY, _PRIMARY, 2)
        except ValueError:
            events.append('00:00 - Same recipient chosen twice; setup refused.')
            return SimulationReport(scenario, tuple(events), 'blocked', False)
        raise RuntimeError('Fallback failed to reject duplicate recipients')

    if not policy.arm(_PRIMARY, _BACKUP, _REFERENCE, minutes=2,
                      now=_START, listener_ready=True):
        raise RuntimeError('Example fallback could not start')
    events.append('00:00 - Fictional primary message accepted by the sample policy.')
    events.append('00:00 - Backup held for two minutes; pretend listener is connected.')

    if scenario == 'Primary replies OK':
        policy.reply(_REFERENCE, _PRIMARY, 'OK')
        events.append('01:00 - Matching OK reply observed in the example.')
        target = policy.due(now=_START + 121, listener_ready=True)
    elif scenario == 'Primary replies CANT':
        policy.reply(_REFERENCE, _PRIMARY, 'CANT')
        events.append('01:00 - Matching CANT reply observed; backup becomes eligible.')
        target = policy.due(now=_START + 60, listener_ready=True)
    elif scenario == 'No reply before timeout':
        events.append('02:00 - No matching reply in the example; listener stays connected.')
        target = policy.due(now=_START + 121, listener_ready=True)
    elif scenario == 'Reply listener disconnects':
        events.append('00:30 - Reply listener lost; waiting cannot be trusted.')
        target = policy.due(now=_START + 30, listener_ready=False)
    elif scenario == 'Windows sleeps or stalls':
        policy.cancel('Example computer slept or stopped responding.')
        events.append('00:30 - Simulated computer sleep; pending backup cancelled.')
        target = policy.due(now=_START + 121, listener_ready=False)
    elif scenario == 'Fallback expires':
        events.append('30:00 - The incident window has expired. Never send late.')
        target = policy.due(now=_START + 1800, listener_ready=True)
    else:  # Late OK after fallback
        events.append('02:00 - Backup became due before an OK arrived.')
        target = policy.due(now=_START + 121, listener_ready=True)
        policy.reply(_REFERENCE, _PRIMARY, 'OK')
        events.append('02:10 - The late OK cannot unsend an attempted backup.')

    would_send = target == _BACKUP
    if target is not None and not would_send:
        raise RuntimeError('Example policy selected an unexpected recipient')
    if would_send:
        events.append('Decision: backup WOULD be attempted once. No request is made here.')
        # Don't call policy.sent: that would write a fake acceptance outcome.
        if policy.due(now=_START + 125, listener_ready=True) is not None:
            raise RuntimeError('Example policy tried to dispatch a second backup')
    else:
        events.append('Decision: no backup request is attempted.')
    return SimulationReport(scenario, tuple(events), policy.pending.state, would_send)
