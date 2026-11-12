"""One complete mock incident through the application queue, with no radio traffic."""
from datetime import datetime, timedelta, timezone
from queue import Queue
from threading import Event
from time import monotonic
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock

from librebeacon.app import LibreBeaconApp
from librebeacon.contacts import ContactRoute
from librebeacon.delivery import DeliveryTracker
from librebeacon.mesh_fallback import MeshFallback
from librebeacon.mesh_replies import MeshReplyTracker
from librebeacon.settings import Settings

REF = 'LB-0123456789ABCDEF'
FIRST = ContactRoute('First', 'notify.mesh_first', True, True, 17)
BACKUP = ContactRoute('Backup', 'notify.mesh_backup', True, True, 18)
GATEWAY = 19


class FakeHA:
    def __init__(self):
        self.sent = []
        self.gateway_state = 'connected'

    def states(self):
        return [{'entity_id': 'meshtastic.gateway_local',
                 'state': self.gateway_state,
                 'attributes': {'device_class': 'gateway'}}]

    def state(self, entity):
        return {'entity_id': entity, 'state': 'unknown',
                'attributes': {'node_id': BACKUP.mesh_node_id,
                               'user_id': '!00000012'}}

    def send_notification(self, entity, message):
        self.sent.append((entity, message))


def radio_reply(response='CANT', *, reference=REF, sender=17, age_seconds=0):
    fired = datetime.now(timezone.utc) - timedelta(seconds=age_seconds)
    return {
        'event_type': 'meshtastic_api_text_message',
        'time_fired': fired.isoformat(),
        'data': {'node': sender, 'message_id': 9876,
                 'data': {'from': sender, 'gateway': GATEWAY,
                          'to': {'node': GATEWAY, 'channel': None},
                          'message': reference + ' ' + response}},
    }


class BackupFlowTests(TestCase):
    def setUp(self):
        self.client = FakeHA()
        self.works = []
        self.status = []
        self.replies_status = []
        self.app = SimpleNamespace(
            queue=Queue(), busy_poll=False,
            root=SimpleNamespace(after=lambda *_: None),
            process_queue=lambda: None,
            settings=Settings(
                enabled=True, enable_emergency_contacts=True,
                emergency_contact_consent=True,
                mesh_gateway_node_id=str(GATEWAY), mesh_fallback_enabled=True,
                mesh_fallback_primary=FIRST.target,
                mesh_fallback_backup=BACKUP.target,
                mesh_fallback_minutes=2,
                emergency_routes=[FIRST.as_dict(), BACKUP.as_dict()]),
            route_records=[FIRST, BACKUP],
            mesh_fallback=MeshFallback(), mesh_replies=MeshReplyTracker(),
            mesh_listener_ready=True, mesh_listener_active=True,
            mesh_listener_stop=Event(),
            deliveries=DeliveryTracker(),
            mesh_reply_state=SimpleNamespace(set=self.replies_status.append),
            status=SimpleNamespace(set=self.status.append),
            refresh_routes=Mock(), client=lambda: self.client,
            start=lambda key,work:self.works.append((key,work)),
            last_fallback_tick=monotonic(),
        )

    def flush(self):
        LibreBeaconApp.process_queue(self.app)

    def accepted_primary(self, reference=REF):
        self.app.queue.put(('emergency_delivery', True,
                            [(FIRST.label, True, '', reference)]))
        self.flush()

    def incoming(self, response='CANT', **kwargs):
        self.app.queue.put(('mesh_reply_event', True, (
            self.app.mesh_listener_stop, radio_reply(response, **kwargs))))
        self.flush()

    def queue_backup(self):
        self.app.last_fallback_tick = monotonic()
        LibreBeaconApp.check_mesh_fallback(self.app)

    def test_accepted_primary_is_tracked_before_backup_is_armed(self):
        self.accepted_primary()
        self.assertIn(REF, self.app.mesh_replies.incidents)
        self.assertEqual(self.app.mesh_fallback.pending.reference, REF)
        self.assertEqual(self.app.mesh_fallback.pending.state, 'waiting')
        self.assertEqual(self.works, [])

    def test_unknown_gateway_identity_holds_backup_even_if_primary_was_accepted(self):
        self.app.settings.mesh_gateway_node_id = ''
        self.accepted_primary()
        self.assertIsNone(self.app.mesh_fallback.pending)
        self.assertEqual(self.works, [])
        self.assertTrue(any('unavailable' in value for value in self.replies_status))

    def test_unavailable_reply_tracker_holds_backup(self):
        self.app.mesh_replies.register = Mock(side_effect=ValueError('tracker full'))
        self.accepted_primary()
        self.assertIsNone(self.app.mesh_fallback.pending)
        self.assertEqual(self.works, [])

    def test_matching_ok_cancels_and_never_queues_backup(self):
        self.accepted_primary()
        self.incoming('OK')
        self.assertEqual(self.app.mesh_fallback.pending.state, 'cancelled')
        self.queue_backup()
        self.assertEqual(self.works, [])
        self.assertEqual(self.client.sent, [])

    def test_matching_cant_queues_exactly_one_backup(self):
        self.accepted_primary()
        self.incoming('CANT')
        self.assertEqual(self.app.mesh_fallback.pending.state, 'cant')
        self.queue_backup()
        self.assertEqual(len(self.works), 1)
        target, accepted, _, reference = self.works.pop()[1]()
        self.assertEqual(target, BACKUP.target)
        self.assertTrue(accepted)
        self.assertTrue(reference.startswith('LB-'))
        self.assertEqual(len(self.client.sent), 1)
        self.queue_backup()
        self.assertEqual(self.works, [])

    def test_disconnected_gateway_blocks_queued_backup(self):
        self.accepted_primary()
        self.incoming('CANT')
        self.queue_backup()
        self.assertEqual(len(self.works), 1)
        self.client.gateway_state = 'disconnected'
        self.assertFalse(self.works[0][1]()[1])
        self.assertEqual(self.client.sent, [])

    def test_lost_listener_blocks_after_matching_cant(self):
        self.accepted_primary()
        self.incoming('CANT')
        self.app.mesh_listener_stop.set()
        self.app.queue.put(('mesh_reply_stopped', True, (
            self.app.mesh_listener_stop, None)))
        self.flush()
        self.queue_backup()
        self.assertEqual(self.works, [])
        self.assertEqual(self.app.mesh_fallback.pending.state, 'cancelled')

    def test_delayed_cant_reply_does_not_trigger_instant_backup(self):
        self.accepted_primary()
        incident = self.app.mesh_replies.incidents[REF]
        incident.created_at -= timedelta(minutes=5)
        self.incoming('CANT', age_seconds=180)
        self.assertEqual(self.app.mesh_fallback.pending.state, 'waiting')
        self.queue_backup()
        self.assertEqual(self.works, [])

    def test_wrong_sender_does_not_trigger_a_backup(self):
        self.accepted_primary()
        self.incoming('CANT', sender=21)
        self.assertEqual(self.app.mesh_fallback.pending.state, 'waiting')
        self.queue_backup()
        self.assertEqual(self.works, [])

    def test_primary_rejection_never_arms_backup(self):
        self.app.queue.put(('emergency_delivery', True,
                            [(FIRST.label, False, 'HomeAssistantError', '')]))
        self.flush()
        self.assertIsNone(self.app.mesh_fallback.pending)
