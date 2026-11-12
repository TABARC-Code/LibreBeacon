"""Mock clocks and destinations. No actual contact should hear a thing."""
import unittest
from librebeacon.mesh_fallback import MeshFallback, require_backup_send
from librebeacon.contacts import ContactRoute
from librebeacon.settings import Settings

REF = 'LB-0123456789ABCDEF'

class FallbackTests(unittest.TestCase):
    def setUp(self):
        self.f = MeshFallback()
        self.assertTrue(self.f.arm('notify.mesh_one', 'notify.mesh_two', REF,
                                   minutes=10, now=1000, listener_ready=True))

    def test_default_is_off(self):
        self.assertFalse(Settings().mesh_fallback_enabled)

    def test_no_reply_sends_only_one_backup_after_delay(self):
        self.assertIsNone(self.f.due(now=1599, listener_ready=True))
        self.assertEqual(self.f.due(now=1600, listener_ready=True), 'notify.mesh_two')
        self.assertIsNone(self.f.due(now=1700, listener_ready=True))
        self.f.sent(accepted=True)
        self.assertIn('delivery unconfirmed', self.f.describe())
        self.assertIsNone(self.f.due(now=1900, listener_ready=True))

    def test_listener_lost_cancels_no_reply_fallback(self):
        self.assertIsNone(self.f.due(now=1300, listener_ready=False))
        self.assertIn('cancelled', self.f.describe())
        self.assertIsNone(self.f.due(now=1600, listener_ready=True))

    def test_ok_holds_backup(self):
        self.f.reply(REF, 'notify.mesh_one', 'OK')
        self.assertIsNone(self.f.due(now=1600, listener_ready=True))
        self.assertIn('OK', self.f.describe())

    def test_cant_triggers_one_fallback(self):
        self.f.reply(REF, 'notify.mesh_one', 'CANT')
        self.assertEqual(self.f.due(now=1010, listener_ready=True), 'notify.mesh_two')
        self.assertIsNone(self.f.due(now=1011, listener_ready=True))

    def test_wrong_reply_cannot_cancel(self):
        for reference,destination,response in ((REF,'notify.mesh_two','OK'),('LB-FFFFFFFFFFFFFFFF','notify.mesh_one','OK'),(REF,'notify.mesh_one','UNKNOWN')):
            self.f.reply(reference,destination,response)
        self.assertEqual(self.f.due(now=1600,listener_ready=True),'notify.mesh_two')

    def test_manual_cancel(self):
        self.f.cancel()
        self.assertIsNone(self.f.due(now=1600,listener_ready=True))

    def test_no_reply_after_window_expiry(self):
        self.assertIsNone(self.f.due(now=2800,listener_ready=True))
        self.assertIn('expired', self.f.describe())

    def test_does_not_replace_pending_incident(self):
        self.assertFalse(self.f.arm('notify.mesh_one','notify.mesh_two', 'LB-FFFFFFFFFFFFFFFF',minutes=10,now=1100,listener_ready=True))
        self.assertEqual(self.f.pending.reference,REF)

    def test_invalid_delays_and_targets(self):
        for primary,backup,delay in (('a','a',10),('','b',10),('a','b',0),('a','b',21),('a','b',True),('a','b','10')):
            with self.subTest(primary=primary,backup=backup,delay=delay),self.assertRaises(ValueError):
                MeshFallback.validate(primary,backup,delay)

    def test_not_armed_without_listener(self):
        g=MeshFallback()
        self.assertFalse(g.arm('a','b',REF,minutes=10,now=1,listener_ready=False))
        self.assertIsNone(g.pending)

    def test_failed_backup_does_not_retry(self):
        self.f.due(now=1600,listener_ready=True)
        self.f.sent(accepted=False)
        self.assertIn('failed',self.f.describe())
        self.assertIsNone(self.f.due(now=1800,listener_ready=True))

if __name__=='__main__':unittest.main()



class QueuedBackupTests(unittest.TestCase):
    def setUp(self):
        self.primary = ContactRoute('First', 'notify.mesh_first', True, True, 17)
        self.backup = ContactRoute('Backup', 'notify.mesh_backup', True, True, 18)
        self.settings = Settings(
            enabled=True,
            enable_emergency_contacts=True,
            emergency_contact_consent=True,
            mesh_fallback_enabled=True,
            mesh_fallback_primary=self.primary.target,
            mesh_fallback_backup=self.backup.target,
            emergency_routes=[self.primary.as_dict(), self.backup.as_dict()])
        self.engine = MeshFallback()
        self.engine.arm(self.primary.target, self.backup.target, REF,
                        minutes=2, now=100, listener_ready=True)
        self.engine.due(now=220, listener_ready=True)

    def test_queued_backup_still_allowed(self):
        require_backup_send(self.engine, self.settings, self.backup, listener_ready=True)

    def test_revoking_any_global_switch_blocks_worker(self):
        for name in ('enabled','enable_emergency_contacts','emergency_contact_consent',
                     'mesh_fallback_enabled'):
            with self.subTest(name=name):
                setattr(self.settings,name,False)
                with self.assertRaises(ValueError):
                    require_backup_send(self.engine, self.settings, self.backup, listener_ready=True)
                setattr(self.settings,name,True)

    def test_revoked_contact_and_changed_selection_block_worker(self):
        self.settings.emergency_routes = [self.primary.as_dict()]
        with self.assertRaises(ValueError):
            require_backup_send(self.engine, self.settings, self.backup, listener_ready=True)
        self.settings.emergency_routes = [self.primary.as_dict(), self.backup.as_dict()]
        self.settings.mesh_fallback_backup = self.primary.target
        with self.assertRaises(ValueError):
            require_backup_send(self.engine, self.settings, self.backup, listener_ready=True)

    def test_listener_loss_blocks_even_after_cant(self):
        with self.assertRaises(ValueError):
            require_backup_send(self.engine, self.settings, self.backup, listener_ready=False)
        cancelled = MeshFallback()
        cancelled.arm(self.primary.target,self.backup.target,REF,minutes=2,now=100,listener_ready=True)
        cancelled.reply(REF,self.primary.target,'CANT')
        self.assertIsNone(cancelled.due(now=101,listener_ready=False))
        self.assertEqual(cancelled.pending.state,'cancelled')

    def test_operator_can_cancel_queued_send(self):
        self.engine.cancel('Operator stopped the backup')
        self.assertEqual(self.engine.pending.state,'cancelled')
        self.assertIn('cannot be recalled',self.engine.pending.outcome)
        with self.assertRaises(ValueError):
            require_backup_send(self.engine,self.settings,self.backup,listener_ready=True)
        self.engine.sent(accepted=True)
        self.assertEqual(self.engine.pending.state,'cancelled')


