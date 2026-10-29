"""Gateway health checks use records only; test runs never contact a radio."""
import unittest
from datetime import datetime, timedelta, timezone
from librebeacon.mesh_health import discover_gateways, gateway_summary, node_last_heard

NOW = datetime(2026, 10, 29, 11, 20, tzinfo=timezone.utc)


def gateway(entity='meshtastic.gateway_lab', state='Connected', kind='gateway'):
    return {'entity_id': entity, 'state': state,
            'last_changed': (NOW - timedelta(days=200)).isoformat(),
            'attributes': {'device_class': kind, 'friendly_name': 'Garage gateway'}}


def last_heard(node, dt):
    return {'entity_id': f'sensor.meshtastic_gw_{node}_node_last_heard',
            'state': dt.isoformat() if isinstance(dt, datetime) else dt}


class GatewayTests(unittest.TestCase):
    def test_one_confirmed_gateway(self):
        result = discover_gateways([gateway()], now=NOW)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].status, 'HA REPORTS CONNECTED')
        self.assertTrue(result[0].verified_type)
        self.assertIn('not checked', result[0].detail)

    def test_old_ha_state_timestamp_is_not_a_heartbeat(self):
        result = discover_gateways([gateway()], now=NOW)
        self.assertEqual(result[0].status, 'HA REPORTS CONNECTED')
        self.assertNotIn('200', gateway_summary(result, now=NOW))

    def test_disconnected_and_unavailable(self):
        for state in ('Disconnected', 'unavailable'):
            with self.subTest(state=state):
                self.assertEqual(discover_gateways([gateway(state=state)], now=NOW)[0].status,
                                 'DISCONNECTED')

    def test_wrong_type_and_renamed_channel(self):
        states = [gateway('meshtastic.channel_family', 'Connected', 'channel'),
                  gateway('meshtastic.gateway_mum', 'Connected', 'channel')]
        result = discover_gateways(states, now=NOW)
        self.assertEqual([r.entity_id for r in result], ['meshtastic.gateway_mum'])
        self.assertEqual(result[0].status, 'UNVERIFIED')

    def test_unknown_state_not_green(self):
        self.assertEqual(discover_gateways([gateway(state='banana')], now=NOW)[0].status,
                         'UNKNOWN')

    def test_missing_entities_report_without_inventing_gateway(self):
        self.assertEqual(discover_gateways([None, {}, {'entity_id': 2}], now=NOW), [])
        self.assertIn('No Meshtastic gateway', gateway_summary([], now=NOW))

    def test_multiple_gateways_and_duplicate_ids(self):
        states = [gateway('meshtastic.gateway_a'), gateway('meshtastic.gateway_a'),
                  gateway('meshtastic.gateway_b', 'Disconnected')]
        report = discover_gateways(states, now=NOW)
        self.assertEqual(len(report), 2)
        self.assertEqual([r.status for r in report], ['HA REPORTS CONNECTED', 'DISCONNECTED'])

    def test_bad_inputs(self):
        with self.assertRaises(ValueError):
            discover_gateways({}, now=NOW)
        with self.assertRaises(ValueError):
            discover_gateways([], now=datetime(2026, 10, 29))


class LastHeardTests(unittest.TestCase):
    def test_recent_record_is_not_delivery_proof(self):
        result = node_last_heard([last_heard(42, NOW - timedelta(minutes=5))], 42, now=NOW)
        self.assertEqual(result.status, 'RECENT OBSERVATION')
        self.assertIn('not proof of reachability', result.detail)

    def test_old_data(self):
        result = node_last_heard([last_heard(42, NOW - timedelta(hours=2))], 42, now=NOW)
        self.assertEqual(result.status, 'OLD OBSERVATION')

    def test_invalid_and_future_data(self):
        for state in ('unavailable', 'oops', '2026-10-29T10:00:00'):
            self.assertEqual(node_last_heard([last_heard(42, state)], 42, now=NOW).status,
                             'NOT VERIFIED')
        self.assertEqual(node_last_heard([last_heard(42, NOW + timedelta(hours=2))], 42,
                                         now=NOW).status, 'CLOCK ERROR')

    def test_multiple_gateway_observations_do_not_get_cherry_picked(self):
        records = [last_heard(42, NOW - timedelta(minutes=1)),
                   {'entity_id':'sensor.meshtastic_other_42_node_last_heard',
                    'state': (NOW - timedelta(hours=10)).isoformat()}]
        self.assertEqual(node_last_heard(records, 42, now=NOW).status, 'NOT VERIFIED')

    def test_exact_node_id_required(self):
        self.assertEqual(node_last_heard([last_heard(421, NOW)], 42, now=NOW).status,
                         'NOT VERIFIED')
        with self.assertRaises(ValueError):
            node_last_heard([], True, now=NOW)

    def test_wrong_clock_does_not_prove_activity(self):
        with self.assertRaises(ValueError):
            node_last_heard([], 42, now=datetime(2026, 10, 29))


if __name__ == '__main__':
    unittest.main()
