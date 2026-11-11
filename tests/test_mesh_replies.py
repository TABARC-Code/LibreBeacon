"""Simulated radio and Home Assistant replies. No real device gets a message."""
from datetime import datetime, timedelta, timezone
from threading import Event
from unittest.mock import patch
import json
import unittest

from librebeacon.mesh_replies import MeshReplyTracker, node_number, MAX_TRACKED_INCIDENTS, RETAIN_AFTER_EXPIRY
from librebeacon.mesh_stream import websocket_url, listen_for_replies

NOW = datetime(2026, 11, 1, 12, tzinfo=timezone.utc)
NODE = 0x3213ABCD
GATEWAY = 0x12345678
REF = 'LB-0123456789ABCDEF'


def reply(*, text=None, node=NODE, gateway=GATEWAY, dest=GATEWAY, channel=None,
          sender=None, fired=None, packet_id=101):
    return {
        'event_type':'meshtastic_api_text_message',
        'time_fired':(fired or (NOW + timedelta(seconds=15))).isoformat(),
        'data':{
            'node': node, 'message_id':packet_id, 'config_entry_id':'meshtastic-entry',
            'data':{'from': node if sender is None else sender,
                    'to':{'node':dest,'channel':channel},
                    'gateway':gateway,'message': text if text is not None else REF+' OK'}
        }
    }