class BackupWorkerTests(unittest.TestCase):
    # These sit beside the actual worker, not just its policy class.
    def make_queued_send(self):
        from types import SimpleNamespace
        from threading import Event
        from time import monotonic
        from librebeacon.app import LibreBeaconApp

        first = ContactRoute('First', 'notify.mesh_first', True, True, 17)
        backup = ContactRoute('Backup', 'notify.mesh_backup', True, True, 18)
        settings = Settings(enabled=True, enable_emergency_contacts=True,
                            emergency_contact_consent=True, mesh_fallback_enabled=True,
                            mesh_fallback_primary=first.target, mesh_fallback_backup=backup.target,
                            emergency_routes=[first.as_dict(), backup.as_dict()])
        engine = MeshFallback()
        engine.arm(first.target, backup.target, REF, minutes=2,
                   now=monotonic()-150, listener_ready=True)

        class FakeHA:
            def __init__(self):
                self.sent = []
                self.after_lookup = None
                self.gateway_state = 'connected'
                self.after_gateway = None

            def states(self):
                if self.after_gateway:
                    self.after_gateway()
                return [{'entity_id': 'meshtastic.gateway_local',
                         'state': self.gateway_state,
                         'attributes': {'device_class': 'gateway'}}]

            def state(self, target):
                if self.after_lookup:
                    self.after_lookup()
                return {'entity_id': target, 'state': 'unknown',
                        'attributes': {'node_id': 18, 'user_id': '!00000012'}}

            def send_notification(self, target, message):
                self.sent.append((target, message))

        client = FakeHA()
        queued, status = [], []
        app = SimpleNamespace(mesh_fallback=engine, settings=settings,
                              mesh_listener_ready=True, mesh_listener_active=True,
                              mesh_listener_stop=Event(), last_fallback_tick=monotonic(),
                              client=lambda: client,
                              status=SimpleNamespace(set=status.append),
                              start=lambda key, work: queued.append((key, work)))
        LibreBeaconApp.check_mesh_fallback(app)
        self.assertEqual(len(queued), 1)
        self.assertEqual(queued[0][0], 'mesh_fallback_delivery')
        return app, client, queued[0][1]

    def test_live_backup_worker_sends_one_approved_message(self):
        _, client, send = self.make_queued_send()
        target, accepted, error, reference = send()
        self.assertEqual((target, accepted, error), ('notify.mesh_backup', True, ''))
        self.assertEqual(len(client.sent), 1)
        self.assertEqual(client.sent[0][0], target)
        self.assertTrue(reference.startswith('LB-'))

    def test_consent_revoked_while_ha_lookup_was_pending(self):
        app, client, send = self.make_queued_send()
        client.after_lookup = lambda: app.settings.emergency_routes[-1].update(consent=False)
        self.assertFalse(send()[1])
        self.assertEqual(client.sent, [])

    def test_stop_listening_while_ha_lookup_was_pending(self):
        app, client, send = self.make_queued_send()
        def disconnect():
            app.mesh_listener_ready = False
            app.mesh_listener_stop.set()
        client.after_lookup = disconnect
        self.assertFalse(send()[1])
        self.assertEqual(client.sent, [])

    def test_cancelling_while_ha_lookup_was_pending(self):
        app, client, send = self.make_queued_send()
        client.after_lookup = lambda: app.mesh_fallback.cancel('Operator stopped backup')
        self.assertFalse(send()[1])
        self.assertEqual(client.sent, [])

    def test_disconnected_gateway_blocks_queued_backup(self):
        app, client, send = self.make_queued_send()
        client.gateway_state = 'disconnected'
        self.assertFalse(send()[1])
        self.assertEqual(client.sent, [])

    def test_untyped_gateway_blocks_queued_backup(self):
        app, client, send = self.make_queued_send()
        client.states = lambda: [{'entity_id': 'meshtastic.gateway_local',
                                  'state': 'connected', 'attributes': {}}]
        self.assertFalse(send()[1])
        self.assertEqual(client.sent, [])

    def test_consent_revoked_during_gateway_lookup_blocks_backup(self):
        app, client, send = self.make_queued_send()
        client.after_gateway = lambda: app.settings.emergency_routes[-1].update(consent=False)
        self.assertFalse(send()[1])
        self.assertEqual(client.sent, [])

    def test_listener_disconnected_during_gateway_lookup_blocks_backup(self):
        app, client, send = self.make_queued_send()
        client.after_gateway = app.mesh_listener_stop.set
        self.assertFalse(send()[1])
        self.assertEqual(client.sent, [])
