"""M3 radio messages and routing: mocked Home Assistant, never a real send."""
from dataclasses import replace
import re
import unittest
from librebeacon.mesh_messages import (
    MeshText, MESH_TEXT_MAX_BYTES, build_mesh_message, check_mesh_text, new_reference
)
from librebeacon.contacts import ContactRoute, dispatch_route, dispatch_emergency
from librebeacon.delivery import DeliveryTracker

NODE = 0xFAB012
ROUTE = ContactRoute('Carer', 'notify.mesh_carer', True, True, NODE)


def state(node=NODE, *, shared=False):
    if shared:
        return {'entity_id': ROUTE.target, 'state': 'unknown', 'attributes': {}}
    return {'entity_id': ROUTE.target, 'state': 'unknown',
            'attributes': {'node_id': node, 'user_id': f'!{node:08x}', 'friendly_name': 'Carer'}}


class FakeHA:
    def __init__(self, current=None, *, fail=False):
        self.current = state() if current is None else current
        self.fail = fail
        self.calls = []

    def state(self, target):
        return self.current

    def send_notification(self, target, message):
        if self.fail:
            raise RuntimeError('upstream failed')
        self.calls.append((target, message))

    def run_script(self, target, *, event, message):
        self.calls.append((target, message))


class MessageTests(unittest.TestCase):
    def test_random_reference_has_strict_format(self):
        refs = [new_reference() for _ in range(20)]
        self.assertEqual(len(set(refs)), len(refs))
        self.assertTrue(all(re.fullmatch(r'LB-[0-9A-F]{16}', value) for value in refs))

    def test_test_message_is_unmistakable_and_private(self):
        msg = build_mesh_message('test')
        self.assertIn('TEST ONLY', msg.body)
        self.assertIn('No emergency', msg.body)
        self.assertNotIn('glucose', msg.body.lower())
        self.assertLessEqual(len(msg.body.encode('utf8')), MESH_TEXT_MAX_BYTES)
        self.assertEqual(check_mesh_text(msg, 'test'), msg)

    def test_critical_low_default_omits_value(self):
        msg = build_mesh_message('critical_low', mmol=2.2)
        self.assertIn('ALERT', msg.body)
        self.assertNotIn('2.2', msg.body)
        self.assertNotIn('Glucose:', msg.body)
        self.assertLessEqual(len(msg.body.encode('utf8')), MESH_TEXT_MAX_BYTES)

    def test_critical_opt_in_includes_value(self):
        msg = build_mesh_message('critical_low', include_value=True, mmol=2.2)
        self.assertIn('2.2 mmol/L', msg.body)
        self.assertLessEqual(len(msg.body.encode('utf8')), MESH_TEXT_MAX_BYTES)

    def test_invalid_value_and_kind_rejected(self):
        for mmol in (None, float('nan'), float('inf'), 0, -1, 100, True, '2.4'):
            with self.subTest(mmol=mmol), self.assertRaises(ValueError):
                build_mesh_message('critical_low', include_value=True, mmol=mmol)
        with self.assertRaises(ValueError):
            build_mesh_message('test', include_value=True, mmol=2)
        with self.assertRaises(ValueError):
            build_mesh_message('test', mmol=2)
        with self.assertRaises(ValueError):
            build_mesh_message('other')

    def test_references_and_previews_cannot_be_forged(self):
        for bad in ('LB-123', 'LB-0123456789abcdef', 'BAD-0123456789ABCDEF', 'LB-'+'0'*16+'!'):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                build_mesh_message('test', reference=bad)
        original = build_mesh_message('test')
        with self.assertRaises(ValueError):
            check_mesh_text(replace(original, body=original.body+' extra'), 'test')
        with self.assertRaises(ValueError):
            check_mesh_text(replace(original, kind='critical_low'), 'test')

    def test_mesh_requires_explicit_event_type_and_consent(self):
        ha = FakeHA()
        with self.assertRaises(ValueError):
            dispatch_route(ha, ROUTE, 'generic arbitrary text')
        with self.assertRaises(ValueError):
            dispatch_route(ha, replace(ROUTE, consent=False), '', mesh_kind='test')
        self.assertEqual(ha.calls, [])

    def test_test_preview_is_exact_payload_sent(self):
        ha = FakeHA()
        prepared = build_mesh_message('test')
        reference = dispatch_route(ha, ROUTE, 'ignored', mesh_kind='test', mesh_text=prepared)
        self.assertEqual(reference, prepared.reference)
        self.assertEqual(ha.calls, [(ROUTE.target, prepared.body)])

    def test_renamed_shared_or_changed_node_never_sends(self):
        for record in (state(shared=True), state(0xACCC)):
            ha = FakeHA(record)
            with self.assertRaises(ValueError):
                dispatch_route(ha, ROUTE, 'ignored', mesh_kind='critical_low')
            self.assertEqual(ha.calls, [])

    def test_critical_prepared_payload_cannot_bypass_privacy(self):
        ha=FakeHA()
        with self.assertRaises(ValueError):
            dispatch_route(ha, ROUTE, 'ignored', mesh_kind='critical_low',
                           mesh_text=build_mesh_message('critical_low',include_value=True,mmol=2))
        self.assertEqual(ha.calls, [])

    def test_partial_failure_preserves_other_destination(self):
        bad = ContactRoute('Mesh', 'notify.mesh_carer', True, True, NODE)
        other = ContactRoute('Phone', 'notify.phone', True, True)
        ha = FakeHA(state(123))
        events=[]
        dispatch_emergency([bad,other],ha,'Long original phone message',lambda *x:events.append(x))
        self.assertEqual(len(events),2)
        self.assertEqual([event[1] for event in events],[False,True])
        self.assertEqual(ha.calls,[('notify.phone','Long original phone message')])

    def test_critical_mesh_and_phone_can_use_different_messages(self):
        ha=FakeHA()
        other=ContactRoute('Phone','notify.phone',True,True)
        events=[]
        dispatch_emergency([ROUTE,other],ha,'Long original phone message',lambda *x:events.append(x),
                           include_value=False,mmol=2.4)
        self.assertEqual(ha.calls[1][1],'Long original phone message')
        self.assertNotIn('2.4',ha.calls[0][1])
        self.assertLessEqual(len(ha.calls[0][1].encode('utf8')),MESH_TEXT_MAX_BYTES)
        self.assertTrue(re.fullmatch(r'LB-[0-9A-F]{16}',events[0][3]))
        self.assertEqual(events[1][3],'')

    def test_delivery_tracker_keeps_reference_only(self):
        tracker=DeliveryTracker()
        ref=build_mesh_message('test').reference
        tracker.record(ROUTE.target,accepted=True,kind='test',reference=ref)
        self.assertIn(ref,tracker.description(ROUTE.target))
        self.assertIn('unconfirmed',tracker.description(ROUTE.target))
        with self.assertRaises(ValueError):
            tracker.record(ROUTE.target,accepted=True,kind='test',reference='contact@example.org')


if __name__=='__main__':
    unittest.main()