class MeshtasticReplies(unittest.TestCase):
    def setUp(self):
        self.tracker = MeshReplyTracker()
        self.item = self.tracker.register(REF,'notify.mesh_carer',NODE,GATEWAY,'critical_low',now=NOW)

    def test_identity_number_formats(self):
        self.assertEqual(node_number('!3213abcd'),NODE)
        self.assertEqual(node_number(str(NODE)),NODE)
        for invalid in (None, True, 0, -1, 0x100000000, '0x123', '!123', '12xyz'):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                node_number(invalid)

    def test_approved_direct_reply_observed_but_not_attendance(self):
        out=self.tracker.receive(reply(),now=NOW+timedelta(minutes=1))
        self.assertIs(out,self.item)
        self.assertIn('attendance not confirmed',self.tracker.status(REF))
        self.assertEqual(out.response,'OK')
        self.assertIsNone(self.tracker.receive(reply(),now=NOW+timedelta(minutes=2)))

    def test_cant_reply_is_distinct(self):
        res=self.tracker.receive(reply(text=REF+' CANT'),now=NOW+timedelta(minutes=1))
        self.assertEqual(res.response,'CANT')
        self.assertIn('cannot attend',self.tracker.status(REF))

    def test_wrong_nodes_channels_and_gateways_are_rejected(self):
        variants=(reply(node=12),reply(sender=12),reply(gateway=33),
                  reply(dest=23),reply(channel=0),reply(dest=None,channel=0),
                  reply(text='wrong '+REF+' OK'),reply(text=REF+' ok'),
                  reply(text='LB-FFFFFFFFFFFFFFFF OK'),reply(packet_id=-1))
        for event in variants:
            with self.subTest(event=event):
                self.assertIsNone(self.tracker.receive(event,now=NOW+timedelta(minutes=1)))
        self.assertEqual(self.item.response,'')

    def test_expired_or_early_or_old_event_cannot_acknowledge(self):
        for event,received in (
            (reply(), NOW+timedelta(minutes=30)),
            (reply(fired=NOW-timedelta(seconds=1)), NOW+timedelta(minutes=1)),
            (reply(fired=NOW+timedelta(minutes=31)), NOW+timedelta(minutes=1)),
            (reply(fired=NOW+timedelta(minutes=1)), NOW+timedelta(seconds=1)),
        ):
            self.assertIsNone(self.tracker.receive(event,now=received))
        self.assertIn('expired',self.tracker.status(REF,now=NOW+timedelta(minutes=31)))

    def test_malformed_and_wrong_event_types_cannot_acknowledge(self):
        for event in (None,{},'hello',{'event_type':'state_changed'},reply(text='x'*1024)):
            self.assertIsNone(self.tracker.receive(event,now=NOW+timedelta(minutes=1)))
        event=reply();event.pop('time_fired')
        self.assertIsNone(self.tracker.receive(event,now=NOW+timedelta(minutes=1)))
        self.assertEqual(self.item.response,'')

    def test_duplicate_refs_rejected_and_test_incidents_allowed(self):
        with self.assertRaises(ValueError):
            self.tracker.register(REF,'notify.mesh_other',123,GATEWAY,'test',now=NOW)
        self.assertEqual(self.tracker.register('LB-FFFFFFFFFFFFFFFF','notify.mesh_carer',NODE,GATEWAY,'test',now=NOW).kind,'test')


    def test_old_ha_event_is_not_treated_as_a_new_reply(self):
        old = reply(fired=NOW + timedelta(seconds=15))
        self.assertIsNone(self.tracker.receive(old,now=NOW+timedelta(minutes=5)))
        self.assertEqual(self.item.response,'')
        fresh = reply(fired=NOW + timedelta(minutes=4,seconds=45))
        self.assertIs(self.tracker.receive(fresh,now=NOW+timedelta(minutes=5)),self.item)

    def test_packet_numbers_can_repeat_between_different_incidents(self):
        second = 'LB-FFFFFFFFFFFFFFFF'
        self.tracker.register(second,'notify.mesh_carer',NODE,GATEWAY,'test',now=NOW)
        self.assertIsNotNone(self.tracker.receive(reply(packet_id=101),now=NOW+timedelta(minutes=1)))
        next_event = reply(text=second+' OK', packet_id=101)
        self.assertEqual(self.tracker.receive(next_event,now=NOW+timedelta(minutes=1)).reference,second)
        self.assertEqual(len(self.tracker.seen_packets),2)

    def test_prune_releases_incidents_and_packet_ids_together(self):
        self.assertIsNotNone(self.tracker.receive(reply(),now=NOW+timedelta(minutes=1)))
        at = NOW + timedelta(minutes=31) + RETAIN_AFTER_EXPIRY
        self.assertEqual(self.tracker.prune(now=at),1)
        self.assertEqual(self.tracker.incidents,{})
        self.assertEqual(self.tracker.seen_packets,set())
        self.assertEqual(self.tracker.prune(now=at),0)

    def test_register_cleans_old_history_before_checking_capacity(self):
        later = NOW + timedelta(hours=2)
        result = self.tracker.register('LB-EEEEEEEEEEEEEEEE','notify.mesh_carer',
                                      NODE,GATEWAY,'test',now=later)
        self.assertEqual(result.reference,'LB-EEEEEEEEEEEEEEEE')
        self.assertNotIn(REF,self.tracker.incidents)

    def test_tracker_capacity_rejects_a_new_record_without_eviction(self):
        for n in range(1,MAX_TRACKED_INCIDENTS):
            self.tracker.register('LB-'+f'{n:016X}','notify.mesh_carer',
                                  NODE,GATEWAY,'test',now=NOW)
        self.assertEqual(len(self.tracker.incidents),MAX_TRACKED_INCIDENTS)
        with self.assertRaisesRegex(ValueError,'tracker full'):
            self.tracker.register('LB-FFFFFFFFFFFFFFFF','notify.mesh_carer',
                                  NODE,GATEWAY,'test',now=NOW)
        self.assertEqual(len(self.tracker.incidents),MAX_TRACKED_INCIDENTS)

    def test_bad_reference_and_naive_prune_clock_rejected(self):
        for bad in (None,True,42,[],{},'bogus'):
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                self.tracker.register(bad,'notify.mesh_carer',NODE,GATEWAY,'test',now=NOW)
        with self.assertRaises(ValueError):
            self.tracker.prune(now=datetime(2026,11,1,12))


    def test_unpaired_unicode_in_event_text_does_not_crash_tracker(self):
        # JSON can legally decode this escape to an invalid Unicode scalar.
        raw = json.dumps(chr(0xD800))
        event = reply(text=json.loads(raw))
        self.assertEqual(event['data']['data']['message'], chr(0xD800))
        self.assertIsNone(self.tracker.receive(event,now=NOW+timedelta(minutes=1)))
        self.assertEqual(self.item.response,'')

    def test_oversized_or_non_text_message_is_ignored(self):
        for value in ('x'*10000, b'opaque', None, {'message': REF+' OK'}, REF+' OK '+chr(0xDC00)):
            with self.subTest(kind=type(value).__name__):
                event=reply()
                event['data']['data']['message']=value
                self.assertIsNone(self.tracker.receive(event,now=NOW+timedelta(minutes=1)))
        self.assertEqual(self.item.response,'')

    def test_extreme_timestamp_offset_is_not_an_exception(self):
        event=reply()
        event['time_fired']='0001-01-01T00:00:00+14:00'
        self.assertIsNone(self.tracker.receive(event,now=NOW+timedelta(minutes=1)))
        self.assertEqual(self.item.response,'')

    def test_upstream_text_event_shape_with_metadata(self):
        # Matches the integration's _on_text_message event payload fields.
        event=reply(packet_id=529)
        event['data']['data'].update({
            'from_id': f'!{NODE:08x}', 'hops_away': 1, 'hop_start': 3,
            'hop_limit': 2, 'rx_snr': 6.5, 'rx_rssi': -85,
            'via_mqtt': False, 'xeddsa_signed': False,
            'reply_id': None, 'is_reaction': False,
        })
        found=self.tracker.receive(event,now=NOW+timedelta(minutes=1))
        self.assertIs(found,self.item)
        self.assertEqual(found.response,'OK')

    def test_stream_url_uses_same_host_and_tls(self):
        self.assertEqual(websocket_url('https://ha.example.org:8123'), 'wss://ha.example.org:8123/api/websocket')
        self.assertEqual(websocket_url('http://ha.local:8123'), 'ws://ha.local:8123/api/websocket')
        for invalid in ('ftp://something','http://bad@evil','http://x/path'):
            with self.assertRaises(Exception): websocket_url(invalid)


