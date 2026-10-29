"""Every send is mocked: not a single radio gets an unsolicited test."""
import unittest
from librebeacon.meshtastic import discover_mesh_choices, appears_shared, is_mesh_entity, require_mesh_choice
from librebeacon.contacts import ContactRoute


class MeshDestinationTests(unittest.TestCase):
    def test_direct_and_shared_entities(self):
        states = [
            {'entity_id': 'notify.mesh_alice', 'state': 'unknown', 'attributes': {'friendly_name': 'Alice radio', 'node_id': 17, 'user_id': '!00000011'}},
            {'entity_id': 'notify.mesh_channel_0', 'state': 'unknown', 'attributes': {}},
            {'entity_id': 'notify.mesh_friends', 'state': 'unavailable', 'attributes': {}},
            {'entity_id': 'notify.mesh_misc', 'state': 'unknown', 'attributes': {'friendly_name': 'Public alerts'}},
            {'entity_id': 'notify.phone', 'state': 'unknown', 'attributes': {}},
        ]
        result = discover_mesh_choices(states)
        self.assertEqual([x.entity_id for x in result if x.selectable], ['notify.mesh_alice'])
        self.assertEqual(len(result), 4)

    def test_no_accidental_substring_rejection(self):
        self.assertFalse(appears_shared('notify.mesh_allison', 'Allison'))
        self.assertTrue(appears_shared('notify.mesh_all', ''))
        self.assertTrue(appears_shared('notify.mesh_mother', 'Family Group'))

    def test_route_rejects_known_shared_destinations(self):
        for target in ('notify.mesh_public', 'notify.mesh_channel_private',
                       'notify.mesh_everyone', 'notify.mesh_group_family', 'notify.mesh_all'):
            with self.subTest(target=target), self.assertRaises(ValueError):
                ContactRoute('Family', target, True, True).validate()

    def test_current_state_must_still_be_an_individual_destination(self):
        with self.assertRaises(ValueError):
            require_mesh_choice('notify.mesh_contact', [
                {'entity_id': 'notify.mesh_contact', 'state': 'unknown',
                 'attributes': {'friendly_name': 'Household channel'}}])
        with self.assertRaises(ValueError):
            require_mesh_choice('notify.mesh_contact', [])
        self.assertEqual(require_mesh_choice('notify.mesh_contact', [
            {'entity_id': 'notify.mesh_contact', 'state': 'unknown',
             'attributes': {'friendly_name': 'Receiver', 'node_id': 32, 'user_id': '!00000020'} }]).entity_id, 'notify.mesh_contact')

    def test_reject_changed_target_before_dispatch(self):
        from librebeacon.contacts import dispatch_route
        class Renamed:
            def state(self, name):
                return {'entity_id': name, 'state': 'unknown',
                        'attributes': {'friendly_name': 'Public channel'}}
            def send_notification(self, *args):
                raise AssertionError('Should not attempt a send')
        with self.assertRaises(ValueError):
            dispatch_route(Renamed(), ContactRoute('Partner', 'notify.mesh_partner', True, True), 'TEST ONLY')

    def test_bad_discovery_records_do_not_crash(self):
        self.assertEqual(discover_mesh_choices([None, {}, {'entity_id': 1}]), [])
        self.assertFalse(is_mesh_entity(None))


if __name__ == '__main__':
    unittest.main()
