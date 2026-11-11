"""Button-led, opt-in Meshtastic field checks. Nothing sends on opening."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from tkinter import ttk, messagebox, filedialog
import tkinter as tk
from uuid import uuid4

from .contacts import read_routes
from .mesh_field_trial import (MeshFieldTrial, MANUAL_FIELD_CASES, MANUAL_OUTCOMES,
                               send_confirmed_field_test)
from .mesh_health import discover_gateways
from .homeassistant import HomeAssistantError
from .meshtastic import is_mesh_entity, require_mesh_choice
from . import __version__


class MeshFieldWizard:
    def __init__(self, app):
        self.app = app
        self.session_key = uuid4().hex
        self.model = MeshFieldTrial()
        self.busy = False
        self.routes = [route for route in read_routes(app.settings.emergency_routes)
                       if is_mesh_entity(route.target) and route.enabled and route.consent
                       and route.mesh_node_id is not None]
        self.root = tk.Toplevel(app.root)
        self.root.title('Meshtastic field check — TEST ONLY')
        self.root.geometry('760x610')
        self.root.minsize(630, 440)
        self.root.protocol('WM_DELETE_WINDOW', self.close)
        outer = ttk.Frame(self.root, padding=14)
        outer.pack(fill='both', expand=True)
        ttk.Label(outer, text='Meshtastic real-device checks',
                  font=('Segoe UI', 16, 'bold')).pack(anchor='w')
        ttk.Label(outer, text='No message is sent until you prepare it, see the exact text and confirm. '
                  'This is not a medical alarm. Use a consenting receiver and TEST ONLY messages.',
                  wraplength=710).pack(anchor='w', pady=5)
        self.notebook = ttk.Notebook(outer)
        self.notebook.pack(fill='both', expand=True, pady=9)
        self.first = ttk.Frame(self.notebook, padding=12)
        self.second = ttk.Frame(self.notebook, padding=12)
        self.third = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(self.first, text='1 · Check')
        self.notebook.add(self.second, text='2 · Send test')
        self.notebook.add(self.third, text='3 · Report')
        self.status = tk.StringVar(value='NOT CHECKED. Nothing has been transmitted.')
        self._build_checks()
        self._build_send()
        self._build_report()
        ttk.Label(outer, textvariable=self.status, wraplength=720,
                  justify='left').pack(anchor='w', pady=5)
        ttk.Button(outer, text='Close', command=self.close).pack(anchor='e')
        self.refresh()

    def _build_checks(self):
        frame = self.first
        ttk.Label(frame, text='1. Ask Home Assistant about its Meshtastic gateway.',
                  wraplength=690).pack(anchor='w', pady=5)
        ttk.Button(frame, text='Check Gateway (read-only)', command=self.check_gateway).pack(anchor='w', pady=7)
        self.gateway_label = tk.StringVar()
        ttk.Label(frame, textvariable=self.gateway_label, wraplength=650).pack(anchor='w', pady=7)
        ttk.Label(frame, text='2. Choose a saved, consented individual receiver. '
                  'If none appear, configure it under Emergency contacts and save first.',
                  wraplength=690).pack(anchor='w', pady=8)
        names = [r.label for r in self.routes]
        self.recipient_choice = tk.StringVar(value='')
        self.recipient_box = ttk.Combobox(frame, state='readonly', textvariable=self.recipient_choice,
                                          values=names, width=45)
        self.recipient_box.pack(anchor='w', pady=5)
        self.recipient_box.bind('<<ComboboxSelected>>', self.change_recipient)
        ttk.Button(frame, text='Check Selected Node (read-only)',
                   command=self.check_recipient).pack(anchor='w', pady=8)
        ttk.Button(frame, text='Confirm Node Owner by Separate Contact',
                   command=self.confirm_owner).pack(anchor='w', pady=5)
        self.recipient_label = tk.StringVar()
        ttk.Label(frame, textvariable=self.recipient_label, wraplength=650).pack(anchor='w')
        ttk.Label(frame, text='A saved node number is only a technical match. '
                  'Check its actual owner with a separate trusted contact method.',
                  wraplength=670).pack(anchor='w', pady=8)

    def _build_send(self):
        ttk.Label(self.second, text='No glucose values or actual emergency message are used.',
                  wraplength=690).pack(anchor='w', pady=6)
        ttk.Button(self.second, text='Preview TEST ONLY Message', command=self.preview).pack(anchor='w', pady=7)
        self.preview_label = tk.StringVar(value='No test prepared.')
        ttk.Label(self.second, textvariable=self.preview_label,
                  wraplength=670).pack(anchor='w', pady=8)
        self.send_button = ttk.Button(self.second, text='Send Confirmed TEST ONLY Message',
                                      command=self.send_test)
        self.send_button.pack(anchor='w', pady=8)
        ttk.Label(self.second, text='An accepted request is not a delivery receipt. '
                  'Ask the intended person to confirm the reference independently.',
                  wraplength=680).pack(anchor='w', pady=5)
        ttk.Button(self.second, text='Record User-Reported Receipt',
                   command=self.confirm_receipt).pack(anchor='w', pady=5)
        self.send_label = tk.StringVar()
        ttk.Label(self.second, textvariable=self.send_label, wraplength=650).pack(anchor='w', pady=5)

    def _build_report(self):
        ttk.Label(self.third, text='Only a local redacted report is saved when you choose Save. '
                  'Hardware results remain NOT RUN until actually observed.',
                  wraplength=700).pack(anchor='w', pady=5)
        review = ttk.LabelFrame(self.third, text='Record a witnessed field check', padding=8)
        review.pack(fill='x', pady=5)
        ttk.Label(review, text='Only record something you actually tried. PASS means you observed it, '
                  'not that a medical alarm is dependable.', wraplength=660).pack(anchor='w')
        self.case_label = tk.StringVar(value='')
        self.case_options = {f'{code} · {label}': code for code, label in MANUAL_FIELD_CASES}
        self.case_picker = ttk.Combobox(review, textvariable=self.case_label,
                                        values=list(self.case_options), state='readonly', width=60)
        self.case_picker.pack(anchor='w', pady=3)
        self.outcome = tk.StringVar(value='NOT RUN')
        ttk.Combobox(review, textvariable=self.outcome, values=MANUAL_OUTCOMES,
                     state='readonly', width=15).pack(anchor='w', pady=3)
        ttk.Button(review, text='Record Operator-Reported Result',
                   command=self.record_case).pack(anchor='w', pady=4)
        self.report_text = tk.Text(self.third, wrap='word', height=9,
                                   font=('Consolas', max(10, self.app.accessible_size-2)))
        self.report_text.pack(fill='both', expand=True)
        bar = ttk.Frame(self.third)
        bar.pack(anchor='w', pady=6)
        ttk.Button(bar, text='Refresh Report', command=self.refresh).pack(side='left', padx=4)
        ttk.Button(bar, text='Save Redacted Report', command=self.save_report).pack(side='left', padx=4)
        ttk.Button(bar, text='Open Safe Simulation',
                   command=self.app.open_mesh_simulation).pack(side='left', padx=4)

    def close(self):
        # A pending check doesn't get to send just because the window has gone.
        self.model.cancel()
        self.session_key = ''
        self.root.destroy()

    def refresh(self):
        model = self.model
        self.gateway_label.set(f'Gateway: {model.gateway_observation}. Connection reports do not prove radio coverage.')
        self.recipient_label.set(f'Recipient: {model.recipient_observation}. '
                                 + ('Owner check recorded by operator.' if model.owner_confirmed else 'Owner not confirmed.'))
        self.send_label.set(f'Request: {model.request_result}. Receipt: {model.receipt}.')
        self.preview_label.set(model.prepared.body if model.prepared else 'No test prepared.')
        self.recipient_box.configure(state='disabled' if self.busy else 'readonly')
        self.send_button.configure(state='normal' if model.prepared and model.preview_fresh()
                                   and not model.authorised and model.request_result == 'NOT SENT'
                                   and not self.busy else 'disabled')
        self.report_text.configure(state='normal')
        self.report_text.delete('1.0', tk.END)
        self.report_text.insert(tk.END, model.report(__version__))
        self.report_text.configure(state='disabled')

    def _submit(self, action, work):
        if self.busy:
            return
        self.busy = True
        key = self.session_key
        self.status.set('Checking Home Assistant…')
        self.refresh()
        def run():
            try:
                return (key, action, True, work())
            except Exception as exc:
                # Do not put raw service errors on screen or in a report.
                return (key, action, False, exc.__class__.__name__)
        self.app.start('mesh_field_trial', run)

    def change_recipient(self, _event=None):
        if self.busy:
            self.status.set('A check is still running. Choose the recipient again afterwards.')
            return
        picked = self.recipient_choice.get()
        route = next((r for r in self.routes if r.label == picked), None)
        if route is None:
            return
        self.model.select(route)
        self.status.set('Receiver selected. Check the node before preparing a test.')
        self.refresh()

    def check_gateway(self):
        if self.busy:
            return
        self.model.gateway_checked([])
        self.refresh()
        try:
            client = self.app.client()
        except HomeAssistantError:
            self.status.set('Connect Home Assistant first. No radio test was sent.')
            return
        # Reset before the network read so a failed check doesn't leave a green-looking state.
        def run():
            records = discover_gateways(client.states(), now=datetime.now(timezone.utc))
            return records
        self._submit('gateway', run)

    def check_recipient(self):
        if self.busy:
            return
        route = self.model.route
        if route is None or not self.model.gateway_ready:
            messagebox.showinfo('Receiver check', 'Check one gateway and choose a saved recipient first.')
            return
        self.model.recipient_checked_result(False)
        self.refresh()
        try:
            client = self.app.client()
        except HomeAssistantError:
            self.status.set('Connect Home Assistant before checking a recipient.')
            return
        def run():
            require_mesh_choice(route.target, [client.state(route.target)],
                                expected_node_id=route.mesh_node_id)
            return True
        self._submit('recipient', run)

    def confirm_owner(self):
        if self.busy or not self.model.recipient_checked or self.model.route is None:
            messagebox.showinfo('Recipient identity', 'Check the selected node first.')
            return
        route = self.model.route
        if messagebox.askyesno('Confirm who owns the radio',
                f'Destination: {route.target}\nNode: !{route.mesh_node_id:08x}\n\n'
                'Have you independently confirmed that this radio belongs to your intended, consenting recipient?'):
            self.model.confirm_owner()
            self.status.set('Recipient identity confirmed by the operator for this test session.')
            self.refresh()

    def preview(self):
        if self.busy:
            return
        try:
            prepared = self.model.preview()
        except ValueError as exc:
            messagebox.showinfo('TEST ONLY', str(exc))
            return
        self.preview_label.set(prepared.body)
        self.status.set('Preview ready. No transmission has occurred.')
        self.notebook.select(self.second)
        self.refresh()

    def send_test(self):
        if self.busy or self.model.prepared is None or self.model.route is None:
            return
        route, prepared = self.model.route, self.model.prepared
        if not messagebox.askyesno('Send TEST ONLY message',
                 f'CONFIRM ONE REAL RADIO TRANSMISSION\n\n'
                 f'Recipient: {route.label}\nEntity: {route.target}\n\n'
                 f'Exact message:\n{prepared.body}\n\n'
                 'Are you with a consenting receiver who expects this test?'):
            self.status.set('Test cancelled. Nothing has been sent.')
            return
        try:
            client = self.app.client()
            self.model.approve()
        except (ValueError, HomeAssistantError) as exc:
            messagebox.showerror('Test not ready', str(exc))
            return
        def run():
            # The callback runs again after HA's node lookup. This must read
            # the current consent, not a copy taken before the network call.
            def current_routes():
                return read_routes(self.app.settings.emergency_routes)
            return send_confirmed_field_test(client, self.model, current_routes)
        self._submit('send', run)

    def confirm_receipt(self):
        try:
            if self.model.request_result != 'ACCEPTED BY HA; DELIVERY UNKNOWN':
                raise ValueError('Send and complete an accepted test request first')
        except ValueError as exc:
            messagebox.showinfo('No accepted request', str(exc))
            return
        if messagebox.askyesno('User-reported receipt',
                'Did the intended recipient tell you, through a separate trusted means, '
                'that they received this exact TEST ONLY reference?\n\n'
                'This records your report, not independent verification.'):
            self.model.record_receipt()
            self.status.set('User-reported receipt recorded locally. No medical safety claim.')
            self.refresh()

    def on_result(self, item):
        key, action, ok, payload = item
        if key != self.session_key or not self.root.winfo_exists():
            return
        self.busy = False
        if not ok:
            if action == 'gateway':
                self.model.gateway_checked([])
            elif action == 'recipient':
                self.model.recipient_checked_result(False)
            elif action == 'send':
                self.model.failed_send(blocked=(payload == 'FieldTestBlocked'))
            self.status.set('Check failed (' + payload + '). No delivery claim made.')
            self.refresh()
            return
        if action == 'gateway':
            self.model.gateway_checked(payload)
            self.status.set('Gateway observation recorded. A connection is not a radio test.')
        elif action == 'recipient':
            self.model.recipient_checked_result(payload is True)
            self.status.set('Node metadata matched. Ask the owner to verify the radio separately.')
        elif action == 'send':
            self.model.sent(True)
            self.status.set('Home Assistant accepted TEST ONLY. Ask the receiver whether it arrived.')
        self.refresh()

    def record_case(self):
        if self.busy:
            self.status.set('Finish the current check before recording another result.')
            return
        code = self.case_options.get(self.case_label.get())
        if code is None:
            messagebox.showinfo('Field check', 'Choose a numbered field case first.')
            return
        outcome = self.outcome.get()
        if outcome != 'NOT RUN' and not messagebox.askyesno(
                'Record observed result',
                f'Case {code}: {outcome}\n\nDid you perform this check and observe this result? '
                'It will be recorded as OPERATOR REPORTED, not independently verified.'):
            return
        try:
            self.model.record_observation(code, outcome)
        except ValueError as exc:
            messagebox.showerror('Field check', str(exc))
            return
        self.status.set(f'Case {code}: {self.model.cases[code]}. Only saved locally if you choose Save.')
        self.refresh()

    def save_report(self):
        # Explicit local save. Nothing gets uploaded or stored automatically.
        destination = filedialog.asksaveasfilename(parent=self.root,
                  title='Save redacted Meshtastic report', defaultextension='.txt',
                  filetypes=[('Text report', '*.txt')],
                  initialfile='LibreBeacon-Mesh-Field-Check.txt')
        if not destination:
            return
        try:
            Path(destination).write_text(self.model.report(__version__), encoding='utf-8')
        except OSError:
            messagebox.showerror('Report', 'Could not save the report to that location.')
        else:
            self.status.set('Redacted test report saved on this computer.')