class FakeSocket:
    def __init__(self, messages, stop):
        self.messages=list(messages)
        self.sent=[]
        self.stop=stop
        self.closed=False
    def settimeout(self, value): self.timeout=value
    def send(self, data): self.sent.append(json.loads(data))
    def recv(self):
        if self.messages:
            msg=self.messages.pop(0)
            if msg.get('type')=='event':self.stop.set()
            return json.dumps(msg)
        self.stop.set()
        return json.dumps({'type':'noop'})
    def close(self):self.closed=True


class StreamTests(unittest.TestCase):
    def test_authenticate_subscribe_then_pass_only_subscribed_event(self):
        stop=Event()
        event=reply()
        socket=FakeSocket([
            {'type':'auth_required'}, {'type':'auth_ok'},
            {'type':'result','id':1,'success':True},
            {'type':'event','id':1,'event':event},
        ],stop)
        items=[]; statuses=[]
        import websocket
        with patch.object(websocket,'create_connection',return_value=socket) as connect:
            listen_for_replies('https://ha.example.org','secret',stop,items.append,statuses.append)
        self.assertEqual(items,[event])
        self.assertEqual(socket.sent[0],{'type':'auth','access_token':'secret'})
        self.assertEqual(socket.sent[1],{'id':1,'type':'subscribe_events','event_type':'meshtastic_api_text_message'})
        self.assertTrue(socket.closed)
        self.assertNotIn('secret',' '.join(statuses))
        self.assertIn('wss://ha.example.org/api/websocket',connect.call_args.args)

    def test_refuse_auth_fail_and_do_not_forward(self):
        stop=Event(); socket=FakeSocket([{'type':'auth_required'},{'type':'auth_invalid'}],stop)
        statuses=[]; messages=[]
        import websocket
        with patch.object(websocket,'create_connection',return_value=socket):
            listen_for_replies('http://ha.local','secret',stop,messages.append,statuses.append)
        self.assertEqual(messages,[])
        self.assertTrue(socket.closed)
        self.assertIn('disconnected',statuses[-1])

if __name__ == '__main__': unittest.main()
