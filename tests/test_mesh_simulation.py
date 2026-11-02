"""Fictional nodes and a fixed clock. Nothing here transmits a message."""
import unittest
from unittest.mock import patch
from librebeacon.mesh_simulation import SCENARIOS, simulate_fallback


class MeshSimulationTests(unittest.TestCase):
    def test_every_case_has_an_explicit_simulation_warning(self):
        for case in SCENARIOS:
            with self.subTest(case=case):
                report = simulate_fallback(case)
                self.assertIn('SIMULATION ONLY', report.text)
                self.assertIn('no radio messages sent', report.text)
                self.assertNotIn('mmol/L', report.text)

    def test_scenarios_never_call_any_radio_sender(self):
        with patch('librebeacon.contacts.dispatch_route', side_effect=AssertionError('Actual dispatch!')):
            with patch('librebeacon.homeassistant.HomeAssistant', side_effect=AssertionError('HA connection!')):
                for case in SCENARIOS:
                    simulate_fallback(case)

    def test_ok_and_failures_hold_backup(self):
        for name in ('Primary replies OK', 'Reply listener disconnects',
                     'Windows sleeps or stalls', 'Fallback expires', 'Contact selection invalid'):
            with self.subTest(name=name):
                self.assertFalse(simulate_fallback(name).backup_would_send)

    def test_cant_or_timeout_produces_a_single_backup_decision(self):
        for name in ('Primary replies CANT', 'No reply before timeout', 'Late OK after fallback'):
            with self.subTest(name=name):
                self.assertTrue(simulate_fallback(name).backup_would_send)
                self.assertIn('WOULD TRY one request', simulate_fallback(name).text)

    def test_refuses_unknown_scenario(self):
        with self.assertRaises(ValueError):
            simulate_fallback('alert my family')

    def test_simulation_cannot_appear_as_real_acceptance(self):
        for case in SCENARIOS:
            report=simulate_fallback(case)
            self.assertNotIn('accepted by Home Assistant', report.text)
            self.assertNotIn('delivery confirmed', report.text)

    def test_report_is_deterministic(self):
        for case in SCENARIOS:
            self.assertEqual(simulate_fallback(case),simulate_fallback(case))

    def test_no_settings_or_external_data_required(self):
        with patch('librebeacon.settings.Settings.load',side_effect=AssertionError('Settings read!')):
            for case in SCENARIOS:
                self.assertIsNotNone(simulate_fallback(case).state)

if __name__ == '__main__': unittest.main()
