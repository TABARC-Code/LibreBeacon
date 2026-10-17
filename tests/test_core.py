import unittest
from datetime import datetime, timezone, timedelta
from librebeacon.core import AlertEngine, Reading, ReadingError, decode_reading
from librebeacon.app import LibreBeaconApp
from types import SimpleNamespace
from librebeacon.settings import Settings
from librebeacon.homeassistant import HomeAssistant, HomeAssistantError

NOW = datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc)

def states(value='5.6', unit='mmol/L', stamp=None):
    stamp=stamp or NOW - timedelta(minutes=2)
    return ({'state':value,'attributes':{'unit_of_measurement':unit}},
            {'state':stamp.isoformat(),'attributes':{'device_class':'timestamp'}})

class DataTests(unittest.TestCase):
    def test_good_mmol(self):
        r=decode_reading(*states())
        self.assertAlmostEqual(r.mmol,5.6)
        r.validated(10,NOW)

    def test_mgdl_conversion(self):
        r=decode_reading(*states('180.182','mg/dL'))
        self.assertAlmostEqual(r.mmol,10.0,places=4)

    def test_unknown_units_rejected(self):
        for unit in ('','mmol','unknown'):
            with self.subTest(unit=unit),self.assertRaises(ReadingError):
                decode_reading(*states(unit=unit))

    def test_bad_values_rejected(self):
        for val in ('unknown','unavailable','NaN','inf','-1','0','600'):
            with self.subTest(val=val),self.assertRaises(ReadingError):
                decode_reading(*states(val))

    def test_freshness_source_timestamp_not_homeassistant_update(self):
        a,b=states(stamp=NOW-timedelta(minutes=20))
        a['last_updated']=NOW.isoformat()
        with self.assertRaises(ReadingError):
            decode_reading(a,b).validated(10,NOW)

    def test_future_time_rejected(self):
        with self.assertRaises(ReadingError):
            decode_reading(*states(stamp=NOW+timedelta(minutes=5))).validated(10,NOW)

    def test_timestamp_requires_timezone(self):
        a,b=states(); b['state']='2026-10-17T11:58:00'
        with self.assertRaises(ReadingError):decode_reading(a,b)

    def test_low_deduplicated_within_episode(self):
        a=AlertEngine()
        low=Reading(3.0,NOW, 'mmol/l')
        self.assertEqual(a.observe(low,3.9,13.0,10,NOW), 'low')
        self.assertIsNone(a.observe(low,3.9,13.0,10,NOW))
        a.invalidate()
        self.assertIsNone(a.observe(low,3.9,13.0,10,NOW))

    def test_resets_on_normal_only_and_cooldown(self):
        a=AlertEngine()
        self.assertEqual(a.observe(Reading(3,NOW,'mmol/l'),3.9,13,10,NOW),'low')
        a.observe(Reading(6,NOW,'mmol/l'),3.9,13,10,NOW)
        self.assertIsNone(a.observe(Reading(3,NOW,'mmol/l'),3.9,13,10,NOW))
        future=NOW+timedelta(minutes=20)
        a.observe(Reading(6,future,'mmol/l'),3.9,13,10,future)
        self.assertEqual(a.observe(Reading(3,future,'mmol/l'),3.9,13,10,future),'low')

    def test_low_to_high_not_suppressed_by_same_event_cooldown(self):
        a=AlertEngine()
        self.assertEqual(a.observe(Reading(3,NOW,'mmol/l'),3.9,13,10,NOW),'low')
        self.assertEqual(a.observe(Reading(15,NOW,'mmol/l'),3.9,13,10,NOW),'high')

    def test_high(self):
        self.assertEqual(AlertEngine().observe(Reading(15,NOW,'mmol/l'),3.9,13,10,NOW),'high')

    def test_enabled_requires_both_sensors_and_thresholds(self):
        with self.assertRaises(ValueError):
            LibreBeaconApp.validate(Settings(enabled=True))

    def test_contact_requires_consent(self):
        with self.assertRaises(ValueError):
            LibreBeaconApp.validate(Settings(enable_contacts=True))

    def test_manual_refresh_never_sends_automatic_alert(self):
        class Flag:
            def set(self, value): pass
        alerts=[]
        dummy=SimpleNamespace(number=Flag(),details=Flag(),status=Flag(),
            settings=Settings(enabled=True,low_mmol='3.9',high_mmol='13.0'),
            engine=AlertEngine(),alert=lambda event,message,mmol=None: alerts.append(event))
        LibreBeaconApp.show_reading(dummy,*states('3.0'),allow_alerts=False)
        self.assertEqual(alerts,[])

    def test_auto_refresh_can_send_alert(self):
        class Flag:
            def set(self, value): pass
        alerts=[]
        dummy=SimpleNamespace(number=Flag(),details=Flag(),status=Flag(),event_label=Flag(),
            settings=Settings(enabled=True,low_mmol='3.9',high_mmol='13.0'),
            engine=AlertEngine(),alert=lambda event,message,mmol=None: alerts.append(event))
        a,b=states('3.0',stamp=datetime.now(timezone.utc)-timedelta(minutes=2))
        LibreBeaconApp.show_reading(dummy,a,b,allow_alerts=True)
        self.assertEqual(alerts,['low'])

    def test_url_rejects_credentials_and_paths(self):
        for url in ('file:///x','http://name:pw@example.com','https://example.com/internal', 'x'):
            with self.subTest(url=url), self.assertRaises(HomeAssistantError):
                HomeAssistant(url,'TOKEN')

    def test_script_id_validated_without_network(self):
        api=HomeAssistant('http://localhost:8123','TOKEN')
        with self.assertRaises(HomeAssistantError):
            api.run_script('light.kitchen',event='test',message='Test')

if __name__=='__main__':unittest.main()
