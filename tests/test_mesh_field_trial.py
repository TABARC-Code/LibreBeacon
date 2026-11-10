"""A field check must never become an unattended radio test."""
import unittest
from datetime import datetime, timezone
from librebeacon.contacts import ContactRoute
from librebeacon.mesh_field_trial import FIELD_CASES, MeshFieldTrial, send_confirmed_field_test


ROUTE = ContactRoute('Home receiver', 'notify.mesh_home_receiver', True, True, 0xAABB22)
OTHER = ContactRoute('Second receiver', 'notify.mesh_second_receiver', True, True, 0xAA0066)


class FakeClient:
    def __init__(self, gateway='Connected', node=0xAABB22):
        self.calls = []
        self.gateway = gateway
        self.node = node

    def states(self):
        self.calls.append('states')
        return [{'entity_id': 'meshtastic.gateway_local', 'state': self.gateway,
                 'attributes': {'device_class': 'gateway'}}]

    def state(self, entity):
        self.calls.append('state')
        return {'entity_id': entity, 'state': 'unknown',
                'attributes': {'node_id': self.node, 'user_id': f'!{self.node:08x}'}}

    def send_notification(self, target, message):
        self.calls.append(('notify', target, message))


class FieldTrialTests(unittest.TestCase):
    def ready(self, route=ROUTE):
        model = MeshFieldTrial()
        model.select(route)
        model.gateway_checked(['HA REPORTS CONNECTED'])
        model.recipient_checked_result(True)
        model.confirm_owner()
        return model

    def test_opens_with_no_preapproved_results(self):
        model = MeshFieldTrial()
        self.assertFalse(model.gateway_ready)
        self.assertIsNone(model.prepared)
        self.assertTrue(all(status == 'NOT RUN' for status in model.cases.values()))
        self.assertEqual(len(FIELD_CASES), 13)
        with self.assertRaises(ValueError):
            model.approve()
        with self.assertRaises(ValueError):
            model.consume_send()

    def test_does_not_select_an_unconsented_or_disabled_node(self):
        for route in [ContactRoute('A','notify.mesh_a',False,True,333),
                      ContactRoute('B','notify.mesh_b',True,False,334),
                      ContactRoute('C','notify.mesh_c',True,True,None),
                      ContactRoute('D','notify.mobile',True,True)]:
            with self.subTest(route=route.label), self.assertRaises(ValueError):
                MeshFieldTrial().select(route)

    def test_gateway_must_be_one_explicitly_connected_record(self):
        t = MeshFieldTrial(); t.select(ROUTE)
        for states in [[], ['UNVERIFIED'], ['DISCONNECTED'], ['HA REPORTS CONNECTED']*2,
                       ['HA REPORTS CONNECTED','DISCONNECTED']]:
            t.gateway_checked(states)
            self.assertFalse(t.gateway_ready)
            with self.assertRaises(ValueError): t.preview()
        t.gateway_checked(['HA REPORTS CONNECTED'])
        self.assertTrue(t.gateway_ready)
        with self.assertRaises(ValueError): t.preview()

    def test_owner_must_be_confirmed_before_preview(self):
        model = MeshFieldTrial()
        model.select(ROUTE)
        model.gateway_checked(['HA REPORTS CONNECTED'])
        model.recipient_checked_result(True)
        with self.assertRaises(ValueError):
            model.preview()
        model.confirm_owner()
        self.assertIn('TEST ONLY', model.preview().body)

    def test_revoked_contact_blocks_after_confirmation(self):
        model=self.ready()
        model.preview(); model.approve()
        client=FakeClient()
        with self.assertRaises(ValueError):
            send_confirmed_field_test(client,model,[])
        self.assertEqual(client.calls,[])

    def test_preview_never_sends(self):
        client = FakeClient()
        t = self.ready()
        preview = t.preview()
        self.assertIn('TEST ONLY', preview.body)
        self.assertNotIn('glucose', preview.body.casefold())
        with self.assertRaises(ValueError): send_confirmed_field_test(client, t, [ROUTE, OTHER])
        self.assertEqual(client.calls, [])

    def test_explicit_approval_sends_only_once(self):
        client = FakeClient()
        t = self.ready()
        t.preview()
        t.approve()
        ref = send_confirmed_field_test(client, t, [ROUTE, OTHER])
        self.assertTrue(ref.startswith('LB-'))
        self.assertEqual(len([x for x in client.calls if isinstance(x,tuple)]), 1)
        self.assertEqual(client.calls[-1][1], ROUTE.target)
        self.assertIn('TEST ONLY', client.calls[-1][2])
        with self.assertRaises(ValueError): send_confirmed_field_test(client, t, [ROUTE, OTHER])
        self.assertEqual(len([x for x in client.calls if isinstance(x,tuple)]), 1)
        t.sent(True)
        self.assertEqual(t.cases['03'], 'HA REQUEST ACCEPTED ONLY')
        self.assertEqual(t.cases['04'], 'NOT RUN')

    def test_gateway_loss_blocks_real_send_without_retry(self):
        client = FakeClient(gateway='Disconnected')
        t = self.ready()
        t.preview(); t.approve()
        with self.assertRaises(ValueError): send_confirmed_field_test(client, t, [ROUTE, OTHER])
        self.assertNotIn('notify', client.calls)
        t.sent(False)
        self.assertEqual(t.request_result, 'REQUEST FAILED')
        with self.assertRaises(ValueError): send_confirmed_field_test(client, t, [ROUTE, OTHER])

    def test_replaced_node_blocks_send(self):
        client = FakeClient(node=0xAABB23)
        t = self.ready()
        t.preview(); t.approve()
        with self.assertRaises(ValueError): send_confirmed_field_test(client, t, [ROUTE, OTHER])
        self.assertFalse(any(isinstance(x, tuple) for x in client.calls))
        t.sent(False)

    def test_new_recipient_or_gateway_resets_permission(self):
        t=self.ready(); t.preview(); t.approve()
        t.select(OTHER)
        self.assertIsNone(t.prepared)
        self.assertFalse(t.authorised)
        self.assertEqual(t.cases['02'], 'NOT RUN')
        t.gateway_checked(['HA REPORTS CONNECTED'])
        t.recipient_checked_result(True)
        t.confirm_owner()
        t.preview(); t.approve()
        t.gateway_checked([])
        self.assertFalse(t.authorised)
        self.assertFalse(t.recipient_checked)
        self.assertEqual(t.cases['02'], 'NOT RUN')

    def test_receipt_requires_accepted_request_and_is_only_reported(self):
        t=self.ready(); t.preview()
        with self.assertRaises(ValueError): t.record_receipt()
        t.approve(); t.consume_send(); t.sent(True); t.record_receipt()
        self.assertEqual(t.cases['04'], 'USER REPORTED RECEIPT')
        self.assertIn('NOT INDEPENDENTLY VERIFIED',t.receipt)

    def test_rechecking_gateway_clears_previous_request_and_receipt(self):
        t = self.ready(); t.preview(); t.approve(); t.consume_send(); t.sent(True)
        t.record_receipt()
        t.gateway_checked(['HA REPORTS CONNECTED'])
        self.assertEqual(t.request_result, 'NOT SENT')
        self.assertEqual(t.receipt, 'NOT CONFIRMED')
        self.assertEqual(t.cases['03'], 'NOT RUN')
        self.assertEqual(t.cases['04'], 'NOT RUN')
        with self.assertRaises(ValueError): t.record_receipt()

    def test_rechecking_recipient_clears_previous_request_and_receipt(self):
        t = self.ready(); t.preview(); t.approve(); t.consume_send(); t.sent(True)
        t.record_receipt()
        t.recipient_checked_result(False)
        self.assertEqual(t.request_result, 'NOT SENT')
        self.assertEqual(t.receipt, 'NOT CONFIRMED')
        self.assertEqual(t.cases['03'], 'NOT RUN')
        self.assertEqual(t.cases['04'], 'NOT RUN')
        with self.assertRaises(ValueError): t.preview()

    def test_report_is_private_and_not_a_success_claim(self):
        t=self.ready(); t.preview()
        text=t.report('4.11.0')
        for sensitive in [ROUTE.label, ROUTE.target, f'{ROUTE.mesh_node_id:08x}',
                          t.prepared.body, t.prepared.reference]:
            self.assertNotIn(sensitive,text)
        self.assertIn('NOT RUN',text)
        self.assertIn('Home Assistant',text)
        self.assertNotIn('TEST PASSED',text)

    def test_report_rejects_injected_version_line(self):
        with self.assertRaises(ValueError):
            MeshFieldTrial().report('4.11.0\nContact: abc')


if __name__ == '__main__':
    unittest.main()
