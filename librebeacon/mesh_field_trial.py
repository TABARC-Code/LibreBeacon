"""A field-test notebook that doesn't need medical readings or radio traffic.

Only the operator can authorise a test. Reports leave names and node IDs out.
It's tempting to mark a connected gateway as 'passed'. Don't.
"""
from __future__ import annotations

from datetime import datetime, timezone
from dataclasses import dataclass, field

from .contacts import ContactRoute
from .meshtastic import is_mesh_entity
from .mesh_messages import MeshText, build_mesh_message
from .mesh_health import discover_gateways
from .contacts import dispatch_route

FIELD_CASES = (
    ('01', 'Windows install and keyboard access'),
    ('02', 'Receiver identity and consent'),
    ('03', 'Private test request'),
    ('04', 'Actual recipient receipt'),
    ('05', 'Matching radio reply'),
    ('06', 'Invalid reply rejection'),
    ('07', 'Gateway disconnected'),
    ('08', 'Home Assistant listener loss'),
    ('09', 'Windows sleep and resume'),
    ('10', 'Recipient identity change'),
    ('11', 'Consent withdrawn'),
    ('12', 'Assistive technology and display'),
    ('13', 'Physical radio range and battery'),
)


@dataclass
class MeshFieldTrial:
    """One session, one test request at a time. No persistence until Save."""

    route: ContactRoute | None = None
    gateway_observation: str = 'NOT CHECKED'
    gateway_ready: bool = False
    recipient_observation: str = 'NOT CHECKED'
    recipient_checked: bool = False
    owner_confirmed: bool = False
    prepared: MeshText | None = None
    authorised: bool = False
    request_result: str = 'NOT SENT'
    receipt: str = 'NOT CONFIRMED'
    cases: dict[str, str] = field(default_factory=lambda: {key: 'NOT RUN' for key, _ in FIELD_CASES})
    started: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def select(self, route: ContactRoute) -> None:
        route.validate()
        if not is_mesh_entity(route.target) or not route.enabled or not route.consent or route.mesh_node_id is None:
            raise ValueError('Choose an enabled, consented individual mesh recipient')
        self.route = route
        self.recipient_checked = False
        self.owner_confirmed = False
        self.recipient_observation = 'NOT CHECKED'
        self.prepared = None
        self.authorised = False
        self.request_result = 'NOT SENT'
        self.receipt = 'NOT CONFIRMED'
        # A new receiver means a new test. Never borrow the old results.
        for code in ('02', '03', '04'):
            self.cases[code] = 'NOT RUN'

    def gateway_checked(self, states: list[str]) -> None:
        # These are statuses from the read-only HA gateway classifier.
        connected = sum(state == 'HA REPORTS CONNECTED' for state in states)
        self.gateway_ready = len(states) == 1 and connected == 1
        self.gateway_observation = ('HA REPORTS CONNECTED' if self.gateway_ready else
                                    'GATEWAY NOT VERIFIED')
        self.recipient_checked = False
        self.owner_confirmed = False
        self.recipient_observation = 'NOT CHECKED'
        self.prepared = None
        self.authorised = False
        self.request_result = 'NOT SENT'
        self.receipt = 'NOT CONFIRMED'
        # Old receipt notes belong to the old check, not the next receiver test.
        self.cases['02'] = 'NOT RUN'
        self.cases['03'] = 'NOT RUN'
        self.cases['04'] = 'NOT RUN'

    def recipient_checked_result(self, matches: bool) -> None:
        self.recipient_checked = bool(matches and self.gateway_ready and self.route is not None)
        self.owner_confirmed = False
        self.recipient_observation = 'NODE ID MATCHED' if self.recipient_checked else 'NOT VERIFIED'
        self.cases['02'] = 'SOFTWARE CHECK ONLY' if self.recipient_checked else 'NOT RUN'
        self.prepared = None
        self.authorised = False
        self.request_result = 'NOT SENT'
        self.receipt = 'NOT CONFIRMED'
        self.cases['03'] = 'NOT RUN'
        self.cases['04'] = 'NOT RUN'

    def confirm_owner(self) -> None:
        if not self.recipient_checked or self.route is None:
            raise ValueError('Check the recipient metadata before confirming its owner')
        # Human attestation; technical identity cannot prove who holds the radio.
        self.owner_confirmed = True
        self.cases['02'] = 'OPERATOR REPORTED IDENTITY CHECK'

    def preview(self) -> MeshText:
        if not self.gateway_ready or not self.recipient_checked or not self.owner_confirmed or self.route is None:
            raise ValueError('Check the gateway and confirm the receiver with its owner first')
        self.prepared = build_mesh_message('test')
        self.authorised = False
        self.request_result = 'NOT SENT'
        self.receipt = 'NOT CONFIRMED'
        self.cases['03'] = 'NOT RUN'
        self.cases['04'] = 'NOT RUN'
        return self.prepared

    def approve(self) -> None:
        if self.prepared is None or not self.gateway_ready or not self.recipient_checked or not self.owner_confirmed:
            raise ValueError('Preview a test and check the recipient first')
        if self.request_result != 'NOT SENT':
            raise ValueError('A new test needs a fresh preview')
        self.authorised = True

    def consume_send(self) -> tuple[ContactRoute, MeshText]:
        if (not self.authorised or self.prepared is None or self.route is None
                or not self.gateway_ready or not self.recipient_checked or not self.owner_confirmed
                or self.request_result != 'NOT SENT'):
            raise ValueError('A confirmed, unsent test is required')
        self.authorised = False
        self.request_result = 'IN PROGRESS'
        return self.route, self.prepared

    def sent(self, accepted: bool) -> None:
        if self.request_result != 'IN PROGRESS':
            raise ValueError('There is no pending test request')
        self.request_result = 'ACCEPTED BY HA; DELIVERY UNKNOWN' if accepted else 'REQUEST FAILED'
        self.cases['03'] = 'HA REQUEST ACCEPTED ONLY' if accepted else 'REQUEST FAILED'

    def record_receipt(self) -> None:
        if self.request_result != 'ACCEPTED BY HA; DELIVERY UNKNOWN':
            raise ValueError('No accepted test request to confirm')
        self.receipt = 'OPERATOR-REPORTED RECEIPT; NOT INDEPENDENTLY VERIFIED'
        self.cases['04'] = 'USER REPORTED RECEIPT'

    def report(self, version: str) -> str:
        # Keep this deliberately dull. Names, IDs, exact radio texts and
        # glucose numbers belong nowhere near an exported test report.
        if not isinstance(version, str) or not version or '\n' in version:
            raise ValueError('Invalid application version')
        lines = [f'LibreBeacon {version} — local Meshtastic field checklist',
                 f'Session started (UTC): {self.started.astimezone(timezone.utc).isoformat(timespec="seconds")}',
                 'This report is not evidence of medical or emergency reliability.',
                 f'Home Assistant gateway: {self.gateway_observation}',
                 f'Recipient node metadata: {self.recipient_observation}',
                 f'Test request: {self.request_result}',
                 f'Physical receipt: {self.receipt}', '',
                 'Field checks (NOT RUN unless recorded below):']
        for code, label in FIELD_CASES:
            lines.append(f'{code}. {label}: {self.cases[code]}')
        lines.extend(['', 'No recipient names, radio IDs, message bodies, tokens or glucose history are included.',
                      'A request accepted by Home Assistant is not a radio receipt.',
                      'Keep the official Libre alarms active.'])
        return '\n'.join(lines) + '\n'


def send_confirmed_field_test(client, trial: MeshFieldTrial, approved_routes: list[ContactRoute]) -> str:
    """Recheck the gateway and recipient immediately before that one send.

    Never call this for a preview. The session spends its permission once,
    even when Home Assistant fails. No optimistic retries, thanks.
    """
    route, prepared = trial.consume_send()
    if route not in approved_routes:
        raise ValueError('Recipient authorisation changed; recheck before sending')
    current = discover_gateways(client.states(), now=datetime.now(timezone.utc))
    if len(current) != 1 or current[0].status != 'HA REPORTS CONNECTED':
        raise ValueError('Meshtastic gateway is no longer verified')
    return dispatch_route(client, route, prepared.body,
                          mesh_kind='test', mesh_text=prepared)
