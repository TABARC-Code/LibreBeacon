"""Mock transports: sending a test must never reach someone's actual inbox."""
import unittest
from datetime import timedelta
from librebeacon.contacts import ContactRoute, read_routes, emergency_message, dispatch_emergency, dispatch_route
from librebeacon.core import AlertEngine, Reading, ReadingError
from librebeacon.app import LibreBeaconApp
from librebeacon.settings import Settings
from librebeacon.homeassistant import HomeAssistant, HomeAssistantError
from datetime import datetime, timezone

NOW = datetime(2026, 10, 17, 12, tzinfo=timezone.utc)

class FakeHomeAssistant:
    def __init__(self, broken=None):
        self.broken = broken
        self.requests = []
    def state(self, target):
        return {'entity_id': target, 'state': 'unknown', 'attributes': {}}
    def send_notification(self, target, message):
        self.requests.append(('notify',target,message))
        if self.broken==target: raise HomeAssistantError('Cannot reach target')
    def run_script(self, target, *, event, message):
        self.requests.append(('script',target,event,message))
        if self.broken==target: raise HomeAssistantError('Cannot reach target')

class ContactTests(unittest.TestCase):
    def test_disabled_by_default(self):
        s=Settings()
        self.assertFalse(s.enabled)
        self.assertFalse(s.enable_emergency_contacts)
        self.assertFalse(s.emergency_contact_consent)
        self.assertEqual(s.emergency_routes,[])
        self.assertEqual(s.critical_low_mmol,'')

    def test_no_broadcast_or_untyped_destinations(self):
        for entity in ('notify','light.kitchen','', 'script.', 'notify.bad/id'):
            with self.subTest(entity=entity), self.assertRaises(ValueError):
                ContactRoute('Friend',entity,True,True).validate()

    def test_reject_common_mesh_broadcast_destinations(self):
        for entity in ('notify.mesh_channel_public','notify.mesh_broadcast','notify.mesh_all'):
            with self.subTest(entity=entity), self.assertRaises(ValueError):
                ContactRoute('Friend',entity,True,True).validate()

    def test_unexpected_boolean_text_rejected(self):
        with self.assertRaises(ValueError):
            read_routes([{'label':'Friend','target':'notify.friend','consent':'false','enabled':True}])

    def test_consent_required(self):
        with self.assertRaises(ValueError):
            ContactRoute('Friend','notify.friend',False,True).validate()
        with self.assertRaises(ValueError):
            LibreBeaconApp.validate(Settings(enable_emergency_contacts=True))

    def test_no_duplicate_recipient(self):
        x=ContactRoute('One','notify.friend',True,True).as_dict()
        with self.assertRaises(ValueError):
            read_routes([x,x])

    def test_missing_critical_threshold_blocks_enable(self):
        s=Settings(enable_emergency_contacts=True,emergency_contact_consent=True,
                   emergency_routes=[ContactRoute('One','notify.friend',True,True).as_dict()])
        with self.assertRaisesRegex(ValueError,'critical-low threshold'):
            LibreBeaconApp.validate(s)

    def test_threshold_must_be_lower(self):
        for critical in ('4.0','0','nan','13'):
            with self.subTest(critical=critical),self.assertRaises(ValueError):
                LibreBeaconApp.validate(Settings(low_mmol='3.9',critical_low_mmol=critical))

    def test_normal_then_low_then_critical(self):
        e=AlertEngine()
        def r(value):return Reading(value,NOW,'mmol/l')
        self.assertIsNone(e.observe(r(6),3.9,13,10,NOW,critical_low=3.0))
        self.assertEqual(e.observe(r(3.5),3.9,13,10,NOW,critical_low=3.0),'low')
        self.assertEqual(e.observe(r(2.5),3.9,13,10,NOW,critical_low=3.0),'critical_low')
        self.assertIsNone(e.observe(r(2.4),3.9,13,10,NOW,critical_low=3.0))
        self.assertIsNone(e.observe(r(3.5),3.9,13,10,NOW,critical_low=3.0))

    def test_critical_never_emitted_for_stale(self):
        with self.assertRaises(ReadingError):
            AlertEngine().observe(Reading(2.0,NOW-timedelta(minutes=30),'mmol/l'),
                                  3.9,13,10,NOW,critical_low=3.0)

    def test_glucose_private_by_default(self):
        message=emergency_message()
        self.assertNotIn('mmol',message)
        self.assertIn('critical-low',message)
        self.assertIn('2.4 mmol/L',emergency_message(True,2.4))

    def test_selected_notify_entity_only(self):
        h=FakeHomeAssistant()
        dispatch_route(h,ContactRoute('One','notify.friend',True,True),'TEST ONLY')
        self.assertEqual(h.requests,[('notify','notify.friend','TEST ONLY')])

    def test_selected_script_only(self):
        h=FakeHomeAssistant()
        dispatch_route(h,ContactRoute('Two','script.send_email',True,True),'TEST ONLY')
        self.assertEqual(h.requests,[('script','script.send_email','critical_low','TEST ONLY')])

    def test_other_contact_attempted_after_failure(self):
        h=FakeHomeAssistant('notify.broken')
        contacts=[ContactRoute('One','notify.broken',True,True),
                  ContactRoute('Two','notify.working',True,True)]
        results=[]
        dispatch_emergency(contacts,h,emergency_message(),lambda *args:results.append(args))
        self.assertEqual([r[1] for r in results],[False,True])
        self.assertEqual(len(h.requests),2)

    def test_specific_notify_only_and_safe_payload(self):
        api=HomeAssistant('http://localhost:8123','not-real')
        api.request=lambda method,path,payload:(method,path,payload)
        self.assertEqual(api.send_notification('notify.mesh_friend','hello'),None)
        with self.assertRaises(HomeAssistantError):
            api.send_notification('notify','test')
        with self.assertRaises(HomeAssistantError):
            api.send_notification('script.bad','test')

    def test_validate_good_config_when_monitoring_off(self):
        s=Settings(low_mmol='3.9',critical_low_mmol='3.0',
                   enable_emergency_contacts=True,emergency_contact_consent=True,
                   emergency_routes=[ContactRoute('Friend','notify.friend',True,True).as_dict()])
        LibreBeaconApp.validate(s)

