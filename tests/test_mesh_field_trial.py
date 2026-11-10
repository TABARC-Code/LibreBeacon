"""A field check must never become an unattended radio test."""
import unittest
from datetime import datetime, timezone, timedelta
from dataclasses import replace
from librebeacon.contacts import ContactRoute
from librebeacon.mesh_field_trial import FIELD_CASES, MeshFieldTrial, send_confirmed_field_test
from librebeacon.mesh_health import GatewayStatus


ROUTE = ContactRoute('Home receiver', 'notify.mesh_home_receiver', True, True, 0xAABB22)
OTHER = ContactRoute('Second receiver', 'notify.mesh_second_receiver', True, True, 0xAA0066)
GATEWAY = GatewayStatus('meshtastic.gateway_local', 'Local gateway', 'HA REPORTS CONNECTED',
                        'Home Assistant observation', datetime.now(timezone.utc), True)


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
        model.gateway_checked([GATEWAY])
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
        for states in [[], ['UNVERIFIED'], ['DISCONNECTED'], [GATEWAY, GATEWAY],
                       [GATEWAY, 'DISCONNECTED'],
                       [GatewayStatus('meshtastic.gateway_local', 'Local', 'HA REPORTS CONNECTED',
                                      'No type', datetime.now(timezone.utc), False)]]:
            t.gateway_checked(states)
            self.assertFalse(t.gateway_ready)
            with self.assertRaises(ValueError): t.preview()
        t.gateway_checked([GATEWAY])
        self.assertTrue(t.gateway_ready)
        with self.assertRaises(ValueError): t.preview()

    def test_owner_must_be_confirmed_before_preview(self):
        model = MeshFieldTrial()
        model.select(ROUTE)
        model.gateway_checked([GATEWAY])
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
        self.assertEqual(t.request_result, 'REQUEST FAILED; DELIVERY UNKNOWN')
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
        t.gateway_checked([GATEWAY])
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
        t.gateway_checked([GATEWAY])
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

    def test_operator_can_record_only_manual_cases(self):
        from librebeacon.mesh_field_trial import MANUAL_FIELD_CASES
        t = MeshFieldTrial()
        self.assertEqual(len(MANUAL_FIELD_CASES), 10)
        for code in ('02', '03', '04', '00', '14'):
            with self.subTest(code=code), self.assertRaises(ValueError):
                t.record_observation(code, 'PASS')
        for outcome in ('pass', 'SUCCESS', '', 'PASS\nNode: A', None, True):
            with self.subTest(outcome=outcome), self.assertRaises(ValueError):
                t.record_observation('12', outcome)
        t.record_observation('12', 'FAIL')
        self.assertEqual(t.cases['12'], 'OPERATOR REPORTED FAIL')
        self.assertIn('12. Assistive technology and display: OPERATOR REPORTED FAIL', t.report('4.12.0'))
        t.record_observation('12', 'NOT RUN')
        self.assertEqual(t.cases['12'], 'NOT RUN')

    def test_new_test_does_not_reuse_old_radio_reply_claims(self):
        t = self.ready()
        t.record_observation('05', 'PASS')
        t.record_observation('06', 'FAIL')
        t.preview()
        self.assertEqual(t.cases['05'], 'NOT RUN')
        self.assertEqual(t.cases['06'], 'NOT RUN')
        t.record_observation('05', 'PASS')
        t.gateway_checked([GATEWAY])
        self.assertEqual(t.cases['05'], 'NOT RUN')
        t.recipient_checked_result(True)
        t.confirm_owner()
        t.record_observation('05', 'FAIL')
        t.select(OTHER)
        self.assertEqual(t.cases['05'], 'NOT RUN')

    def test_report_never_includes_custom_field_notes(self):
        t = self.ready()
        t.record_observation('07', 'PASS')
        report = t.report('4.12.0')
        self.assertIn('OPERATOR REPORTED PASS', report)
        self.assertIn('not independent validation', report)
        self.assertNotIn(ROUTE.label, report)
        self.assertNotIn(ROUTE.target, report)

    def test_gateway_identity_is_pinned_before_sending(self):
        t = self.ready()
        self.assertEqual(t.gateway_entity_id, GATEWAY.entity_id)
        t.preview(); t.approve()
        class SwitchedGateway(FakeClient):
            def states(self):
                records = super().states()
                records[0]['entity_id'] = 'meshtastic.gateway_other'
                return records
        client = SwitchedGateway()
        with self.assertRaisesRegex(ValueError, 'gateway changed'):
            send_confirmed_field_test(client, t, [ROUTE])
        self.assertFalse(any(isinstance(c, tuple) for c in client.calls))
        t.failed_send()
        self.assertEqual(t.request_result, 'REQUEST FAILED; DELIVERY UNKNOWN')

    def test_untyped_or_ambiguous_gateway_cannot_enable_send(self):
        t = MeshFieldTrial()
        t.select(ROUTE)
        t.gateway_checked(['HA REPORTS CONNECTED'])
        self.assertFalse(t.gateway_ready)
        self.assertIsNone(t.gateway_entity_id)
        t.gateway_checked([GATEWAY, GATEWAY])
        self.assertFalse(t.gateway_ready)
        t.gateway_checked([GatewayStatus('meshtastic.gateway_local', 'Local', 'HA REPORTS CONNECTED',
                                         'No type', datetime.now(timezone.utc), False)])
        self.assertFalse(t.gateway_ready)

    def test_failure_before_permission_consumed_clears_approval(self):
        t = self.ready(); t.preview(); t.approve()
        t.failed_send()
        self.assertFalse(t.authorised)
        self.assertIsNone(t.prepared)
        self.assertEqual(t.request_result, 'BLOCKED BEFORE SEND')
        self.assertEqual(t.cases['03'], 'BLOCKED BEFORE SEND')
        with self.assertRaises(ValueError): t.consume_send()
        with self.assertRaises(ValueError): t.failed_send()

    def test_rechecking_gateway_clears_its_pinned_identity(self):
        t = self.ready()
        t.preview(); t.approve()
        t.gateway_checked([])
        self.assertIsNone(t.gateway_entity_id)
        self.assertFalse(t.authorised)
        self.assertIsNone(t.prepared)

    def test_live_gateway_still_sends_to_the_pinned_receiver(self):
        t = self.ready()
        t.preview(); t.approve()
        c = FakeClient()
        ref = send_confirmed_field_test(c, t, [ROUTE])
        self.assertTrue(ref.startswith('LB-'))
        self.assertEqual(len([call for call in c.calls if isinstance(call, tuple)]), 1)

    def test_ui_callback_handles_failure_before_consuming_send(self):
        from types import SimpleNamespace
        from librebeacon.mesh_field_ui import MeshFieldWizard

        t = self.ready(); t.preview(); t.approve()
        output = []
        stub = SimpleNamespace(
            model=t, busy=True, session_key='one',
            root=SimpleNamespace(winfo_exists=lambda: True),
            status=SimpleNamespace(set=output.append),
            refresh=lambda: None,
        )
        MeshFieldWizard.on_result(stub, ('one', 'send', False, 'ValueError'))
        self.assertFalse(stub.busy)
        self.assertEqual(t.request_result, 'BLOCKED BEFORE SEND')
        self.assertFalse(t.authorised)
        self.assertTrue(output)

    def test_old_gateway_check_cannot_be_previewed(self):
        t = self.ready()
        t.gateway_checked_at = replace(t.gateway_checked_at,
                                       wall=t.gateway_checked_at.wall - timedelta(minutes=6))
        with self.assertRaisesRegex(ValueError, 'expired'):
            t.preview()
        self.assertIsNone(t.prepared)

    def test_old_recipient_check_cannot_be_previewed(self):
        t = self.ready()
        t.recipient_checked_at = replace(t.recipient_checked_at,
                                         wall=t.recipient_checked_at.wall - timedelta(minutes=6))
        with self.assertRaisesRegex(ValueError, 'expired'):
            t.preview()

    def test_sleep_simulation_expires_preview_before_approval(self):
        t = self.ready(); t.preview()
        t.previewed_at = replace(t.previewed_at,
                                 wall=t.previewed_at.wall - timedelta(minutes=6))
        with self.assertRaisesRegex(ValueError, 'expired'):
            t.approve()
        self.assertFalse(t.authorised)
        self.assertIsNone(t.prepared)

    def test_late_gateway_check_blocks_radio_transmission(self):
        t = self.ready(); t.preview(); t.approve()
        t.gateway_checked_at = replace(t.gateway_checked_at,
                                       wall=t.gateway_checked_at.wall - timedelta(minutes=6))
        c = FakeClient()
        with self.assertRaisesRegex(ValueError, 'expired'):
            send_confirmed_field_test(c, t, [ROUTE])
        self.assertEqual(c.calls, [])
        self.assertFalse(t.authorised)

    def test_monotonic_timing_expiry_also_blocks_test(self):
        t = self.ready(); t.preview(); t.approve()
        t.previewed_at = replace(t.previewed_at, tick=t.previewed_at.tick - 500)
        c = FakeClient()
        with self.assertRaisesRegex(ValueError, 'expired'):
            send_confirmed_field_test(c, t, [ROUTE])
        self.assertEqual(c.calls, [])

    def test_clock_moved_backward_blocks_old_approval(self):
        t = self.ready(); t.preview()
        t.previewed_at = replace(t.previewed_at,
                                 wall=t.previewed_at.wall + timedelta(minutes=3))
        with self.assertRaisesRegex(ValueError, 'expired'):
            t.approve()
        self.assertFalse(t.authorised)

    def test_aging_during_gateway_query_stops_send(self):
        t = self.ready(); t.preview(); t.approve()
        class SlowState(FakeClient):
            def states(self):
                t.previewed_at = replace(t.previewed_at,
                                         wall=t.previewed_at.wall - timedelta(minutes=6))
                return super().states()
        c = SlowState()
        with self.assertRaisesRegex(ValueError, 'expired'):
            send_confirmed_field_test(c, t, [ROUTE])
        self.assertFalse(any(isinstance(call, tuple) for call in c.calls))


    def test_cancelled_wizard_cannot_send(self):
        t = self.ready(); t.preview(); t.approve(); t.cancel()
        c = FakeClient()
        with self.assertRaisesRegex(ValueError, 'cancelled'):
            send_confirmed_field_test(c, t, [ROUTE])
        self.assertFalse(t.authorised)
        self.assertIsNone(t.prepared)
        self.assertEqual(c.calls, [])

    def test_cancel_during_gateway_lookup_stops_before_notification(self):
        t = self.ready(); t.preview(); t.approve()
        class ClosingGateway(FakeClient):
            def states(self):
                states = super().states()
                t.cancel()
                return states
        c = ClosingGateway()
        with self.assertRaisesRegex(ValueError, 'cancelled'):
            send_confirmed_field_test(c, t, [ROUTE])
        self.assertFalse(any(isinstance(x, tuple) for x in c.calls))

    def test_cancel_during_node_lookup_stops_before_send(self):
        t = self.ready(); t.preview(); t.approve()
        class ClosingNode(FakeClient):
            def state(self, entity):
                result = super().state(entity)
                t.cancel()
                return result
        c = ClosingNode()
        with self.assertRaisesRegex(ValueError, 'cancelled'):
            send_confirmed_field_test(c, t, [ROUTE])
        self.assertFalse(any(isinstance(x, tuple) for x in c.calls))

    def test_cancelled_test_cannot_start_a_fresh_preview(self):
        t = self.ready(); t.cancel()
        with self.assertRaises(ValueError): t.preview()
        with self.assertRaises(ValueError): t.approve()

    def test_close_cancels_field_model(self):
        from types import SimpleNamespace
        from librebeacon.mesh_field_ui import MeshFieldWizard
        t = self.ready(); t.preview()
        closed = []
        stub = SimpleNamespace(model=t, session_key='live',
                               root=SimpleNamespace(destroy=lambda: closed.append(True)))
        MeshFieldWizard.close(stub)
        self.assertTrue(t.cancelled)
        self.assertEqual(stub.session_key, '')
        self.assertEqual(closed, [True])

if __name__ == '__main__':
    unittest.main()
