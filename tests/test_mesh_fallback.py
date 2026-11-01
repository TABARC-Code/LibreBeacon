"""Mock clocks and destinations. No actual contact should hear a thing."""
import unittest
from librebeacon.mesh_fallback import MeshFallback
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
        self.assertEqual(self.f.due(now=1010, listener_ready=False), 'notify.mesh_two')
        self.assertIsNone(self.f.due(now=1011, listener_ready=False))

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