if __name__ == '__main__':unittest.main()

class IntegrationTests(unittest.TestCase):
    def test_settings_round_trip_preserves_contacts_without_secrets(self):
        from tempfile import TemporaryDirectory
        from pathlib import Path
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / 'settings.json'
            route = ContactRoute('Person A','notify.person_a',True,True).as_dict()
            s = Settings(low_mmol='4',critical_low_mmol='3',emergency_routes=[route])
            s.save(path)
            contents=path.read_text(encoding='utf-8')
            self.assertNotIn('Bearer ',contents)
            self.assertEqual(Settings.load(path).emergency_routes,[route])

    def test_emergency_disabled_never_issues_contact_requests(self):
        from types import SimpleNamespace
        from librebeacon.app import LibreBeaconApp
        s=Settings(enable_emergency_contacts=False,enable_contacts=False,
                   enable_visual=False,enable_sound=False,enable_speech=False,
                   enable_ha_visual=False,emergency_routes=[ContactRoute('A','notify.a',True,True).as_dict()])
        dummy=SimpleNamespace(settings=s)
        LibreBeaconApp.alert(dummy,'critical_low','critical reading',2.4)

    def test_selected_contacts_sent_on_critical_only(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        class FakeStatus:
            def set(self, text):pass
        sender=FakeHomeAssistant()
        s=Settings(enable_emergency_contacts=True,enable_contacts=False,
                   enable_visual=False,enable_sound=False,enable_speech=False,
                   enable_ha_visual=False,emergency_routes=[ContactRoute('A','notify.a',True,True).as_dict()])
        completed=[]
        dummy=SimpleNamespace(settings=s,session_token='token',status=FakeStatus(),
                  start=lambda key, fn: completed.append((key,fn())))
        with patch('librebeacon.app.HomeAssistant',return_value=sender):
            LibreBeaconApp.alert(dummy,'low','ordinary',3.3)
            self.assertEqual(sender.requests,[])
            LibreBeaconApp.alert(dummy,'critical_low','critical',2.3)
        self.assertEqual([x[1] for x in sender.requests],['notify.a'])
        self.assertEqual(len(completed),1)
        self.assertEqual(completed[0][0], 'emergency_delivery')
        self.assertEqual([x[1] for x in completed[0][1]], [True])
