"""The radio listener's previous worker must not govern the current session."""
from queue import Queue
from threading import Event
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch
import time

from librebeacon.app import LibreBeaconApp


class ListenerSessionTests(TestCase):
    def app(self):
        queue = Queue()
        stop = Event()
        fallback = SimpleNamespace(cancel=Mock(), reply=Mock())
        tracker = SimpleNamespace(receive=Mock(return_value=SimpleNamespace(
            reference='LB-0123456789ABCDEF', destination='notify.mesh_one', response='CANT')))
        statuses = []
        app = SimpleNamespace(
            queue=queue, mesh_listener_stop=stop, mesh_listener_active=True,
            mesh_listener_ready=True, mesh_replies=tracker, mesh_fallback=fallback,
            mesh_reply_state=SimpleNamespace(set=statuses.append),
            root=SimpleNamespace(after=lambda *args: None),
            refresh_routes=Mock(), status=SimpleNamespace(set=lambda text: None),
            busy_poll=False,
        )
        return app, statuses

    def flush(self, app):
        LibreBeaconApp.process_queue(app)

    def test_old_events_and_old_shutdown_do_not_affect_new_session(self):
        app, statuses = self.app()
        old = Event()
        app.queue.put(('mesh_reply_event', True, (old, {'event_type': 'meshtastic_api_text_message'})))
        app.queue.put(('mesh_reply_status', True, (old, 'Reply listener disconnected')))
        app.queue.put(('mesh_reply_stopped', True, (old, None)))
        self.flush(app)
        self.assertTrue(app.mesh_listener_ready)
        self.assertTrue(app.mesh_listener_active)
        self.assertEqual(statuses, [])
        app.mesh_replies.receive.assert_not_called()
        app.mesh_fallback.reply.assert_not_called()
        app.mesh_fallback.cancel.assert_not_called()

    def test_current_reply_updates_the_matching_fallback_only(self):
        app, statuses = self.app()
        app.queue.put(('mesh_reply_event', True, (app.mesh_listener_stop, {'event_type': 'meshtastic_api_text_message'})))
        self.flush(app)
        app.mesh_replies.receive.assert_called_once()
        app.mesh_fallback.reply.assert_called_once_with(
            'LB-0123456789ABCDEF', 'notify.mesh_one', 'CANT')
        self.assertTrue(any('Matching radio reply' in value for value in statuses))

    def test_stopping_session_discards_queued_reply_and_listening_status(self):
        app, statuses = self.app()
        current = app.mesh_listener_stop
        current.set()
        app.queue.put(('mesh_reply_event', True, (current, {'event_type': 'meshtastic_api_text_message'})))
        app.queue.put(('mesh_reply_status', True, (current, 'Listening for Meshtastic replies; Windows must remain awake')))
        app.queue.put(('mesh_reply_stopped', True, (current, None)))
        self.flush(app)
        app.mesh_replies.receive.assert_not_called()
        app.mesh_fallback.reply.assert_not_called()
        self.assertFalse(app.mesh_listener_active)
        self.assertFalse(app.mesh_listener_ready)
        app.mesh_fallback.cancel.assert_called_once()
        self.assertEqual(statuses[-1], 'Reply listener OFF. Restart to listen again.')

    def test_event_before_listener_ready_is_discarded(self):
        app, _ = self.app()
        app.mesh_listener_ready = False
        app.queue.put(('mesh_reply_event', True, (app.mesh_listener_stop, {})))
        self.flush(app)
        app.mesh_replies.receive.assert_not_called()

    def test_worker_captures_the_original_stop_event(self):
        app, _ = self.app()
        app.mesh_listener_active = False
        app.gateway_node_text = SimpleNamespace(get=lambda: '305419896')
        app.settings = SimpleNamespace(mesh_gateway_node_id='305419896')
        app.client = lambda: SimpleNamespace(base_url='http://ha.local', token='fake')
        with patch('librebeacon.app.Thread') as thread, patch(
                'librebeacon.app.listen_for_replies') as listen:
            LibreBeaconApp.start_mesh_reply_listener(app)
            first = app.mesh_listener_stop
            worker = thread.call_args.kwargs['target']
            # The next connection must not donate its stop event to the old worker.
            app.mesh_listener_stop = Event()
            worker()
        self.assertIs(listen.call_args.args[2], first)
        self.assertTrue(first.is_set())
        item = app.queue.get_nowait()
        self.assertEqual(item[:2], ('mesh_reply_stopped', True))
        self.assertIs(item[2][0], first)

    def test_queued_backup_stops_if_socket_closed_before_ui_catches_up(self):
        app, _ = self.app()
        app.mesh_listener_stop.set()
        app.last_fallback_tick = time.monotonic()
        app.mesh_fallback.pending = object()
        app.mesh_fallback.due = Mock(return_value=None)
        app.mesh_fallback.describe = lambda: 'backup cancelled'
        LibreBeaconApp.check_mesh_fallback(app)
        self.assertFalse(app.mesh_fallback.due.call_args.kwargs['listener_ready'])

    def test_listener_ready_status_from_current_session(self):
        app, statuses = self.app()
        app.mesh_listener_ready = False
        app.queue.put(('mesh_reply_status', True, (
            app.mesh_listener_stop, 'Listening for Meshtastic replies; Windows must remain awake')))
        self.flush(app)
        self.assertTrue(app.mesh_listener_ready)
        self.assertIn('Listening for Meshtastic replies', statuses[-1])

    def test_malformed_untagged_status_is_ignored(self):
        app, statuses = self.app()
        app.queue.put(('mesh_reply_status', True, 'Reply listener disconnected'))
        self.flush(app)
        self.assertTrue(app.mesh_listener_ready)
        self.assertEqual(statuses, [])
