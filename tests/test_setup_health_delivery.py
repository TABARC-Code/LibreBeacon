"""Offline checks; no messages leave this test process."""
import unittest
from datetime import datetime, timedelta, timezone

from librebeacon.settings import Settings
from librebeacon.readiness import setup_checks
from librebeacon.health import ConnectionHealth
from librebeacon.delivery import DeliveryTracker
from librebeacon.contacts import read_routes, ContactRoute

NOW = datetime(2026, 10, 19, 12, tzinfo=timezone.utc)


class SetupTests(unittest.TestCase):
    def test_first_run_does_not_enable_notifications(self):
        s = Settings()
        checks = setup_checks(s, False)
        self.assertFalse(s.enabled)
        self.assertFalse(s.enable_emergency_contacts)
        self.assertFalse(checks[0].ready)
        self.assertFalse(checks[1].ready)
        self.assertFalse(checks[2].ready)

    def test_ready_when_explicitly_configured(self):
        s = Settings(ha_url='http://homeassistant.local:8123',
                     glucose_entity='sensor.glucose', timestamp_entity='sensor.measurement_time',
                     low_mmol='3.9', high_mmol='13.0')
        checks = setup_checks(s, True)
        self.assertTrue(all(x.ready for x in checks[:4]))
        self.assertFalse(checks[4].ready)

    def test_thresholds_do_not_accept_nan(self):
        for bad in ('nan', 'inf', '', '14'):
            s = Settings(low_mmol=bad, high_mmol='13')
            self.assertFalse(setup_checks(s, True)[2].ready)

    def test_same_sensor_cannot_pass_setup(self):
        s = Settings(glucose_entity='sensor.one', timestamp_entity='sensor.one')
        self.assertFalse(setup_checks(s, True)[1].ready)

    def test_contacts_ready_with_named_routes(self):
        route = ContactRoute('Neighbour', 'notify.neighbour', True, True)
        s = Settings(emergency_routes=[route.as_dict()])
        self.assertTrue(setup_checks(s, False)[4].ready)

    def test_duplicate_contact_nickname_rejected(self):
        with self.assertRaisesRegex(ValueError,'different nickname'):
            read_routes([ContactRoute('Friend','notify.a',True,True).as_dict(),
                         ContactRoute('FRIEND','notify.b',True,True).as_dict()])


class HealthTests(unittest.TestCase):
    def test_initially_not_checked(self):
        self.assertEqual(ConnectionHealth().report(NOW,10).state, 'NOT CHECKED')

    def test_measurement_time_not_poll_time(self):
        h = ConnectionHealth()
        h.success(NOW-timedelta(minutes=12), NOW)
        self.assertEqual(h.report(NOW, 10).state, 'STALE')

    def test_old_reading_goes_stale_without_new_poll(self):
        h = ConnectionHealth()
        h.success(NOW, NOW)
        self.assertEqual(h.report(NOW+timedelta(minutes=3), 10).state, 'CURRENT')
        self.assertEqual(h.report(NOW+timedelta(minutes=11),10).state, 'STALE')

    def test_failure_and_recovery(self):
        h = ConnectionHealth()
        h.failure(NOW)
        h.failure(NOW+timedelta(minutes=1))
        r = h.report(NOW+timedelta(minutes=1),10)
        self.assertEqual(r.state,'UNAVAILABLE')
        self.assertIn('2 consecutive',r.detail)
        h.success(NOW+timedelta(minutes=2),NOW+timedelta(minutes=2))
        self.assertEqual(h.report(NOW+timedelta(minutes=2),10).state,'CURRENT')

    def test_future_clock_warning(self):
        h=ConnectionHealth()
        h.success(NOW+timedelta(minutes=8),NOW)
        self.assertEqual(h.report(NOW, 10).state,'CLOCK ERROR')


class DeliveryTests(unittest.TestCase):
    def test_cannot_confirm_without_accepted_request(self):
        d=DeliveryTracker()
        with self.assertRaises(ValueError): d.confirm('notify.neighbour')
        d.record('notify.neighbour', accepted=False,kind='test')
        with self.assertRaises(ValueError): d.confirm('notify.neighbour')

    def test_accepted_not_automatically_confirmed(self):
        d=DeliveryTracker()
        d.record('notify.neighbour', accepted=True,kind='test')
        self.assertIn('unconfirmed',d.description('notify.neighbour'))
        d.confirm('notify.neighbour')
        self.assertIn('manually',d.description('notify.neighbour'))

    def test_new_attempt_clears_old_manual_reply(self):
        d=DeliveryTracker()
        d.record('notify.neighbour',accepted=True,kind='test')
        d.confirm('notify.neighbour')
        d.record('notify.neighbour',accepted=True,kind='critical_low')
        self.assertIn('unconfirmed',d.description('notify.neighbour'))

    def test_no_glucose_details_in_tracker(self):
        d=DeliveryTracker()
        d.record('notify.neighbour',accepted=True,kind='test')
        self.assertEqual(set(vars(d.attempts['notify.neighbour'])),
                         {'accepted','kind','confirmed_manually','attempted_at','error_type','reference'})


if __name__ == '__main__':
    unittest.main()
