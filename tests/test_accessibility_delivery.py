"""Local-only tests. No glucose network calls, emails or alarms to third parties."""
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from librebeacon.app import LibreBeaconApp
from librebeacon.delivery import DeliveryTracker
from librebeacon.outputs import SOUND_PATTERNS, tone_pattern, beep
from librebeacon.settings import Settings
from librebeacon.contacts import ContactRoute

NOW = datetime(2026, 10, 27, 18, 0, tzinfo=timezone.utc)


class AccessibilityTests(unittest.TestCase):
    def test_no_motion_without_opt_in(self):
        self.assertFalse(Settings().pulse_visual)

    def test_patterns_are_short_and_bounded(self):
        self.assertEqual(set(SOUND_PATTERNS), {'Gentle', 'Standard', 'Distinct'})
        for style in SOUND_PATTERNS:
            pattern = tone_pattern(style)
            self.assertGreater(len(pattern), 0)
            self.assertLessEqual(sum(length for _, length in pattern), 650)
            self.assertTrue(all(400 <= freq <= 1000 and 50 <= duration <= 250
                                for freq, duration in pattern))

    def test_invalid_pattern_rejected_before_audio(self):
        with self.assertRaises(ValueError):
            tone_pattern('siren')
        with self.assertRaises(ValueError):
            LibreBeaconApp.validate(Settings(sound_style='siren'))

    def test_non_windows_audio_reports_unavailable(self):
        with patch('librebeacon.outputs.sys.platform', 'linux'):
            self.assertFalse(beep('Gentle'))

    def test_emergency_enabled_requires_active_contact(self):
        route = ContactRoute('Friend', 'notify.friend', True, False)
        s = Settings(enable_emergency_contacts=True, emergency_contact_consent=True,
                     emergency_routes=[route.as_dict()], critical_low_mmol='3.0',low_mmol='4.0')
        with self.assertRaisesRegex(ValueError, 'Enable at least one'):
            LibreBeaconApp.validate(s)

    def test_old_saved_settings_remain_compatible(self):
        settings = Settings()
        self.assertEqual(settings.sound_style, 'Standard')
        self.assertFalse(settings.pulse_visual)


class DiagnosticTests(unittest.TestCase):
    def test_attempt_time_and_failure_label(self):
        tracker = DeliveryTracker()
        tracker.record('notify.friend', accepted=False, kind='test',
                       error_type='HomeAssistantError', now=NOW)
        self.assertIn('HomeAssistantError', tracker.description('notify.friend'))
        self.assertIn('failed', tracker.summary(['notify.friend']))

    def test_unsafe_error_text_is_not_exposed(self):
        tracker = DeliveryTracker()
        tracker.record('notify.friend', accepted=False, kind='test',
                       error_type='Bearer secret123 contact@example.org', now=NOW)
        self.assertNotIn('secret123', tracker.description('notify.friend'))
        self.assertNotIn('example.org', tracker.description('notify.friend'))

    def test_last_attempt_only_no_message_body(self):
        tracker = DeliveryTracker()
        tracker.record('notify.friend', accepted=True, kind='test', now=NOW)
        tracker.record('notify.friend', accepted=False, kind='critical_low', now=NOW)
        self.assertEqual(len(tracker.attempts), 1)
        self.assertIn('failed', tracker.description('notify.friend'))
        self.assertNotIn('accepted', tracker.description('notify.friend'))

    def test_accepted_is_not_automatically_delivered(self):
        tracker = DeliveryTracker()
        tracker.record('notify.friend', accepted=True, kind='test', now=NOW)
        self.assertIn('unconfirmed', tracker.description('notify.friend'))
        self.assertNotIn('0 failed; 1 manually', tracker.summary(['notify.friend']))


if __name__ == '__main__':
    unittest.main()

class ReleaseTests(unittest.TestCase):
    def test_version_matches_windows_installer(self):
        from pathlib import Path
        from librebeacon import __version__
        root = Path(__file__).resolve().parents[1]
        self.assertIn(f'!define APP_VERSION "{__version__}"',
                      (root / 'installer' / 'LibreBeacon.nsi').read_text(encoding='utf-8'))
        self.assertIn(f'version = "{__version__}"',
                      (root / 'pyproject.toml').read_text(encoding='utf-8'))
