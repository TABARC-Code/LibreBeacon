"""Node-pinning tests. Mocked HA, and no live radio messages sent."""
import unittest
from librebeacon.meshtastic import discover_mesh_choices, require_mesh_choice
from librebeacon.contacts import ContactRoute, read_routes, dispatch_route, dispatch_emergency


def node(entity='notify.mesh_friend', number=0x1234, *, name='My friend', state='unknown'):
    return {'entity_id': entity, 'state': state,
            'attributes': {'friendly_name': name, 'node_id': number, 'user_id': f'!{number:08x}'}}


class FakeHA:
    def __init__(self, state):
        self.record = state
        self.sent = []

    def state(self, entity_id):
        return self.record

    def send_notification(self, entity_id, text):
        self.sent.append((entity_id, text))

    def run_script(self, entity_id, *, event, message):
        self.sent.append((entity_id, message))


class MeshIdentityTests(unittest.TestCase):
    def test_numeric_identity_and_user_id_from_integration(self):
        choice = discover_mesh_choices([node()])[0]
        self.assertTrue(choice.selectable)
        self.assertEqual(choice.node_id, 0x1234)

    def test_renamed_channel_cannot_be_a_person(self):
        fake_channel = {'entity_id': 'notify.mesh_friend', 'state': 'unknown',
                        'attributes': {'friendly_name': 'Alice'}}
        self.assertFalse(discover_mesh_choices([fake_channel])[0].selectable)
        self.assertFalse(discover_mesh_choices([node(name='My channel')])[0].selectable)

    def test_inconsistent_user_id_or_bool_is_rejected(self):
        for bad in ({'node_id': 9, 'user_id': '!0000000a'},
                    {'node_id': True, 'user_id': '!00000001'},
                    {'node_id': -1, 'user_id': '!-0000001'},
                    {'node_id': 2**32, 'user_id': '!100000000'},
                    {'node_id': '9', 'user_id': '!00000009'}):
            entry = node()
            entry['attributes'].update(bad)
            with self.subTest(bad=bad):
                self.assertFalse(discover_mesh_choices([entry])[0].selectable)

    def test_pin_mismatch_or_missing_blocks_before_send(self):
        route = ContactRoute('Neighbour', 'notify.mesh_friend', True, True, 0x1234)
        for current in (node(number=0x5678), {'entity_id': 'notify.mesh_friend', 'attributes': {}},
                        node(state='unavailable'), node(name='Public channel')):
            client = FakeHA(current)
            with self.subTest(current=current), self.assertRaises(ValueError):
                dispatch_route(client, route, 'TEST ONLY', mesh_kind='test')
            self.assertEqual(client.sent, [])

    def test_valid_pinned_route_sends_to_one_target(self):
        route = ContactRoute('Neighbour', 'notify.mesh_friend', True, True, 0x1234)
        client = FakeHA(node())
        dispatch_route(client, route, 'TEST ONLY', mesh_kind='test')
        self.assertEqual(len(client.sent), 1)
        self.assertEqual(client.sent[0][0], 'notify.mesh_friend')
        self.assertIn('TEST ONLY', client.sent[0][1])
        self.assertIn('LB-', client.sent[0][1])

    def test_old_enabled_mesh_route_migrates_to_disabled(self):
        saved = [{'label': 'Neighbour', 'target': 'notify.mesh_friend',
                  'consent': True, 'enabled': True}]
        migrated = read_routes(saved)
        self.assertEqual(len(migrated), 1)
        self.assertFalse(migrated[0].enabled)
        self.assertIsNone(migrated[0].mesh_node_id)
        self.assertFalse(migrated[0].as_dict()['enabled'])

    def test_pinned_record_round_trip(self):
        route = ContactRoute('Neighbour', 'notify.mesh_friend', True, True, 0x1234)
        self.assertEqual(read_routes([route.as_dict()]), [route])

    def test_non_mesh_unaffected_by_migration(self):
        route = ContactRoute('Email', 'notify.mail', True, True)
        self.assertEqual(read_routes([route.as_dict()]), [route])

    def test_bad_mesh_node_id_never_enables(self):
        for value in (True, '123', 0, -1, 2**33):
            with self.subTest(value=value), self.assertRaises(ValueError):
                ContactRoute('Neighbour', 'notify.mesh_friend', True, True, value).validate()

    def test_bad_mesh_contact_does_not_block_other_contact(self):
        mesh = ContactRoute('Mesh', 'notify.mesh_friend', True, True, 0x1234)
        email = ContactRoute('Email', 'notify.mail', True, True)
        client = FakeHA(node(number=0x5678))
        outcomes = []
        dispatch_emergency([mesh, email], client, 'TEST ONLY', lambda *a: outcomes.append(a))
        self.assertEqual(len(outcomes), 2)
        self.assertEqual([row[1] for row in outcomes], [False, True])
        self.assertEqual(client.sent, [('notify.mail', 'TEST ONLY')])


if __name__ == '__main__':
    unittest.main()
